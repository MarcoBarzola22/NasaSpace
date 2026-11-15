"""Pruebas de la curva de Kc y de la demanda ETc (T015).

Criterios que verifica: CA-8.8 (curva de Kc por etapas de FAO-56) y CA-7.1/CA-8.8 en la
integración ETc = Kc × ET₀ con la ET₀ de Penman–Monteith (ejemplo 18 de FAO-56).
"""

from __future__ import annotations

import pytest

from app.domain import et0
from app.domain.kc_curve import (
    crop_evapotranspiration_mm,
    daily_etc_mm,
    kc_for_crop,
    kc_for_day,
)
from app.domain.types import CropSpec, SowingSpec, Stages

STAGES = Stages(initial=30, development=40, mid=50, late=30)  # 150 días
KC = {"kc_initial": 0.30, "kc_mid": 1.20, "kc_end": 0.35}

MAIZE = CropSpec(
    crop_code="maize",
    crop_type="grain",
    sowing=SowingSpec(1, 15, 10),
    stages=STAGES,
    root_depth_initial_m=0.25,
    root_depth_max_m=1.2,
    depletion_fraction_p=0.55,
    ky=1.25,
    ym_t_ha=9.0,
    **KC,
)


def kc(day: int) -> float:
    return kc_for_day(STAGES, day_in_cycle=day, **KC)


def test_kc_curve_stage_boundaries() -> None:
    assert kc(1) == 0.30
    assert kc(30) == 0.30  # último día de la etapa inicial
    assert kc(70) == pytest.approx(1.20, abs=1e-12)  # fin del desarrollo
    assert kc(120) == 1.20  # fin de la etapa media
    assert kc(150) == pytest.approx(0.35, abs=1e-12)  # fin del ciclo


def test_kc_curve_linear_in_development_and_late_stage() -> None:
    assert kc(31) == pytest.approx(0.30 + 1 / 40 * 0.90, abs=1e-12)
    assert kc(50) == pytest.approx(0.30 + 20 / 40 * 0.90, abs=1e-12)
    assert kc(121) == pytest.approx(1.20 - 1 / 30 * 0.85, abs=1e-12)
    assert kc(135) == pytest.approx(1.20 - 15 / 30 * 0.85, abs=1e-12)
    development = [kc(day) for day in range(30, 71)]
    steps = [b - a for a, b in zip(development, development[1:], strict=False)]
    assert max(steps) - min(steps) < 1e-12  # pendiente constante


def test_kc_curve_matches_the_crop_helper() -> None:
    for day in (1, 31, 70, 100, 121, 150):
        assert kc_for_crop(MAIZE, day) == kc(day)


def test_kc_curve_stays_between_its_extremes() -> None:
    values = [kc(day) for day in range(1, 151)]
    assert min(values) >= 0.30 - 1e-12
    assert max(values) <= 1.20 + 1e-12


def test_kc_curve_rejects_days_outside_the_cycle() -> None:
    for day in (0, -1, 151):
        with pytest.raises(ValueError, match="ciclo"):
            kc(day)


def test_kc_curve_with_single_day_stages() -> None:
    stages = Stages(1, 1, 1, 1)
    values = [kc_for_day(stages, 0.3, 1.2, 0.4, day) for day in (1, 2, 3, 4)]
    assert values == pytest.approx([0.3, 1.2, 1.2, 0.4])


def test_etc_is_kc_times_et0() -> None:
    assert crop_evapotranspiration_mm(1.2, 3.88) == pytest.approx(4.656)
    assert crop_evapotranspiration_mm(0.0, 5.0) == 0.0
    assert crop_evapotranspiration_mm(0.8, 0.0) == 0.0


def test_etc_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="Kc"):
        crop_evapotranspiration_mm(-0.1, 3.0)
    with pytest.raises(ValueError, match="ET₀"):
        crop_evapotranspiration_mm(1.0, -0.2)


def test_etc_integrates_et0_penman_monteith_and_the_kc_curve() -> None:
    """ETc diaria con la ET₀ del ejemplo 18 de FAO-56 (3,88 mm/día) repetida en el ciclo."""
    et0_mm = et0.et0_from_components(
        t_max_c=21.5,
        t_min_c=12.3,
        ea_kpa=1.409,
        rs_mj_m2_day=22.07,
        rso_mj_m2_day=30.90,
        wind_2m_ms=2.078,
        elevation_m=100.0,
    )
    etc = daily_etc_mm(MAIZE, [et0_mm] * 150)
    assert len(etc) == 150
    assert etc[0] == pytest.approx(0.30 * et0_mm)
    assert etc[69] == pytest.approx(1.20 * et0_mm)  # día 70, inicio de la etapa media
    assert etc[149] == pytest.approx(0.35 * et0_mm)
    assert all(value >= 0 for value in etc)
    assert max(etc) == pytest.approx(1.20 * et0_mm)
    assert sum(etc) == pytest.approx(sum(kc(day) for day in range(1, 151)) * et0_mm)


def test_etc_never_exceeds_kc_max_times_et0_for_varying_et0() -> None:
    et0_series = [0.0 if day % 10 == 0 else 2.0 + (day % 7) for day in range(150)]
    etc = daily_etc_mm(MAIZE, et0_series)
    for value, reference in zip(etc, et0_series, strict=True):
        assert 0.0 <= value <= 1.20 * reference + 1e-12


def test_etc_requires_one_et0_value_per_cycle_day() -> None:
    with pytest.raises(ValueError, match="150"):
        daily_etc_mm(MAIZE, [3.0] * 149)
