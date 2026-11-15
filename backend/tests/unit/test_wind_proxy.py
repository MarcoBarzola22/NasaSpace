"""Pruebas del proxy de viento fuerte sin cultivo vivo (T024).

Criterios que verifican: CA-11.1 (WS2M_MAX estrictamente mayor que 8 m/s), CA-11.2 (solo en días
sin cultivo vivo), CA-11.3 (conteos por escenario), CA-11.4 (dato faltante = «sin dato de viento»)
y CA-11.6 (el rastrojo no convierte un barbecho en cultivo vivo), y los casos CL-10, CL-21, CL-22.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta

import pytest

from app.core.constants import WIND_STRONG_THRESHOLD_MS, WIND_STRONG_VARIABLE
from app.domain import calendar as cal
from app.domain import wind_proxy
from app.domain.types import CropSegment, FallowSegment, Timeline
from app.domain.wind_proxy import is_strong_wind, soil_exposure
from tests.builders.rotations import invariant_rotations, make_crop
from tests.builders.weather import synthetic_weather

START = date(2008, 7, 1)
CROP = make_crop("test", 1, 1, 7, (1, 1, 1, 1))  # ciclo de 4 días


def timeline(*kinds: tuple[str, int]) -> Timeline:
    """Arma una línea de tiempo con tramos ('f', días) de barbecho y ('c', 4) de cultivo."""
    segments, cursor = [], START
    for kind, days in kinds:
        end = cursor + timedelta(days=days - 1)
        if kind == "c":
            segments.append(CropSegment(CROP, cursor, end))
        else:
            segments.append(FallowSegment(cursor, end))
        cursor = end + timedelta(days=1)
    return Timeline(tuple(segments))


# --- Umbral estricto (CL-21, CL-22) ---


def test_wind_threshold_is_the_approved_constant() -> None:
    assert WIND_STRONG_THRESHOLD_MS == 8.0
    assert WIND_STRONG_VARIABLE == "WS2M_MAX"
    result = soil_exposure(timeline(("f", 1)), [9.0])
    assert result.wind_variable == "WS2M_MAX"
    assert result.threshold_ms == 8.0


def test_wind_exactly_eight_without_crop_does_not_count() -> None:
    result = soil_exposure(timeline(("f", 1)), [8.0])
    assert result.strong_wind_days_without_live_crop == 0
    assert result.no_live_crop_days == 1


def test_wind_above_eight_without_crop_counts() -> None:
    result = soil_exposure(timeline(("f", 1)), [8.1])
    assert result.strong_wind_days_without_live_crop == 1


def test_wind_above_eight_with_a_live_crop_does_not_count() -> None:
    result = soil_exposure(timeline(("c", 4)), [8.1, 12.0, 20.0, 9.0])
    assert result.strong_wind_days_without_live_crop == 0
    assert result.live_crop_days == 4
    assert result.no_live_crop_days == 0


def test_wind_is_strong_helper_is_strictly_greater() -> None:
    assert not is_strong_wind(7.99)
    assert not is_strong_wind(8.0)
    assert is_strong_wind(8.0000001)
    assert is_strong_wind(15.0)


# --- Solo cuentan los días de barbecho ---


def test_wind_counts_only_the_fallow_days_of_a_mixed_timeline() -> None:
    line = timeline(("f", 3), ("c", 4), ("f", 2))
    wind = [9.0, 8.0, 10.0, 9.0, 9.0, 9.0, 9.0, 8.5, 3.0]
    result = soil_exposure(line, wind)
    assert result.window_days == 9
    assert result.live_crop_days == 4
    assert result.no_live_crop_days == 5
    assert result.strong_wind_days_without_live_crop == 3  # días 1 y 3 (barbecho inicial) y el 8
    assert result.no_wind_data_days_without_live_crop == 0


def test_wind_live_plus_no_live_days_equal_the_window() -> None:
    for key, rotation in invariant_rotations().items():
        for year in (2008, 2011):
            line = cal.build_timeline(cal.build_window(year, 1, 7), rotation)
            wind, _ = synthetic_weather(seed=3, n_days=line.n_days)
            result = soil_exposure(line, [value / 30 for value in wind])
            assert result.live_crop_days + result.no_live_crop_days == result.window_days, key
            assert result.window_days == line.n_days
            assert 0 <= result.strong_wind_days_without_live_crop <= result.no_live_crop_days


def test_wind_cover_crop_counts_as_a_live_crop() -> None:
    line = cal.build_timeline(cal.build_window(2008, 1, 7), invariant_rotations()["cover_only"])
    result = soil_exposure(line, [9.0] * line.n_days)
    assert result.live_crop_days == 120  # centeno de cobertura: 20 + 40 + 40 + 20 días
    assert result.strong_wind_days_without_live_crop == line.n_days - 120


def test_wind_residue_cover_does_not_turn_fallow_into_live_crop() -> None:
    covered = Timeline((FallowSegment(START, START + timedelta(days=2), residue_cover_pct=100.0),))
    result = soil_exposure(covered, [9.0, 9.0, 9.0])
    assert result.no_live_crop_days == 3
    assert result.strong_wind_days_without_live_crop == 3


# --- Datos faltantes (CL-10, CA-11.4) ---


def test_wind_missing_data_on_a_fallow_day_is_neither_strong_nor_calm() -> None:
    result = soil_exposure(timeline(("f", 3)), [None, 9.0, 5.0])
    assert result.no_wind_data_days_without_live_crop == 1
    assert result.strong_wind_days_without_live_crop == 1
    assert result.no_live_crop_days == 3  # el día sin dato igual es un día sin cultivo vivo


def test_wind_missing_data_with_a_live_crop_is_ignored() -> None:
    result = soil_exposure(timeline(("c", 4)), [None, None, 9.0, None])
    assert result.no_wind_data_days_without_live_crop == 0
    assert result.strong_wind_days_without_live_crop == 0


def test_wind_all_missing_gives_no_strong_days() -> None:
    result = soil_exposure(timeline(("f", 5)), [None] * 5)
    assert result.no_wind_data_days_without_live_crop == 5
    assert result.strong_wind_days_without_live_crop == 0


# --- Entradas inválidas y forma de la función ---


def test_wind_rejects_a_series_of_the_wrong_length() -> None:
    with pytest.raises(ValueError, match="5 valores"):
        soil_exposure(timeline(("f", 5)), [9.0] * 4)


@pytest.mark.parametrize("bad", [-0.1, float("nan")])
def test_wind_rejects_invalid_wind_values(bad: float) -> None:
    with pytest.raises(ValueError, match="WS2M_MAX"):
        soil_exposure(timeline(("f", 2)), [bad, 9.0])


def test_wind_function_only_receives_the_raw_ws2m_max_series() -> None:
    parameters = list(inspect.signature(soil_exposure).parameters)
    assert parameters == ["timeline", "wind_max_ms"]
    assert "ws2m" not in " ".join(parameters).lower().replace("ws2m_max", "")
    assert hasattr(wind_proxy, "SoilExposure")


def test_wind_empty_timeline_gives_all_zero_counts() -> None:
    result = soil_exposure(Timeline(()), [])
    assert (result.window_days, result.live_crop_days, result.no_live_crop_days) == (0, 0, 0)
