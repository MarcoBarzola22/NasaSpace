"""Evapotranspiración de referencia ET₀ de FAO-56 Penman–Monteith (RF-7, T010–T012).

Funciones puras en Python estándar. Las ecuaciones se numeran como en FAO-56 (Allen et al.,
1998). Unidades: temperaturas en °C, presiones de vapor en kPa, radiaciones en MJ/m²/día,
viento en m/s, ET₀ en mm/día. Los valores de referencia de las pruebas están en
``specs/001-agrodss-backend/research.md`` (V-3).

``et0_from_components`` recibe ``ea`` y ``Rs`` directamente (como el ejemplo 18 de FAO-56);
``et0_penman_monteith`` parte de un ``Weather`` con punto de rocío ya completo.
"""

from __future__ import annotations

import math

from app.core.constants import (
    ALBEDO,
    HARGREAVES_KRS,
    KELVIN_OFFSET,
    STEFAN_BOLTZMANN_MJ_K4_M2_DAY,
)
from app.domain.types import Weather

_SOLAR_CONSTANT_MJ_M2_MIN = 0.0820
_PM_TEMPERATURE_OFFSET_C = 273.0  # ec. 6 usa T + 273; Rnl usa 273,16 (KELVIN_OFFSET)


# --- Psicrometría (ec. 7, 8, 11–14) ---


def atmospheric_pressure_kpa(elevation_m: float) -> float:
    """Presión atmosférica P a la altitud dada (ec. 7)."""
    return 101.3 * ((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26


def psychrometric_constant_kpa_c(pressure_kpa: float) -> float:
    """Constante psicrométrica γ (ec. 8)."""
    return 0.000665 * pressure_kpa


def saturation_vapour_pressure_kpa(temperature_c: float) -> float:
    """Presión de saturación de vapor e°(T) (ec. 11)."""
    return 0.6108 * math.exp(17.27 * temperature_c / (temperature_c + 237.3))


def mean_saturation_vapour_pressure_kpa(t_max_c: float, t_min_c: float) -> float:
    """Presión media de saturación es = (e°(Tmáx) + e°(Tmín)) / 2 (ec. 12)."""
    return (saturation_vapour_pressure_kpa(t_max_c) + saturation_vapour_pressure_kpa(t_min_c)) / 2


def slope_vapour_pressure_curve_kpa_c(t_mean_c: float) -> float:
    """Pendiente de la curva de presión de vapor Δ (ec. 13)."""
    return 4098.0 * saturation_vapour_pressure_kpa(t_mean_c) / (t_mean_c + 237.3) ** 2


def actual_vapour_pressure_kpa(dew_point_c: float) -> float:
    """Presión real de vapor ea a partir del punto de rocío: ea = e°(Tdew) (ec. 14)."""
    return saturation_vapour_pressure_kpa(dew_point_c)


# --- Radiación (ec. 21–25, 37–40) ---


def inverse_relative_distance(day_of_year: int) -> float:
    """Inverso de la distancia relativa Tierra–Sol dr (ec. 23)."""
    return 1.0 + 0.033 * math.cos(2.0 * math.pi / 365.0 * day_of_year)


def solar_declination_rad(day_of_year: int) -> float:
    """Declinación solar δ (ec. 24)."""
    return 0.409 * math.sin(2.0 * math.pi / 365.0 * day_of_year - 1.39)


def sunset_hour_angle_rad(latitude_rad: float, declination_rad: float) -> float:
    """Ángulo horario de la puesta del sol ωs (ec. 25).

    En latitudes polares el argumento del arco coseno sale de [-1, 1]; se acota para dar noche
    polar (ωs = 0) o día polar (ωs = π) en lugar de un error.
    """
    argument = -math.tan(latitude_rad) * math.tan(declination_rad)
    return math.acos(max(-1.0, min(1.0, argument)))


def extraterrestrial_radiation_mj_m2_day(latitude_deg: float, day_of_year: int) -> float:
    """Radiación extraterrestre diaria Ra (ec. 21); latitud negativa en el hemisferio sur."""
    latitude_rad = math.radians(latitude_deg)
    declination_rad = solar_declination_rad(day_of_year)
    sunset_angle_rad = sunset_hour_angle_rad(latitude_rad, declination_rad)
    ra = (
        (24.0 * 60.0 / math.pi)
        * _SOLAR_CONSTANT_MJ_M2_MIN
        * inverse_relative_distance(day_of_year)
        * (
            sunset_angle_rad * math.sin(latitude_rad) * math.sin(declination_rad)
            + math.cos(latitude_rad) * math.cos(declination_rad) * math.sin(sunset_angle_rad)
        )
    )
    return max(0.0, ra)


def clear_sky_radiation_mj_m2_day(ra_mj_m2_day: float, elevation_m: float) -> float:
    """Radiación de cielo despejado Rso = (0,75 + 2·10⁻⁵ z) Ra (ec. 37)."""
    return (0.75 + 2e-5 * elevation_m) * ra_mj_m2_day


def hargreaves_radiation_mj_m2_day(
    t_max_c: float,
    t_min_c: float,
    ra_mj_m2_day: float,
    rso_mj_m2_day: float,
    krs: float = HARGREAVES_KRS,
) -> float:
    """Radiación solar estimada con la temperatura, Rs = kRs √(Tmáx − Tmín) Ra (ec. 50).

    Se limita a Rso, porque la radiación real no supera la de cielo despejado.
    """
    if t_max_c < t_min_c:
        raise ValueError("La temperatura máxima no puede ser menor que la mínima.")
    return min(krs * math.sqrt(t_max_c - t_min_c) * ra_mj_m2_day, rso_mj_m2_day)


def net_shortwave_radiation_mj_m2_day(rs_mj_m2_day: float) -> float:
    """Radiación neta de onda corta Rns = (1 − α) Rs (ec. 38)."""
    return (1.0 - ALBEDO) * rs_mj_m2_day


def net_longwave_radiation_mj_m2_day(
    t_max_c: float,
    t_min_c: float,
    ea_kpa: float,
    rs_mj_m2_day: float,
    rso_mj_m2_day: float,
) -> float:
    """Radiación neta de onda larga Rnl (ec. 39), con temperaturas absolutas a 273,16 K."""
    if rso_mj_m2_day <= 0:
        raise ValueError("Rso debe ser mayor que 0 (sin radiación de cielo despejado).")
    if rs_mj_m2_day < 0:
        raise ValueError("La radiación solar Rs no puede ser negativa.")
    relative_shortwave = min(rs_mj_m2_day / rso_mj_m2_day, 1.0)
    mean_t4 = ((t_max_c + KELVIN_OFFSET) ** 4 + (t_min_c + KELVIN_OFFSET) ** 4) / 2.0
    return (
        STEFAN_BOLTZMANN_MJ_K4_M2_DAY
        * mean_t4
        * (0.34 - 0.14 * math.sqrt(ea_kpa))
        * (1.35 * relative_shortwave - 0.35)
    )


def net_radiation_mj_m2_day(
    t_max_c: float,
    t_min_c: float,
    ea_kpa: float,
    rs_mj_m2_day: float,
    rso_mj_m2_day: float,
) -> float:
    """Radiación neta Rn = Rns − Rnl (ec. 40)."""
    return net_shortwave_radiation_mj_m2_day(rs_mj_m2_day) - net_longwave_radiation_mj_m2_day(
        t_max_c, t_min_c, ea_kpa, rs_mj_m2_day, rso_mj_m2_day
    )


# --- Penman–Monteith (ec. 6) ---


def et0_from_components(
    *,
    t_max_c: float,
    t_min_c: float,
    ea_kpa: float,
    rs_mj_m2_day: float,
    rso_mj_m2_day: float,
    wind_2m_ms: float,
    elevation_m: float,
) -> float:
    """ET₀ diaria (mm/día) con ea y Rs dados; flujo de calor del suelo G = 0 (ec. 42).

    Es la forma que reproduce el ejemplo 18 de FAO-56 (humedad y radiación ya resueltas).
    Puede dar un valor negativo en días fríos y húmedos; ``clamp_negative_et0`` lo corrige.
    """
    if wind_2m_ms < 0:
        raise ValueError("La velocidad del viento no puede ser negativa.")
    t_mean_c = (t_max_c + t_min_c) / 2.0
    delta = slope_vapour_pressure_curve_kpa_c(t_mean_c)
    gamma = psychrometric_constant_kpa_c(atmospheric_pressure_kpa(elevation_m))
    es_kpa = mean_saturation_vapour_pressure_kpa(t_max_c, t_min_c)
    rn = net_radiation_mj_m2_day(t_max_c, t_min_c, ea_kpa, rs_mj_m2_day, rso_mj_m2_day)
    radiation_term = 0.408 * delta * rn
    aerodynamic_term = (
        gamma * 900.0 / (t_mean_c + _PM_TEMPERATURE_OFFSET_C) * wind_2m_ms * (es_kpa - ea_kpa)
    )
    return (radiation_term + aerodynamic_term) / (delta + gamma * (1.0 + 0.34 * wind_2m_ms))


def et0_penman_monteith(weather: Weather, elevation_m: float) -> float:
    """ET₀ diaria (mm/día) de un día completo; ea sale del punto de rocío (ec. 14)."""
    return et0_from_components(
        t_max_c=weather.t_max_c,
        t_min_c=weather.t_min_c,
        ea_kpa=actual_vapour_pressure_kpa(weather.dew_point_c),
        rs_mj_m2_day=weather.solar_radiation_mj_m2,
        rso_mj_m2_day=weather.clear_sky_radiation_mj_m2,
        wind_2m_ms=weather.wind_2m_ms,
        elevation_m=elevation_m,
    )


def clamp_negative_et0(et0_mm_day: float) -> tuple[float, bool]:
    """Lleva una ET₀ negativa a 0 (CA-7.2); devuelve el valor y si hubo que corregirlo."""
    if et0_mm_day < 0:
        return 0.0, True
    return et0_mm_day, False
