"""Parser de la respuesta de NASA POWER y procedencia de la serie (RF-5, RF-6, RF-13; T040).

Convierte el JSON crudo en una serie diaria del dominio (``DailyClimate``), con un registro por
cada fecha de la consulta, en orden:

- el valor de relleno (``header.fill_value``, −999,0 si no se declara) pasa a ``None`` (CA-6.1);
- una fecha ausente de una variable también es ``None`` (CA-6.1);
- nunca se interpola ni se completa nada (CA-6.2);
- un cuerpo que no es JSON, la falta de ``properties.parameter``, de alguna de las siete
  variables, una unidad distinta de la esperada o la falta de elevación son
  ``PowerBadResponseError`` (CA-5.5). Las unidades jamás se convierten en silencio.

Rutas JSON verificadas en ``research.md`` §V-1: ``properties.parameter.<VAR>.<YYYYMMDD>``,
``parameters.<VAR>.units``, ``header.fill_value``, ``header.api.version`` y
``geometry.coordinates`` = [longitud, latitud, elevación].

La serie vive solo en memoria durante la solicitud (CA-5.2): este módulo no escribe nada.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.core import messages
from app.core.config import (
    POWER_EXPECTED_UNITS,
    POWER_FILL_VALUE_DEFAULT,
    POWER_VARIABLES,
    Settings,
)
from app.core.exceptions import PowerBadResponseError
from app.domain.types import DailyClimate
from app.services.power_client import PowerQuery, PowerRawResponse

_FIELD_BY_VARIABLE = {
    "PRECTOTCORR": "precipitation_mm",
    "T2M_MAX": "t_max_c",
    "T2M_MIN": "t_min_c",
    "T2MDEW": "dew_point_c",
    "WS2M": "wind_mean_ms",
    "WS2M_MAX": "wind_max_ms",
    "ALLSKY_SFC_SW_DWN": "solar_radiation_mj_m2",
}


@dataclass(frozen=True, slots=True)
class VariableProvenance:
    code: str
    name: str
    unit: str
    use: str
    missing_days: int


@dataclass(frozen=True, slots=True)
class Provenance:
    """Procedencia de la serie (CA-13.1) y su rótulo de celda (CA-13.2)."""

    source: str
    service: str
    retrieval: str
    queried_at: datetime
    source_version: str | None
    requested_latitude_deg: float
    requested_longitude_deg: float
    source_latitude_deg: float
    source_longitude_deg: float
    elevation_m: float
    spatial_note: str
    date_start: date
    date_end: date
    variables: tuple[VariableProvenance, ...]
    label: str


@dataclass(frozen=True, slots=True)
class ClimateSeries:
    """Serie diaria completa de la consulta, un registro por fecha, en orden."""

    days: tuple[DailyClimate, ...]
    elevation_m: float
    provenance: Provenance


def _bad(detail: str) -> PowerBadResponseError:
    return PowerBadResponseError(f"Respuesta de NASA POWER inesperada: {detail}")


def _load_json(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise _bad("el cuerpo no es JSON") from error
    if not isinstance(payload, dict):
        raise _bad("la raíz no es un objeto")
    return payload


def _dig(payload: Any, *path: str) -> Any:
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise _bad("falta " + ".".join(path))
        node = node[key]
    return node


def _number(value: Any) -> float | None:
    """Número finito o ``None`` si es el relleno de la fuente; otro tipo es un formato inválido."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _bad("un valor diario no es numérico")
    return None if not math.isfinite(value) else float(value)


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _coordinates(payload: dict[str, Any]) -> tuple[float, float, float]:
    coordinates = _dig(payload, "geometry", "coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 3:
        raise _bad("falta la elevación en geometry.coordinates[2]")
    values = []
    for item in coordinates[:3]:
        if isinstance(item, bool) or not isinstance(item, int | float) or not math.isfinite(item):
            raise _bad("las coordenadas no son numéricas")
        values.append(float(item))
    return values[0], values[1], values[2]


def _variable_series(
    payload: dict[str, Any], variable: str, fill_value: float
) -> dict[date, float | None]:
    raw = _dig(payload, "properties", "parameter", variable)
    if not isinstance(raw, dict):
        raise _bad(f"la serie de {variable} no es un objeto")
    units = _dig(payload, "parameters", variable, "units")
    if units != POWER_EXPECTED_UNITS[variable]:
        raise _bad(
            f"unidad de {variable}: «{units}» en lugar de «{POWER_EXPECTED_UNITS[variable]}»"
        )
    series: dict[date, float | None] = {}
    for key, value in raw.items():
        day = _parse_date(str(key))
        if day is None:
            continue
        number = _number(value)
        series[day] = None if number is None or number == fill_value else number
    return series


def parse_power_response(
    raw: PowerRawResponse, query: PowerQuery, settings: Settings | None = None
) -> ClimateSeries:
    """Interpreta la respuesta de NASA POWER para el rango de ``query``."""
    payload = _load_json(raw.body)
    _dig(payload, "properties", "parameter")  # falta de la estructura base → error explícito
    header = payload.get("header")
    declared_fill = header.get("fill_value") if isinstance(header, dict) else None
    fill_value = (
        float(declared_fill)
        if isinstance(declared_fill, int | float) and not isinstance(declared_fill, bool)
        else POWER_FILL_VALUE_DEFAULT
    )
    longitude, latitude, elevation = _coordinates(payload)

    by_variable = {
        variable: _variable_series(payload, variable, fill_value) for variable in POWER_VARIABLES
    }
    count = (query.end - query.start).days + 1
    days: list[DailyClimate] = []
    for offset in range(count):
        day = query.start + timedelta(days=offset)
        values = {
            _FIELD_BY_VARIABLE[variable]: by_variable[variable].get(day)
            for variable in POWER_VARIABLES
        }
        days.append(DailyClimate(day=day, **values))

    version = header.get("api", {}).get("version") if isinstance(header, dict) else None
    provenance = _build_provenance(
        raw,
        query,
        days,
        latitude,
        longitude,
        elevation,
        version if isinstance(version, str) else None,
        community=(settings or Settings()).power_community,
    )
    return ClimateSeries(tuple(days), elevation, provenance)


def _build_provenance(
    raw: PowerRawResponse,
    query: PowerQuery,
    days: list[DailyClimate],
    source_latitude: float,
    source_longitude: float,
    elevation: float,
    version: str | None,
    *,
    community: str,
) -> Provenance:
    variables = []
    for code in POWER_VARIABLES:
        name, unit, use = messages.POWER_VARIABLE_INFO[code]
        field = _FIELD_BY_VARIABLE[code]
        missing = sum(1 for day in days if getattr(day, field) is None)
        variables.append(VariableProvenance(code, name, unit, use, missing))
    return Provenance(
        source=messages.PROVENANCE_SOURCE,
        service=messages.PROVENANCE_SERVICE.format(community=community),
        retrieval=messages.PROVENANCE_RETRIEVAL,
        queried_at=raw.requested_at,
        source_version=version,
        requested_latitude_deg=query.latitude_deg,
        requested_longitude_deg=query.longitude_deg,
        source_latitude_deg=source_latitude,
        source_longitude_deg=source_longitude,
        elevation_m=elevation,
        spatial_note=messages.PROVENANCE_SPATIAL_NOTE,
        date_start=query.start,
        date_end=query.end,
        variables=tuple(variables),
        label=messages.CELL_SCALE_LABEL,
    )
