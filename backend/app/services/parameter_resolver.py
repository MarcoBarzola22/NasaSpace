"""Resolución de los parámetros efectivos y de su origen (RF-1, RF-3, RF-4, RF-14; T037).

Convierte la solicitud validada en la entrada del cálculo (los tipos de ``domain``) y en la
«entrada resuelta» que se devuelve al usuario: para cada parámetro, su valor efectivo, su origen
(``user``, ``fao_reference``, ``team_default`` o ``system_default``), su cita y una nota.

Reglas:

- Un parámetro omitido toma el valor de referencia del catálogo (CA-3.3) y se registra un
  supuesto; uno ingresado queda con origen ``user`` (CA-3.4). Nada se completa con valores
  inventados: si falta un valor sin referencia, es un error de uso (la validación debía
  detenerlo).
- La profundidad radicular (inicial y máxima) se limita a la profundidad efectiva y se registra
  el supuesto (CA-3.10).
- El Kc base de barbecho por defecto es 0,20 (CA-1.9); el rastrojo omitido es 0 % (CA-3.12); la
  fecha de inicio por defecto es el 1 de julio (D-6). Cada uno registra su supuesto.

Un valor omitido se distingue de uno ingresado con ``model_fields_set`` de Pydantic: ingresar
explícitamente 0 es un valor del usuario, no un valor omitido.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core import messages
from app.core.constants import (
    DEFAULT_WINDOW_START_DAY,
    DEFAULT_WINDOW_START_MONTH,
    FALLOW_EVAPORATION_LAYER_M,
    FALLOW_KC_BASE_DEFAULT,
)
from app.domain.types import CropSpec, ParcelSpec, RotationSpec, SowingSpec, Stages
from app.domain.water_balance import initial_storage_mm, profile_capacity_mm
from app.models.request import CropIn, RotationIn, SimulationRequest
from app.services.assumptions import AssumptionRegistry
from app.services.catalog_service import (
    STAGE_KEYS,
    STATUS_FAO,
    STATUS_TEAM,
    Catalog,
    CropReference,
)

ORIGIN_USER = "user"
ORIGIN_FAO = "fao_reference"
ORIGIN_TEAM = "team_default"
ORIGIN_SYSTEM = "system_default"

_SIMPLE_PARAMETERS = (
    "kc_initial",
    "kc_mid",
    "kc_end",
    "root_depth_initial_m",
    "root_depth_max_m",
    "depletion_fraction_p",
)
_UNITS = {
    "kc_initial": "adimensional",
    "kc_mid": "adimensional",
    "kc_end": "adimensional",
    "stage_lengths_days": "días",
    "root_depth_initial_m": "m",
    "root_depth_max_m": "m",
    "depletion_fraction_p": "adimensional",
    "ky": "adimensional",
}


@dataclass(frozen=True, slots=True)
class ResolvedValue:
    """Un parámetro con su valor efectivo, origen, cita y nota (plan §5.1)."""

    value: Any
    origin: str
    source: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedCrop:
    position: int  # desde 1
    spec: CropSpec
    crop_name: str
    parameters: dict[str, ResolvedValue]


@dataclass(frozen=True, slots=True)
class ResolvedRotation:
    rotation_id: str
    name: str | None
    initial_residue_cover_pct: ResolvedValue
    crops: tuple[ResolvedCrop, ...]
    spec: RotationSpec


@dataclass(frozen=True, slots=True)
class ResolvedParcel:
    spec: ParcelSpec
    name: str | None
    profile_capacity_mm: float
    initial_storage_mm: float
    fallow_kc_base: ResolvedValue
    fallow_evaporation_layer_m: ResolvedValue


@dataclass(frozen=True, slots=True)
class ResolvedWindow:
    start_day: int
    start_month: int
    start_years: tuple[int, ...]
    start_defaulted: bool


@dataclass(frozen=True, slots=True)
class ResolvedInput:
    parcel: ResolvedParcel
    window: ResolvedWindow
    currency: str | None
    rotations: tuple[ResolvedRotation, ...]


def crop_scope_id(rotation_id: str, position: int, parameter: str) -> str:
    """Identificador del alcance de un supuesto de cultivo: ``A/1/ky``."""
    return f"{rotation_id}/{position}/{parameter}"


def fallow_scope_id(rotation_id: str, after_position: int) -> str:
    """Identificador del alcance de un supuesto de barbecho: ``B/3`` (tras el cultivo 3)."""
    return f"{rotation_id}/{after_position}"


def resolve_parameters(
    request: SimulationRequest, catalog: Catalog, registry: AssumptionRegistry
) -> ResolvedInput:
    """Parámetros efectivos y origen de toda la solicitud; registra sus supuestos."""
    parcel = _resolve_parcel(request, registry)
    window = _resolve_window(request, registry)
    depth_m = request.parcel.effective_depth_m
    rotations = tuple(
        _resolve_rotation(rotation, catalog, depth_m, registry) for rotation in request.rotations
    )
    return ResolvedInput(parcel, window, request.currency, rotations)


# --- Parcela y ventana ---


def _resolve_parcel(request: SimulationRequest, registry: AssumptionRegistry) -> ResolvedParcel:
    parcel = request.parcel
    if parcel.fallow_kc_base is None:
        kc_base = ResolvedValue(
            FALLOW_KC_BASE_DEFAULT, ORIGIN_TEAM, messages.FALLOW_KC_SOURCE, None
        )
        registry.add("FALLOW_KC_BASE_DEFAULT", value=FALLOW_KC_BASE_DEFAULT, unit="adimensional")
    else:
        kc_base = ResolvedValue(parcel.fallow_kc_base, ORIGIN_USER)
    spec = ParcelSpec(
        latitude_deg=parcel.latitude_deg,
        longitude_deg=parcel.longitude_deg,
        theta_fc_m3_m3=parcel.theta_fc_m3_m3,
        theta_wp_m3_m3=parcel.theta_wp_m3_m3,
        effective_depth_m=parcel.effective_depth_m,
        initial_available_water_pct=parcel.initial_available_water_pct,
        fallow_kc_base=kc_base.value,
    )
    return ResolvedParcel(
        spec=spec,
        name=parcel.name,
        profile_capacity_mm=profile_capacity_mm(spec),
        initial_storage_mm=initial_storage_mm(spec),
        fallow_kc_base=kc_base,
        fallow_evaporation_layer_m=ResolvedValue(
            FALLOW_EVAPORATION_LAYER_M,
            ORIGIN_SYSTEM,
            messages.FALLOW_EVAPORATION_LAYER_SOURCE,
        ),
    )


def _resolve_window(request: SimulationRequest, registry: AssumptionRegistry) -> ResolvedWindow:
    window = request.window
    omitted = {"start_day", "start_month"} - window.model_fields_set
    if omitted:
        registry.add(
            "WINDOW_START_DEFAULT",
            value=messages.WINDOW_START_DEFAULT_VALUE,
        )
    return ResolvedWindow(
        start_day=window.start_day
        if "start_day" in window.model_fields_set
        else DEFAULT_WINDOW_START_DAY,
        start_month=(
            window.start_month
            if "start_month" in window.model_fields_set
            else DEFAULT_WINDOW_START_MONTH
        ),
        start_years=tuple(sorted(set(window.start_years))),
        start_defaulted=bool(omitted),
    )


# --- Rotaciones y cultivos ---


def _resolve_rotation(
    rotation: RotationIn, catalog: Catalog, depth_m: float, registry: AssumptionRegistry
) -> ResolvedRotation:
    if "initial_residue_cover_pct" in rotation.model_fields_set:
        residue = ResolvedValue(rotation.initial_residue_cover_pct, ORIGIN_USER)
    else:
        residue = ResolvedValue(0.0, ORIGIN_SYSTEM)
        registry.add(
            "NO_RESIDUE_DECLARED",
            scope="fallow",
            scope_id=fallow_scope_id(rotation.id, 0),
            value=0.0,
            unit="%",
        )
    crops = tuple(
        _resolve_crop(rotation, position, crop, catalog, depth_m, registry)
        for position, crop in enumerate(rotation.crops, start=1)
    )
    spec = RotationSpec(
        rotation_id=rotation.id,
        crops=tuple(crop.spec for crop in crops),
        initial_residue_cover_pct=residue.value,
        name=rotation.name,
    )
    return ResolvedRotation(rotation.id, rotation.name, residue, crops, spec)


def _reference(
    rotation_id: str,
    position: int,
    parameter: str,
    reference: CropReference,
    registry: AssumptionRegistry,
) -> ResolvedValue:
    """Valor de referencia del catálogo, con su supuesto (CA-3.3)."""
    entry = reference.reference_values[parameter]
    if entry.value is None:
        raise ValueError(
            f"{reference.crop_code}.{parameter} no tiene referencia y no se ingresó: "
            "la validación debía detener la solicitud."
        )
    scope = crop_scope_id(rotation_id, position, parameter)
    if entry.status == STATUS_FAO:
        code, note = "FAO_REFERENCE_VALUE", messages.NOTE_FAO_REFERENCE
    elif parameter == "root_depth_initial_m":
        code, note = "INITIAL_ROOT_DEPTH_TEAM", messages.NOTE_TEAM_REFERENCE
    elif entry.status == STATUS_TEAM:
        code, note = "TEAM_REFERENCE_VALUE", messages.NOTE_TEAM_REFERENCE
    else:
        raise ValueError(f"Estado inesperado del catálogo: {entry.status}")
    registry.add(
        code,
        scope="crop",
        scope_id=scope,
        value=_assumption_value(entry.value),
        unit=_UNITS[parameter],
        origin=entry.origin,
        source=entry.source,
    )
    return ResolvedValue(entry.value, entry.origin or ORIGIN_FAO, entry.source, note)


def _assumption_value(value: Any) -> float | str:
    if isinstance(value, dict):
        return "/".join(str(value[key]) for key in STAGE_KEYS)
    return value


def _resolve_crop(
    rotation: RotationIn,
    position: int,
    crop: CropIn,
    catalog: Catalog,
    depth_m: float,
    registry: AssumptionRegistry,
) -> ResolvedCrop:
    reference = catalog.get(crop.crop_code)
    is_grain = reference.crop_type == "grain"
    parameters: dict[str, ResolvedValue] = {}

    for parameter in _SIMPLE_PARAMETERS:
        user_value = getattr(crop, parameter)
        parameters[parameter] = (
            ResolvedValue(user_value, ORIGIN_USER)
            if user_value is not None
            else _reference(rotation.id, position, parameter, reference, registry)
        )

    if crop.stage_lengths_days is not None:
        lengths = crop.stage_lengths_days
        stages_value = {key: getattr(lengths, key) for key in STAGE_KEYS}
        parameters["stage_lengths_days"] = ResolvedValue(stages_value, ORIGIN_USER)
    else:
        parameters["stage_lengths_days"] = _reference(
            rotation.id, position, "stage_lengths_days", reference, registry
        )

    if is_grain:
        parameters["ky"] = (
            ResolvedValue(crop.ky, ORIGIN_USER)
            if crop.ky is not None
            else _reference(rotation.id, position, "ky", reference, registry)
        )
        parameters["ym_t_ha"] = ResolvedValue(crop.ym_t_ha, ORIGIN_USER)

    _limit_root_depths(rotation.id, position, parameters, depth_m, registry)

    if "residue_cover_after_pct" in crop.model_fields_set:
        residue = ResolvedValue(crop.residue_cover_after_pct, ORIGIN_USER)
    else:
        residue = ResolvedValue(0.0, ORIGIN_SYSTEM)
        registry.add(
            "NO_RESIDUE_DECLARED",
            scope="fallow",
            scope_id=fallow_scope_id(rotation.id, position),
            value=0.0,
            unit="%",
        )
    parameters["residue_cover_after_pct"] = residue

    economics = crop.economics
    stages = parameters["stage_lengths_days"].value
    spec = CropSpec(
        crop_code=crop.crop_code,
        crop_type=reference.crop_type,
        sowing=SowingSpec(crop.sowing.window_year, crop.sowing.day, crop.sowing.month),
        stages=Stages(stages["initial"], stages["development"], stages["mid"], stages["late"]),
        kc_initial=parameters["kc_initial"].value,
        kc_mid=parameters["kc_mid"].value,
        kc_end=parameters["kc_end"].value,
        root_depth_initial_m=parameters["root_depth_initial_m"].value,
        root_depth_max_m=parameters["root_depth_max_m"].value,
        depletion_fraction_p=parameters["depletion_fraction_p"].value,
        ky=parameters["ky"].value if is_grain else None,
        ym_t_ha=parameters["ym_t_ha"].value if is_grain else None,
        residue_cover_after_pct=residue.value,
        price_per_t=economics.price_per_t if economics is not None else None,
        direct_costs_per_ha=economics.direct_costs_per_ha if economics is not None else None,
    )
    return ResolvedCrop(position, spec, reference.name, parameters)


def _limit_root_depths(
    rotation_id: str,
    position: int,
    parameters: dict[str, ResolvedValue],
    depth_m: float,
    registry: AssumptionRegistry,
) -> None:
    """Limita Zr inicial y máxima a la profundidad efectiva (CA-3.10)."""
    for parameter in ("root_depth_initial_m", "root_depth_max_m"):
        resolved = parameters[parameter]
        if resolved.value <= depth_m:
            continue
        label = (
            messages.ORIGIN_LABEL_USER
            if resolved.origin == ORIGIN_USER
            else messages.ORIGIN_LABEL_REFERENCE
        )
        parameters[parameter] = ResolvedValue(
            depth_m,
            resolved.origin,
            resolved.source,
            messages.NOTE_ROOT_DEPTH_LIMITED.format(origin_label=label, original=resolved.value),
        )
        registry.add(
            "ROOT_DEPTH_LIMITED",
            scope="crop",
            scope_id=crop_scope_id(rotation_id, position, parameter),
            value=depth_m,
            unit="m",
        )
