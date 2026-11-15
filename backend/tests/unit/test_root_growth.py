"""Pruebas del crecimiento radicular (T015).

Criterios que verifica: CA-8.4 (Zr crece desde la inicial hasta la máxima y se mantiene) y
CA-3.10 (nunca supera la profundidad efectiva del perfil).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.domain.root_growth import root_depth_m
from app.domain.types import CropSpec, SowingSpec, Stages

MAIZE = CropSpec(
    crop_code="maize",
    crop_type="grain",
    sowing=SowingSpec(1, 15, 10),
    stages=Stages(30, 40, 50, 30),  # crecimiento hasta el día 70
    kc_initial=0.30,
    kc_mid=1.20,
    kc_end=0.35,
    root_depth_initial_m=0.25,
    root_depth_max_m=1.2,
    depletion_fraction_p=0.55,
    ky=1.25,
    ym_t_ha=9.0,
)
DEEP = 2.0  # profundidad efectiva que no limita


def test_root_depth_starts_at_the_initial_value_and_reaches_the_maximum() -> None:
    assert root_depth_m(MAIZE, 1, DEEP) == 0.25
    assert root_depth_m(MAIZE, 70, DEEP) == pytest.approx(1.2, abs=1e-12)


def test_root_depth_is_constant_after_development() -> None:
    for day in (71, 100, 120, 150):
        assert root_depth_m(MAIZE, day, DEEP) == pytest.approx(1.2, abs=1e-12)


def test_root_depth_grows_linearly_and_monotonically() -> None:
    depths = [root_depth_m(MAIZE, day, DEEP) for day in range(1, 71)]
    steps = [b - a for a, b in zip(depths, depths[1:], strict=False)]
    assert all(step > 0 for step in steps)
    assert max(steps) - min(steps) < 1e-12
    assert depths[34] == pytest.approx(0.25 + (34 / 69) * 0.95)  # día 35


def test_root_depth_never_exceeds_the_effective_depth() -> None:
    deep_roots = replace(MAIZE, root_depth_max_m=1.8)
    for day in range(1, 151):
        assert root_depth_m(deep_roots, day, 0.9) <= 0.9
    assert root_depth_m(deep_roots, 150, 0.9) == 0.9
    assert root_depth_m(deep_roots, 1, 0.2) == 0.2  # incluso la Zr inicial se limita


def test_root_depth_with_equal_initial_and_maximum_is_constant() -> None:
    constant = replace(MAIZE, root_depth_initial_m=0.6, root_depth_max_m=0.6)
    assert {root_depth_m(constant, day, DEEP) for day in range(1, 151)} == {0.6}


def test_root_depth_with_a_one_day_growth_period() -> None:
    quick = replace(MAIZE, stages=Stages(1, 1, 10, 5))
    assert root_depth_m(quick, 1, DEEP) == 0.25
    assert root_depth_m(quick, 2, DEEP) == pytest.approx(1.2)


def test_root_depth_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="ciclo"):
        root_depth_m(MAIZE, 0, DEEP)
    with pytest.raises(ValueError, match="ciclo"):
        root_depth_m(MAIZE, 151, DEEP)
    with pytest.raises(ValueError, match="profundidad"):
        root_depth_m(MAIZE, 10, 0.0)
