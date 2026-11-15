"""Pruebas del balance hídrico diario continuo (T017, T018, T019, T020).

Criterios que verifica: CA-8.1 (cronología continua), CA-8.3 (humedad inicial), CA-8.4 y CA-8.5
(raíces y agua bajo ellas), CA-8.6 (transferencia exacta entre segmentos), CA-8.8, CA-8.9,
CA-8.10 y CA-8.11 (Kc, Ks, evaporación de barbecho y rastrojo constante), CA-8.12 y CA-8.13
(lluvia y excedente perdido), CA-8.14 y CA-8.15 (límites físicos), CA-8.16 y CA-8.17 (cierre de
masa y error de integridad), CA-9.6 (días con estrés y almacenamiento al sembrar y al terminar)
y los casos límite CL-13 a CL-17.

Perfil de referencia: 1,2 m de profundidad, agua útil 0,16 m³/m³ → capacidad de 192 mm.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.core.exceptions import CalculationIntegrityError
from app.domain import calendar as cal
from app.domain import water_balance as wb
from app.domain.types import CropSegment, FallowSegment, ParcelSpec, Timeline
from app.domain.water_balance import run_daily_balance
from tests.builders.rotations import invariant_rotations, make_crop
from tests.builders.weather import synthetic_weather

START = date(2008, 7, 1)
BASE = ParcelSpec(
    latitude_deg=-33.68,
    longitude_deg=-65.47,
    theta_fc_m3_m3=0.28,
    theta_wp_m3_m3=0.12,
    effective_depth_m=1.2,
    initial_available_water_pct=50.0,
)
CAPACITY_MM = 192.0
EPS = 1e-9


def parcel(pct: float, **changes: float) -> ParcelSpec:
    return replace(BASE, initial_available_water_pct=pct, **changes)


def pct_for_storage(storage_mm: float) -> float:
    return storage_mm / wb.profile_capacity_mm(BASE) * 100.0


def fallow_timeline(n_days: int, residue_pct: float = 0.0) -> Timeline:
    return Timeline((FallowSegment(START, START + timedelta(days=n_days - 1), residue_pct),))


def crop_timeline(crop, n_days: int | None = None) -> Timeline:
    days = n_days or crop.stages.total_days
    return Timeline((CropSegment(crop, START, START + timedelta(days=days - 1)),))


def full_depth_crop(stages, kc, p=0.5):
    """Cultivo cuya zona radicular abarca todo el perfil (Zr = 1,2 m desde el día 1)."""
    base = make_crop("test", 1, 1, 7, stages, zr_initial_m=1.2, zr_max_m=1.2, p=p)
    return replace(base, kc_initial=kc[0], kc_mid=kc[1], kc_end=kc[2])


# --- T017: barbecho, estado inicial y lluvia en cascada ---


def test_fallow_heavy_rain_becomes_excess_and_profile_stays_at_capacity() -> None:
    """CL-13: 300 mm con el perfil al 50 % dejan 192 mm y 204 mm de excedente."""
    run = run_daily_balance(fallow_timeline(1), [300.0], [0.0], parcel(50.0), record_days=True)
    assert run.final_storage_mm == pytest.approx(CAPACITY_MM, abs=EPS)
    assert run.excess_lost_mm == pytest.approx(300.0 - 96.0, abs=EPS)
    assert run.daily[0].excess_mm == pytest.approx(204.0, abs=EPS)
    assert run.closure_mm == pytest.approx(0.0, abs=EPS)


def test_fallow_excess_is_not_accumulated_for_later_days() -> None:
    rain = [300.0, 0.0, 0.0]
    run = run_daily_balance(fallow_timeline(3), rain, [0.0] * 3, parcel(50.0), record_days=True)
    assert [round(d.excess_mm, 6) for d in run.daily] == [204.0, 0.0, 0.0]
    assert all(d.storage_mm == pytest.approx(CAPACITY_MM, abs=EPS) for d in run.daily)


def test_fallow_zero_initial_moisture_gives_no_evaporation() -> None:
    """CL-14: con 0 % y sin lluvia, la evaporación es 0 todos los días."""
    run = run_daily_balance(
        fallow_timeline(30), [0.0] * 30, [5.0] * 30, parcel(0.0), record_days=True
    )
    assert all(d.actual_mm == 0.0 for d in run.daily)
    assert run.fallow_evaporation_mm == 0.0
    assert run.final_storage_mm == 0.0


def test_fallow_full_profile_sends_the_first_rain_to_excess() -> None:
    """CL-15: con el perfil al 100 %, toda la lluvia del día 1 es excedente."""
    run = run_daily_balance(fallow_timeline(1), [25.0], [0.0], parcel(100.0), record_days=True)
    assert run.excess_lost_mm == pytest.approx(25.0, abs=EPS)
    assert run.final_storage_mm == pytest.approx(CAPACITY_MM, abs=EPS)


def test_fallow_dry_spell_does_not_touch_the_lower_zone() -> None:
    """120 días secos: solo se seca la capa de 0,15 m; el agua profunda se conserva."""
    run = run_daily_balance(
        fallow_timeline(120), [0.0] * 120, [5.0] * 120, parcel(50.0), record_days=True
    )
    initial_layer_mm = 96.0 * 0.15 / 1.2  # 12 mm en la capa activa
    assert all(d.lower_storage_mm == pytest.approx(84.0, abs=EPS) for d in run.daily)
    assert run.fallow_evaporation_mm == pytest.approx(initial_layer_mm, abs=EPS)
    assert run.fallow_evaporation_mm <= 24.0  # capacidad de la capa de 0,15 m
    assert run.final_storage_mm == pytest.approx(84.0, abs=EPS)


def test_fallow_evaporation_uses_kc_base_and_et0() -> None:
    run = run_daily_balance(fallow_timeline(1), [0.0], [5.0], parcel(100.0), record_days=True)
    assert run.daily[0].demand_mm == pytest.approx(0.20 * 5.0, abs=EPS)
    assert run.daily[0].actual_mm == pytest.approx(1.0, abs=EPS)
    custom = run_daily_balance(
        fallow_timeline(1), [0.0], [5.0], parcel(100.0, fallow_kc_base=0.15), record_days=True
    )
    assert custom.daily[0].demand_mm == pytest.approx(0.75, abs=EPS)


def test_fallow_residue_cover_reduces_evaporation() -> None:
    et0, rain = [2.0] * 10, [0.0] * 10
    bare = run_daily_balance(fallow_timeline(10, 0.0), rain, et0, parcel(100.0))
    half = run_daily_balance(fallow_timeline(10, 50.0), rain, et0, parcel(100.0))
    covered = run_daily_balance(fallow_timeline(10, 100.0), rain, et0, parcel(100.0))
    assert bare.fallow_evaporation_mm == pytest.approx(4.0, abs=EPS)
    assert half.fallow_evaporation_mm == pytest.approx(3.0, abs=EPS)
    assert covered.fallow_evaporation_mm == pytest.approx(2.0, abs=EPS)


def test_fallow_storage_stays_within_limits_with_extreme_weather() -> None:
    rain, et0 = synthetic_weather(seed=7, n_days=731)
    run = run_daily_balance(fallow_timeline(731), rain, et0, parcel(50.0), record_days=True)
    capacity = wb.profile_capacity_mm(BASE)
    assert len(run.daily) == 731
    assert all(-EPS <= d.storage_mm <= capacity + EPS for d in run.daily)
    assert all(d.actual_mm <= d.demand_mm + EPS for d in run.daily)


def test_fallow_initial_moisture_is_spread_uniformly_over_the_profile() -> None:
    run = run_daily_balance(fallow_timeline(1), [0.0], [0.0], parcel(50.0), record_days=True)
    assert run.initial_storage_mm == pytest.approx(96.0, abs=EPS)
    assert run.daily[0].active_storage_mm == pytest.approx(12.0, abs=EPS)
    assert run.daily[0].lower_storage_mm == pytest.approx(84.0, abs=EPS)


# --- T018: días con cultivo (Kc, Ks, ETc, ETa) ---


def test_crop_day_five_day_hand_calculation() -> None:
    """Perfil completo como zona radicular, p = 0,5 (AFA = 96 mm), W₀ = 100,5 mm, sin lluvia.

    Etapas 2/1/1/1 y Kc 0,4/1,0/0,6 con ET₀ = 5 mm/día → Kc = 0,4; 0,4; 1,0; 1,0; 0,6.
    ETc = 2; 2; 5; 5; 3 mm.
    Día 1: Ks = 1 (agotamiento 91,5 ≤ 96)   → ETa = 2        → W = 98,5
    Día 2: Ks = 1 (agotamiento 93,5 ≤ 96)   → ETa = 2        → W = 96,5
    Día 3: Ks = 1 (agotamiento 95,5 ≤ 96)   → ETa = 5        → W = 91,5
    Día 4: agotamiento 100,5 > 96 → Ks = 91,5/96 = 0,953125  → ETa = 4,765625  → W = 86,734375
    Día 5: Ks = 86,734375/96 = 0,903483…                     → ETa = 3/96·86,734375 = 2,71044921875
                                                              → W = 84,02392578125
    """
    crop = full_depth_crop((2, 1, 1, 1), (0.4, 1.0, 0.6))
    run = run_daily_balance(
        crop_timeline(crop),
        [0.0] * 5,
        [5.0] * 5,
        parcel(pct_for_storage(100.5)),
        record_days=True,
    )
    assert [round(d.demand_mm, 9) for d in run.daily] == [2.0, 2.0, 5.0, 5.0, 3.0]
    assert [d.ks for d in run.daily][:3] == [1.0, 1.0, 1.0]
    assert run.daily[3].ks == pytest.approx(0.953125, abs=1e-12)
    assert run.daily[4].ks == pytest.approx(86.734375 / 96.0, abs=1e-12)
    expected_eta = [2.0, 2.0, 5.0, 4.765625, 2.71044921875]
    for record, eta in zip(run.daily, expected_eta, strict=True):
        assert record.actual_mm == pytest.approx(eta, abs=EPS)
    expected_storage = [98.5, 96.5, 91.5, 86.734375, 84.02392578125]
    for record, storage in zip(run.daily, expected_storage, strict=True):
        assert record.storage_mm == pytest.approx(storage, abs=EPS)
    segment = run.segments[0]
    assert segment.demand_mm == pytest.approx(17.0, abs=EPS)  # ETm
    assert segment.actual_mm == pytest.approx(16.47607421875, abs=EPS)  # ETa
    assert segment.stress_days == 2
    assert run.closure_mm == pytest.approx(0.0, abs=EPS)


def test_crop_day_root_zone_at_wilting_point_gives_zero_ks_and_eta() -> None:
    crop = full_depth_crop((2, 1, 1, 1), (0.4, 1.0, 0.6))
    run = run_daily_balance(
        crop_timeline(crop), [0.0] * 5, [5.0] * 5, parcel(0.0), record_days=True
    )
    assert all(d.ks == 0.0 for d in run.daily)
    assert all(d.actual_mm == 0.0 for d in run.daily)
    assert run.segments[0].stress_days == 5
    assert run.segments[0].demand_mm == pytest.approx(17.0, abs=EPS)  # la demanda sigue existiendo


def test_crop_day_ks_is_one_while_water_is_plentiful() -> None:
    crop = full_depth_crop((2, 1, 1, 1), (0.4, 1.0, 0.6))
    run = run_daily_balance(
        crop_timeline(crop), [0.0] * 5, [5.0] * 5, parcel(100.0), record_days=True
    )
    assert all(d.ks == 1.0 for d in run.daily)
    assert run.segments[0].stress_days == 0
    assert run.crop_eta_mm == pytest.approx(run.segments[0].demand_mm, abs=EPS)


def test_crop_day_eta_never_exceeds_etc_or_available_water() -> None:
    crop = make_crop("maize", 1, 1, 7, (30, 40, 50, 30))
    rain, et0 = synthetic_weather(seed=3, n_days=150)
    run = run_daily_balance(crop_timeline(crop), rain, et0, parcel(30.0), record_days=True)
    assert len(run.daily) == 150
    for record in run.daily:
        assert record.actual_mm <= record.demand_mm + EPS
        assert record.actual_mm <= record.available_mm + EPS
        assert record.ks is not None and 0.0 <= record.ks <= 1.0
    assert run.segments[0].stress_days == sum(1 for d in run.daily if d.ks < 1.0)


def test_crop_day_etc_uses_the_kc_curve() -> None:
    crop = make_crop("maize", 1, 1, 7, (30, 40, 50, 30))
    run = run_daily_balance(
        crop_timeline(crop), [0.0] * 150, [4.0] * 150, parcel(100.0), record_days=True
    )
    assert run.daily[0].demand_mm == pytest.approx(0.30 * 4.0)
    assert run.daily[69].demand_mm == pytest.approx(1.20 * 4.0)  # día 70: Kc medio
    assert run.daily[149].demand_mm == pytest.approx(0.35 * 4.0)


def test_crop_day_rain_during_the_cycle_replenishes_the_active_zone() -> None:
    crop = full_depth_crop((2, 1, 1, 1), (0.4, 1.0, 0.6))
    rain = [0.0, 0.0, 0.0, 60.0, 0.0]
    run = run_daily_balance(
        crop_timeline(crop), rain, [5.0] * 5, parcel(pct_for_storage(100.5)), record_days=True
    )
    # Día 4: Ks se calcula con el estado de la mañana (91,5 mm) → 0,953125; la lluvia no lo cambia.
    assert run.daily[3].ks == pytest.approx(0.953125, abs=1e-12)
    assert run.daily[3].available_mm == pytest.approx(91.5 + 60.0, abs=EPS)
    assert run.daily[4].ks == 1.0  # al día siguiente el perfil está repuesto
    assert run.closure_mm == pytest.approx(0.0, abs=EPS)


# --- T019: transferencia entre segmentos y crecimiento radicular ---


def test_transfer_end_storage_is_the_start_storage_of_the_next_segment() -> None:
    timeline = cal.build_timeline(
        cal.build_window(2008, 1, 7), invariant_rotations()["zero_day_fallow"]
    )
    kinds = [segment.is_crop for segment in timeline.segments]
    assert kinds == [False, True, False, True, True, False]  # 3 cultivos y 3 barbechos
    rain, et0 = synthetic_weather(seed=11, n_days=timeline.n_days)
    run = run_daily_balance(timeline, rain, et0, parcel(50.0))
    assert len(run.segments) == 6
    for previous, following in zip(run.segments, run.segments[1:], strict=False):
        assert previous.storage_at_end_mm == following.storage_at_start_mm
    assert run.segments[0].storage_at_start_mm == pytest.approx(run.initial_storage_mm, abs=EPS)
    assert run.segments[-1].storage_at_end_mm == run.final_storage_mm


def test_transfer_plan_case_maize_end_to_fallow_start() -> None:
    """El maíz termina con 31,2 mm; al empezar el barbecho, 3,9 mm quedan en la capa de 0,15 m."""
    crop = full_depth_crop((1, 1, 1, 1), (0.0, 0.0, 0.0))
    timeline = Timeline(
        (
            CropSegment(crop, START, START + timedelta(days=3)),
            FallowSegment(START + timedelta(days=4), START + timedelta(days=5)),
        )
    )
    run = run_daily_balance(
        timeline, [0.0] * 6, [0.0] * 6, parcel(pct_for_storage(31.2)), record_days=True
    )
    assert run.segments[0].storage_at_end_mm == pytest.approx(31.2, abs=EPS)
    assert run.segments[1].storage_at_start_mm == run.segments[0].storage_at_end_mm
    first_fallow_day = run.daily[4]
    assert first_fallow_day.active_storage_mm == pytest.approx(3.9, abs=EPS)
    assert first_fallow_day.lower_storage_mm == pytest.approx(27.3, abs=EPS)
    assert first_fallow_day.storage_mm == pytest.approx(31.2, abs=EPS)


def test_transfer_shallow_roots_cannot_use_deep_water_until_they_grow() -> None:
    """CL-16: capa superficial seca y agua debajo → el cultivo sufre estrés al nacer y, al crecer
    la raíz, incorpora el agua de la zona inferior."""
    crop = make_crop("maize", 1, 1, 7, (30, 40, 50, 30), zr_initial_m=0.25, zr_max_m=1.2)
    timeline = Timeline(
        (
            FallowSegment(START, START + timedelta(days=59)),
            CropSegment(crop, START + timedelta(days=60), START + timedelta(days=209)),
        )
    )
    n_days = timeline.n_days
    run = run_daily_balance(
        timeline,
        [0.0] * n_days,
        [6.0] * 60 + [4.0] * 150,
        parcel(50.0, fallow_kc_base=1.0),
        record_days=True,
    )
    last_fallow, crop_day_1 = run.daily[59], run.daily[60]
    assert last_fallow.active_storage_mm == pytest.approx(0.0, abs=EPS)  # capa seca
    assert last_fallow.lower_storage_mm == pytest.approx(84.0, abs=EPS)  # agua debajo
    # Día 1 del cultivo: la zona pasa de 0,15 a 0,25 m e incorpora 84·0,10/1,05 = 8 mm. Con
    # TAW = 40 mm y p = 0,55, Ks = 8/(0,45·40) = 0,444 y el cultivo consume Ks·ETc = 0,533 mm.
    assert crop_day_1.ks == pytest.approx(8.0 / (0.45 * 40.0), abs=1e-9)
    assert crop_day_1.active_storage_mm + crop_day_1.actual_mm == pytest.approx(8.0, abs=EPS)
    assert crop_day_1.demand_mm == pytest.approx(0.30 * 4.0, abs=EPS)  # ETc = Kc inicial × ET₀
    assert crop_day_1.actual_mm == pytest.approx(crop_day_1.ks * crop_day_1.demand_mm, abs=EPS)
    assert crop_day_1.lower_storage_mm == pytest.approx(76.0, abs=EPS)
    assert run.segments[1].stress_days > 0
    # A medida que la raíz profundiza, el agua de la zona inferior pasa a ser accesible.
    crop_day_70 = run.daily[60 + 69]
    assert crop_day_70.active_depth_m == pytest.approx(1.2, abs=EPS)
    assert crop_day_70.lower_storage_mm == pytest.approx(0.0, abs=EPS)
    assert crop_day_70.lower_storage_mm < crop_day_1.lower_storage_mm


def test_transfer_zero_day_fallow_between_crops_keeps_the_water() -> None:
    """CL-17: soja de segunda el día siguiente a la cosecha del trigo, sin barbecho."""
    timeline = cal.build_timeline(
        cal.build_window(2008, 1, 7), invariant_rotations()["zero_day_fallow"]
    )
    rain, et0 = synthetic_weather(seed=5, n_days=timeline.n_days)
    run = run_daily_balance(timeline, rain, et0, parcel(50.0), record_days=True)
    wheat, soy = run.segments[3], run.segments[4]
    assert (wheat.crop_code, soy.crop_code) == ("wheat", "soybean_second")
    assert soy.start == wheat.end + timedelta(days=1)
    assert soy.storage_at_start_mm == wheat.storage_at_end_mm


def test_transfer_the_active_zone_follows_the_segment_kind() -> None:
    timeline = cal.build_timeline(
        cal.build_window(2008, 1, 7), invariant_rotations()["long_fallow"]
    )
    rain, et0 = synthetic_weather(seed=2, n_days=timeline.n_days)
    run = run_daily_balance(timeline, rain, et0, parcel(50.0), record_days=True)
    for record in run.daily:
        if not record.is_crop:
            assert record.active_depth_m == 0.15
        else:
            assert 0.25 - EPS <= record.active_depth_m <= 1.2 + EPS


# --- T020: cierre de masa y error de integridad ---


def test_closure_of_a_731_day_run_is_within_tolerance() -> None:
    window = cal.build_window(2011, 1, 7)
    assert window.n_days == 731
    timeline = cal.build_timeline(window, invariant_rotations()["zero_day_fallow"])
    rain, et0 = synthetic_weather(seed=21, n_days=731)
    run = run_daily_balance(timeline, rain, et0, parcel(50.0), record_days=True)
    assert abs(run.closure_mm) <= 0.01
    balance = run.final_storage_mm - run.initial_storage_mm
    flows = run.precipitation_mm - run.crop_eta_mm - run.fallow_evaporation_mm - run.excess_lost_mm
    assert balance == pytest.approx(flows, abs=0.01)
    assert run.precipitation_mm == pytest.approx(sum(rain), abs=1e-6)
    assert len(run.daily) == 731


def test_closure_run_exposes_the_required_totals() -> None:
    run = run_daily_balance(fallow_timeline(2), [10.0, 0.0], [5.0, 5.0], parcel(50.0))
    for name in (
        "initial_storage_mm",
        "final_storage_mm",
        "precipitation_mm",
        "crop_eta_mm",
        "fallow_evaporation_mm",
        "excess_lost_mm",
        "closure_mm",
    ):
        assert isinstance(getattr(run, name), float), name
    assert run.daily == ()  # sin record_days no se guarda la serie diaria (CA-15.5)


def test_closure_integrity_error_on_forced_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    def leaky_redistribute(w_active, w_lower, z_old, z_new, depth):
        return w_active - 5.0, w_lower  # pierde 5 mm sin declararlos

    monkeypatch.setattr(wb, "redistribute", leaky_redistribute)
    with pytest.raises(CalculationIntegrityError):
        run_daily_balance(fallow_timeline(3), [10.0] * 3, [1.0] * 3, parcel(80.0))


def test_closure_run_level_tolerance_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wb, "MASS_CLOSURE_TOLERANCE_MM", -1.0)  # cualquier cierre "excede"
    with pytest.raises(CalculationIntegrityError, match="cierre de masa") as error:
        run_daily_balance(fallow_timeline(3), [10.0] * 3, [1.0] * 3, parcel(50.0))
    assert error.value.closure_mm is not None


def test_closure_rejects_invalid_inputs() -> None:
    timeline = fallow_timeline(3)
    with pytest.raises(ValueError, match="3 valores"):
        run_daily_balance(timeline, [0.0] * 2, [0.0] * 3, parcel(50.0))
    with pytest.raises(ValueError, match="lluvia"):
        run_daily_balance(timeline, [0.0, -1.0, 0.0], [0.0] * 3, parcel(50.0))
    with pytest.raises(ValueError, match="ET₀"):
        run_daily_balance(timeline, [0.0] * 3, [0.0, -0.1, 0.0], parcel(50.0))
    with pytest.raises(ValueError, match="θPMP"):
        run_daily_balance(timeline, [0.0] * 3, [0.0] * 3, replace(BASE, theta_wp_m3_m3=0.3))
    with pytest.raises(ValueError, match="humedad"):
        run_daily_balance(timeline, [0.0] * 3, [0.0] * 3, parcel(120.0))
    with pytest.raises(ValueError, match="segmentos"):
        run_daily_balance(Timeline(()), [], [], parcel(50.0))


def test_closure_rejects_a_crop_segment_with_the_wrong_length() -> None:
    crop = make_crop("maize", 1, 1, 7, (30, 40, 50, 30))  # 150 días
    with pytest.raises(ValueError, match="150"):
        run_daily_balance(crop_timeline(crop, 100), [0.0] * 100, [1.0] * 100, parcel(50.0))


@pytest.mark.parametrize(
    ("w_active_mm", "ks"),
    [(100.0, 1.0), (50.0, 1.0), (25.0, 0.5), (10.0, 0.2), (0.0, 0.0)],
)
def test_crop_day_ks_is_linear_between_the_readily_available_water_and_the_wilting_point(
    w_active_mm: float, ks: float
) -> None:
    """CA-8.9: Ks = 1 hasta agotar p·ADT y luego decrece linealmente hasta 0 (ec. 84)."""
    assert wb._stress_coefficient(w_active_mm, 100.0, 0.5) == pytest.approx(ks, abs=EPS)


def test_fallow_residue_cover_stays_constant_during_the_whole_fallow() -> None:
    """CA-8.11: sin descomposición, la demanda diaria no cambia aunque pasen los días."""
    run = run_daily_balance(
        fallow_timeline(60, 60.0), [0.0] * 60, [5.0] * 60, parcel(100.0), record_days=True
    )
    expected = 0.20 * 5.0 * wb.residue_factor(60.0)
    assert all(d.demand_mm == pytest.approx(expected, abs=EPS) for d in run.daily)
