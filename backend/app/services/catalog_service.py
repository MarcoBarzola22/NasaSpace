"""Carga y validación del catálogo de cultivos con valores de referencia FAO (RF-2).

El catálogo es un archivo estático versionado con el código; no contiene series climáticas
ni datos del usuario. Se valida al cargarlo: un valor numérico sin cita, un parámetro fuera
del conjunto permitido o un valor incoherente hacen fallar la carga con un error explícito
(``CatalogError``, definido en ``app.core.exceptions``; los textos, en ``app.core.messages``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core import messages
from app.core.exceptions import CatalogError

__all__ = [
    "CatalogError",
    "Catalog",
    "CropReference",
    "ReferenceValue",
    "load_catalog",
]

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "crop_catalog.json"

PARAMETER_CODES: tuple[str, ...] = (
    "kc_initial",
    "kc_mid",
    "kc_end",
    "stage_lengths_days",
    "root_depth_initial_m",
    "root_depth_max_m",
    "depletion_fraction_p",
    "ky",
)
STAGE_KEYS: tuple[str, ...] = ("initial", "development", "mid", "late")
CROP_TYPES: frozenset[str] = frozenset({"grain", "cover"})

# Estados de un valor en el archivo del catálogo (son datos del archivo JSON, no mensajes).
STATUS_FAO = "referencia"
STATUS_TEAM = "decisión del equipo"
STATUS_NO_REFERENCE = "sin referencia"
STATUS_NOT_APPLICABLE = "no aplica"
VALUED_STATUSES: frozenset[str] = frozenset({STATUS_FAO, STATUS_TEAM})
EMPTY_STATUSES: frozenset[str] = frozenset({STATUS_NO_REFERENCE, STATUS_NOT_APPLICABLE})
ORIGIN_BY_STATUS: dict[str, str] = {STATUS_FAO: "fao_reference", STATUS_TEAM: "team_default"}


def _catalog_error(problems: list[str]) -> CatalogError:
    return CatalogError(problems, messages.CATALOG_INVALID.format(problems=" | ".join(problems)))


@dataclass(frozen=True)
class ReferenceValue:
    """Un parámetro de referencia de un cultivo, con su estado, origen y cita."""

    value: float | dict[str, int] | None
    unit: str
    status: str
    origin: str | None
    source: str | None
    note: str | None


@dataclass(frozen=True)
class CropReference:
    crop_code: str
    name: str
    crop_type: str
    reference_values: dict[str, ReferenceValue]


@dataclass(frozen=True)
class Catalog:
    version: str
    reviewed_on: str
    reviewed_by: str
    label: str
    crops: tuple[CropReference, ...]

    def get(self, crop_code: str) -> CropReference:
        for crop in self.crops:
            if crop.crop_code == crop_code:
                return crop
        raise KeyError(crop_code)

    @property
    def crop_codes(self) -> tuple[str, ...]:
        return tuple(crop.crop_code for crop in self.crops)


def load_catalog(path: Path | None = None) -> Catalog:
    """Lee y valida el catálogo; lanza `CatalogError` con todos los defectos si es inválido."""
    catalog_path = path or DEFAULT_CATALOG_PATH
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _catalog_error(
            [messages.CATALOG_UNREADABLE.format(file=catalog_path.name, error=error)]
        ) from error
    return _build_catalog(raw)


def _build_catalog(raw: Any) -> Catalog:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise _catalog_error([messages.CATALOG_ROOT_NOT_OBJECT])

    for key in ("catalog_version", "reviewed_on", "reviewed_by", "label"):
        if not _is_text(raw.get(key)):
            problems.append(messages.CATALOG_MISSING_FIELD.format(key=key))

    raw_crops = raw.get("crops")
    crops: list[CropReference] = []
    if not isinstance(raw_crops, list) or not raw_crops:
        problems.append(messages.CATALOG_CROPS_EMPTY)
    else:
        seen: set[str] = set()
        for raw_crop in raw_crops:
            crop = _build_crop(raw_crop, problems)
            if crop is None:
                continue
            if crop.crop_code in seen:
                problems.append(messages.CATALOG_DUPLICATE_CROP.format(crop_code=crop.crop_code))
            seen.add(crop.crop_code)
            crops.append(crop)

    if problems:
        raise _catalog_error(problems)
    return Catalog(
        version=raw["catalog_version"],
        reviewed_on=raw["reviewed_on"],
        reviewed_by=raw["reviewed_by"],
        label=raw["label"],
        crops=tuple(crops),
    )


def _build_crop(raw_crop: Any, problems: list[str]) -> CropReference | None:
    if not isinstance(raw_crop, dict) or not _is_text(raw_crop.get("crop_code")):
        problems.append(messages.CATALOG_CROP_NOT_OBJECT)
        return None
    code = raw_crop["crop_code"]
    if not _is_text(raw_crop.get("name")):
        problems.append(messages.CATALOG_CROP_NAME_MISSING.format(crop_code=code))
    crop_type = raw_crop.get("crop_type")
    if crop_type not in CROP_TYPES:
        problems.append(messages.CATALOG_CROP_TYPE_INVALID.format(crop_code=code))

    raw_values = raw_crop.get("reference_values")
    if not isinstance(raw_values, dict):
        problems.append(messages.CATALOG_VALUES_MISSING.format(crop_code=code))
        return None

    for extra in sorted(set(raw_values) - set(PARAMETER_CODES)):
        problems.append(
            messages.CATALOG_PARAMETER_NOT_ALLOWED.format(crop_code=code, parameter=extra)
        )
    values: dict[str, ReferenceValue] = {}
    for parameter in PARAMETER_CODES:
        raw_value = raw_values.get(parameter)
        if raw_value is None:
            problems.append(
                messages.CATALOG_PARAMETER_MISSING.format(crop_code=code, parameter=parameter)
            )
            continue
        value = _build_value(f"{code}.{parameter}", parameter, raw_value, problems)
        if value is not None:
            values[parameter] = value

    _check_crop_rules(code, crop_type, values, problems)
    return CropReference(
        crop_code=code,
        name=str(raw_crop.get("name", "")),
        crop_type=str(crop_type),
        reference_values=values,
    )


def _build_value(
    where: str, parameter: str, raw_value: Any, problems: list[str]
) -> ReferenceValue | None:
    if not isinstance(raw_value, dict):
        problems.append(messages.CATALOG_VALUE_NOT_OBJECT.format(where=where))
        return None
    status = raw_value.get("status")
    value = raw_value.get("value")
    source = raw_value.get("source")
    origin = raw_value.get("origin")

    if status in EMPTY_STATUSES:
        if value is not None or source is not None or origin is not None:
            problems.append(
                messages.CATALOG_EMPTY_STATUS_HAS_VALUE.format(where=where, status=status)
            )
    elif status in VALUED_STATUSES:
        if not _is_text(source):
            problems.append(messages.CATALOG_NO_SOURCE.format(where=where))
        expected_origin = ORIGIN_BY_STATUS[status]
        if origin != expected_origin:
            problems.append(
                messages.CATALOG_WRONG_ORIGIN.format(
                    where=where, status=status, expected=expected_origin
                )
            )
        problems.extend(
            messages.CATALOG_VALUE_ISSUE.format(where=where, issue=issue)
            for issue in _check_value(parameter, value)
        )
    else:
        problems.append(messages.CATALOG_UNKNOWN_STATUS.format(where=where, status=status))
        return None

    return ReferenceValue(
        value=value,
        unit=str(raw_value.get("unit", "")),
        status=status,
        origin=origin,
        source=source,
        note=raw_value.get("note"),
    )


def _check_value(parameter: str, value: Any) -> list[str]:
    """Rangos físicos de cada parámetro con valor (CA-3.9)."""
    if parameter == "stage_lengths_days":
        if not isinstance(value, dict) or set(value) != set(STAGE_KEYS):
            return [messages.CATALOG_STAGES_NOT_FOUR]
        if any(not _is_int(days) or days < 1 for days in value.values()):
            return [messages.CATALOG_STAGE_DAYS_INVALID]
        return []
    if not _is_number(value):
        return [messages.CATALOG_VALUE_NOT_NUMBER]
    if parameter in ("kc_initial", "kc_mid", "kc_end", "ky") and value < 0:
        return [messages.CATALOG_NEGATIVE]
    if parameter in ("root_depth_initial_m", "root_depth_max_m") and value <= 0:
        return [messages.CATALOG_NOT_POSITIVE]
    if parameter == "depletion_fraction_p" and not 0 < value < 1:
        return [messages.CATALOG_FRACTION_RANGE]
    return []


def _check_crop_rules(
    code: str, crop_type: Any, values: dict[str, ReferenceValue], problems: list[str]
) -> None:
    ky = values.get("ky")
    if ky is not None:
        if crop_type == "cover" and ky.status != STATUS_NOT_APPLICABLE:
            problems.append(messages.CATALOG_COVER_HAS_KY.format(crop_code=code))
        if crop_type == "grain" and ky.status == STATUS_NOT_APPLICABLE:
            problems.append(messages.CATALOG_GRAIN_NEEDS_KY.format(crop_code=code))
    initial = values.get("root_depth_initial_m")
    maximum = values.get("root_depth_max_m")
    if (
        initial is not None
        and maximum is not None
        and _is_number(initial.value)
        and _is_number(maximum.value)
        and initial.value > maximum.value
    ):
        problems.append(messages.CATALOG_ROOT_DEPTH_ORDER.format(crop_code=code))


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
