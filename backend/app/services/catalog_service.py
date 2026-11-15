"""Carga y validación del catálogo de cultivos con valores de referencia FAO (RF-2).

El catálogo es un archivo estático versionado con el código; no contiene series climáticas
ni datos del usuario. Se valida al cargarlo: un valor numérico sin cita, un parámetro fuera
del conjunto permitido o un valor incoherente hacen fallar la carga con un error explícito.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

STATUS_FAO = "referencia"
STATUS_TEAM = "decisión del equipo"
STATUS_NO_REFERENCE = "sin referencia"
STATUS_NOT_APPLICABLE = "no aplica"
VALUED_STATUSES: frozenset[str] = frozenset({STATUS_FAO, STATUS_TEAM})
EMPTY_STATUSES: frozenset[str] = frozenset({STATUS_NO_REFERENCE, STATUS_NOT_APPLICABLE})
ORIGIN_BY_STATUS: dict[str, str] = {STATUS_FAO: "fao_reference", STATUS_TEAM: "team_default"}


class CatalogError(Exception):
    """El catálogo de cultivos es inválido. `problems` lista todos los defectos encontrados."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = list(problems)
        super().__init__("Catálogo de cultivos inválido: " + " | ".join(self.problems))


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
        raise CatalogError([f"no se pudo leer {catalog_path.name}: {error}"]) from error
    return _build_catalog(raw)


def _build_catalog(raw: Any) -> Catalog:
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise CatalogError(["la raíz del catálogo debe ser un objeto"])

    for key in ("catalog_version", "reviewed_on", "reviewed_by", "label"):
        if not _is_text(raw.get(key)):
            problems.append(f"falta el campo «{key}»")

    raw_crops = raw.get("crops")
    crops: list[CropReference] = []
    if not isinstance(raw_crops, list) or not raw_crops:
        problems.append("«crops» debe ser una lista con al menos un cultivo")
    else:
        seen: set[str] = set()
        for raw_crop in raw_crops:
            crop = _build_crop(raw_crop, problems)
            if crop is None:
                continue
            if crop.crop_code in seen:
                problems.append(f"cultivo repetido: {crop.crop_code}")
            seen.add(crop.crop_code)
            crops.append(crop)

    if problems:
        raise CatalogError(problems)
    return Catalog(
        version=raw["catalog_version"],
        reviewed_on=raw["reviewed_on"],
        reviewed_by=raw["reviewed_by"],
        label=raw["label"],
        crops=tuple(crops),
    )


def _build_crop(raw_crop: Any, problems: list[str]) -> CropReference | None:
    if not isinstance(raw_crop, dict) or not _is_text(raw_crop.get("crop_code")):
        problems.append("cada cultivo debe ser un objeto con «crop_code»")
        return None
    code = raw_crop["crop_code"]
    if not _is_text(raw_crop.get("name")):
        problems.append(f"{code}: falta el nombre")
    crop_type = raw_crop.get("crop_type")
    if crop_type not in CROP_TYPES:
        problems.append(f"{code}: «crop_type» debe ser «grain» o «cover»")

    raw_values = raw_crop.get("reference_values")
    if not isinstance(raw_values, dict):
        problems.append(f"{code}: faltan los valores de referencia")
        return None

    for extra in sorted(set(raw_values) - set(PARAMETER_CODES)):
        problems.append(f"{code}.{extra}: parámetro no permitido en el catálogo")
    values: dict[str, ReferenceValue] = {}
    for parameter in PARAMETER_CODES:
        raw_value = raw_values.get(parameter)
        if raw_value is None:
            problems.append(f"{code}.{parameter}: falta el parámetro")
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
        problems.append(f"{where}: debe ser un objeto")
        return None
    status = raw_value.get("status")
    value = raw_value.get("value")
    source = raw_value.get("source")
    origin = raw_value.get("origin")

    if status in EMPTY_STATUSES:
        if value is not None or source is not None or origin is not None:
            problems.append(f"{where}: con estado «{status}» no debe haber valor, origen ni cita")
    elif status in VALUED_STATUSES:
        if not _is_text(source):
            problems.append(f"{where}: el valor no tiene cita («source» vacío)")
        expected_origin = ORIGIN_BY_STATUS[status]
        if origin != expected_origin:
            problems.append(f"{where}: el origen de «{status}» debe ser «{expected_origin}»")
        problems.extend(f"{where}: {issue}" for issue in _check_value(parameter, value))
    else:
        problems.append(f"{where}: estado desconocido «{status}»")
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
            return ["las duraciones deben tener exactamente las 4 etapas"]
        if any(not _is_int(days) or days < 1 for days in value.values()):
            return ["cada duración debe ser un entero de 1 día o más"]
        return []
    if not _is_number(value):
        return ["el valor debe ser numérico"]
    if parameter in ("kc_initial", "kc_mid", "kc_end", "ky") and value < 0:
        return ["no puede ser negativo"]
    if parameter in ("root_depth_initial_m", "root_depth_max_m") and value <= 0:
        return ["debe ser mayor que 0"]
    if parameter == "depletion_fraction_p" and not 0 < value < 1:
        return ["debe estar entre 0 y 1 (sin incluirlos)"]
    return []


def _check_crop_rules(
    code: str, crop_type: Any, values: dict[str, ReferenceValue], problems: list[str]
) -> None:
    ky = values.get("ky")
    if ky is not None:
        if crop_type == "cover" and ky.status != STATUS_NOT_APPLICABLE:
            problems.append(f"{code}.ky: un cultivo de cobertura no lleva Ky («no aplica»)")
        if crop_type == "grain" and ky.status == STATUS_NOT_APPLICABLE:
            problems.append(f"{code}.ky: un cultivo de grano necesita Ky o «sin referencia»")
    initial = values.get("root_depth_initial_m")
    maximum = values.get("root_depth_max_m")
    if (
        initial is not None
        and maximum is not None
        and _is_number(initial.value)
        and _is_number(maximum.value)
        and initial.value > maximum.value
    ):
        problems.append(f"{code}: la Zr inicial no puede superar la Zr máxima")


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
