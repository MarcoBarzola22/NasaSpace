"""Pruebas del calendario (T013, T014).

Criterios que verifica: CA-3.5 (fin de ciclo), CA-3.6 (solapamiento), CA-3.7 (ciclo fuera de
la ventana), CA-3.8 y CA-4.3 (29 de febrero), CA-3.11 (barbecho), CA-4.2 (ventana de 730 o 731
días), CA-8.2 (cronología continua) y los casos límite CL-3, CL-4, CL-5 y CL-17.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core.exceptions import CalculationIntegrityError
from app.domain import calendar as cal
from app.domain.types import CropSpec, RotationSpec, SowingSpec, Stages


def crop(
    code: str,
    window_year: int,
    day: int,
    month: int,
    stages: tuple[int, int, int, int],
    residue_after_pct: float = 0.0,
) -> CropSpec:
    return CropSpec(
        crop_code=code,
        crop_type="grain",
        sowing=SowingSpec(window_year, day, month),
        stages=Stages(*stages),
        kc_initial=0.3,
        kc_mid=1.2,
        kc_end=0.35,
        root_depth_initial_m=0.25,
        root_depth_max_m=1.2,
        depletion_fraction_p=0.55,
        ky=1.0,
        ym_t_ha=5.0,
        residue_cover_after_pct=residue_after_pct,
    )


# Rotación B del plan §5.2: maíz → trigo → soja de segunda (ventana desde el 1 de julio).
MAIZE = crop("maize", 1, 15, 10, (30, 40, 50, 30), residue_after_pct=60.0)
WHEAT = crop("wheat", 1, 1, 6, (25, 55, 70, 35))
SOY_SECOND = crop("soybean_second", 2, 3, 12, (15, 25, 50, 20))
ROTATION_B = RotationSpec("B", (MAIZE, WHEAT, SOY_SECOND))


# --- T013: fechas, ventanas, siembra y fin de ciclo ---


def test_calendar_leap_years() -> None:
    assert [cal.is_leap_year(y) for y in (2000, 1900, 2008, 2010, 2012, 2100)] == [
        True,
        False,
        True,
        False,
        True,
        False,
    ]


def test_calendar_days_in_month_and_valid_dates() -> None:
    assert cal.days_in_month(2008, 2) == 29
    assert cal.days_in_month(2009, 2) == 28
    assert cal.days_in_month(2009, 4) == 30
    assert cal.is_valid_date(2008, 2, 29)
    assert not cal.is_valid_date(2009, 2, 29)
    assert not cal.is_valid_date(2009, 13, 1)
    assert not cal.is_valid_date(2009, 4, 31)
    with pytest.raises(ValueError, match="mes"):
        cal.days_in_month(2009, 0)


def test_calendar_day_of_year() -> None:
    assert cal.day_of_year(date(2009, 1, 1)) == 1
    assert cal.day_of_year(date(2009, 12, 31)) == 365
    assert cal.day_of_year(date(2008, 12, 31)) == 366
    assert cal.day_of_year(date(2009, 9, 3)) == 246  # ejemplo 8 de FAO-56
    assert cal.day_of_year(date(1998, 7, 6)) == 187  # ejemplo 18 de FAO-56


def test_calendar_feb_29_is_detected_and_rejected() -> None:
    assert cal.is_feb_29(29, 2)
    assert not cal.is_feb_29(28, 2)
    assert not cal.is_feb_29(29, 3)
    with pytest.raises(ValueError, match="29 de febrero"):
        cal.validate_recurring_day_month(29, 2)


@pytest.mark.parametrize(("day", "month"), [(0, 5), (32, 1), (31, 4), (30, 2), (1, 0), (1, 13)])
def test_calendar_recurring_date_range_validation(day: int, month: int) -> None:
    with pytest.raises(ValueError):
        cal.validate_recurring_day_month(day, month)


def test_calendar_recurring_date_accepts_every_regular_day() -> None:
    for month in range(1, 13):
        for day in range(1, cal.days_in_month(2001, month) + 1):
            cal.validate_recurring_day_month(day, month)


def test_window_lengths_for_regular_and_leap_spans() -> None:
    w2008 = cal.build_window(2008, 1, 7)
    assert (w2008.first_day, w2008.last_day) == (date(2008, 7, 1), date(2010, 6, 30))
    assert w2008.n_days == 730
    w2011 = cal.build_window(2011, 1, 7)
    assert (w2011.first_day, w2011.last_day) == (date(2011, 7, 1), date(2013, 6, 30))
    assert w2011.n_days == 731  # incluye el 29 de febrero de 2012 (CL-3)
    assert cal.build_window(2009, 1, 3).n_days == 730
    assert cal.build_window(2011, 1, 3).n_days == 731


def test_window_rejects_feb_29_start() -> None:
    with pytest.raises(ValueError, match="29 de febrero"):
        cal.build_window(2008, 29, 2)


def test_sowing_dates_follow_the_window_year() -> None:
    window = cal.build_window(2008, 1, 7)
    assert cal.sowing_date(window, SowingSpec(1, 1, 4)) == date(2009, 4, 1)
    assert cal.sowing_date(window, SowingSpec(2, 15, 11)) == date(2009, 11, 15)
    assert cal.sowing_date(window, SowingSpec(1, 15, 10)) == date(2008, 10, 15)
    assert cal.sowing_date(window, SowingSpec(1, 1, 7)) == date(2008, 7, 1)
    assert cal.sowing_date(window, SowingSpec(2, 15, 6)) == date(2010, 6, 15)


def test_sowing_date_always_falls_inside_the_window() -> None:
    window = cal.build_window(2008, 1, 7)
    for window_year in (1, 2):
        for month in range(1, 13):
            for day in range(1, cal.days_in_month(2001, month) + 1):
                sown = cal.sowing_date(window, SowingSpec(window_year, day, month))
                assert window.first_day <= sown <= window.last_day, (window_year, day, month)


def test_sowing_date_rejects_invalid_inputs() -> None:
    window = cal.build_window(2008, 1, 7)
    with pytest.raises(ValueError, match="1 o 2"):
        cal.sowing_date(window, SowingSpec(3, 1, 4))
    with pytest.raises(ValueError, match="29 de febrero"):
        cal.sowing_date(window, SowingSpec(1, 29, 2))


def test_cycle_end_counts_the_sowing_as_day_one() -> None:
    assert cal.cycle_end(date(2008, 10, 15), Stages(30, 40, 50, 30)) == date(2009, 3, 13)
    assert cal.cycle_end(date(2008, 10, 15), Stages(1, 1, 1, 1)) == date(2008, 10, 18)
    # Un ciclo que cruza un 29 de febrero termina un día antes en el calendario (CL-4).
    assert cal.cycle_end(date(2011, 10, 15), Stages(30, 40, 50, 30)) == date(2012, 3, 12)


def test_cycle_end_rejects_empty_cycles() -> None:
    with pytest.raises(ValueError, match="duración"):
        cal.cycle_end(date(2008, 10, 15), Stages(0, 0, 0, 0))


# --- T014: línea de tiempo y problemas de calendario ---


def assert_continuous(timeline_days: list[tuple[date, date]], first: date, last: date) -> None:
    assert timeline_days[0][0] == first
    assert timeline_days[-1][1] == last
    for (_, previous_end), (next_start, _) in zip(timeline_days, timeline_days[1:], strict=False):
        assert next_start == previous_end + timedelta(days=1)


def test_timeline_covers_every_day_once() -> None:
    for start_year in (2008, 2011):
        window = cal.build_window(start_year, 1, 7)
        timeline = cal.build_timeline(window, ROTATION_B)
        assert timeline.n_days == window.n_days
        assert_continuous(
            [(s.start, s.end) for s in timeline.segments], window.first_day, window.last_day
        )
        assert sum(s.n_days for s in timeline.segments) == window.n_days


def test_timeline_plan_example_rotation_b_2008() -> None:
    timeline = cal.build_timeline(cal.build_window(2008, 1, 7), ROTATION_B)
    layout = [(s.is_crop, s.start, s.end) for s in timeline.segments]
    assert layout == [
        (False, date(2008, 7, 1), date(2008, 10, 14)),
        (True, date(2008, 10, 15), date(2009, 3, 13)),
        (False, date(2009, 3, 14), date(2009, 5, 31)),
        (True, date(2009, 6, 1), date(2009, 12, 2)),
        (True, date(2009, 12, 3), date(2010, 3, 22)),
        (False, date(2010, 3, 23), date(2010, 6, 30)),
    ]


def test_timeline_has_no_fallow_between_wheat_and_second_soy() -> None:
    """CL-17: trigo hasta el 2009-12-02 y soja de segunda sembrada el 2009-12-03."""
    timeline = cal.build_timeline(cal.build_window(2008, 1, 7), ROTATION_B)
    segments = list(timeline.segments)
    wheat_index = next(
        i for i, s in enumerate(segments) if s.is_crop and s.end == date(2009, 12, 2)
    )
    assert segments[wheat_index + 1].is_crop
    assert segments[wheat_index + 1].start == date(2009, 12, 3)


def test_timeline_residue_cover_follows_the_previous_crop() -> None:
    rotation = RotationSpec("A", ROTATION_B.crops, initial_residue_cover_pct=30.0)
    timeline = cal.build_timeline(cal.build_window(2008, 1, 7), rotation)
    fallows = [s for s in timeline.segments if not s.is_crop]
    assert [f.residue_cover_pct for f in fallows] == [30.0, 60.0, 0.0]


def test_timeline_without_crops_is_a_single_fallow() -> None:
    window = cal.build_window(2008, 1, 7)
    timeline = cal.build_timeline(window, RotationSpec("A", (), initial_residue_cover_pct=20.0))
    assert len(timeline.segments) == 1
    assert timeline.segments[0].residue_cover_pct == 20.0
    assert timeline.n_days == 730


def test_timeline_rejects_an_invalid_rotation() -> None:
    overlapping = RotationSpec("A", (MAIZE, crop("wheat", 1, 13, 3, (10, 10, 10, 10))))
    with pytest.raises(ValueError, match="solapa"):
        cal.build_timeline(cal.build_window(2008, 1, 7), overlapping)


def test_calendar_issues_overlap_only_in_scenarios_without_feb_29() -> None:
    """CL-4: el maíz termina el 13-mar solo si no cruza un 29 de febrero."""
    rotation = RotationSpec(
        "A", (crop("maize", 1, 15, 10, (30, 40, 50, 30)), crop("wheat", 1, 13, 3, (10, 10, 10, 10)))
    )
    issues = cal.calendar_issues(rotation, [2008, 2009, 2010, 2011, 2012], 1, 7)
    assert [(i.kind, i.start_year, i.crop_position, i.other_position) for i in issues] == [
        ("overlap", 2008, 2, 1),
        ("overlap", 2009, 2, 1),
        ("overlap", 2010, 2, 1),
        ("overlap", 2012, 2, 1),
    ]
    assert all(i.rotation_id == "A" for i in issues)


def test_calendar_issues_outside_window_only_in_one_scenario() -> None:
    """CL-5: un ciclo de 366 días sembrado el 1-jul del año 2 solo cabe si hay 29 de febrero."""
    rotation = RotationSpec("A", (crop("long", 2, 1, 7, (100, 100, 100, 66)),))
    issues = cal.calendar_issues(rotation, [2008, 2010], 1, 7)
    assert [(i.kind, i.start_year, i.crop_position) for i in issues] == [
        ("outside_window", 2008, 1)
    ]


def test_calendar_issues_none_for_the_plan_rotation() -> None:
    assert cal.calendar_issues(ROTATION_B, [2008, 2011, 2017], 1, 7) == []


def test_calendar_issues_report_every_problem_of_a_scenario() -> None:
    rotation = RotationSpec(
        "C", (crop("a", 1, 1, 10, (50, 50, 50, 50)), crop("b", 1, 20, 10, (10, 10, 10, 10)))
    )
    kinds = [i.kind for i in cal.calendar_issues(rotation, [2008], 1, 7)]
    assert kinds == ["overlap"]
    out = RotationSpec("C", (crop("a", 2, 1, 7, (200, 200, 200, 200)),))
    assert [i.kind for i in cal.calendar_issues(out, [2008], 1, 7)] == ["outside_window"]


def test_timeline_continuity_check_detects_a_gap() -> None:
    window = cal.build_window(2008, 1, 7)
    gap = cal.Timeline(
        (cal.FallowSegment(window.first_day, date(2008, 12, 31)),)
    )  # termina antes del fin de la ventana
    with pytest.raises(CalculationIntegrityError):
        cal._check_continuity(gap, window)
