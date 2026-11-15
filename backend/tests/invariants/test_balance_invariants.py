"""Invariantes del balance hídrico sobre clima extremo sintético (T021; plan §9.3; RNF-9).

Cada corrida (rotación × suelo × humedad inicial × semilla) simula una ventana de 730 o 731
días con lluvias aleatorias, un día de 300 mm, una sequía de 120 días y ET₀ entre 0 y 9 mm/día.
Se verifica, con la serie diaria registrada y sin confiar en los controles internos del motor:

Cada día
  1. 0 ≤ agua de la zona activa ≤ su capacidad y 0 ≤ agua de la zona inferior ≤ la suya, y por
     lo tanto 0 ≤ almacenamiento ≤ capacidad del perfil (CA-8.14).
  2. ETa ≤ ETc (o evaporación real ≤ demandada) y ETa ≤ agua disponible (CA-8.15).
  3. Cierre diario: Δalmacenamiento = lluvia − consumo − excedente, con error ≤ 1e-9 mm.
  4. El excedente solo existe si el perfil quedó lleno tras la lluvia (no se acumula, CA-8.13).

Cada corrida
  5. |error de cierre de masa| ≤ 0,01 mm (CA-8.16).
  6. Cronología: exactamente ``n_days`` días consecutivos, sin huecos ni duplicados (CA-8.2).
  7. El almacenamiento final de cada segmento es idéntico al inicial del siguiente (CA-8.6).
  8. La suma por segmentos coincide con los totales de la corrida.

La matriz reducida (5 semillas) corre en cada ``pytest``; la completa (50 semillas) lleva la marca
``slow``: ``pytest tests/invariants -m slow``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain import calendar as cal
from app.domain.types import ParcelSpec, Timeline
from app.domain.water_balance import BalanceRun, profile_capacity_mm, run_daily_balance
from tests.builders.rotations import invariant_rotations
from tests.builders.weather import synthetic_weather

EPS = 1e-9
CLOSURE_TOLERANCE_MM = 0.01

# (profundidad efectiva m, agua útil m³/m³)
SOILS = [(0.3, 0.05), (1.2, 0.16), (2.0, 0.25)]
HUMIDITIES = [0.0, 50.0, 100.0]
ROTATIONS = sorted(invariant_rotations())
REDUCED_SEEDS = range(5)
FULL_SEEDS = range(50)


def make_parcel(depth_m: float, awc: float, humidity_pct: float) -> ParcelSpec:
    return ParcelSpec(
        latitude_deg=-33.68,
        longitude_deg=-65.47,
        theta_fc_m3_m3=0.10 + awc,
        theta_wp_m3_m3=0.10,
        effective_depth_m=depth_m,
        initial_available_water_pct=humidity_pct,
    )


def build_case(seed: int, rotation_key: str) -> tuple[Timeline, list[float], list[float]]:
    start_year = 2008 if seed % 2 == 0 else 2011  # ventanas de 730 y de 731 días
    timeline = cal.build_timeline(
        cal.build_window(start_year, 1, 7), invariant_rotations()[rotation_key]
    )
    rain, et0 = synthetic_weather(seed, timeline.n_days)
    return timeline, rain, et0


def check_run(parcel: ParcelSpec, timeline: Timeline, run: BalanceRun) -> None:
    capacity = profile_capacity_mm(parcel)
    days = run.daily

    # 6. Cronología continua.
    assert len(days) == timeline.n_days
    assert days[0].day == timeline.segments[0].start
    for previous, current in zip(days, days[1:], strict=False):
        assert current.day == previous.day + timedelta(days=1)
    assert days[-1].day == timeline.segments[-1].end

    previous_storage = run.initial_storage_mm
    for record in days:
        # 1. Límites físicos.
        assert -EPS <= record.active_storage_mm <= record.active_capacity_mm + EPS
        assert -EPS <= record.lower_storage_mm <= record.lower_capacity_mm + EPS
        assert -EPS <= record.storage_mm <= capacity + EPS
        # 2. ETa ≤ ETc y ETa ≤ agua disponible.
        assert 0.0 <= record.actual_mm <= record.demand_mm + EPS
        assert record.actual_mm <= record.available_mm + EPS
        # 3. Cierre diario.
        assert record.excess_mm >= 0.0
        delta = record.storage_mm - previous_storage
        assert abs(delta - (record.rain_mm - record.actual_mm - record.excess_mm)) <= EPS
        previous_storage = record.storage_mm
        # 4. El excedente solo aparece con el perfil lleno tras la lluvia.
        if record.excess_mm > EPS:
            assert record.storage_mm + record.actual_mm >= capacity - 1e-6

    # 5. Cierre de masa de la corrida.
    assert abs(run.closure_mm) <= CLOSURE_TOLERANCE_MM
    assert run.final_storage_mm == pytest.approx(days[-1].storage_mm, abs=EPS)

    # 7. Transferencia exacta entre segmentos.
    for current, following in zip(run.segments, run.segments[1:], strict=False):
        assert current.storage_at_end_mm == following.storage_at_start_mm

    # 8. Los totales coinciden con la serie diaria y con los segmentos.
    assert run.precipitation_mm == pytest.approx(sum(d.rain_mm for d in days), abs=1e-6)
    assert run.excess_lost_mm == pytest.approx(sum(d.excess_mm for d in days), abs=1e-6)
    crop_eta = sum(d.actual_mm for d in days if d.is_crop)
    fallow_evap = sum(d.actual_mm for d in days if not d.is_crop)
    assert run.crop_eta_mm == pytest.approx(crop_eta, abs=1e-6)
    assert run.fallow_evaporation_mm == pytest.approx(fallow_evap, abs=1e-6)
    assert sum(s.actual_mm for s in run.segments) == pytest.approx(crop_eta + fallow_evap, abs=1e-6)


def run_combination(seeds: range, soil: tuple[float, float], humidity: float, key: str) -> None:
    parcel = make_parcel(*soil, humidity)
    for seed in seeds:
        timeline, rain, et0 = build_case(seed, key)
        run = run_daily_balance(timeline, rain, et0, parcel, record_days=True)
        check_run(parcel, timeline, run)


COMBINATIONS = [
    pytest.param(soil, humidity, key, id=f"D{soil[0]}-AWC{soil[1]}-W{humidity:.0f}-{key}")
    for soil in SOILS
    for humidity in HUMIDITIES
    for key in ROTATIONS
]


def test_invariants_matrix_has_180_runs() -> None:
    assert len(COMBINATIONS) * len(REDUCED_SEEDS) == 180


@pytest.mark.parametrize(("soil", "humidity", "key"), COMBINATIONS)
def test_balance_invariants_reduced_matrix(
    soil: tuple[float, float], humidity: float, key: str
) -> None:
    run_combination(REDUCED_SEEDS, soil, humidity, key)


@pytest.mark.slow
@pytest.mark.parametrize(("soil", "humidity", "key"), COMBINATIONS)
def test_balance_invariants_full_matrix(
    soil: tuple[float, float], humidity: float, key: str
) -> None:
    run_combination(FULL_SEEDS, soil, humidity, key)


def test_synthetic_weather_is_reproducible_and_extreme() -> None:
    first = synthetic_weather(seed=4, n_days=731)
    assert first == synthetic_weather(seed=4, n_days=731)
    assert first != synthetic_weather(seed=5, n_days=731)
    rain, et0 = first
    assert max(rain) == 300.0
    assert 0.0 <= min(et0) and max(et0) <= 9.0
    longest = current = 0
    for value in rain:
        current = current + 1 if value == 0.0 else 0
        longest = max(longest, current)
    assert longest >= 120  # incluye la sequía de 120 días
