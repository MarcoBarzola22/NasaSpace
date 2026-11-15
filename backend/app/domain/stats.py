"""Rangos descriptivos entre escenarios y diferencias de margen entre rotaciones (RF-12; T025).

Recibe, por cada año de inicio simulado, los resultados del balance hídrico (a través del
rendimiento FAO-33 y la exposición al viento) y de la economía ya calculados por separado, y los
consolida por rotación en mínimo, mediana y máximo (CA-12.1).

Reglas:

- Los rangos son **descriptivos de los años elegidos**; no son probabilidades ni pronósticos
  (CA-12.5). Cada rango informa cuántos escenarios lo componen (``n``).
- La mediana es el valor central o, con n par, el promedio de los dos centrales (CA-12.2).
- Con un solo escenario se informa ese valor y la marca ``no_range`` («sin rango», CA-12.3).
- Los escenarios bloqueados no entran en los rangos y se listan aparte (CA-12.4).
- Un valor «no calculado» (``None``) nunca se reemplaza por 0. El rango de un cultivo se calcula
  con los escenarios donde el valor existe (y su ``n`` lo muestra). El margen bruto de la rotación
  solo se resume si está calculado en **todos** los escenarios; si no, no hay rango y se listan
  los años donde falta (CA-12.1).
- Las diferencias de margen entre rotaciones (B−A, C−A, C−B) son descriptivas: no ordenan ni
  recomiendan (CA-17.5).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.economics import STATUS_COMPUTED, RotationEconomics
from app.domain.wind_proxy import SoilExposure
from app.domain.yield_response import YieldResult


@dataclass(frozen=True, slots=True)
class Range:
    """Mínimo, mediana y máximo de ``n`` valores."""

    n: int
    minimum: float
    median: float
    maximum: float

    @property
    def no_range(self) -> bool:
        """Con un solo valor no hay rango que informar (CA-12.3)."""
        return self.n == 1


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    """Resultado de una rotación en un escenario calculado (un año de inicio)."""

    rotation_id: str
    start_year: int
    crop_codes: tuple[str, ...]
    yields: tuple[YieldResult, ...]
    economics: RotationEconomics
    exposure: SoilExposure


@dataclass(frozen=True, slots=True)
class CropRanges:
    position: int  # desde 1
    crop_code: str
    yield_t_ha: Range | None  # None: cultivo de cobertura o rendimiento no calculado
    eta_etm_ratio: Range | None


@dataclass(frozen=True, slots=True)
class RotationRanges:
    rotation_id: str
    n_scenarios: int
    scenarios_included: tuple[int, ...]
    scenarios_excluded: tuple[int, ...]
    crops: tuple[CropRanges, ...]
    gross_margin_per_ha: Range | None
    margin_not_computed_years: tuple[int, ...]
    strong_wind_days_without_live_crop: Range | None


@dataclass(frozen=True, slots=True)
class MarginDifference:
    """Margen bruto de ``minuend`` menos el de ``subtrahend`` en un escenario (descriptivo)."""

    start_year: int
    minuend_rotation_id: str
    subtrahend_rotation_id: str
    gross_margin_difference_per_ha: float


def describe(values: Sequence[float]) -> Range:
    """Mínimo, mediana y máximo de una lista no vacía de números finitos."""
    if not values:
        raise ValueError("No hay valores para resumir.")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Los valores a resumir deben ser números finitos.")
    return Range(
        n=len(values),
        minimum=float(min(values)),
        median=float(statistics.median(values)),
        maximum=float(max(values)),
    )


def _describe_or_none(values: Sequence[float]) -> Range | None:
    return describe(values) if values else None


def _validate_runs(rotation_id: str, runs: Sequence[ScenarioRun]) -> None:
    years = [run.start_year for run in runs]
    if len(set(years)) != len(years):
        raise ValueError(f"La rotación {rotation_id} tiene escenarios repetidos.")
    for run in runs:
        if run.rotation_id != rotation_id:
            raise ValueError(f"El resultado de {run.rotation_id} no pertenece a {rotation_id}.")
        if len(run.yields) != len(run.crop_codes):
            raise ValueError(f"Rendimientos y cultivos no coinciden en {rotation_id}.")
    if len({run.crop_codes for run in runs}) > 1:
        raise ValueError(f"Los escenarios de {rotation_id} no tienen los mismos cultivos.")


def rotation_ranges(
    rotation_id: str,
    runs: Sequence[ScenarioRun],
    excluded_start_years: Sequence[int] = (),
) -> RotationRanges:
    """Consolida los escenarios calculados de una rotación en rangos descriptivos."""
    _validate_runs(rotation_id, runs)
    ordered = sorted(runs, key=lambda run: run.start_year)
    excluded = tuple(sorted(excluded_start_years))
    if set(excluded) & {run.start_year for run in ordered}:
        raise ValueError("Un escenario no puede estar a la vez incluido y excluido.")

    crops: list[CropRanges] = []
    crop_codes = ordered[0].crop_codes if ordered else ()
    for index, crop_code in enumerate(crop_codes):
        results = [run.yields[index] for run in ordered]
        crops.append(
            CropRanges(
                position=index + 1,
                crop_code=crop_code,
                yield_t_ha=_describe_or_none(
                    [r.yield_t_ha for r in results if r.yield_t_ha is not None]
                ),
                eta_etm_ratio=_describe_or_none(
                    [r.eta_etm_ratio for r in results if r.eta_etm_ratio is not None]
                ),
            )
        )

    margins = {
        run.start_year: run.economics.gross_margin_per_ha
        for run in ordered
        if run.economics.status == STATUS_COMPUTED and run.economics.gross_margin_per_ha is not None
    }
    not_computed = tuple(run.start_year for run in ordered if run.start_year not in margins)
    margin_range = describe(list(margins.values())) if ordered and not not_computed else None

    return RotationRanges(
        rotation_id=rotation_id,
        n_scenarios=len(ordered),
        scenarios_included=tuple(run.start_year for run in ordered),
        scenarios_excluded=excluded,
        crops=tuple(crops),
        gross_margin_per_ha=margin_range,
        margin_not_computed_years=not_computed,
        strong_wind_days_without_live_crop=_describe_or_none(
            [run.exposure.strong_wind_days_without_live_crop for run in ordered]
        ),
    )


def margin_differences(
    runs_by_rotation: Mapping[str, Sequence[ScenarioRun]],
) -> list[MarginDifference]:
    """Diferencias de margen bruto entre pares de rotaciones, por escenario (D-15).

    Para las rotaciones ordenadas por identificador (A < B < C) se calcula la posterior menos la
    anterior: B−A, C−A y C−B. Un par se omite en un escenario si alguno de los dos márgenes no
    está calculado o si una de las rotaciones no tiene ese escenario.
    """
    margins: dict[str, dict[int, float]] = {}
    for rotation_id, runs in runs_by_rotation.items():
        _validate_runs(rotation_id, runs)
        margins[rotation_id] = {
            run.start_year: run.economics.gross_margin_per_ha
            for run in runs
            if run.economics.status == STATUS_COMPUTED
            and run.economics.gross_margin_per_ha is not None
        }
    ids = sorted(margins)
    years = sorted(
        {year for runs in runs_by_rotation.values() for year in (r.start_year for r in runs)}
    )
    differences: list[MarginDifference] = []
    for year in years:
        for later_index, later in enumerate(ids):
            for earlier in ids[:later_index]:
                if year in margins[later] and year in margins[earlier]:
                    differences.append(
                        MarginDifference(
                            start_year=year,
                            minuend_rotation_id=later,
                            subtrahend_rotation_id=earlier,
                            gross_margin_difference_per_ha=margins[later][year]
                            - margins[earlier][year],
                        )
                    )
    return differences
