"""Registro de supuestos de una solicitud (RF-14; T030).

Cada supuesto lleva un código estable, su descripción en español, el alcance, el valor usado con
su unidad y el origen (CA-14.1). Los supuestos que se repiten día a día (una sustitución, una
ET₀ llevada a 0) se agrupan en una sola entrada con el conteo y las fechas (CA-14.4).

El registro es de **una solicitud**: se crea vacío, se llena durante el cálculo y se descarta
(RNF-8). No guarda nada fuera de la memoria. Con la misma secuencia de altas devuelve siempre la
misma lista, en el orden de la primera aparición de cada supuesto (RNF-1).

Los códigos y sus textos están en ``app.core.messages``. Un código desconocido es un error de
programación y se rechaza al registrarlo, para que un error de tipeo no pase inadvertido.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.core import messages
from app.core.constants import (
    DEFAULT_WIND_2M_MS,
    DEW_POINT_SEMIARID_OFFSET_C,
    HARGREAVES_KRS,
)
from app.domain.missing_data import (
    SUBST_DEW_POINT,
    SUBST_RADIATION,
    SUBST_WIND,
    Substitution,
)

SCOPES: tuple[str, ...] = ("request", "rotation", "crop", "fallow", "scenario", "date")
ORIGINS: tuple[str, ...] = ("user", "fao_reference", "team_default", "system_default")

# Supuestos que van en toda respuesta: CA-14.2 más los siempre vigentes del plan §11.
ALWAYS_ON: tuple[str, ...] = (
    "RAINFED_NO_IRRIGATION",
    "TOP_DOWN_INFILTRATION",
    "EXCESS_LOST",
    "NO_CAPILLARY_RISE",
    "INITIAL_MOISTURE_UNIFORM",
    "INITIAL_MOISTURE_EACH_SCENARIO",
    "FIXED_DEPTH_PROFILE",
    "CONSTANT_PRICES_COSTS",
    "PARAMETERS_NOT_CALIBRATED",
    "CELL_SCALE_CLIMATE",
    "UNIFORM_REDISTRIBUTION",
    "LINEAR_ROOT_GROWTH",
    "AVAILABLE_WATER_LIMITS",
    "HUMIDITY_FROM_DEW_POINT",
    "NO_KC_CLIMATE_ADJUSTMENT",
)

# Origen por defecto de cada código (plan §11 y CA-14.1): quién lo decidió.
_FAO = "fao_reference"
_TEAM = "team_default"
_SYSTEM = "system_default"
DEFAULT_ORIGIN: dict[str, str] = {
    "RAINFED_NO_IRRIGATION": _SYSTEM,
    "TOP_DOWN_INFILTRATION": _TEAM,
    "EXCESS_LOST": _SYSTEM,
    "NO_CAPILLARY_RISE": _SYSTEM,
    "INITIAL_MOISTURE_UNIFORM": _SYSTEM,
    "INITIAL_MOISTURE_EACH_SCENARIO": _SYSTEM,
    "FIXED_DEPTH_PROFILE": _SYSTEM,
    "CONSTANT_PRICES_COSTS": _SYSTEM,
    "PARAMETERS_NOT_CALIBRATED": _SYSTEM,
    "CELL_SCALE_CLIMATE": _SYSTEM,
    "UNIFORM_REDISTRIBUTION": _TEAM,
    "LINEAR_ROOT_GROWTH": _TEAM,
    "AVAILABLE_WATER_LIMITS": _SYSTEM,
    "HUMIDITY_FROM_DEW_POINT": _FAO,
    "NO_KC_CLIMATE_ADJUSTMENT": _TEAM,
    "FALLOW_EVAPORATION_LAYER": _FAO,
    "INITIAL_ROOT_DEPTH_TEAM": _TEAM,
    "SUBST_HUMIDITY_TMIN": _FAO,
    "SUBST_RADIATION_HARGREAVES": _FAO,
    "SUBST_WIND_FAO56_DEFAULT": _FAO,
    "WINDOW_START_DEFAULT": _TEAM,
    "UNPUBLISHED_DATA_BLOCK": _TEAM,
    "FAO_REFERENCE_VALUE": _FAO,
    "TEAM_REFERENCE_VALUE": _TEAM,
    "USER_VALUE": "user",
    "ROOT_DEPTH_LIMITED": _SYSTEM,
    "NO_RESIDUE_DECLARED": _SYSTEM,
    "FALLOW_KC_BASE_DEFAULT": _TEAM,
    "RESIDUE_NO_DECOMPOSITION": _SYSTEM,
    "ET0_NEGATIVE_CLAMPED": _SYSTEM,
    "YIELD_CLIPPED_TO_ZERO": _SYSTEM,
}

# Valor y unidad de cada sustitución de FAO-56 (CA-6.4–CA-6.6).
_SUBSTITUTION_VALUES: dict[str, tuple[float, str]] = {
    SUBST_RADIATION: (HARGREAVES_KRS, "kRs (adimensional)"),
    SUBST_DEW_POINT: (DEW_POINT_SEMIARID_OFFSET_C, "°C por debajo de Tmín"),
    SUBST_WIND: (DEFAULT_WIND_2M_MS, "m/s"),
}


@dataclass(frozen=True, slots=True)
class Assumption:
    """Una entrada del registro, ya agrupada."""

    code: str
    description: str
    scope: str
    scope_id: str | None
    value: float | str | None
    unit: str | None
    origin: str
    source: str | None
    count: int
    dates: tuple[date, ...]


_Key = tuple[str, str, str | None, float | str | None, str | None, str, str | None]


class AssumptionRegistry:
    """Acumula supuestos y los entrega agrupados y en orden estable."""

    def __init__(self) -> None:
        self._counts: dict[_Key, int] = {}
        self._dates: dict[_Key, set[date]] = {}

    def add(
        self,
        code: str,
        *,
        scope: str = "request",
        scope_id: str | None = None,
        value: float | str | None = None,
        unit: str | None = None,
        origin: str | None = None,
        source: str | None = None,
        day: date | None = None,
    ) -> None:
        """Registra un supuesto; si ya existe con el mismo alcance, suma uno al conteo."""
        if code not in messages.ASSUMPTION_DESCRIPTIONS:
            raise ValueError(f"Código de supuesto desconocido: {code}")
        if scope not in SCOPES:
            raise ValueError(f"Alcance de supuesto desconocido: {scope}")
        resolved_origin = origin or DEFAULT_ORIGIN[code]
        if resolved_origin not in ORIGINS:
            raise ValueError(f"Origen de supuesto desconocido: {resolved_origin}")
        resolved_source = source if source is not None else messages.ASSUMPTION_SOURCES.get(code)
        key: _Key = (code, scope, scope_id, value, unit, resolved_origin, resolved_source)
        self._counts[key] = self._counts.get(key, 0) + 1
        dates = self._dates.setdefault(key, set())
        if day is not None:
            dates.add(day)

    def add_always_on(self) -> None:
        """Agrega los supuestos que acompañan a toda respuesta (CA-14.2)."""
        for code in ALWAYS_ON:
            self.add(code)

    def add_substitutions(self, scenario_id: str, substitutions: Iterable[Substitution]) -> None:
        """Registra, por fecha, cada sustitución de FAO-56 de un escenario (CA-6.4–CA-6.7)."""
        for substitution in substitutions:
            value, unit = _SUBSTITUTION_VALUES[substitution.method]
            for day in substitution.dates:
                self.add(
                    substitution.method,
                    scope="scenario",
                    scope_id=scenario_id,
                    value=value,
                    unit=unit,
                    day=day,
                )

    def entries(self) -> list[Assumption]:
        """Supuestos agrupados, en el orden de la primera aparición; fechas en orden creciente."""
        return [
            Assumption(
                code=code,
                description=messages.ASSUMPTION_DESCRIPTIONS[code],
                scope=scope,
                scope_id=scope_id,
                value=value,
                unit=unit,
                origin=origin,
                source=source,
                count=count,
                dates=tuple(sorted(self._dates[key])),
            )
            for key, count in self._counts.items()
            for code, scope, scope_id, value, unit, origin, source in [key]
        ]

    def __len__(self) -> int:
        return len(self._counts)
