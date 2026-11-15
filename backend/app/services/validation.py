"""Validación semántica de la solicitud (RF-1, RF-3, RF-4, RF-10; T035 y T036).

Se ejecuta **después** de la validación estructural (Pydantic) y **antes** de cualquier consulta
a NASA POWER (CA-5.3). Junta todos los errores en una sola lista (CA-16.1) en lugar de detenerse
en el primero. No lee archivos ni la red: recibe el catálogo ya cargado y la fecha de «hoy».

Comprueba:

- parcela: θPMP < θCC (CA-1.3) y latitud en [−60°, 60°] (CA-1.12);
- ventana: fecha de inicio válida y distinta del 29 de febrero (CA-4.3), años distintos (CA-4.3),
  cada ventana termina antes de hoy (CA-4.4);
- cultivos: existen en el catálogo (CA-3.2), reglas de grano y cobertura (CA-3.2, CA-3.13),
  parámetros «sin referencia» que faltan (CA-2.3), Zr inicial ≤ Zr máxima (CA-3.9) y fecha de
  siembra válida y distinta del 29 de febrero (CA-3.8);
- calendario, por cada año de inicio: sin solapamientos (CA-3.6) y con el ciclo dentro de la
  ventana (CA-3.7), con las mismas funciones que usa el cálculo (``domain.calendar``);
- datos económicos: ``currency`` presente si hay precio o costos (CA-10.6) y sin precio en un
  cultivo de cobertura (CA-3.13).

Los textos en español están en ``app.core.messages``; aquí solo hay códigos y rutas de campo.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core import messages
from app.core.config import RADIATION_COVERAGE_START
from app.core.constants import MAX_ABS_LATITUDE_DEG
from app.core.exceptions import InputValidationError
from app.domain.calendar import (
    ISSUE_OUTSIDE_WINDOW,
    ISSUE_OVERLAP,
    build_window,
    cycle_end,
    issues_for_cycles,
    sowing_date,
    validate_recurring_day_month,
)
from app.domain.types import SowingSpec, Stages
from app.models.request import CropIn, RotationIn, SimulationRequest
from app.services.catalog_service import (
    STAGE_KEYS,
    STATUS_NO_REFERENCE,
    Catalog,
    CropReference,
)
from app.services.window_service import REASON_ENDS_AFTER_TODAY, SpecificYears, resolve_window

# Códigos estables de cada tipo de error (para pruebas y para el frontend).
CODE_LATITUDE_OUT_OF_RANGE = "latitude_out_of_range"
CODE_THETA_INCOHERENT = "theta_incoherent"
CODE_START_DATE_INVALID = "start_date_invalid"
CODE_DUPLICATE_YEARS = "duplicate_start_years"
CODE_WINDOW_ENDS_AFTER_TODAY = "window_ends_after_today"
CODE_DUPLICATE_ROTATION = "duplicate_rotation_id"
CODE_UNKNOWN_CROP = "unknown_crop"
CODE_YM_REQUIRED = "ym_required"
CODE_FORBIDDEN_FOR_COVER = "forbidden_for_cover_crop"
CODE_MISSING_REFERENCE = "missing_reference_parameter"
CODE_ROOT_DEPTH_ORDER = "root_depth_initial_exceeds_max"
CODE_SOWING_DATE_INVALID = "sowing_date_invalid"
CODE_CURRENCY_REQUIRED = "currency_required"
CODE_CALENDAR_OVERLAP = "calendar_overlap"
CODE_CALENDAR_OUTSIDE_WINDOW = "calendar_outside_window"

# Parámetros simples que el catálogo puede marcar «sin referencia» (el Ky solo aplica al grano).
_SIMPLE_PARAMETERS = (
    "kc_initial",
    "kc_mid",
    "kc_end",
    "root_depth_initial_m",
    "root_depth_max_m",
    "depletion_fraction_p",
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Un defecto de la solicitud: dónde está (ruta de campo), qué pasa y un código estable."""

    field: str
    message: str
    code: str


def validate_request(
    request: SimulationRequest, catalog: Catalog, *, today: date
) -> list[ValidationIssue]:
    """Devuelve todos los defectos semánticos de la solicitud (lista vacía si es válida)."""
    issues: list[ValidationIssue] = []
    issues.extend(_check_parcel(request))
    window_issues, scenario_years, start_day, start_month = _check_window(request, today)
    issues.extend(window_issues)
    issues.extend(_check_currency(request))
    seen_ids: set[str] = set()
    for rotation_index, rotation in enumerate(request.rotations):
        if rotation.id in seen_ids:
            issues.append(
                ValidationIssue(
                    f"rotations[{rotation_index}].id",
                    messages.DUPLICATE_ROTATION.format(rotation_id=rotation.id),
                    CODE_DUPLICATE_ROTATION,
                )
            )
        seen_ids.add(rotation.id)
        issues.extend(_check_rotation_crops(rotation_index, rotation, catalog))
        if start_day is not None and start_month is not None:
            issues.extend(
                _check_calendar(
                    rotation_index, rotation, catalog, scenario_years, start_day, start_month
                )
            )
    return issues


def raise_if_invalid(request: SimulationRequest, catalog: Catalog, *, today: date) -> None:
    """Lanza ``InputValidationError`` con todos los defectos; no hace nada si no hay ninguno."""
    issues = validate_request(request, catalog, today=today)
    if issues:
        raise InputValidationError(
            [
                {"field": issue.field, "message": issue.message, "code": issue.code}
                for issue in issues
            ]
        )


# --- Parcela (CA-1.3, CA-1.12) ---


def _check_parcel(request: SimulationRequest) -> list[ValidationIssue]:
    parcel = request.parcel
    issues: list[ValidationIssue] = []
    if abs(parcel.latitude_deg) > MAX_ABS_LATITUDE_DEG:
        issues.append(
            ValidationIssue(
                "parcel.latitude_deg",
                messages.LATITUDE_OUT_OF_RANGE.format(
                    latitude=parcel.latitude_deg, limit=MAX_ABS_LATITUDE_DEG
                ),
                CODE_LATITUDE_OUT_OF_RANGE,
            )
        )
    if parcel.theta_wp_m3_m3 >= parcel.theta_fc_m3_m3:
        issues.append(
            ValidationIssue(
                "parcel.theta_wp_m3_m3",
                messages.THETA_INCOHERENT.format(
                    theta_wp=parcel.theta_wp_m3_m3, theta_fc=parcel.theta_fc_m3_m3
                ),
                CODE_THETA_INCOHERENT,
            )
        )
    return issues


# --- Ventana (CA-4.3, CA-4.4) ---


def _years_text(years: Sequence[int]) -> str:
    if len(years) == 1:
        return messages.SCENARIO_ONE.format(year=years[0])
    return messages.SCENARIO_MANY.format(years=", ".join(str(year) for year in years))


def _check_window(
    request: SimulationRequest, today: date
) -> tuple[list[ValidationIssue], list[int], int | None, int | None]:
    """Errores de la ventana y los datos para validar el calendario.

    Devuelve (errores, años únicos a revisar, día de inicio, mes de inicio). El día y el mes son
    ``None`` si la fecha de inicio es inválida: sin ella no se puede razonar sobre escenarios.
    """
    window = request.window
    issues: list[ValidationIssue] = []
    try:
        validate_recurring_day_month(window.start_day, window.start_month)
    except ValueError as error:
        issues.append(ValidationIssue("window.start_day", str(error), CODE_START_DATE_INVALID))
        return issues, [], None, None

    resolution = resolve_window(
        SpecificYears(tuple(window.start_years)),
        today=today,
        first_covered_day=RADIATION_COVERAGE_START,
        start_day=window.start_day,
        start_month=window.start_month,
    )
    if resolution.duplicates:
        issues.append(
            ValidationIssue(
                "window.start_years",
                messages.DUPLICATE_YEARS.format(
                    years=", ".join(str(year) for year in resolution.duplicates)
                ),
                CODE_DUPLICATE_YEARS,
            )
        )
    for rejected in resolution.rejected:
        if rejected.reason == REASON_ENDS_AFTER_TODAY:
            issues.append(
                ValidationIssue(
                    "window.start_years",
                    messages.WINDOW_ENDS_AFTER_TODAY.format(
                        year=rejected.year, last_day=rejected.window_last_day
                    ),
                    CODE_WINDOW_ENDS_AFTER_TODAY,
                )
            )
    unique_years = sorted(set(window.start_years))
    return issues, unique_years, window.start_day, window.start_month


# --- Datos económicos (CA-10.6) ---


def _check_currency(request: SimulationRequest) -> list[ValidationIssue]:
    if request.currency is not None:
        return []
    has_economics = any(
        crop.economics is not None
        and (
            crop.economics.price_per_t is not None or crop.economics.direct_costs_per_ha is not None
        )
        for rotation in request.rotations
        for crop in rotation.crops
    )
    if not has_economics:
        return []
    return [ValidationIssue("currency", messages.CURRENCY_REQUIRED, CODE_CURRENCY_REQUIRED)]


# --- Cultivos (CA-2.3, CA-3.2, CA-3.8, CA-3.9, CA-3.13) ---


def _crop_path(rotation_index: int, crop_index: int) -> str:
    return f"rotations[{rotation_index}].crops[{crop_index}]"


def _reference_number(reference: CropReference, parameter: str) -> float | None:
    value = reference.reference_values[parameter].value
    return float(value) if isinstance(value, int | float) else None


def _is_missing_reference(reference: CropReference, parameter: str) -> bool:
    return reference.reference_values[parameter].status == STATUS_NO_REFERENCE


def _check_rotation_crops(
    rotation_index: int, rotation: RotationIn, catalog: Catalog
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for crop_index, crop in enumerate(rotation.crops):
        path = _crop_path(rotation_index, crop_index)
        try:
            reference = catalog.get(crop.crop_code)
        except KeyError:
            issues.append(
                ValidationIssue(
                    f"{path}.crop_code",
                    messages.UNKNOWN_CROP.format(
                        crop_code=crop.crop_code, options=", ".join(catalog.crop_codes)
                    ),
                    CODE_UNKNOWN_CROP,
                )
            )
            continue
        issues.extend(_check_sowing_date(path, crop))
        if reference.crop_type == "cover":
            issues.extend(_check_cover_crop(path, crop))
        else:
            issues.extend(_check_grain_crop(path, crop))
        issues.extend(_check_missing_references(path, crop, reference))
        issues.extend(_check_root_depths(path, crop, reference))
    return issues


def _check_sowing_date(path: str, crop: CropIn) -> list[ValidationIssue]:
    try:
        validate_recurring_day_month(crop.sowing.day, crop.sowing.month)
    except ValueError as error:
        return [ValidationIssue(f"{path}.sowing.day", str(error), CODE_SOWING_DATE_INVALID)]
    return []


def _check_grain_crop(path: str, crop: CropIn) -> list[ValidationIssue]:
    if crop.ym_t_ha is None:
        return [ValidationIssue(f"{path}.ym_t_ha", messages.YM_REQUIRED, CODE_YM_REQUIRED)]
    return []


def _check_cover_crop(path: str, crop: CropIn) -> list[ValidationIssue]:
    present = {
        "ym_t_ha": crop.ym_t_ha is not None,
        "ky": crop.ky is not None,
        "economics.price_per_t": crop.economics is not None
        and crop.economics.price_per_t is not None,
    }
    return [
        ValidationIssue(
            f"{path}.{name}",
            messages.FORBIDDEN_FOR_COVER.format(label=messages.COVER_FORBIDDEN_LABELS[name]),
            CODE_FORBIDDEN_FOR_COVER,
        )
        for name, is_present in present.items()
        if is_present
    ]


def _check_missing_references(
    path: str, crop: CropIn, reference: CropReference
) -> list[ValidationIssue]:
    """Parámetros que el catálogo marca «sin referencia» y el usuario no ingresó (CA-2.3)."""
    missing: list[str] = [
        parameter
        for parameter in _SIMPLE_PARAMETERS
        if getattr(crop, parameter) is None and _is_missing_reference(reference, parameter)
    ]
    if crop.stage_lengths_days is None and _is_missing_reference(reference, "stage_lengths_days"):
        missing.append("stage_lengths_days")
    if (
        reference.crop_type == "grain"
        and crop.ky is None
        and _is_missing_reference(reference, "ky")
    ):
        missing.append("ky")
    return [
        ValidationIssue(
            f"{path}.{parameter}",
            messages.MISSING_REFERENCE.format(
                label=messages.PARAMETER_LABELS[parameter], crop_code=crop.crop_code
            ),
            CODE_MISSING_REFERENCE,
        )
        for parameter in missing
    ]


def _check_root_depths(path: str, crop: CropIn, reference: CropReference) -> list[ValidationIssue]:
    """Zr inicial ≤ Zr máxima con los valores efectivos (los del usuario o los del catálogo)."""
    initial = (
        crop.root_depth_initial_m
        if crop.root_depth_initial_m is not None
        else _reference_number(reference, "root_depth_initial_m")
    )
    maximum = (
        crop.root_depth_max_m
        if crop.root_depth_max_m is not None
        else _reference_number(reference, "root_depth_max_m")
    )
    if initial is not None and maximum is not None and initial > maximum:
        return [
            ValidationIssue(
                f"{path}.root_depth_initial_m",
                messages.ROOT_DEPTH_ORDER.format(initial=initial, maximum=maximum),
                CODE_ROOT_DEPTH_ORDER,
            )
        ]
    return []


# --- Calendario por escenario (CA-3.6, CA-3.7) ---


def _effective_stages(crop: CropIn, reference: CropReference) -> Stages | None:
    """Duración de etapas efectiva: la del usuario o la del catálogo; ``None`` si no hay."""
    if crop.stage_lengths_days is not None:
        lengths = crop.stage_lengths_days
        return Stages(lengths.initial, lengths.development, lengths.mid, lengths.late)
    value = reference.reference_values["stage_lengths_days"].value
    if isinstance(value, dict) and set(value) == set(STAGE_KEYS):
        return Stages(value["initial"], value["development"], value["mid"], value["late"])
    return None


def _check_calendar(
    rotation_index: int,
    rotation: RotationIn,
    catalog: Catalog,
    start_years: Sequence[int],
    start_day: int,
    start_month: int,
) -> list[ValidationIssue]:
    """Solapamientos y ciclos fuera de la ventana, agrupados por cultivo con sus años.

    Si algún cultivo no tiene fecha o duración utilizable, esos defectos ya se informaron y no se
    puede razonar sobre el calendario de la rotación: se omite.
    """
    sowings: list[SowingSpec] = []
    stages: list[Stages] = []
    for crop in rotation.crops:
        try:
            reference = catalog.get(crop.crop_code)
            validate_recurring_day_month(crop.sowing.day, crop.sowing.month)
        except (KeyError, ValueError):
            return []
        effective = _effective_stages(crop, reference)
        if effective is None:
            return []
        sowings.append(SowingSpec(crop.sowing.window_year, crop.sowing.day, crop.sowing.month))
        stages.append(effective)

    years_by_problem: dict[tuple[str, int, int | None], list[int]] = defaultdict(list)
    for start_year in start_years:
        window = build_window(start_year, start_day, start_month)
        cycles = []
        for sowing, crop_stages in zip(sowings, stages, strict=True):
            start = sowing_date(window, sowing)
            cycles.append((start, cycle_end(start, crop_stages)))
        for issue in issues_for_cycles(rotation.id, cycles, window):
            key = (issue.kind, issue.crop_position, issue.other_position)
            years_by_problem[key].append(start_year)

    result: list[ValidationIssue] = []
    for (kind, position, other_position), years in sorted(
        years_by_problem.items(), key=lambda item: (item[0][1], item[0][0])
    ):
        crop = rotation.crops[position - 1]
        path = _crop_path(rotation_index, position - 1)
        if kind == ISSUE_OVERLAP and other_position is not None:
            other = rotation.crops[other_position - 1]
            result.append(
                ValidationIssue(
                    f"{path}.sowing",
                    messages.CALENDAR_OVERLAP.format(
                        rotation_id=rotation.id,
                        position=position,
                        crop_code=crop.crop_code,
                        other_position=other_position,
                        other_code=other.crop_code,
                        years=_years_text(years),
                    ),
                    CODE_CALENDAR_OVERLAP,
                )
            )
        elif kind == ISSUE_OUTSIDE_WINDOW:
            result.append(
                ValidationIssue(
                    f"{path}.sowing",
                    messages.CALENDAR_OUTSIDE_WINDOW.format(
                        rotation_id=rotation.id,
                        position=position,
                        crop_code=crop.crop_code,
                        years=_years_text(years),
                    ),
                    CODE_CALENDAR_OUTSIDE_WINDOW,
                )
            )
    return result
