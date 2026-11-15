"""Pruebas de los rangos descriptivos y las diferencias de margen (T025).

Criterios que verifica: CA-12.1 (mínimo, mediana y máximo por cultivo, margen y días de viento),
CA-12.2 (mediana con n par), CA-12.3 (un solo escenario), CA-12.4 (escenarios bloqueados excluidos
y listados), CA-10.4 (margen no calculado: nunca se reemplaza por 0) y CA-15.4 (diferencias de
margen entre rotaciones calculadas por el backend, sin ordenar ni recomendar).
"""

from __future__ import annotations

import pytest

from app.domain.economics import RotationEconomics
from app.domain.stats import (
    ScenarioRun,
    describe,
    margin_differences,
    rotation_ranges,
)
from app.domain.wind_proxy import SoilExposure
from app.domain.yield_response import YieldResult

CODES = ("maize", "rye_cover", "soybean_first")


def yield_result(yield_t_ha: float | None, ratio: float | None) -> YieldResult:
    relative = None if yield_t_ha is None else yield_t_ha / 9.0
    return YieldResult(500.0, 400.0, ratio, yield_t_ha, relative, False)


def economics(margin: float | None) -> RotationEconomics:
    if margin is None:
        return RotationEconomics("not_computed", None, None, None, None, (), ())
    return RotationEconomics("computed", margin + 1000, 1000.0, margin, None, (), ())


def exposure(strong_days: int) -> SoilExposure:
    return SoilExposure(730, 400, 330, strong_days, 0)


def run(
    year: int,
    maize: tuple[float | None, float | None] = (5.0, 0.7),
    rye_ratio: float | None = 0.8,
    soy: tuple[float | None, float | None] = (2.0, 0.6),
    margin: float | None = 300.0,
    strong_days: int = 5,
    rotation_id: str = "A",
    codes: tuple[str, ...] = CODES,
) -> ScenarioRun:
    return ScenarioRun(
        rotation_id=rotation_id,
        start_year=year,
        crop_codes=codes,
        yields=(
            yield_result(*maize),
            yield_result(None, rye_ratio),  # cultivo de cobertura: sin rendimiento
            yield_result(*soy),
        ),
        economics=economics(margin),
        exposure=exposure(strong_days),
    )


# --- describe: mínimo, mediana y máximo ---


def test_stats_describe_odd_values_in_any_order() -> None:
    result = describe([1, 5, 3])
    assert (result.n, result.minimum, result.median, result.maximum) == (3, 1.0, 3.0, 5.0)
    assert result.no_range is False


def test_stats_describe_even_count_uses_the_average_of_the_two_central_values() -> None:
    result = describe([5.08, 7.54])
    assert result.n == 2
    assert result.median == pytest.approx(6.31, abs=1e-12)
    assert (result.minimum, result.maximum) == (5.08, 7.54)
    assert describe([4, 9]).median == 6.5
    assert describe([1, 2, 3, 10]).median == 2.5


def test_stats_describe_single_value_is_flagged_as_no_range() -> None:
    result = describe([4.2])
    assert (result.n, result.minimum, result.median, result.maximum) == (1, 4.2, 4.2, 4.2)
    assert result.no_range is True


def test_stats_describe_handles_negative_and_repeated_values() -> None:
    result = describe([-95.0, -95.0, 120.5])
    assert (result.minimum, result.median, result.maximum) == (-95.0, -95.0, 120.5)


def test_stats_describe_rejects_empty_and_non_finite_input() -> None:
    with pytest.raises(ValueError, match="No hay valores"):
        describe([])
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finitos"):
            describe([1.0, bad])


# --- Rangos por rotación ---


def test_stats_rotation_ranges_for_three_scenarios() -> None:
    runs = [
        run(2008, maize=(5.08, 0.65), margin=321.5, strong_days=9),
        run(2011, maize=(7.54, 0.87), margin=610.1, strong_days=4),
        run(2014, maize=(6.00, 0.75), margin=-100.0, strong_days=6),
    ]
    ranges = rotation_ranges("A", runs)
    assert ranges.rotation_id == "A"
    assert ranges.n_scenarios == 3
    assert ranges.scenarios_included == (2008, 2011, 2014)
    assert ranges.scenarios_excluded == ()
    maize = ranges.crops[0]
    assert (maize.position, maize.crop_code) == (1, "maize")
    assert (maize.yield_t_ha.minimum, maize.yield_t_ha.median, maize.yield_t_ha.maximum) == (
        5.08,
        6.0,
        7.54,
    )
    assert (maize.eta_etm_ratio.minimum, maize.eta_etm_ratio.median) == (0.65, 0.75)
    margin = ranges.gross_margin_per_ha
    assert (margin.n, margin.minimum, margin.median, margin.maximum) == (3, -100.0, 321.5, 610.1)
    wind = ranges.strong_wind_days_without_live_crop
    assert (wind.minimum, wind.median, wind.maximum) == (4.0, 6.0, 9.0)
    assert ranges.margin_not_computed_years == ()


def test_stats_rotation_ranges_do_not_depend_on_the_input_order() -> None:
    runs = [run(2014, margin=1.0), run(2008, margin=3.0), run(2011, margin=2.0)]
    ranges = rotation_ranges("A", runs)
    assert ranges.scenarios_included == (2008, 2011, 2014)
    assert ranges.gross_margin_per_ha.median == 2.0


def test_stats_rotation_ranges_with_two_scenarios_use_the_average_median() -> None:
    ranges = rotation_ranges("A", [run(2008, margin=100.0), run(2011, margin=300.0)])
    assert ranges.n_scenarios == 2
    assert ranges.gross_margin_per_ha.median == 200.0


def test_stats_rotation_ranges_single_scenario_has_no_range() -> None:
    ranges = rotation_ranges("A", [run(2008, maize=(5.0, 0.7), margin=250.0, strong_days=7)])
    assert ranges.n_scenarios == 1
    assert ranges.gross_margin_per_ha.no_range is True
    assert ranges.gross_margin_per_ha.minimum == ranges.gross_margin_per_ha.maximum == 250.0
    assert ranges.crops[0].yield_t_ha.no_range is True
    assert ranges.strong_wind_days_without_live_crop.no_range is True


def test_stats_blocked_scenarios_are_excluded_and_listed() -> None:
    ranges = rotation_ranges(
        "A", [run(2008), run(2011, margin=500.0)], excluded_start_years=[2017, 2014]
    )
    assert ranges.n_scenarios == 2
    assert ranges.scenarios_included == (2008, 2011)
    assert ranges.scenarios_excluded == (2014, 2017)


def test_stats_a_scenario_cannot_be_included_and_excluded() -> None:
    with pytest.raises(ValueError, match="incluido y excluido"):
        rotation_ranges("A", [run(2008)], excluded_start_years=[2008])


def test_stats_without_calculated_scenarios_everything_is_empty() -> None:
    ranges = rotation_ranges("A", [], excluded_start_years=[2008, 2011])
    assert ranges.n_scenarios == 0
    assert ranges.crops == ()
    assert ranges.gross_margin_per_ha is None
    assert ranges.strong_wind_days_without_live_crop is None
    assert ranges.scenarios_excluded == (2008, 2011)


# --- Valores «no calculados» ---


def test_stats_margin_range_is_none_if_any_scenario_has_no_margin() -> None:
    runs = [run(2008, margin=100.0), run(2011, margin=None), run(2014, margin=300.0)]
    ranges = rotation_ranges("A", runs)
    assert ranges.gross_margin_per_ha is None
    assert ranges.margin_not_computed_years == (2011,)
    # El resto de los rangos se calcula con normalidad: el margen faltante no los contamina.
    assert ranges.crops[0].yield_t_ha.n == 3
    assert ranges.strong_wind_days_without_live_crop.n == 3


def test_stats_margin_is_never_treated_as_zero() -> None:
    runs = [run(2008, margin=100.0), run(2011, margin=None)]
    ranges = rotation_ranges("A", runs)
    assert ranges.gross_margin_per_ha is None  # con un 0 inventado habría salido mediana 50
    assert ranges.margin_not_computed_years == (2011,)


def test_stats_all_margins_missing_lists_every_year() -> None:
    ranges = rotation_ranges("A", [run(2008, margin=None), run(2011, margin=None)])
    assert ranges.gross_margin_per_ha is None
    assert ranges.margin_not_computed_years == (2008, 2011)


def test_stats_yield_range_uses_only_the_scenarios_where_it_was_computed() -> None:
    runs = [
        run(2008, maize=(5.0, 0.7)),
        run(2011, maize=(None, None)),  # ETm = 0: sin rendimiento ni cociente
        run(2014, maize=(7.0, 0.9)),
    ]
    maize = rotation_ranges("A", runs).crops[0]
    assert maize.yield_t_ha.n == 2
    assert (maize.yield_t_ha.minimum, maize.yield_t_ha.median, maize.yield_t_ha.maximum) == (
        5.0,
        6.0,
        7.0,
    )
    assert maize.eta_etm_ratio.n == 2


def test_stats_cover_crop_has_water_ranges_but_no_yield_range() -> None:
    runs = [run(2008, rye_ratio=0.76), run(2011, rye_ratio=0.9)]
    rye = rotation_ranges("A", runs).crops[1]
    assert rye.crop_code == "rye_cover"
    assert rye.yield_t_ha is None
    assert rye.eta_etm_ratio.median == pytest.approx(0.83)


def test_stats_a_crop_with_no_value_in_any_scenario_has_no_range() -> None:
    runs = [run(2008, soy=(None, None)), run(2011, soy=(None, None))]
    soy = rotation_ranges("A", runs).crops[2]
    assert soy.yield_t_ha is None and soy.eta_etm_ratio is None


def test_stats_wind_days_are_described_like_any_other_range() -> None:
    wind = rotation_ranges("A", [run(2008, strong_days=0), run(2011, strong_days=0)])
    assert wind.strong_wind_days_without_live_crop.maximum == 0.0


# --- Entradas inconsistentes ---


def test_stats_rejects_repeated_scenarios_and_mixed_rotations() -> None:
    with pytest.raises(ValueError, match="repetidos"):
        rotation_ranges("A", [run(2008), run(2008)])
    with pytest.raises(ValueError, match="no pertenece"):
        rotation_ranges("A", [run(2008), run(2011, rotation_id="B")])


def test_stats_rejects_scenarios_with_different_crops() -> None:
    other = run(2011, codes=("maize", "rye_cover", "wheat"))
    with pytest.raises(ValueError, match="mismos cultivos"):
        rotation_ranges("A", [run(2008), other])


# --- Diferencias de margen entre rotaciones ---


def test_stats_margin_differences_for_three_rotations() -> None:
    runs = {
        "A": [run(2008, margin=100.0, rotation_id="A")],
        "B": [run(2008, margin=250.0, rotation_id="B")],
        "C": [run(2008, margin=40.0, rotation_id="C")],
    }
    differences = margin_differences(runs)
    assert [(d.minuend_rotation_id, d.subtrahend_rotation_id) for d in differences] == [
        ("B", "A"),
        ("C", "A"),
        ("C", "B"),
    ]
    assert [d.gross_margin_difference_per_ha for d in differences] == [150.0, -60.0, -210.0]
    assert all(d.start_year == 2008 for d in differences)


def test_stats_margin_differences_skip_pairs_with_a_missing_margin() -> None:
    runs = {
        "A": [run(2008, margin=100.0, rotation_id="A")],
        "B": [run(2008, margin=None, rotation_id="B")],
        "C": [run(2008, margin=40.0, rotation_id="C")],
    }
    differences = margin_differences(runs)
    assert [(d.minuend_rotation_id, d.subtrahend_rotation_id) for d in differences] == [("C", "A")]
    assert differences[0].gross_margin_difference_per_ha == -60.0


def test_stats_margin_differences_are_computed_per_scenario() -> None:
    runs = {
        "A": [run(2008, margin=100.0, rotation_id="A"), run(2011, margin=10.0, rotation_id="A")],
        "B": [run(2008, margin=150.0, rotation_id="B"), run(2011, margin=None, rotation_id="B")],
    }
    differences = margin_differences(runs)
    assert [(d.start_year, d.gross_margin_difference_per_ha) for d in differences] == [(2008, 50.0)]


def test_stats_margin_differences_need_the_scenario_in_both_rotations() -> None:
    runs = {
        "A": [run(2008, margin=1.0, rotation_id="A"), run(2011, margin=2.0, rotation_id="A")],
        "B": [run(2011, margin=5.0, rotation_id="B")],
    }
    assert [(d.start_year, d.gross_margin_difference_per_ha) for d in margin_differences(runs)] == [
        (2011, 3.0)
    ]


def test_stats_margin_differences_with_one_rotation_or_none_are_empty() -> None:
    assert margin_differences({}) == []
    assert margin_differences({"A": [run(2008, rotation_id="A")]}) == []


def test_stats_margin_differences_are_ordered_by_year_then_pair() -> None:
    runs = {
        rotation_id: [
            run(year, margin=float(index * 10 + year), rotation_id=rotation_id)
            for year in (2011, 2008)
        ]
        for index, rotation_id in enumerate("ABC")
    }
    keys = [
        (d.start_year, d.minuend_rotation_id, d.subtrahend_rotation_id)
        for d in margin_differences(runs)
    ]
    assert keys == [
        (2008, "B", "A"),
        (2008, "C", "A"),
        (2008, "C", "B"),
        (2011, "B", "A"),
        (2011, "C", "A"),
        (2011, "C", "B"),
    ]


def test_stats_margin_differences_never_rank_or_label_a_best_rotation() -> None:
    runs = {
        "A": [run(2008, margin=100.0, rotation_id="A")],
        "B": [run(2008, margin=900.0, rotation_id="B")],
    }
    (difference,) = margin_differences(runs)
    assert set(difference.__slots__) == {
        "start_year",
        "minuend_rotation_id",
        "subtrahend_rotation_id",
        "gross_margin_difference_per_ha",
    }
