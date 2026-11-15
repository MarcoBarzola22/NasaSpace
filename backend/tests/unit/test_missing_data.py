"""Pruebas de datos faltantes, sustituciones de FAO-56 y cobertura (T026, T027, T028).

Cubren CA-4.5 (cobertura), CA-6.1 (faltante = relleno o día ausente), CA-6.2 (sin interpolación),
CA-6.3 (bloqueo por lluvia o temperatura), CA-6.4–CA-6.6 (Hargreaves, Tmín − 2 °C, 2 m/s),
CA-6.7 (fechas por variable), CA-6.8 (las sustituciones no llegan al viento fuerte), CA-6.10
(Tmáx < Tmín) y CA-11.4 (WS2M_MAX faltante no se sustituye).
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.core.constants import DEFAULT_WIND_2M_MS, DEW_POINT_SEMIARID_OFFSET_C, HARGREAVES_KRS
from app.domain import missing_data as md
from app.domain.calendar import day_of_year
from app.domain.et0 import (
    clear_sky_radiation_mj_m2_day,
    extraterrestrial_radiation_mj_m2_day,
)
from app.domain.types import DailyClimate

LATITUDE = -33.68
ELEVATION = 700.0
START = date(2020, 1, 1)
COVERAGE = {variable: date(1981, 1, 1) for variable in md.ALL_VARIABLES}
COVERAGE[md.VAR_RADIATION] = date(1984, 1, 1)


def day(offset: int = 0, **overrides: float | None) -> DailyClimate:
    values: dict[str, float | None] = {
        "precipitation_mm": 2.0,
        "t_max_c": 28.0,
        "t_min_c": 14.0,
        "dew_point_c": 12.0,
        "wind_mean_ms": 2.5,
        "wind_max_ms": 5.0,
        "solar_radiation_mj_m2": 20.0,
    }
    values.update(overrides)
    return DailyClimate(day=START + timedelta(days=offset), **values)  # type: ignore[arg-type]


def series(n: int, **overrides_by_offset: dict[str, float | None]) -> list[DailyClimate]:
    return [day(offset, **overrides_by_offset.get(str(offset), {})) for offset in range(n)]


# --- T026: clasificación ---


def test_classify_complete_days_gives_empty_report() -> None:
    report = md.classify_missing(series(5))
    assert report.blocks == () and report.substitutions == ()
    assert not report.is_blocked


@pytest.mark.parametrize(
    ("field", "variable", "code"),
    [
        ("precipitation_mm", "PRECTOTCORR", md.BLOCK_MISSING_PRECIPITATION),
        ("t_max_c", "T2M_MAX", md.BLOCK_MISSING_T_MAX),
        ("t_min_c", "T2M_MIN", md.BLOCK_MISSING_T_MIN),
    ],
)
def test_classify_missing_rain_or_temperature_blocks_with_variable_and_dates(
    field: str, variable: str, code: str
) -> None:
    """CA-6.3: sin sustituto aceptable, el escenario se bloquea indicando variable y fechas."""
    days = series(10, **{"3": {field: None}, "7": {field: None}})
    report = md.classify_missing(days)
    assert report.is_blocked
    (block,) = report.blocks
    assert (block.code, block.variable) == (code, variable)
    assert block.dates == (START + timedelta(days=3), START + timedelta(days=7))
    assert (block.first_date, block.last_date) == (block.dates[0], block.dates[-1])
    assert report.substitutions == ()


def test_classify_t_max_below_t_min_blocks_as_inconsistent_source_data() -> None:
    """CA-6.10: «dato inconsistente de la fuente», con la fecha."""
    days = series(5, **{"2": {"t_max_c": 10.0, "t_min_c": 12.0}})
    report = md.classify_missing(days)
    (block,) = report.blocks
    assert block.code == md.BLOCK_INCONSISTENT_TEMPERATURE
    assert block.dates == (START + timedelta(days=2),)


def test_classify_equal_temperatures_are_consistent() -> None:
    assert not md.classify_missing(series(1, **{"0": {"t_max_c": 15.0, "t_min_c": 15.0}})).blocks


def test_classify_missing_temperature_is_not_reported_as_inconsistent() -> None:
    report = md.classify_missing(series(3, **{"1": {"t_max_c": None}}))
    assert [block.code for block in report.blocks] == [md.BLOCK_MISSING_T_MAX]


def test_classify_radiation_dew_point_and_wind_are_substitutions_without_block() -> None:
    days = series(
        6,
        **{
            "1": {"solar_radiation_mj_m2": None},
            "2": {"dew_point_c": None},
            "4": {"wind_mean_ms": None},
            "5": {"solar_radiation_mj_m2": None},
        },
    )
    report = md.classify_missing(days)
    assert not report.is_blocked
    by_variable = {item.variable: item for item in report.substitutions}
    assert by_variable["ALLSKY_SFC_SW_DWN"].method == md.SUBST_RADIATION
    assert by_variable["ALLSKY_SFC_SW_DWN"].dates == (
        START + timedelta(days=1),
        START + timedelta(days=5),
    )
    assert by_variable["T2MDEW"].method == md.SUBST_DEW_POINT
    assert by_variable["T2MDEW"].dates == (START + timedelta(days=2),)
    assert by_variable["WS2M"].method == md.SUBST_WIND
    assert by_variable["WS2M"].dates == (START + timedelta(days=4),)


def test_classify_missing_wind_max_is_neither_block_nor_substitution() -> None:
    """CA-11.4: solo afecta al proxy de viento, que lo cuenta como «sin dato»."""
    report = md.classify_missing(series(4, **{"2": {"wind_max_ms": None}}))
    assert report.blocks == () and report.substitutions == ()


def test_classify_absent_day_counts_as_missing() -> None:
    """CA-6.1: un día ausente de la serie se trata como faltante."""
    only_two = [day(0), day(2)]
    days = md.window_days(only_two, START, START + timedelta(days=2))
    codes = {block.code for block in md.classify_missing(days).blocks}
    assert md.BLOCK_MISSING_PRECIPITATION in codes
    assert days[1] == DailyClimate(day=START + timedelta(days=1))


# --- T027: sustituciones de FAO-56 ---


def expected_ra_rso(the_day: date) -> tuple[float, float]:
    ra = extraterrestrial_radiation_mj_m2_day(LATITUDE, day_of_year(the_day))
    return ra, clear_sky_radiation_mj_m2_day(ra, ELEVATION)


def test_substitution_radiation_uses_hargreaves_with_krs_016() -> None:
    """CA-6.4: Rs = min(0,16·√(Tmáx − Tmín)·Ra, Rso)."""
    the_day = day(0, solar_radiation_mj_m2=None)
    ra, rso = expected_ra_rso(the_day.day)
    result = md.apply_substitutions([the_day], LATITUDE, ELEVATION)
    expected = min(HARGREAVES_KRS * math.sqrt(28.0 - 14.0) * ra, rso)
    assert result.weather[0].solar_radiation_mj_m2 == pytest.approx(expected, abs=1e-9)
    assert result.weather[0].solar_radiation_mj_m2 < rso  # no está en el tope
    assert HARGREAVES_KRS == 0.16


def test_substitution_radiation_is_capped_by_clear_sky_radiation() -> None:
    wide = day(0, solar_radiation_mj_m2=None, t_max_c=40.0, t_min_c=0.0)
    _, rso = expected_ra_rso(wide.day)
    result = md.apply_substitutions([wide], LATITUDE, ELEVATION)
    assert result.weather[0].solar_radiation_mj_m2 == pytest.approx(rso, abs=1e-9)


def test_substitution_dew_point_is_t_min_minus_two() -> None:
    """CA-6.5: Tdew = Tmín − 2,0 °C (clima semiárido)."""
    result = md.apply_substitutions([day(0, dew_point_c=None, t_min_c=9.5)], LATITUDE, ELEVATION)
    assert result.weather[0].dew_point_c == pytest.approx(9.5 - DEW_POINT_SEMIARID_OFFSET_C)
    assert DEW_POINT_SEMIARID_OFFSET_C == 2.0


def test_substitution_wind_is_two_meters_per_second() -> None:
    """CA-6.6."""
    result = md.apply_substitutions([day(0, wind_mean_ms=None)], LATITUDE, ELEVATION)
    assert result.weather[0].wind_2m_ms == DEFAULT_WIND_2M_MS == 2.0


def test_substitution_records_variable_method_and_dates() -> None:
    """CA-6.7: variable, método y fecha de cada sustitución."""
    days = [day(0), day(1, solar_radiation_mj_m2=None, dew_point_c=None), day(2, wind_mean_ms=None)]
    result = md.apply_substitutions(days, LATITUDE, ELEVATION)
    recorded = {(item.variable, item.method, item.dates) for item in result.substitutions}
    assert recorded == {
        ("ALLSKY_SFC_SW_DWN", md.SUBST_RADIATION, (START + timedelta(days=1),)),
        ("T2MDEW", md.SUBST_DEW_POINT, (START + timedelta(days=1),)),
        ("WS2M", md.SUBST_WIND, (START + timedelta(days=2),)),
    }


def test_substitution_complete_days_are_passed_through_unchanged() -> None:
    the_day = day(0)
    ra, rso = expected_ra_rso(the_day.day)
    result = md.apply_substitutions([the_day], LATITUDE, ELEVATION)
    weather = result.weather[0]
    assert result.substitutions == ()
    assert (weather.solar_radiation_mj_m2, weather.dew_point_c, weather.wind_2m_ms) == (
        20.0,
        12.0,
        2.5,
    )
    assert weather.extraterrestrial_radiation_mj_m2 == pytest.approx(ra)
    assert weather.clear_sky_radiation_mj_m2 == pytest.approx(rso)


def test_no_interpolation_substituted_value_ignores_neighbouring_days() -> None:
    """CA-6.2: el valor sustituido no cambia si se modifican los días vecinos."""
    target = day(1, solar_radiation_mj_m2=None, dew_point_c=None, wind_mean_ms=None)
    calm = [day(0, wind_mean_ms=1.0), target, day(2, wind_mean_ms=1.0)]
    stormy = [
        day(0, solar_radiation_mj_m2=3.0, dew_point_c=-5.0, wind_mean_ms=9.0),
        target,
        day(2, solar_radiation_mj_m2=33.0, dew_point_c=25.0, wind_mean_ms=9.0),
    ]
    first = md.apply_substitutions(calm, LATITUDE, ELEVATION).weather[1]
    second = md.apply_substitutions(stormy, LATITUDE, ELEVATION).weather[1]
    assert first == second
    assert first.wind_2m_ms == 2.0 and first.dew_point_c == 12.0  # fórmula, no vecinos


def test_substitution_substituted_values_do_not_reach_the_wind_proxy_input() -> None:
    """CA-6.8: ``WS2M_MAX`` nunca se sustituye; ``Weather`` ni siquiera lo contiene."""
    result = md.apply_substitutions([day(0, wind_mean_ms=None, wind_max_ms=None)], LATITUDE, 700.0)
    assert not hasattr(result.weather[0], "wind_max_ms")
    assert result.substitutions[0].variable == "WS2M"


@pytest.mark.parametrize(
    "bad",
    [
        {"precipitation_mm": None},
        {"t_max_c": None},
        {"t_min_c": None},
        {"t_max_c": 5.0, "t_min_c": 8.0},
    ],
)
def test_substitution_rejects_days_that_should_have_been_blocked(bad: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        md.apply_substitutions([day(0, **bad)], LATITUDE, ELEVATION)


# --- T028: cobertura y datos no publicados ---


def trailing(n: int, missing_last: int, variable_field: str) -> list[DailyClimate]:
    return [
        day(offset, **({variable_field: None} if offset >= n - missing_last else {}))
        for offset in range(n)
    ]


def test_coverage_trailing_streak_of_radiation_blocks_windows_that_include_it() -> None:
    """Una racha final de ``None`` en la radiación es «aún no publicado»."""
    data = trailing(30, 4, "solar_radiation_mj_m2")
    blocks = md.check_coverage(data, START, START + timedelta(days=29), COVERAGE)
    (block,) = blocks
    assert block.code == md.BLOCK_UNPUBLISHED == "UNPUBLISHED_DATA_BLOCK"
    assert block.variable == "ALLSKY_SFC_SW_DWN"
    assert block.first_date == START + timedelta(days=26)
    assert block.last_date == START + timedelta(days=29)


def test_coverage_window_ending_before_the_streak_is_not_blocked() -> None:
    data = trailing(30, 4, "solar_radiation_mj_m2")
    assert md.check_coverage(data, START, START + timedelta(days=25), COVERAGE) == ()


def test_coverage_interior_missing_value_does_not_block() -> None:
    data = series(30, **{"10": {"solar_radiation_mj_m2": None}})
    assert md.check_coverage(data, START, START + timedelta(days=29), COVERAGE) == ()


def test_coverage_window_starting_before_a_variable_start_is_blocked() -> None:
    """CA-4.5: la radiación empieza el 1984-01-01; una ventana de 1983 queda bloqueada."""
    first = date(1983, 7, 1)
    data = [DailyClimate(day=first + timedelta(days=i)) for i in range(5)]
    blocks = md.check_coverage(data, first, first + timedelta(days=4), COVERAGE)
    radiation = [block for block in blocks if block.code == md.BLOCK_BEFORE_COVERAGE]
    assert [block.variable for block in radiation] == ["ALLSKY_SFC_SW_DWN"]
    assert radiation[0].last_date == first + timedelta(days=4)


def test_coverage_before_start_reports_only_the_uncovered_period() -> None:
    first = date(1983, 12, 30)
    data = [
        DailyClimate(day=first + timedelta(days=i), solar_radiation_mj_m2=1.0) for i in range(5)
    ]
    (block,) = [
        item
        for item in md.check_coverage(data, first, first + timedelta(days=4), COVERAGE)
        if item.code == md.BLOCK_BEFORE_COVERAGE
    ]
    assert (block.first_date, block.last_date) == (first, date(1983, 12, 31))


def test_coverage_fully_covered_window_is_not_blocked() -> None:
    data = series(30)
    assert md.check_coverage(data, START, START + timedelta(days=29), COVERAGE) == ()


def test_coverage_days_after_the_last_received_day_are_unpublished() -> None:
    data = series(10)
    blocks = md.check_coverage(data, START, START + timedelta(days=14), COVERAGE)
    assert {block.code for block in blocks} == {md.BLOCK_UNPUBLISHED}
    assert {block.variable for block in blocks} == set(md.ALL_VARIABLES)
    assert all(block.first_date == START + timedelta(days=10) for block in blocks)


def test_coverage_unpublished_streak_starts_by_variable() -> None:
    data = trailing(10, 3, "precipitation_mm")
    assert md.unpublished_streak_starts(data) == {"PRECTOTCORR": START + timedelta(days=7)}


# --- assess_window: reunión de las tres reglas ---


def test_assess_unpublished_streak_is_not_repeated_as_missing_or_substitution() -> None:
    data = trailing(30, 4, "solar_radiation_mj_m2")
    report = md.assess_window(data, START, START + timedelta(days=29), COVERAGE)
    assert [block.code for block in report.blocks] == [md.BLOCK_UNPUBLISHED]
    assert report.substitutions == ()  # los 4 días ya los explica el bloqueo


def test_assess_interior_radiation_hole_is_a_substitution_not_a_block() -> None:
    data = series(30, **{"10": {"solar_radiation_mj_m2": None}})
    report = md.assess_window(data, START, START + timedelta(days=29), COVERAGE)
    assert not report.is_blocked
    assert report.substitutions[0].dates == (START + timedelta(days=10),)


def test_assess_missing_rain_inside_the_series_blocks_with_its_date() -> None:
    data = series(30, **{"12": {"precipitation_mm": None}})
    report = md.assess_window(data, START, START + timedelta(days=29), COVERAGE)
    (block,) = report.blocks
    assert block.code == md.BLOCK_MISSING_PRECIPITATION
    assert block.dates == (START + timedelta(days=12),)


def test_assess_only_looks_at_the_days_of_the_window() -> None:
    data = series(30, **{"25": {"precipitation_mm": None}})
    report = md.assess_window(data, START, START + timedelta(days=9), COVERAGE)
    assert not report.is_blocked
