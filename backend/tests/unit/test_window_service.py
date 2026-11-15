"""Pruebas de la resolución de la ventana histórica (RF-4: CA-4.2–CA-4.5, CA-4.7; T032 del pedido).

El reloj se fija en 2026-11-15 y el inicio de cobertura en 1984-01-01 (radiación, V-1).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.core.config import Settings
from app.core.constants import MAX_START_YEARS
from app.services.window_service import (
    REASON_ENDS_AFTER_TODAY,
    AllRecord,
    LastYears,
    SpecificYears,
    coverage_start,
    eligible_start_years,
    power_query_range,
    resolve_window,
    utc_today,
    window_ends_before,
)

TODAY = date(2026, 11, 15)
COVERAGE = date(1984, 1, 1)


def resolve(selection, *, day: int = 1, month: int = 7, today: date = TODAY):
    return resolve_window(
        selection, today=today, first_covered_day=COVERAGE, start_day=day, start_month=month
    )


def test_coverage_start_is_the_latest_variable_start() -> None:
    """La cobertura común la fija la radiación: 1984-01-01 (V-1)."""
    assert coverage_start(Settings()) == date(1984, 1, 1)


def test_default_window_start_makes_2024_the_last_eligible_year() -> None:
    """CA-4.4: la ventana de 2024 termina el 2026-06-30; la de 2025, el 2027-06-30."""
    years = eligible_start_years(today=TODAY, first_covered_day=COVERAGE)
    assert years[0] == 1984
    assert years[-1] == 2024
    assert years == tuple(range(1984, 2025))
    assert window_ends_before(2024, 1, 7, TODAY)
    assert not window_ends_before(2025, 1, 7, TODAY)


def test_current_year_is_never_eligible_for_any_start_date() -> None:
    """Un año cuya ventana llega al año en curso o más allá dejaría un escenario incompleto."""
    for day, month in [(1, 1), (1, 7), (31, 12), (30, 6)]:
        years = eligible_start_years(
            today=TODAY, first_covered_day=COVERAGE, start_day=day, start_month=month
        )
        assert TODAY.year not in years, (day, month)
        assert years, (day, month)


def test_a_january_window_can_end_in_the_previous_calendar_year() -> None:
    years = eligible_start_years(
        today=TODAY, first_covered_day=COVERAGE, start_day=1, start_month=1
    )
    assert years[-1] == 2024  # 2024-01-01 a 2025-12-31
    assert years[0] == 1984  # 1984-01-01 ya está cubierto


def test_first_eligible_year_moves_when_the_window_would_start_before_coverage() -> None:
    """Con inicio 1 de enero y cobertura desde el 2 de enero, el primer año es el siguiente."""
    years = eligible_start_years(
        today=TODAY, first_covered_day=date(1984, 1, 2), start_day=1, start_month=1
    )
    assert years[0] == 1985


def test_last_years_returns_the_n_most_recent_in_ascending_order() -> None:
    resolution = resolve(LastYears(3))
    assert resolution.start_years == (2022, 2023, 2024)
    assert resolution.rejected == ()
    assert resolution.outside_coverage == ()


def test_last_years_allows_overlapping_windows() -> None:
    """CA-4.7: 2023 y 2024 son escenarios independientes aunque sus ventanas se superpongan."""
    assert resolve(LastYears(2)).start_years == (2023, 2024)


@pytest.mark.parametrize("n", [0, -1, MAX_START_YEARS + 1])
def test_last_years_outside_1_to_max_is_rejected(n: int) -> None:
    with pytest.raises(ValueError):
        resolve(LastYears(n))


def test_last_years_at_the_limit_is_accepted() -> None:
    assert len(resolve(LastYears(MAX_START_YEARS)).start_years) == MAX_START_YEARS


def test_all_record_covers_every_eligible_year_from_the_coverage_start() -> None:
    resolution = resolve(AllRecord())
    assert resolution.start_years == tuple(range(1984, 2025))
    assert resolution.exceeds_limit  # 41 años > 10 (CA-4.3): la validación lo informa


def test_all_record_never_starts_before_radiation_coverage() -> None:
    assert min(resolve(AllRecord()).start_years) >= 1984


def test_last_years_never_includes_years_before_coverage() -> None:
    narrow = resolve_window(
        LastYears(10),
        today=date(1990, 1, 1),
        first_covered_day=COVERAGE,
    )
    assert narrow.start_years == (1984, 1985, 1986, 1987)  # ventanas que ya terminaron
    assert min(narrow.start_years) >= 1984


def test_specific_years_are_sorted_and_deduplicated_reporting_the_repeats() -> None:
    resolution = resolve(SpecificYears((2017, 2008, 2011, 2008)))
    assert resolution.start_years == (2008, 2011, 2017)
    assert resolution.duplicates == (2008,)


def test_specific_year_whose_window_ends_after_today_is_rejected_with_its_date() -> None:
    """CA-4.4: 2025 termina el 2027-06-30, después de hoy."""
    resolution = resolve(SpecificYears((2024, 2025, 2026)))
    assert resolution.start_years == (2024,)
    assert [rejected.year for rejected in resolution.rejected] == [2025, 2026]
    assert all(rejected.reason == REASON_ENDS_AFTER_TODAY for rejected in resolution.rejected)
    assert resolution.rejected[0].window_last_day == date(2027, 6, 30)


def test_window_ending_exactly_today_is_rejected() -> None:
    """Una ventana debe terminar estrictamente antes de hoy: el último día aún no se publica."""
    resolution = resolve(SpecificYears((2024,)), today=date(2026, 6, 30))
    assert resolution.start_years == ()
    assert resolution.rejected[0].window_last_day == date(2026, 6, 30)
    assert resolve(SpecificYears((2024,)), today=date(2026, 7, 1)).start_years == (2024,)


def test_specific_year_before_coverage_is_kept_and_flagged_to_be_blocked() -> None:
    """CA-4.5: un año anterior a la cobertura no se rechaza; su escenario se bloqueará."""
    resolution = resolve(SpecificYears((1983, 1990)))
    assert resolution.start_years == (1983, 1990)
    assert resolution.outside_coverage == (1983,)


def test_invalid_start_date_is_rejected_including_february_29() -> None:
    """CA-4.3: el 29 de febrero no se acepta como inicio."""
    with pytest.raises(ValueError):
        resolve(LastYears(2), day=29, month=2)


def test_query_range_spans_earliest_first_day_to_latest_last_day() -> None:
    """CA-5.1: una consulta cubre todas las ventanas."""
    first, last = power_query_range([2017, 2008, 2011], 1, 7)
    assert first == date(2008, 7, 1)
    assert last == date(2019, 6, 30)


def test_query_range_is_not_requested_before_radiation_coverage() -> None:
    """V-1 O-1: no se piden fechas anteriores a la cobertura de la radiación."""
    first, last = power_query_range([1983, 1990], 1, 7, not_before=COVERAGE)
    assert first == date(1984, 1, 1)
    assert last == date(1992, 6, 30)


def test_query_range_rejects_empty_or_fully_uncovered_input() -> None:
    with pytest.raises(ValueError):
        power_query_range([], 1, 7)
    with pytest.raises(ValueError):
        power_query_range([1980], 1, 7, not_before=COVERAGE)  # termina el 1982-06-30


def test_utc_today_is_a_date_in_utc() -> None:
    assert abs((datetime.now(UTC).date() - utc_today()).days) <= 1
