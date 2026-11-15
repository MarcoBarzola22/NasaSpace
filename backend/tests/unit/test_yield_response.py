"""Pruebas del rendimiento bajo déficit, FAO-33 (T022).

Criterios que verifica: CA-9.1 (ETm y ETa del ciclo salen del balance), CA-9.2 (fórmula FAO-33),
CA-9.3 (Ya negativo pasa a 0), CA-9.4 (0 ≤ Ya ≤ Ym), CA-9.5 (ETm = 0), CA-9.6 (resultados por
cultivo) y CA-9.7 (cultivo de cobertura sin rendimiento).
"""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.core.exceptions import CalculationIntegrityError
from app.domain import calendar as cal
from app.domain.types import CropSegment, ParcelSpec, RotationSpec, Timeline
from app.domain.water_balance import run_daily_balance
from app.domain.yield_response import (
    NOTE_COVER_CROP,
    crop_yield,
    crop_yield_from_balance,
    crop_yields,
    relative_yield_fao33,
)
from tests.builders.rotations import invariant_rotations, make_crop
from tests.builders.weather import synthetic_weather

MAIZE = replace(make_crop("maize", 1, 15, 10, (30, 40, 50, 30)), ky=1.25, ym_t_ha=9.0)
RYE = make_crop("rye_cover", 1, 1, 4, (20, 40, 40, 20), crop_type="cover")
PARCEL = ParcelSpec(-33.68, -65.47, 0.28, 0.12, 1.2, 50.0)


def grain(ky: float, ym: float) -> object:
    return replace(MAIZE, ky=ky, ym_t_ha=ym)


# --- Fórmula FAO-33 ---


def test_yield_plan_example_maize() -> None:
    result = crop_yield(MAIZE, etm_mm=642.5, eta_mm=418.9)
    assert result.yield_t_ha == pytest.approx(5.0848, abs=1e-4)
    assert result.relative_yield == pytest.approx(5.0848 / 9.0, abs=1e-5)
    assert result.eta_etm_ratio == pytest.approx(418.9 / 642.5)
    assert result.clipped_to_zero is False
    assert result.reason is None and result.note is None


def test_yield_satisfies_the_fao33_relation() -> None:
    """1 − Ya/Ym = Ky × (1 − ETa/ETm)."""
    result = crop_yield(MAIZE, etm_mm=642.5, eta_mm=418.9)
    assert 1 - result.yield_t_ha / 9.0 == pytest.approx(1.25 * (1 - 418.9 / 642.5), abs=1e-12)


def test_yield_without_deficit_equals_ym() -> None:
    result = crop_yield(MAIZE, etm_mm=600.0, eta_mm=600.0)
    assert result.yield_t_ha == 9.0
    assert result.relative_yield == 1.0


def test_yield_reduces_proportionally_with_water_stress_when_ky_is_one() -> None:
    crop = grain(ky=1.0, ym=10.0)
    for ratio in (1.0, 0.9, 0.75, 0.5, 0.25, 0.0):
        result = crop_yield(crop, etm_mm=500.0, eta_mm=500.0 * ratio)
        assert result.yield_t_ha == pytest.approx(10.0 * ratio, abs=1e-9), ratio


def test_yield_loss_scales_with_ky_at_the_same_stress() -> None:
    ratio = 0.8  # déficit del 20 %
    for ky in (0.0, 0.5, 0.85, 1.0, 1.25, 2.0):
        result = crop_yield(grain(ky, 8.0), etm_mm=500.0, eta_mm=500.0 * ratio)
        assert result.yield_t_ha == pytest.approx(8.0 * (1 - ky * 0.2), abs=1e-9), ky
    assert crop_yield(grain(0.0, 8.0), 500.0, 100.0).yield_t_ha == 8.0  # Ky 0: insensible


def test_yield_decreases_monotonically_as_stress_grows() -> None:
    crop = grain(ky=1.25, ym=9.0)
    yields = [crop_yield(crop, 600.0, 600.0 * r / 20).yield_t_ha for r in range(20, -1, -1)]
    assert yields == sorted(yields, reverse=True)
    assert yields[0] == 9.0


def test_yield_negative_formula_is_clipped_to_zero_and_flagged() -> None:
    result = crop_yield(grain(ky=1.5, ym=9.0), etm_mm=500.0, eta_mm=100.0)  # ETa/ETm = 0,2
    assert result.yield_t_ha == 0.0
    assert result.relative_yield == 0.0
    assert result.clipped_to_zero is True


def test_yield_exactly_zero_formula_is_not_a_clip() -> None:
    result = crop_yield(grain(ky=2.0, ym=9.0), etm_mm=500.0, eta_mm=250.0)  # 1 − 2·0,5 = 0
    assert result.yield_t_ha == 0.0
    assert result.clipped_to_zero is False


def test_yield_relative_function_edges() -> None:
    assert relative_yield_fao33(1.25, 1.0) == (1.0, False)
    assert relative_yield_fao33(1.5, 0.2) == (0.0, True)
    assert relative_yield_fao33(0.85, 0.0) == pytest.approx((0.15, False))


# --- Casos límite ---


def test_yield_etm_zero_gives_no_yield_with_a_reason() -> None:
    result = crop_yield(MAIZE, etm_mm=0.0, eta_mm=0.0)
    assert result.yield_t_ha is None
    assert result.eta_etm_ratio is None
    assert result.reason == "etm_zero"
    assert "ETm = 0" in (result.note or "")


def test_yield_cover_crop_has_no_yield_but_reports_the_water_use() -> None:
    result = crop_yield(RYE, etm_mm=160.2, eta_mm=121.7)
    assert result.yield_t_ha is None and result.relative_yield is None
    assert result.note == NOTE_COVER_CROP == "No aplica (cultivo de cobertura)."
    assert result.reason == "cover_crop"
    assert result.etm_mm == 160.2 and result.eta_mm == 121.7
    assert result.eta_etm_ratio == pytest.approx(121.7 / 160.2)


def test_yield_cover_crop_with_zero_etm_does_not_divide_by_zero() -> None:
    result = crop_yield(RYE, etm_mm=0.0, eta_mm=0.0)
    assert result.yield_t_ha is None and result.eta_etm_ratio is None
    assert result.reason == "cover_crop"


def test_yield_grain_crop_requires_ym_and_ky() -> None:
    with pytest.raises(ValueError, match="Ym"):
        crop_yield(replace(MAIZE, ym_t_ha=None), 500.0, 400.0)
    with pytest.raises(ValueError, match="Ym"):
        crop_yield(replace(MAIZE, ym_t_ha=0.0), 500.0, 400.0)
    with pytest.raises(ValueError, match="Ky"):
        crop_yield(replace(MAIZE, ky=None), 500.0, 400.0)


def test_yield_rejects_negative_inputs_and_eta_above_etm() -> None:
    with pytest.raises(ValueError, match="negativas"):
        crop_yield(MAIZE, -1.0, 0.0)
    with pytest.raises(ValueError, match="Ky"):
        relative_yield_fao33(-0.1, 0.5)
    with pytest.raises(ValueError, match="ETa/ETm"):
        relative_yield_fao33(1.0, 1.2)
    with pytest.raises(CalculationIntegrityError):
        crop_yield(MAIZE, etm_mm=500.0, eta_mm=520.0)


def test_yield_tolerates_float_noise_when_eta_equals_etm() -> None:
    result = crop_yield(MAIZE, etm_mm=500.0, eta_mm=500.0 * (1 + 1e-12))
    assert result.eta_etm_ratio == 1.0
    assert result.yield_t_ha == 9.0


YM_VALUES = [0.5, 3.2, 9.0, 30.0]
KY_VALUES = [0.0, 0.5, 0.85, 1.05, 1.25, 2.0]
RATIOS = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
COMBINATIONS = list(itertools.product(YM_VALUES, KY_VALUES, RATIOS))


def test_yield_bounds_cases_are_at_least_100() -> None:
    assert len(COMBINATIONS) >= 100


@pytest.mark.parametrize(("ym", "ky", "ratio"), COMBINATIONS)
def test_yield_stays_between_zero_and_ym(ym: float, ky: float, ratio: float) -> None:
    result = crop_yield(grain(ky, ym), etm_mm=480.0, eta_mm=480.0 * ratio)
    assert result.yield_t_ha is not None
    assert 0.0 <= result.yield_t_ha <= ym
    assert result.relative_yield == pytest.approx(result.yield_t_ha / ym, abs=1e-12)
    assert result.clipped_to_zero == (1.0 - ky * (1.0 - ratio) < 0.0)


# --- Integración con el balance hídrico ---


def run_rotation(key: str, seed: int, pct: float = 40.0):
    timeline = cal.build_timeline(cal.build_window(2008, 1, 7), invariant_rotations()[key])
    rain, et0 = synthetic_weather(seed, timeline.n_days)
    run = run_daily_balance(
        timeline, rain, et0, replace(PARCEL, initial_available_water_pct=pct), record_days=True
    )
    return timeline, run


def test_yield_etm_and_eta_are_the_sums_over_the_whole_cycle() -> None:
    """ETm = ΣETc y ETa = ΣETa de cada día del ciclo, tal como los registra el balance."""
    _, run = run_rotation("zero_day_fallow", seed=9)
    crop_indexes = [i for i, s in enumerate(run.segments) if s.is_crop]
    assert len(crop_indexes) == 3
    for index in crop_indexes:
        days = [d for d in run.daily if d.segment_index == index]
        segment = run.segments[index]
        assert len(days) == (segment.end - segment.start).days + 1
        assert segment.demand_mm == pytest.approx(sum(d.demand_mm for d in days), abs=1e-9)
        assert segment.actual_mm == pytest.approx(sum(d.actual_mm for d in days), abs=1e-9)


def test_yield_from_the_balance_run_matches_the_formula_by_hand() -> None:
    timeline, run = run_rotation("zero_day_fallow", seed=9)
    rotation = invariant_rotations()["zero_day_fallow"]
    results = crop_yields(run, rotation)
    assert len(results) == 3
    for crop, result, index in zip(
        rotation.crops, results, [i for i, s in enumerate(run.segments) if s.is_crop], strict=True
    ):
        days = [d for d in run.daily if d.segment_index == index]
        etm = sum(d.demand_mm for d in days)
        eta = sum(d.actual_mm for d in days)
        expected = max(0.0, crop.ym_t_ha * (1 - crop.ky * (1 - eta / etm)))
        assert result.etm_mm == pytest.approx(etm, abs=1e-9)
        assert result.eta_mm == pytest.approx(eta, abs=1e-9)
        assert result.yield_t_ha == pytest.approx(expected, abs=1e-9)
        assert 0.0 <= result.yield_t_ha <= crop.ym_t_ha
        assert result.eta_mm <= result.etm_mm + 1e-9


def test_yield_dry_scenario_gives_less_than_a_wet_scenario() -> None:
    crop = make_crop("maize", 1, 1, 7, (30, 40, 50, 30))
    crop = replace(crop, ky=1.25, ym_t_ha=9.0)
    timeline = Timeline((CropSegment(crop, date(2008, 7, 1), date(2008, 7, 1) + timedelta(149)),))
    results = []
    for rain_per_day in (0.0, 2.0, 8.0):
        run = run_daily_balance(
            timeline,
            [rain_per_day] * 150,
            [5.0] * 150,
            replace(PARCEL, initial_available_water_pct=20.0),
        )
        results.append(crop_yield_from_balance(crop, run.segments[0]).yield_t_ha)
    assert results[0] < results[1] < results[2] <= 9.0


def test_yield_cover_crop_rotation_reports_water_use_without_yield() -> None:
    _, run = run_rotation("cover_only", seed=4)
    rotation = invariant_rotations()["cover_only"]
    (result,) = crop_yields(run, rotation)
    assert result.yield_t_ha is None
    assert result.note == NOTE_COVER_CROP
    assert result.etm_mm > 0 and result.eta_mm <= result.etm_mm + 1e-9
    assert result.eta_etm_ratio is not None


def test_yield_pairing_rejects_mismatched_segments() -> None:
    _, run = run_rotation("long_fallow", seed=1)
    other = RotationSpec("A", invariant_rotations()["zero_day_fallow"].crops)
    with pytest.raises(ValueError, match="cultivos"):
        crop_yields(run, other)
    wheat_rotation = RotationSpec("A", (make_crop("wheat", 1, 15, 10, (30, 40, 50, 30)),))
    with pytest.raises(ValueError, match="no corresponde"):
        crop_yields(run, wheat_rotation)
    fallow_segment = next(s for s in run.segments if not s.is_crop)
    with pytest.raises(ValueError, match="no corresponde"):
        crop_yield_from_balance(MAIZE, fallow_segment)
