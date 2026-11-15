"""Generador de respuestas sintéticas de NASA POWER para las pruebas (T038).

Reproduce solo la forma verificada en ``research.md`` §V-1: rutas JSON, cadenas de unidades y
valor de relleno. Los números son sintéticos (no representan clima real). No abre archivos.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

FILL_VALUE = -999.0
DEFAULT_ELEVATION_M = 699.34

UNITS: dict[str, str] = {
    "PRECTOTCORR": "mm/day",
    "T2M_MAX": "C",
    "T2M_MIN": "C",
    "T2MDEW": "C",
    "WS2M": "m/s",
    "WS2M_MAX": "m/s",
    "ALLSKY_SFC_SW_DWN": "MJ/m^2/day",
}

_LONG_NAMES: dict[str, str] = {
    "PRECTOTCORR": "Precipitation Corrected",
    "T2M_MAX": "Temperature at 2 Meters Maximum",
    "T2M_MIN": "Temperature at 2 Meters Minimum",
    "T2MDEW": "Dew/Frost Point at 2 Meters",
    "WS2M": "Wind Speed at 2 Meters",
    "WS2M_MAX": "Wind Speed at 2 Meters Maximum",
    "ALLSKY_SFC_SW_DWN": "All Sky Surface Shortwave Downward Irradiance",
}

# Valores diarios constantes y plausibles (sintéticos).
_DEFAULT_VALUES: dict[str, float] = {
    "PRECTOTCORR": 1.5,
    "T2M_MAX": 28.0,
    "T2M_MIN": 14.0,
    "T2MDEW": 12.0,
    "WS2M": 2.5,
    "WS2M_MAX": 5.0,
    "ALLSKY_SFC_SW_DWN": 20.0,
}


def power_payload(
    start: date,
    end: date,
    *,
    latitude_deg: float = -33.68,
    longitude_deg: float = -65.47,
    values: Mapping[str, float] | None = None,
    fill_dates: Mapping[str, Iterable[date]] | None = None,
    drop_parameter: str | Iterable[str] | None = None,
    units_override: Mapping[str, str] | None = None,
    without_elevation: bool = False,
    trailing_fill: int = 0,
    missing_dates: Iterable[date] = (),
    api_version: str | None = "v2.10.3",
    declare_fill_value: bool = True,
) -> dict[str, Any]:
    """Respuesta JSON de ``/api/temporal/daily/point`` con fechas contiguas de ``start`` a ``end``.

    Opciones:

    - ``fill_dates``: por variable, fechas con el valor de relleno (−999.0);
    - ``drop_parameter``: variable(s) que no aparecen en la respuesta (como la radiación en
      rangos anteriores a 1984);
    - ``units_override``: reemplaza la cadena de unidades de una variable;
    - ``without_elevation``: la geometría trae solo longitud y latitud;
    - ``trailing_fill``: los últimos N días de todas las variables vienen con relleno (aún no
      publicados);
    - ``missing_dates``: fechas que no aparecen en ninguna variable (fecha ausente);
    - ``values``: valor diario por variable en lugar del valor sintético por defecto.
    """
    if end < start:
        raise ValueError("end no puede ser anterior a start")
    dropped = {drop_parameter} if isinstance(drop_parameter, str) else set(drop_parameter or ())
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    absent = set(missing_dates)
    trailing = set(days[len(days) - trailing_fill :]) if trailing_fill > 0 else set()
    series_values = {**_DEFAULT_VALUES, **(values or {})}
    per_variable_fill = {name: set(dates) for name, dates in (fill_dates or {}).items()}

    parameter: dict[str, dict[str, float]] = {}
    for name in UNITS:
        if name in dropped:
            continue
        filled = per_variable_fill.get(name, set()) | trailing
        parameter[name] = {
            day.strftime("%Y%m%d"): FILL_VALUE if day in filled else series_values[name]
            for day in days
            if day not in absent
        }

    coordinates = [longitude_deg, latitude_deg]
    if not without_elevation:
        coordinates.append(DEFAULT_ELEVATION_M)

    header: dict[str, Any] = {
        "title": "NASA/POWER Source Native Resolution Daily Data",
        "sources": ["MERRA2", "POWER"],
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "time_standard": "LST",
    }
    if api_version is not None:
        header["api"] = {"version": api_version, "name": "POWER Daily API"}
    if declare_fill_value:
        header["fill_value"] = FILL_VALUE

    units = {**UNITS, **(units_override or {})}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": {"parameter": parameter},
        "header": header,
        "messages": [],
        "parameters": {
            name: {"units": units[name], "longname": _LONG_NAMES[name]}
            for name in UNITS
            if name not in dropped
        },
        "times": {"data": 0.1, "process": 0.1},
    }
