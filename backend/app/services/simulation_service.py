"""Orquestación de una simulación: de la solicitud validada a los resultados (RF-1…RF-12; T043).

Sigue el pseudocódigo del plan §7.1, con estos pasos:

1. valida la solicitud sin red (CA-5.3, CA-16.1);
2. resuelve los parámetros efectivos y registra los supuestos (CA-14.2, CA-3.3);
3. hace **una sola** consulta a NASA POWER que cubre todas las ventanas calculables (CA-5.1);
4. por escenario: bloquea por cobertura, faltantes o inconsistencias (CA-4.5, CA-6.3, CA-6.10) o,
   si está limpio, sustituye lo que FAO-56 permite, calcula la ET₀ **una vez** (RF-7) y corre
   cada rotación: balance hídrico (RF-8), rendimiento FAO-33 (RF-9), economía (RF-10) y proxy de
   viento (RF-11);
5. consolida rangos entre escenarios y diferencias de margen entre rotaciones (RF-12, D-15).

Un escenario bloqueado no se calcula para ninguna rotación y el resto sigue (CA-16.2). Si todos
se bloquean, no hay resultados y tampoco una excepción (CA-16.3). Un ``CalculationIntegrityError``
en cualquier corrida se propaga y no deja resultados parciales (CA-16.5).

Si ninguna ventana cae dentro de la cobertura de la fuente no se consulta nada: no habría datos
que pedir (ver ``window_service.power_query_range``). Entonces ``provenance`` es ``None``.

Este servicio no escribe archivos ni guarda la serie; el estado vive solo durante la llamada.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.config import Settings
from app.domain.calendar import build_timeline, build_window
from app.domain.economics import CropEconomics, RotationEconomics, rotation_economics
from app.domain.et0 import clamp_negative_et0, et0_penman_monteith
from app.domain.missing_data import (
    BLOCK_BEFORE_COVERAGE,
    Block,
    Substitution,
    apply_substitutions,
    assess_window,
    check_coverage,
    window_days,
)
from app.domain.stats import (
    MarginDifference,
    RotationRanges,
    ScenarioRun,
    margin_differences,
    rotation_ranges,
)
from app.domain.types import CropSegment, Timeline, Weather, Window
from app.domain.water_balance import BalanceRun, SegmentBalance, run_daily_balance
from app.domain.wind_proxy import SoilExposure, soil_exposure
from app.domain.yield_response import YieldResult, crop_yields
from app.models.request import SimulationRequest
from app.services.assumptions import Assumption, AssumptionRegistry
from app.services.catalog_service import Catalog
from app.services.climate_parser import ClimateSeries, Provenance, parse_power_response
from app.services.parameter_resolver import (
    ResolvedInput,
    ResolvedRotation,
    crop_scope_id,
    fallow_scope_id,
    resolve_parameters,
)
from app.services.power_client import PowerClient, PowerQuery
from app.services.validation import raise_if_invalid
from app.services.window_service import coverage_start, power_query_range

STATUS_COMPUTED = "computed"
STATUS_BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ScenarioOutcome:
    """Estado de un escenario (año de inicio), común a todas las rotaciones."""

    start_year: int
    first_day: date
    last_day: date
    n_days: int
    status: str
    blocks: tuple[Block, ...] = ()
    substitutions: tuple[Substitution, ...] = ()
    precipitation_total_mm: float | None = None
    et0_total_mm: float | None = None
    et0_negative_days: tuple[date, ...] = ()


@dataclass(frozen=True, slots=True)
class CropRun:
    """Resultado de un cultivo en un escenario."""

    position: int  # desde 1
    crop_code: str
    crop_type: str
    sowing_date: date
    cycle_end_date: date
    segment: SegmentBalance
    yield_result: YieldResult
    economics: CropEconomics


@dataclass(frozen=True, slots=True)
class RunResult:
    """Una rotación en un escenario calculado."""

    rotation_id: str
    start_year: int
    balance: BalanceRun
    crops: tuple[CropRun, ...]
    economics: RotationEconomics
    exposure: SoilExposure


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    resolved: ResolvedInput
    provenance: Provenance | None
    scenarios: tuple[ScenarioOutcome, ...]
    runs: tuple[RunResult, ...]
    ranges: tuple[RotationRanges, ...]
    comparisons: tuple[MarginDifference, ...]
    assumptions: tuple[Assumption, ...]

    @property
    def all_blocked(self) -> bool:
        return all(scenario.status == STATUS_BLOCKED for scenario in self.scenarios)


def compute_et0_series(
    weather: Sequence[Weather], elevation_m: float
) -> tuple[list[float], list[date]]:
    """ET₀ diaria (FAO-56 Penman–Monteith) con las negativas llevadas a 0 (CA-7.2).

    Devuelve la serie y las fechas en que hubo que llevarla a 0. Se llama una vez por escenario.
    """
    series: list[float] = []
    clamped: list[date] = []
    for day in weather:
        value, was_negative = clamp_negative_et0(et0_penman_monteith(day, elevation_m))
        series.append(value)
        if was_negative:
            clamped.append(day.day)
    return series, clamped


async def simulate(
    request: SimulationRequest,
    *,
    catalog: Catalog,
    settings: Settings,
    power_client: PowerClient,
    today: date,
) -> SimulationOutcome:
    """Ejecuta la simulación completa de una solicitud ya validada estructuralmente."""
    raise_if_invalid(request, catalog, today=today)

    registry = AssumptionRegistry()
    registry.add_always_on()
    resolved = resolve_parameters(request, catalog, registry)

    window_cfg = resolved.window
    windows = [
        build_window(year, window_cfg.start_day, window_cfg.start_month)
        for year in window_cfg.start_years
    ]
    common_start = coverage_start(settings)
    queryable = [window for window in windows if window.first_day >= common_start]

    climate: ClimateSeries | None = None
    if queryable:
        first, last = power_query_range(
            [window.start_year for window in queryable],
            window_cfg.start_day,
            window_cfg.start_month,
            not_before=common_start,
        )
        query = PowerQuery(
            resolved.parcel.spec.latitude_deg, resolved.parcel.spec.longitude_deg, first, last
        )
        raw = await power_client.fetch_daily(query)
        climate = parse_power_response(raw, query, settings)

    scenarios: list[ScenarioOutcome] = []
    runs: list[RunResult] = []
    for window in windows:
        if climate is None or window.first_day < common_start:
            scenarios.append(_blocked_before_coverage(window, climate, settings))
            continue
        report = assess_window(
            climate.days, window.first_day, window.last_day, settings.variable_coverage_start
        )
        if report.is_blocked:
            scenarios.append(_scenario(window, STATUS_BLOCKED, blocks=report.blocks))
            continue
        scenario_runs, outcome = _calculate_scenario(window, climate, resolved, registry)
        scenarios.append(outcome)
        runs.extend(scenario_runs)

    ranges, comparisons = _aggregate(resolved, scenarios, runs)
    return SimulationOutcome(
        resolved=resolved,
        provenance=climate.provenance if climate is not None else None,
        scenarios=tuple(scenarios),
        runs=tuple(runs),
        ranges=ranges,
        comparisons=comparisons,
        assumptions=tuple(registry.entries()),
    )


# --- Escenarios ---


def _scenario(
    window: Window,
    status: str,
    *,
    blocks: tuple[Block, ...] = (),
    substitutions: tuple[Substitution, ...] = (),
    precipitation_total_mm: float | None = None,
    et0_total_mm: float | None = None,
    et0_negative_days: tuple[date, ...] = (),
) -> ScenarioOutcome:
    return ScenarioOutcome(
        start_year=window.start_year,
        first_day=window.first_day,
        last_day=window.last_day,
        n_days=window.n_days,
        status=status,
        blocks=blocks,
        substitutions=substitutions,
        precipitation_total_mm=precipitation_total_mm,
        et0_total_mm=et0_total_mm,
        et0_negative_days=et0_negative_days,
    )


def _blocked_before_coverage(
    window: Window, climate: ClimateSeries | None, settings: Settings
) -> ScenarioOutcome:
    """Ventana que empieza antes de la cobertura de alguna variable (CA-4.5): no se calcula."""
    series = climate.days if climate is not None else ()
    blocks = tuple(
        block
        for block in check_coverage(
            series, window.first_day, window.last_day, settings.variable_coverage_start
        )
        if block.code == BLOCK_BEFORE_COVERAGE
    )
    return _scenario(window, STATUS_BLOCKED, blocks=blocks)


def _calculate_scenario(
    window: Window,
    climate: ClimateSeries,
    resolved: ResolvedInput,
    registry: AssumptionRegistry,
) -> tuple[list[RunResult], ScenarioOutcome]:
    parcel = resolved.parcel.spec
    days = window_days(climate.days, window.first_day, window.last_day)
    substitution = apply_substitutions(days, parcel.latitude_deg, climate.elevation_m)
    weather = substitution.weather
    scenario_id = str(window.start_year)
    registry.add_substitutions(scenario_id, substitution.substitutions)

    et0_mm, negative_days = compute_et0_series(weather, climate.elevation_m)
    for day in negative_days:
        registry.add("ET0_NEGATIVE_CLAMPED", scope="scenario", scope_id=scenario_id, day=day)
    rain_mm = [day.precipitation_mm for day in weather]
    wind_max_ms = [day.wind_max_ms for day in days]  # valores crudos de la fuente (CA-6.8)

    runs = [
        _run_rotation(window, rotation, rain_mm, et0_mm, wind_max_ms, resolved, registry)
        for rotation in resolved.rotations
    ]
    outcome = _scenario(
        window,
        STATUS_COMPUTED,
        substitutions=substitution.substitutions,
        precipitation_total_mm=sum(rain_mm),
        et0_total_mm=sum(et0_mm),
        et0_negative_days=tuple(negative_days),
    )
    return runs, outcome


def _register_fallow_assumptions(
    timeline: Timeline, rotation_id: str, registry: AssumptionRegistry
) -> None:
    """Supuestos de barbecho: capa evaporable y rastrojo sin descomposición (CA-8.10, CA-8.11)."""
    crops_before = 0
    for segment in timeline.segments:
        if isinstance(segment, CropSegment):
            crops_before += 1
            continue
        registry.add("FALLOW_EVAPORATION_LAYER")
        if segment.residue_cover_pct > 0:
            registry.add(
                "RESIDUE_NO_DECOMPOSITION",
                scope="fallow",
                scope_id=fallow_scope_id(rotation_id, crops_before),
                value=segment.residue_cover_pct,
                unit="%",
                day=segment.start,
            )


def _run_rotation(
    window: Window,
    rotation: ResolvedRotation,
    rain_mm: Sequence[float],
    et0_mm: Sequence[float],
    wind_max_ms: Sequence[float | None],
    resolved: ResolvedInput,
    registry: AssumptionRegistry,
) -> RunResult:
    timeline = build_timeline(window, rotation.spec)
    _register_fallow_assumptions(timeline, rotation.rotation_id, registry)
    balance = run_daily_balance(timeline, rain_mm, et0_mm, resolved.parcel.spec)
    yields = crop_yields(balance, rotation.spec)
    economics = rotation_economics(rotation.spec.crops, yields)
    exposure = soil_exposure(timeline, wind_max_ms)

    crop_segments = [segment for segment in timeline.segments if isinstance(segment, CropSegment)]
    balance_segments = [segment for segment in balance.segments if segment.is_crop]
    crops: list[CropRun] = []
    for position, (segment, crop_balance, yield_result, crop_economics) in enumerate(
        zip(crop_segments, balance_segments, yields, economics.crops, strict=True), start=1
    ):
        crops.append(
            CropRun(
                position=position,
                crop_code=segment.crop.crop_code,
                crop_type=segment.crop.crop_type,
                sowing_date=segment.start,
                cycle_end_date=segment.end,
                segment=crop_balance,
                yield_result=yield_result,
                economics=crop_economics,
            )
        )
        if yield_result.clipped_to_zero:
            registry.add(
                "YIELD_CLIPPED_TO_ZERO",
                scope="crop",
                scope_id=crop_scope_id(
                    rotation.rotation_id, position, f"yield@{window.start_year}"
                ),
            )
    return RunResult(
        rotation.rotation_id, window.start_year, balance, tuple(crops), economics, exposure
    )


# --- Consolidación (RF-12, D-15) ---


def _aggregate(
    resolved: ResolvedInput, scenarios: Sequence[ScenarioOutcome], runs: Sequence[RunResult]
) -> tuple[tuple[RotationRanges, ...], tuple[MarginDifference, ...]]:
    blocked_years = [s.start_year for s in scenarios if s.status == STATUS_BLOCKED]
    by_rotation: dict[str, list[ScenarioRun]] = defaultdict(list)
    for run in runs:
        by_rotation[run.rotation_id].append(
            ScenarioRun(
                rotation_id=run.rotation_id,
                start_year=run.start_year,
                crop_codes=tuple(crop.crop_code for crop in run.crops),
                yields=tuple(crop.yield_result for crop in run.crops),
                economics=run.economics,
                exposure=run.exposure,
            )
        )
    ranges = tuple(
        rotation_ranges(
            rotation.rotation_id, by_rotation.get(rotation.rotation_id, []), blocked_years
        )
        for rotation in resolved.rotations
    )
    comparisons = tuple(margin_differences(dict(by_rotation)))
    return ranges, comparisons
