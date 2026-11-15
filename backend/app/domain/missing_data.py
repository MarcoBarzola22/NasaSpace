"""Datos faltantes, sustituciones de FAO-56 y cobertura de la fuente (RF-6, RF-4; T026–T028).

Regla de fondo (CA-6.2): **nunca** se interpola, se promedia con días vecinos ni se copian valores
de otros días, celdas o fuentes. Lo que falta se trata de una de tres maneras:

1. **Bloqueo** del escenario (para todas las rotaciones): faltan la precipitación o una temperatura
   (CA-6.3), la temperatura máxima es menor que la mínima (CA-6.10), la ventana empieza antes de
   la cobertura de una variable (CA-4.5) o incluye la racha final de datos aún no publicados
   (plan, T-13).
2. **Sustitución declarada** de FAO-56, solo para calcular la ET₀ (CA-6.4–CA-6.6, CA-6.8): la
   radiación (Hargreaves, ec. 50), el punto de rocío (Tmín − 2 °C, ec. 48 y anexo 6) y el viento
   medio (2 m/s, valor provisional de FAO-56).
3. **Nada**: un ``WS2M_MAX`` faltante solo afecta al proxy de viento, que lo cuenta como «sin
   dato» (CA-11.4).

Este módulo devuelve códigos estables y fechas; el texto en español de cada código está en
``app.core.messages``. No lee archivos ni la red.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.constants import DEFAULT_WIND_2M_MS, DEW_POINT_SEMIARID_OFFSET_C
from app.domain.calendar import day_of_year
from app.domain.et0 import (
    clear_sky_radiation_mj_m2_day,
    extraterrestrial_radiation_mj_m2_day,
    hargreaves_radiation_mj_m2_day,
)
from app.domain.types import DailyClimate, Weather

# Códigos de las variables de NASA POWER (plan §6.3).
VAR_PRECIPITATION = "PRECTOTCORR"
VAR_T_MAX = "T2M_MAX"
VAR_T_MIN = "T2M_MIN"
VAR_DEW_POINT = "T2MDEW"
VAR_WIND_MEAN = "WS2M"
VAR_WIND_MAX = "WS2M_MAX"
VAR_RADIATION = "ALLSKY_SFC_SW_DWN"

ALL_VARIABLES: tuple[str, ...] = (
    VAR_PRECIPITATION,
    VAR_T_MAX,
    VAR_T_MIN,
    VAR_DEW_POINT,
    VAR_WIND_MEAN,
    VAR_WIND_MAX,
    VAR_RADIATION,
)

# Motivos de bloqueo (códigos estables del contrato).
BLOCK_MISSING_PRECIPITATION = "MISSING_PRECIPITATION"
BLOCK_MISSING_T_MAX = "MISSING_TMAX"
BLOCK_MISSING_T_MIN = "MISSING_TMIN"
BLOCK_INCONSISTENT_TEMPERATURE = "INCONSISTENT_SOURCE_DATA"
BLOCK_UNPUBLISHED = "UNPUBLISHED_DATA_BLOCK"
BLOCK_BEFORE_COVERAGE = "BEFORE_SOURCE_COVERAGE"

# Métodos de sustitución (coinciden con los códigos de supuesto del plan §11).
SUBST_RADIATION = "SUBST_RADIATION_HARGREAVES"
SUBST_DEW_POINT = "SUBST_HUMIDITY_TMIN"
SUBST_WIND = "SUBST_WIND_FAO56_DEFAULT"

_BLOCKING_VARIABLES: tuple[tuple[str, str], ...] = (
    (VAR_PRECIPITATION, BLOCK_MISSING_PRECIPITATION),
    (VAR_T_MAX, BLOCK_MISSING_T_MAX),
    (VAR_T_MIN, BLOCK_MISSING_T_MIN),
)
_SUBSTITUTED_VARIABLES: tuple[tuple[str, str], ...] = (
    (VAR_RADIATION, SUBST_RADIATION),
    (VAR_DEW_POINT, SUBST_DEW_POINT),
    (VAR_WIND_MEAN, SUBST_WIND),
)


@dataclass(frozen=True, slots=True)
class Block:
    """Motivo por el que un escenario no se calcula.

    ``dates`` lista los días puntuales afectados. En los bloqueos por cobertura o por datos no
    publicados la lista va vacía y el período afectado es ``first_date``–``last_date``.
    """

    code: str
    variable: str | None
    first_date: date
    last_date: date
    dates: tuple[date, ...] = ()


@dataclass(frozen=True, slots=True)
class Substitution:
    """Días en que se estimó una variable con FAO-56 en lugar de usar el dato de la fuente."""

    variable: str
    method: str
    dates: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class MissingReport:
    blocks: tuple[Block, ...]
    substitutions: tuple[Substitution, ...]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocks)


@dataclass(frozen=True, slots=True)
class SubstitutionResult:
    weather: tuple[Weather, ...]
    substitutions: tuple[Substitution, ...]


def _value(day: DailyClimate, variable: str) -> float | None:
    return {
        VAR_PRECIPITATION: day.precipitation_mm,
        VAR_T_MAX: day.t_max_c,
        VAR_T_MIN: day.t_min_c,
        VAR_DEW_POINT: day.dew_point_c,
        VAR_WIND_MEAN: day.wind_mean_ms,
        VAR_WIND_MAX: day.wind_max_ms,
        VAR_RADIATION: day.solar_radiation_mj_m2,
    }[variable]


def _dates_block(code: str, variable: str | None, dates: list[date]) -> Block:
    return Block(code, variable, first_date=dates[0], last_date=dates[-1], dates=tuple(dates))


# --- T026: clasificación ---


def classify_missing(days: Sequence[DailyClimate]) -> MissingReport:
    """Clasifica los faltantes de los días de una ventana (CA-6.3, CA-6.10, CA-11.4).

    Cada ``None`` es un dato de relleno o un día ausente (CA-6.1). Los bloqueos se informan por
    variable con todas sus fechas; las sustituciones, por variable y método.
    """
    blocks: list[Block] = []
    for variable, code in _BLOCKING_VARIABLES:
        missing = [day.day for day in days if _value(day, variable) is None]
        if missing:
            blocks.append(_dates_block(code, variable, missing))

    inconsistent = [
        day.day
        for day in days
        if day.t_max_c is not None and day.t_min_c is not None and day.t_max_c < day.t_min_c
    ]
    if inconsistent:
        blocks.append(_dates_block(BLOCK_INCONSISTENT_TEMPERATURE, None, inconsistent))

    substitutions: list[Substitution] = []
    for variable, method in _SUBSTITUTED_VARIABLES:
        missing = [day.day for day in days if _value(day, variable) is None]
        if missing:
            substitutions.append(Substitution(variable, method, tuple(missing)))
    return MissingReport(tuple(blocks), tuple(substitutions))


# --- T027: sustituciones de FAO-56 ---


def apply_substitutions(
    days: Sequence[DailyClimate], latitude_deg: float, elevation_m: float
) -> SubstitutionResult:
    """Completa los días para calcular la ET₀ con los procedimientos de FAO-56 (CA-6.4–CA-6.6).

    - Rs faltante: Rs = min(kRs·√(Tmáx − Tmín)·Ra, Rso), con kRs = 0,16 (ec. 50);
    - Tdew faltante: Tdew = Tmín − 2 °C (ec. 48, anexo 6, clima semiárido);
    - u₂ faltante: 2 m/s (valor provisional de FAO-56).

    Cada día se resuelve solo con sus propias variables: nunca mira el día anterior ni el
    siguiente (CA-6.2). Los días deben estar completos en precipitación y temperaturas y ser
    consistentes (Tmáx ≥ Tmín); si no, es un error de uso: el escenario debía estar bloqueado.
    """
    weather: list[Weather] = []
    missing: dict[str, list[date]] = {variable: [] for variable, _ in _SUBSTITUTED_VARIABLES}
    for day in days:
        if day.precipitation_mm is None or day.t_max_c is None or day.t_min_c is None:
            raise ValueError(f"El día {day.day} no tiene lluvia o temperaturas: debía bloquearse.")
        if day.t_max_c < day.t_min_c:
            raise ValueError(f"El día {day.day} tiene Tmáx < Tmín: debía bloquearse.")
        ra = extraterrestrial_radiation_mj_m2_day(latitude_deg, day_of_year(day.day))
        rso = clear_sky_radiation_mj_m2_day(ra, elevation_m)

        radiation = day.solar_radiation_mj_m2
        if radiation is None:
            radiation = hargreaves_radiation_mj_m2_day(day.t_max_c, day.t_min_c, ra, rso)
            missing[VAR_RADIATION].append(day.day)
        dew_point = day.dew_point_c
        if dew_point is None:
            dew_point = day.t_min_c - DEW_POINT_SEMIARID_OFFSET_C
            missing[VAR_DEW_POINT].append(day.day)
        wind = day.wind_mean_ms
        if wind is None:
            wind = DEFAULT_WIND_2M_MS
            missing[VAR_WIND_MEAN].append(day.day)

        weather.append(
            Weather(
                day=day.day,
                precipitation_mm=day.precipitation_mm,
                t_max_c=day.t_max_c,
                t_min_c=day.t_min_c,
                dew_point_c=dew_point,
                wind_2m_ms=wind,
                solar_radiation_mj_m2=radiation,
                extraterrestrial_radiation_mj_m2=ra,
                clear_sky_radiation_mj_m2=rso,
            )
        )
    substitutions = tuple(
        Substitution(variable, method, tuple(missing[variable]))
        for variable, method in _SUBSTITUTED_VARIABLES
        if missing[variable]
    )
    return SubstitutionResult(tuple(weather), substitutions)


# --- T028: cobertura de la fuente y datos no publicados ---


def unpublished_streak_starts(series: Sequence[DailyClimate]) -> dict[str, date]:
    """Primer día de la racha final de faltantes de cada variable de la serie completa.

    NASA POWER publica con retraso: los últimos días de la consulta llegan con el valor de
    relleno (research.md V-1, O-2). Una racha de faltantes que llega hasta el final de la serie
    se interpreta como «aún no publicado». Las variables sin racha final no figuran.
    """
    ordered = sorted(series, key=lambda day: day.day)
    starts: dict[str, date] = {}
    for variable in ALL_VARIABLES:
        streak_start: date | None = None
        for day in reversed(ordered):
            if _value(day, variable) is not None:
                break
            streak_start = day.day
        if streak_start is not None:
            starts[variable] = streak_start
    return starts


def check_coverage(
    series: Sequence[DailyClimate],
    first_day: date,
    last_day: date,
    coverage_start: Mapping[str, date],
) -> tuple[Block, ...]:
    """Bloqueos por cobertura de la ventana ``first_day``–``last_day`` (CA-4.5).

    - Antes de la cobertura: la ventana empieza antes del primer día con datos de una variable.
    - No publicado: la ventana incluye días de la racha final de faltantes de la serie, o días
      posteriores al último día recibido.

    Un faltante interior no bloquea por cobertura: lo tratan las reglas de RF-6.
    """
    ordered = sorted(series, key=lambda day: day.day)
    series_last = ordered[-1].day if ordered else first_day - timedelta(days=1)
    streaks = unpublished_streak_starts(ordered)

    blocks: list[Block] = []
    for variable in ALL_VARIABLES:
        start = coverage_start.get(variable)
        if start is not None and first_day < start:
            blocks.append(
                Block(
                    BLOCK_BEFORE_COVERAGE,
                    variable,
                    first_date=first_day,
                    last_date=min(last_day, start - timedelta(days=1)),
                )
            )
    for variable in ALL_VARIABLES:
        unpublished_from = streaks.get(variable, series_last + timedelta(days=1))
        if last_day >= unpublished_from:
            blocks.append(
                Block(
                    BLOCK_UNPUBLISHED,
                    variable,
                    first_date=max(first_day, unpublished_from),
                    last_date=last_day,
                )
            )
    return tuple(blocks)


def window_days(
    series: Sequence[DailyClimate], first_day: date, last_day: date
) -> list[DailyClimate]:
    """Los días de la ventana, uno por fecha; una fecha ausente de la serie queda sin datos."""
    by_date = {day.day: day for day in series}
    count = (last_day - first_day).days + 1
    days = [first_day + timedelta(days=offset) for offset in range(count)]
    return [by_date.get(day, DailyClimate(day=day)) for day in days]


def assess_window(
    series: Sequence[DailyClimate],
    first_day: date,
    last_day: date,
    coverage_start: Mapping[str, date],
) -> MissingReport:
    """Informe completo de una ventana: cobertura, faltantes, inconsistencias y sustituciones.

    Los días que ya explica un bloqueo por cobertura o por datos no publicados no se repiten como
    faltantes sueltos ni como sustituciones de la misma variable.
    """
    coverage_blocks = check_coverage(series, first_day, last_day, coverage_start)
    report = classify_missing(window_days(series, first_day, last_day))

    explained: dict[str, list[tuple[date, date]]] = {}
    for block in coverage_blocks:
        if block.variable is not None:
            explained.setdefault(block.variable, []).append((block.first_date, block.last_date))

    def is_explained(variable: str | None, day: date) -> bool:
        return variable is not None and any(
            first <= day <= last for first, last in explained.get(variable, [])
        )

    blocks: list[Block] = list(coverage_blocks)
    for block in report.blocks:
        remaining = [day for day in block.dates if not is_explained(block.variable, day)]
        if remaining:
            blocks.append(_dates_block(block.code, block.variable, remaining))
    substitutions = []
    for substitution in report.substitutions:
        remaining = [
            day for day in substitution.dates if not is_explained(substitution.variable, day)
        ]
        if remaining:
            substitutions.append(
                Substitution(substitution.variable, substitution.method, tuple(remaining))
            )
    return MissingReport(tuple(blocks), tuple(substitutions))
