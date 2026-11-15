"""Pruebas de la redistribución entre compartimentos y del factor de rastrojo (T016).

Criterios que verifica: CA-8.7 (reparto entre la zona activa y el resto del perfil sin crear ni
perder agua) y CA-8.10 (factor de rastrojo: 1 − 0,05 × cobertura/10).
"""

from __future__ import annotations

import itertools

import pytest

from app.domain.water_balance import redistribute, residue_factor

DEPTH_M = 1.2
CAPACITY_PER_M = 160.0  # mm de agua útil por metro (θCC − θPMP = 0,16)

# Estados válidos (agua en la zona activa, agua en la zona inferior) para una zona activa dada.
Z_VALUES = [0.15, 0.25, 0.6, 1.0, 1.2]


def valid_states(z_old_m: float) -> list[tuple[float, float]]:
    cap_active = CAPACITY_PER_M * z_old_m
    cap_lower = CAPACITY_PER_M * (DEPTH_M - z_old_m)
    return [(f * cap_active, g * cap_lower) for f in (0.0, 0.5, 1.0) for g in (0.0, 0.5, 1.0)]


CASES = [
    (w_act, w_low, z_old, z_new)
    for z_old, z_new in itertools.product(Z_VALUES, repeat=2)
    for w_act, w_low in valid_states(z_old)
]


def test_redistribution_cases_are_at_least_twenty() -> None:
    assert len(CASES) >= 20


@pytest.mark.parametrize(("w_act", "w_low", "z_old", "z_new"), CASES)
def test_redistribution_conserves_the_total(
    w_act: float, w_low: float, z_old: float, z_new: float
) -> None:
    new_act, new_low = redistribute(w_act, w_low, z_old, z_new, DEPTH_M)
    assert new_act + new_low == pytest.approx(w_act + w_low, abs=1e-12)


@pytest.mark.parametrize(("w_act", "w_low", "z_old", "z_new"), CASES)
def test_redistribution_keeps_each_zone_within_its_capacity(
    w_act: float, w_low: float, z_old: float, z_new: float
) -> None:
    new_act, new_low = redistribute(w_act, w_low, z_old, z_new, DEPTH_M)
    assert new_act >= -1e-12
    assert new_low >= -1e-12
    assert new_act <= CAPACITY_PER_M * z_new + 1e-9
    assert new_low <= CAPACITY_PER_M * (DEPTH_M - z_new) + 1e-9


def test_redistribution_plan_case_maize_to_fallow() -> None:
    """31,2 mm en todo el perfil (1,2 m) pasan a una capa activa de 0,15 m: 3,9 + 27,3 mm."""
    new_act, new_low = redistribute(31.2, 0.0, 1.2, 0.15, DEPTH_M)
    assert new_act == pytest.approx(3.9, abs=1e-9)
    assert new_low == pytest.approx(27.3, abs=1e-9)


def test_redistribution_deepening_incorporates_water_from_the_lower_zone() -> None:
    new_act, new_low = redistribute(3.9, 27.3, 0.15, 0.25, DEPTH_M)
    expected_moved = 27.3 * (0.25 - 0.15) / (1.2 - 0.15)
    assert new_act == pytest.approx(3.9 + expected_moved, abs=1e-9)
    assert new_low == pytest.approx(27.3 - expected_moved, abs=1e-9)


def test_redistribution_with_full_depth_active_does_not_move_water() -> None:
    assert redistribute(31.2, 0.0, 1.2, 1.2, DEPTH_M) == (31.2, 0.0)
    # Con la zona activa ya en toda la profundidad, profundizar más no cambia nada.
    assert redistribute(31.2, 0.0, 1.2, 1.2, DEPTH_M) == (31.2, 0.0)


def test_redistribution_without_a_change_of_depth_is_identity() -> None:
    assert redistribute(10.0, 20.0, 0.25, 0.25, DEPTH_M) == (10.0, 20.0)


def test_redistribution_round_trip_is_not_lossy_in_total() -> None:
    act, low = 12.0, 84.0
    for z_new in (0.4, 0.9, 0.15, 1.2, 0.25):
        total_before = act + low
        act, low = redistribute(act, low, 0.15, z_new, DEPTH_M)
        act, low = redistribute(act, low, z_new, 0.15, DEPTH_M)
        assert act + low == pytest.approx(total_before, abs=1e-9)
        act, low = 12.0, 84.0


@pytest.mark.parametrize(
    ("cover_pct", "factor"), [(0.0, 1.0), (50.0, 0.75), (100.0, 0.5), (10.0, 0.95), (30.0, 0.85)]
)
def test_residue_factor_values(cover_pct: float, factor: float) -> None:
    assert residue_factor(cover_pct) == pytest.approx(factor, abs=1e-12)


@pytest.mark.parametrize("cover_pct", [-0.1, 100.1, -50.0, 250.0])
def test_residue_factor_rejects_out_of_range_cover(cover_pct: float) -> None:
    with pytest.raises(ValueError, match="rastrojo"):
        residue_factor(cover_pct)
