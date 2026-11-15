"""Pruebas de la ET₀ de FAO-56 (T010, T011, T012).

Criterios que verifica: CA-7.1 (Penman–Monteith con G = 0 y albedo 0,23), CA-7.2 (ET₀ negativa
pasa a 0) y CA-7.3 (ejemplo 18 de FAO-56 con ±0,1 mm/día), y CA-6.4 (radiación estimada con la
temperatura, limitada por Rso). Los valores de referencia están en
``specs/001-agrodss-backend/research.md``, sección V-3.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from app.domain import et0
from app.domain.types import Weather

# Ejemplo 18 (Uccle, Bélgica, 6 de julio), con ea y Rs ya resueltas tal como los imprime FAO-56.
EX18 = {
    "t_max_c": 21.5,
    "t_min_c": 12.3,
    "ea_kpa": 1.409,
    "rs_mj_m2_day": 22.07,
    "rso_mj_m2_day": 30.90,
    "wind_2m_ms": 2.078,
    "elevation_m": 100.0,
}


# --- T010: psicrometría ---


def test_psychrometric_pressure_and_constant_fao56_example_2() -> None:
    pressure = et0.atmospheric_pressure_kpa(1800.0)
    assert pressure == pytest.approx(81.8, abs=0.05)
    assert et0.psychrometric_constant_kpa_c(pressure) == pytest.approx(0.054, abs=0.0005)


def test_psychrometric_annex_2_values_at_20_c() -> None:
    assert et0.saturation_vapour_pressure_kpa(20.0) == pytest.approx(2.338, abs=0.001)
    assert et0.slope_vapour_pressure_curve_kpa_c(20.0) == pytest.approx(0.145, abs=0.001)


@pytest.mark.parametrize(
    ("temperature_c", "e0_kpa", "delta_kpa_c"),
    [(12.5, 1.449, 0.095), (19.0, 2.197, 0.137), (20.0, 2.338, 0.145), (21.0, 2.487, 0.153)]
    + [(21.5, 2.564, 0.157)],
)
def test_psychrometric_annex_2_table_rows(
    temperature_c: float, e0_kpa: float, delta_kpa_c: float
) -> None:
    assert et0.saturation_vapour_pressure_kpa(temperature_c) == pytest.approx(e0_kpa, abs=0.001)
    assert et0.slope_vapour_pressure_curve_kpa_c(temperature_c) == pytest.approx(
        delta_kpa_c, abs=0.001
    )


def test_psychrometric_fao56_example_3() -> None:
    assert et0.saturation_vapour_pressure_kpa(24.5) == pytest.approx(3.075, abs=0.001)
    assert et0.saturation_vapour_pressure_kpa(15.0) == pytest.approx(1.705, abs=0.001)
    assert et0.mean_saturation_vapour_pressure_kpa(24.5, 15.0) == pytest.approx(2.39, abs=0.005)
    assert et0.saturation_vapour_pressure_kpa(19.75) == pytest.approx(2.30, abs=0.005)


def test_psychrometric_actual_pressure_is_saturation_at_dew_point() -> None:
    for dew_point_c in (-5.0, 0.0, 7.3, 12.07, 25.0):
        assert et0.actual_vapour_pressure_kpa(dew_point_c) == et0.saturation_vapour_pressure_kpa(
            dew_point_c
        )


def test_psychrometric_example_18_intermediates() -> None:
    t_mean_c = (21.5 + 12.3) / 2
    pressure = et0.atmospheric_pressure_kpa(100.0)
    assert t_mean_c == pytest.approx(16.9)
    assert pressure == pytest.approx(100.1, abs=0.05)
    assert et0.slope_vapour_pressure_curve_kpa_c(t_mean_c) == pytest.approx(0.122, abs=0.001)
    assert et0.psychrometric_constant_kpa_c(pressure) == pytest.approx(0.0666, abs=0.0005)
    assert et0.saturation_vapour_pressure_kpa(21.5) == pytest.approx(2.564, abs=0.001)
    assert et0.saturation_vapour_pressure_kpa(12.3) == pytest.approx(1.431, abs=0.001)
    assert et0.mean_saturation_vapour_pressure_kpa(21.5, 12.3) == pytest.approx(1.997, abs=0.001)


# --- T011: radiación ---


def test_radiation_fao56_example_8() -> None:
    day_of_year = 246  # 3 de septiembre
    assert et0.inverse_relative_distance(day_of_year) == pytest.approx(0.985, abs=0.001)
    declination = et0.solar_declination_rad(day_of_year)
    assert declination == pytest.approx(0.120, abs=0.001)
    sunset = et0.sunset_hour_angle_rad(math.radians(-20.0), declination)
    assert sunset == pytest.approx(1.527, abs=0.001)
    assert et0.extraterrestrial_radiation_mj_m2_day(-20.0, day_of_year) == pytest.approx(
        32.2, abs=0.1
    )


def test_radiation_example_18_ra_and_rso() -> None:
    ra = et0.extraterrestrial_radiation_mj_m2_day(50.8, 187)  # 50°48′ N, 6 de julio
    assert ra == pytest.approx(41.09, abs=0.1)
    assert et0.clear_sky_radiation_mj_m2_day(41.09, 100.0) == pytest.approx(30.90, abs=0.01)


def test_radiation_example_18_net_radiation() -> None:
    assert et0.net_shortwave_radiation_mj_m2_day(22.07) == pytest.approx(17.00, abs=0.01)
    rnl = et0.net_longwave_radiation_mj_m2_day(21.5, 12.3, 1.409, 22.07, 30.90)
    assert rnl == pytest.approx(3.71, abs=0.01)
    rn = et0.net_radiation_mj_m2_day(21.5, 12.3, 1.409, 22.07, 30.90)
    assert rn == pytest.approx(13.28, abs=0.01)


def test_radiation_longwave_uses_273_16_kelvin_offset() -> None:
    """Con 273 en lugar de 273,16 el resultado cambia; con 273,16 coincide con FAO-56."""
    sigma = 4.903e-9
    factor = (0.34 - 0.14 * math.sqrt(1.409)) * (1.35 * (22.07 / 30.90) - 0.35)

    def rnl(offset: float) -> float:
        mean_t4 = ((21.5 + offset) ** 4 + (12.3 + offset) ** 4) / 2
        return sigma * mean_t4 * factor

    assert et0.net_longwave_radiation_mj_m2_day(21.5, 12.3, 1.409, 22.07, 30.90) == (
        pytest.approx(rnl(273.16), rel=1e-12)
    )
    assert abs(rnl(273.16) - rnl(273.0)) > 1e-3


def test_radiation_relative_shortwave_is_capped_at_one() -> None:
    capped = et0.net_longwave_radiation_mj_m2_day(25.0, 10.0, 1.2, 35.0, 30.0)
    at_limit = et0.net_longwave_radiation_mj_m2_day(25.0, 10.0, 1.2, 30.0, 30.0)
    assert capped == at_limit


def test_radiation_polar_latitude_no_error() -> None:
    june = 170
    assert et0.extraterrestrial_radiation_mj_m2_day(-70.0, june) >= 0.0  # noche polar
    assert et0.extraterrestrial_radiation_mj_m2_day(-70.0, june) == 0.0
    december = 355
    assert et0.extraterrestrial_radiation_mj_m2_day(-70.0, december) > 0.0  # día polar
    assert et0.extraterrestrial_radiation_mj_m2_day(90.0, 80) >= 0.0


def test_radiation_is_never_negative_over_the_year_and_latitude() -> None:
    for latitude in range(-90, 91, 5):
        for day_of_year in range(1, 366, 7):
            ra = et0.extraterrestrial_radiation_mj_m2_day(float(latitude), day_of_year)
            assert 0.0 <= ra < 60.0, (latitude, day_of_year)


def test_radiation_longwave_rejects_missing_clear_sky_radiation() -> None:
    with pytest.raises(ValueError, match="Rso"):
        et0.net_longwave_radiation_mj_m2_day(0.0, -10.0, 0.3, 0.0, 0.0)


# --- T012: Penman–Monteith, Hargreaves y ET₀ negativa ---


def test_et0_fao56_example_18() -> None:
    value = et0.et0_from_components(**EX18)
    assert value == pytest.approx(3.9, abs=0.1)  # criterio CA-7.3
    assert value == pytest.approx(3.88, abs=0.01)  # valor sin redondear del ejemplo


def test_et0_from_weather_matches_example_18() -> None:
    dew_point_c = 237.3 * math.log(1.409 / 0.6108) / (17.27 - math.log(1.409 / 0.6108))
    weather = Weather(
        day=date(1998, 7, 6),
        precipitation_mm=0.0,
        t_max_c=21.5,
        t_min_c=12.3,
        dew_point_c=dew_point_c,
        wind_2m_ms=2.078,
        solar_radiation_mj_m2=22.07,
        extraterrestrial_radiation_mj_m2=41.09,
        clear_sky_radiation_mj_m2=30.90,
    )
    assert et0.et0_penman_monteith(weather, elevation_m=100.0) == pytest.approx(3.88, abs=0.01)


def test_et0_is_larger_with_more_wind_and_radiation() -> None:
    base = et0.et0_from_components(**EX18)
    windy = et0.et0_from_components(**{**EX18, "wind_2m_ms": 5.0})
    sunny = et0.et0_from_components(**{**EX18, "rs_mj_m2_day": 28.0})
    assert windy > base
    assert sunny > base


def test_et0_rejects_negative_wind() -> None:
    with pytest.raises(ValueError, match="viento"):
        et0.et0_from_components(**{**EX18, "wind_2m_ms": -1.0})


def test_hargreaves_fao56_lyon_example() -> None:
    rs = et0.hargreaves_radiation_mj_m2_day(26.6, 14.8, ra_mj_m2_day=40.6, rso_mj_m2_day=30.58)
    assert rs == pytest.approx(22.3, abs=0.1)


def test_hargreaves_capped_by_rso() -> None:
    rs = et0.hargreaves_radiation_mj_m2_day(40.0, 0.0, ra_mj_m2_day=40.0, rso_mj_m2_day=25.0)
    assert rs == 25.0
    assert rs <= 25.0


def test_hargreaves_uses_the_approved_coefficient_by_default() -> None:
    default = et0.hargreaves_radiation_mj_m2_day(26.6, 14.8, 40.6, 100.0)
    explicit = et0.hargreaves_radiation_mj_m2_day(26.6, 14.8, 40.6, 100.0, krs=0.16)
    assert default == explicit
    coastal = et0.hargreaves_radiation_mj_m2_day(26.6, 14.8, 40.6, 100.0, krs=0.19)
    assert coastal > default


def test_hargreaves_rejects_inconsistent_temperatures() -> None:
    with pytest.raises(ValueError, match="máxima"):
        et0.hargreaves_radiation_mj_m2_day(10.0, 12.0, 30.0, 25.0)


def test_clamp_negative_et0() -> None:
    assert et0.clamp_negative_et0(-0.2) == (0.0, True)
    assert et0.clamp_negative_et0(1.5) == (1.5, False)
    assert et0.clamp_negative_et0(0.0) == (0.0, False)
