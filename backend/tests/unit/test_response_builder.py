"""Pruebas del constructor de la respuesta (T045).

Cubren CA-1.11 (coordenadas fuera de San Luis), CA-6.7 (sustituciones por escenario), CA-10.9
(margen no calculado), CA-12.4 (escenarios excluidos), CA-13.1, CA-13.2 (procedencia), CA-14.1
(alcance de los supuestos), CA-14.4 (agrupación), CA-15.1–CA-15.5 (contenido de la respuesta),
CA-16.3 (todos los escenarios bloqueados), CA-16.5 (error de integridad sin resultados parciales),
CA-17.2, CA-17.3 y CA-17.5 (advertencias). Además, el redondeo del plan §5.1.
"""

from __future__ import annotations

import dataclasses
import json
import math
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.core import messages
from app.core.exceptions import CalculationIntegrityError
from app.models.response import SimulationResponse
from app.services import response_builder as rb
from app.services.simulation_service import SimulationOutcome
from tests.builders.requests import plan_request
from tests.builders.simulation import run

REQUEST_ID = "3f2b8c1e-7d4a-4f6b-9a2e-5c8d1b0e7f43"
COMPUTED_AT = datetime(2026, 11, 15, 14, 3, 22, tzinfo=UTC)
RAIN_GAP = {"PRECTOTCORR": [date(2018, 3, 4)], "ALLSKY_SFC_SW_DWN": [date(2009, 1, 17)]}


def build(outcome: SimulationOutcome) -> SimulationResponse:
    return rb.build_response(outcome, request_id=REQUEST_ID, computed_at=COMPUTED_AT)


@pytest.fixture(scope="module")
def outcome() -> SimulationOutcome:
    return run(fill_dates=RAIN_GAP)[0]


@pytest.fixture(scope="module")
def response(outcome: SimulationOutcome) -> SimulationResponse:
    return build(outcome)


def with_run(outcome: SimulationOutcome, index: int, **changes: Any) -> SimulationOutcome:
    """Copia del resultado con una corrida modificada."""
    runs = list(outcome.runs)
    runs[index] = dataclasses.replace(runs[index], **changes)
    return dataclasses.replace(outcome, runs=tuple(runs))


def with_balance(outcome: SimulationOutcome, **changes: Any) -> SimulationOutcome:
    balance = dataclasses.replace(outcome.runs[0].balance, **changes)
    return with_run(outcome, 0, balance=balance)


def decimals(value: float) -> int:
    text = repr(value)
    return len(text.split(".")[1].rstrip("0")) if "." in text else 0


# --- Estructura general ---


def test_response_has_the_thirteen_blocks_and_identification(response: SimulationResponse) -> None:
    assert set(response.model_dump()) == set(SimulationResponse.model_fields)
    assert (response.contract_version, response.model_version) == ("1.0", "0.1.0")
    assert response.request_id == REQUEST_ID and response.computed_at == COMPUTED_AT
    assert response.currency == "USD"


def test_response_serializes_to_json_and_validates_again(response: SimulationResponse) -> None:
    again = SimulationResponse.model_validate(json.loads(response.model_dump_json()))
    assert again == response
    assert "NaN" not in response.model_dump_json() and "Infinity" not in response.model_dump_json()


def test_response_has_no_daily_series(response: SimulationResponse) -> None:
    """CA-15.5: totales y fechas puntuales, nada diario."""
    text = response.model_dump_json()
    assert "daily" not in text
    assert len(text) < 200_000  # 730 días por escenario × 4 corridas serían varios MB


def test_results_cover_each_rotation_and_computed_scenario(response: SimulationResponse) -> None:
    assert [(r.rotation_id, r.start_year) for r in response.results] == [
        ("A", 2008),
        ("B", 2008),
        ("A", 2011),
        ("B", 2011),
    ]
    first = response.results[0]
    assert first.water_balance.initial_storage_mm == 96.0
    assert first.water_balance.et0_mm == response.scenarios[0].et0_total_mm
    assert abs(first.water_balance.mass_balance_error_mm) <= 0.01


def test_crop_results_include_dates_storage_ratio_and_yield(response: SimulationResponse) -> None:
    maize, rye, soybean = response.results[0].crops
    assert (maize.sowing_date, maize.cycle_end_date) == (date(2008, 10, 15), date(2009, 3, 13))
    assert maize.yield_t_ha is not None and 0 <= maize.yield_t_ha <= 9.0
    assert 0 < maize.eta_etm_ratio <= 1 and maize.relative_yield is not None
    assert rye.yield_t_ha is None and rye.yield_note == "No aplica (cultivo de cobertura)."
    assert rye.economics.gross_margin_label == "Margen bruto negativo"
    assert soybean.sowing_date == date(2009, 11, 15)


def test_soil_exposure_states_the_rule_and_the_source(response: SimulationResponse) -> None:
    exposure = response.results[0].soil_exposure
    assert exposure.wind_variable == "WS2M_MAX" and exposure.threshold_ms == 8.0
    assert "8,0 m/s" in exposure.rule and "sin cultivo vivo" in exposure.rule
    assert exposure.threshold_source == messages.WIND_THRESHOLD_SOURCE
    assert "suelo desnudo" in exposure.note
    assert exposure.live_crop_days + exposure.no_live_crop_days == exposure.window_days


# --- Redondeo (plan §5.1) ---


def test_rounding_rules() -> None:
    assert rb.round_mm(2.26) == 2.3 and rb.round_mm(2.24) == 2.2
    assert rb.round_ratio(0.65249) == 0.652 and rb.round_ratio(0.6525) in (0.652, 0.653)
    assert rb.round_t_ha(5.0848) == 5.08 and rb.round_t_ha(6.3151) == 6.32
    assert rb.round_money(915.264) == 915.26 and rb.round_money(295.265) in (295.26, 295.27)
    assert rb.round_mm(2.26) != 2.26


def test_rounding_keeps_none() -> None:
    assert rb.round_t_ha(None) is None and rb.round_ratio(None) is None
    assert rb.round_money(None) is None


def test_rounding_never_returns_negative_zero() -> None:
    assert math.copysign(1.0, rb.round_mm(-0.04)) == 1.0
    assert math.copysign(1.0, rb.round_money(-0.001)) == 1.0


def test_every_value_in_the_response_respects_its_decimals(response: SimulationResponse) -> None:
    for result in response.results:
        balance = result.water_balance
        for value in (
            balance.initial_storage_mm,
            balance.final_storage_mm,
            balance.precipitation_mm,
            balance.et0_mm,
            balance.crop_eta_mm,
            balance.fallow_evaporation_mm,
            balance.excess_lost_mm,
            balance.mass_balance_error_mm,
        ):
            assert decimals(value) <= 1
        for crop in result.crops:
            assert decimals(crop.etm_mm) <= 1 and decimals(crop.eta_mm) <= 1
            assert decimals(crop.storage_at_sowing_mm) <= 1
            assert crop.eta_etm_ratio is None or decimals(crop.eta_etm_ratio) <= 3
            assert crop.yield_t_ha is None or decimals(crop.yield_t_ha) <= 2
            for money in (
                crop.economics.income_per_ha,
                crop.economics.direct_costs_per_ha,
                crop.economics.gross_margin_per_ha,
            ):
                assert money is None or decimals(money) <= 2
    for ranges in response.ranges:
        for crop in ranges.crops:
            if crop.yield_t_ha:
                assert decimals(crop.yield_t_ha.median) <= 2
            if crop.eta_etm_ratio:
                assert decimals(crop.eta_etm_ratio.median) <= 3
        assert ranges.gross_margin_per_ha is None or decimals(ranges.gross_margin_per_ha.min) <= 2
    assert all(decimals(c.gross_margin_difference_per_ha) <= 2 for c in response.comparisons)


def test_mass_balance_error_is_computed_unrounded_and_rounded_at_the_end(
    outcome: SimulationOutcome,
) -> None:
    assert (
        build(with_balance(outcome, closure_mm=0.004))
        .results[0]
        .water_balance.mass_balance_error_mm
        == 0.0
    )
    assert (
        build(with_balance(outcome, closure_mm=0.0079))
        .results[0]
        .water_balance.mass_balance_error_mm
        == 0.0
    )
    assert (
        build(with_balance(outcome, closure_mm=-0.0001))
        .results[0]
        .water_balance.mass_balance_error_mm
        == 0.0
    )


# --- Integridad (CA-16.5, plan §6.2) ---


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nan_or_infinity_in_a_balance_raises_an_integrity_error(
    outcome: SimulationOutcome, bad: float
) -> None:
    for field in ("precipitation_mm", "crop_eta_mm", "excess_lost_mm", "closure_mm"):
        with pytest.raises(CalculationIntegrityError):
            build(with_balance(outcome, **{field: bad}))


def test_nan_in_a_scenario_total_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    scenarios = list(outcome.scenarios)
    scenarios[0] = dataclasses.replace(scenarios[0], et0_total_mm=math.nan)
    with pytest.raises(CalculationIntegrityError):
        build(dataclasses.replace(outcome, scenarios=tuple(scenarios)))


def test_nan_in_a_yield_or_margin_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    crop = outcome.runs[0].crops[0]
    bad_yield = dataclasses.replace(crop.yield_result, yield_t_ha=math.nan)
    crops = (dataclasses.replace(crop, yield_result=bad_yield), *outcome.runs[0].crops[1:])
    with pytest.raises(CalculationIntegrityError):
        build(with_run(outcome, 0, crops=crops))
    bad_margin = dataclasses.replace(crop.economics, gross_margin_per_ha=math.inf)
    crops = (dataclasses.replace(crop, economics=bad_margin), *outcome.runs[0].crops[1:])
    with pytest.raises(CalculationIntegrityError):
        build(with_run(outcome, 0, crops=crops))


def test_nan_in_a_resolved_parameter_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    rotation = outcome.resolved.rotations[0]
    crop = rotation.crops[0]
    parameters = {
        **crop.parameters,
        "kc_mid": dataclasses.replace(crop.parameters["kc_mid"], value=math.nan),
    }
    bad_crop = dataclasses.replace(crop, parameters=parameters)
    bad_rotation = dataclasses.replace(rotation, crops=(bad_crop, *rotation.crops[1:]))
    resolved = dataclasses.replace(
        outcome.resolved, rotations=(bad_rotation, *outcome.resolved.rotations[1:])
    )
    with pytest.raises(CalculationIntegrityError):
        build(dataclasses.replace(outcome, resolved=resolved))


def test_storage_above_capacity_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    with pytest.raises(CalculationIntegrityError) as caught:
        build(with_balance(outcome, final_storage_mm=192.5))
    assert "capacidad" in str(caught.value)


def test_negative_storage_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    with pytest.raises(CalculationIntegrityError):
        build(with_balance(outcome, final_storage_mm=-1.0))


def test_a_yield_above_ym_or_negative_raises_an_integrity_error(outcome: SimulationOutcome) -> None:
    crop = outcome.runs[0].crops[0]
    for changes in ({"relative_yield": 1.2}, {"yield_t_ha": -0.5}):
        bad = dataclasses.replace(crop.yield_result, **changes)
        crops = (dataclasses.replace(crop, yield_result=bad), *outcome.runs[0].crops[1:])
        with pytest.raises(CalculationIntegrityError):
            build(with_run(outcome, 0, crops=crops))


# --- Escenarios, bloqueos y sustituciones ---


def test_blocked_scenario_lists_its_reason_with_variable_date_and_spanish_message(
    response: SimulationResponse,
) -> None:
    blocked = next(s for s in response.scenarios if s.start_year == 2017)
    assert blocked.status == "blocked" and blocked.precipitation_total_mm is None
    (reason,) = blocked.blocked_reasons
    assert (reason.code, reason.variable, reason.dates) == (
        "MISSING_PRECIPITATION",
        "PRECTOTCORR",
        [date(2018, 3, 4)],
    )
    assert reason.message == messages.BLOCK_REASONS["MISSING_PRECIPITATION"]
    assert (reason.first_date, reason.last_date) == (date(2018, 3, 4), date(2018, 3, 4))


def test_substituted_days_show_variable_method_count_and_dates(
    response: SimulationResponse,
) -> None:
    """CA-6.7."""
    computed = next(s for s in response.scenarios if s.start_year == 2008)
    (item,) = computed.substituted_days
    assert (item.variable, item.count, item.dates) == ("ALLSKY_SFC_SW_DWN", 1, [date(2009, 1, 17)])
    assert item.method == "Hargreaves (FAO-56, ec. 50), kRs = 0,16"
    assert (computed.window_start, computed.window_end, computed.days) == (
        date(2008, 7, 1),
        date(2010, 6, 30),
        730,
    )


def test_ranges_label_and_excluded_scenarios(response: SimulationResponse) -> None:
    for ranges in response.ranges:
        assert ranges.label == messages.RANGE_LABEL
        assert ranges.scenarios_excluded == [2017] and ranges.n_scenarios == 2
        assert ranges.gross_margin_per_ha is not None and ranges.gross_margin_per_ha.n == 2
        assert ranges.gross_margin_per_ha.min <= ranges.gross_margin_per_ha.median


def test_comparisons_are_descriptive(response: SimulationResponse) -> None:
    assert [
        (c.start_year, c.minuend_rotation_id, c.subtrahend_rotation_id)
        for c in response.comparisons
    ] == [
        (2008, "B", "A"),
        (2011, "B", "A"),
    ]
    assert "no indica qué rotación conviene" in response.comparisons[0].label
    assert "(B − A)" in response.comparisons[0].label


def test_not_computed_margin_is_null_with_its_reason() -> None:
    """CA-10.9 y CA-10.4: sin precio no hay margen; nunca 0."""
    payload = plan_request()
    del payload["rotations"][1]["crops"][0]["economics"]["price_per_t"]
    built = build(run(payload, fill_dates=RAIN_GAP)[0])
    result_b = next(r for r in built.results if r.rotation_id == "B")
    assert result_b.rotation_economics.status == "not_computed"
    assert result_b.rotation_economics.gross_margin_per_ha is None
    (missing,) = result_b.rotation_economics.crops_missing_economics
    assert (missing.position, missing.crop_code, missing.reason) == (
        1,
        "maize",
        "missing_economic_data",
    )
    assert "price_per_t" in missing.missing_fields
    ranges_b = next(r for r in built.ranges if r.rotation_id == "B")
    assert ranges_b.gross_margin_per_ha is None and ranges_b.margin_not_computed_years == [
        2008,
        2011,
    ]
    assert built.comparisons == []


# --- Procedencia ---


def test_provenance_has_label_variables_and_location(response: SimulationResponse) -> None:
    provenance = response.provenance
    assert provenance is not None
    assert provenance.label == messages.CELL_SCALE_LABEL
    assert provenance.requested_location.latitude_deg == -33.68
    assert provenance.source_location.elevation_m == pytest.approx(699.34)
    assert (provenance.date_range.start, provenance.date_range.end) == (
        date(2008, 7, 1),
        date(2019, 6, 30),
    )
    assert {v.code: v.missing_days for v in provenance.variables}["PRECTOTCORR"] == 1
    assert provenance.queried_at.tzinfo is not None


def test_provenance_is_null_when_no_window_was_covered_and_everything_is_blocked() -> None:
    payload = plan_request()
    payload["window"]["start_years"] = [1982, 1983]
    built = build(run(payload)[0])
    assert built.provenance is None
    assert built.results == [] and [s.status for s in built.scenarios] == ["blocked", "blocked"]
    assert built.comparisons == []
    codes = {w.code for w in built.warnings}
    assert "SCENARIOS_BLOCKED" in codes
    assert all(r.n_scenarios == 0 for r in built.ranges)
    assert json.loads(built.model_dump_json())["provenance"] is None


def test_all_blocked_after_querying_still_reports_provenance() -> None:
    built = build(
        run(fill_dates={"PRECTOTCORR": [date(2008, 7, 5), date(2011, 7, 5), date(2017, 7, 5)]})[0]
    )
    assert built.provenance is not None and built.results == []


# --- Entrada resuelta ---


def test_resolved_input_shows_values_with_origin_and_the_profile_capacity(
    response: SimulationResponse,
) -> None:
    parcel = response.resolved_input.parcel
    assert (parcel.profile_capacity_mm, parcel.initial_storage_mm) == (192.0, 96.0)
    assert (parcel.fallow_kc_base.value, parcel.fallow_kc_base.origin) == (0.2, "team_default")
    assert parcel.fallow_evaporation_layer_m.value == 0.15
    maize = response.resolved_input.rotations[0].crops[0]
    assert maize.parameters["ky"].origin == "fao_reference"
    assert maize.parameters["kc_mid"].origin == "user"
    assert maize.parameters["root_depth_max_m"].value == 1.2
    assert maize.calibrated is False
    assert response.resolved_input.window.start_years == [2008, 2011, 2017]


# --- Supuestos ---


def test_assumption_scopes_become_structured_objects() -> None:
    crop = rb.assumption_scope("crop", "A/1/ky")
    assert (crop.level, crop.rotation_id, crop.position, crop.parameter) == ("crop", "A", 1, "ky")
    fallow = rb.assumption_scope("fallow", "B/3")
    assert (fallow.level, fallow.rotation_id, fallow.after_position) == ("fallow", "B", 3)
    assert rb.assumption_scope("fallow", "B/0").after_position == 0
    scenario = rb.assumption_scope("scenario", "2008")
    assert (scenario.level, scenario.start_year) == ("scenario", 2008)
    assert rb.assumption_scope("request", None).level == "request"
    assert rb.assumption_scope("rotation", "C").rotation_id == "C"
    yield_scope = rb.assumption_scope("crop", "A/2/yield@2011")
    assert (yield_scope.parameter, yield_scope.start_year, yield_scope.position) == (
        "yield_t_ha",
        2011,
        2,
    )


@pytest.mark.parametrize(
    ("scope", "scope_id"),
    [("crop", "A/1"), ("crop", None), ("fallow", "B"), ("scenario", "dos mil"), ("galaxy", "x")],
)
def test_an_unreadable_scope_is_an_integrity_error(scope: str, scope_id: str | None) -> None:
    with pytest.raises(CalculationIntegrityError):
        rb.assumption_scope(scope, scope_id)


def test_assumptions_in_the_response_have_structured_scope_and_grouping(
    response: SimulationResponse,
) -> None:
    by_key = {(a.code, a.scope.level): a for a in response.assumptions}
    ky = next(
        a
        for a in response.assumptions
        if a.code == "FAO_REFERENCE_VALUE"
        and a.scope.parameter == "ky"
        and a.scope.rotation_id == "A"
    )
    assert (ky.scope.level, ky.scope.position, ky.value, ky.origin) == (
        "crop",
        1,
        1.25,
        "fao_reference",
    )
    assert ky.count is None and ky.dates is None
    radiation = next(
        a
        for a in response.assumptions
        if a.code == "SUBST_RADIATION_HARGREAVES" and a.scope.start_year == 2008
    )
    assert (radiation.count, radiation.dates) == (1, [date(2009, 1, 17)])
    assert ("RAINFED_NO_IRRIGATION", "request") in by_key
    assert all(a.description for a in response.assumptions)


# --- Advertencias ---


def test_four_fixed_warnings_are_always_present_in_order() -> None:
    clean = build(run()[0])
    assert [w.code for w in clean.warnings] == [
        "HISTORICAL_DESCRIPTIVE",
        "UNCALIBRATED_PARAMETERS",
        "CELL_SCALE_DATA",
        "NOT_A_RECOMMENDATION",
    ]
    for warning in clean.warnings:
        assert warning.message == messages.WARNINGS[warning.code]


def test_substitutions_and_blocked_warnings_appear_only_when_they_apply(
    response: SimulationResponse,
) -> None:
    by_code = {w.code: w.message for w in response.warnings}
    assert by_code["SUBSTITUTIONS_PRESENT"].startswith(messages.WARNINGS["SUBSTITUTIONS_PRESENT"])
    assert "2008" in by_code["SUBSTITUTIONS_PRESENT"]
    assert by_code["SCENARIOS_BLOCKED"].startswith(messages.WARNINGS["SCENARIOS_BLOCKED"])
    assert by_code["SCENARIOS_BLOCKED"].endswith("2017.")
    only_blocked = build(run(fill_dates={"PRECTOTCORR": [date(2018, 3, 4)]})[0])
    assert "SUBSTITUTIONS_PRESENT" not in {w.code for w in only_blocked.warnings}
    clean = build(run()[0])
    assert {"SUBSTITUTIONS_PRESENT", "SCENARIOS_BLOCKED"}.isdisjoint(
        {w.code for w in clean.warnings}
    )


def test_outside_san_luis_warning_depends_on_the_coordinates() -> None:
    assert rb.is_outside_san_luis(-31.42, -64.18)  # Córdoba
    assert not rb.is_outside_san_luis(-33.68, -65.47)  # Villa Mercedes
    payload = plan_request()
    payload["parcel"].update(latitude_deg=-31.42, longitude_deg=-64.18)
    outside = build(run(payload)[0])
    assert "OUTSIDE_SAN_LUIS" in {w.code for w in outside.warnings}
    inside = build(run()[0])
    assert "OUTSIDE_SAN_LUIS" not in {w.code for w in inside.warnings}


def test_warning_texts_come_from_messages_and_avoid_forbidden_terms(
    response: SimulationResponse,
) -> None:
    for warning in response.warnings:
        lowered = warning.message.lower()
        assert not any(term in lowered for term in messages.FORBIDDEN_TERMS), warning.code


def test_response_texts_contain_no_forbidden_term(response: SimulationResponse) -> None:
    """CA-17.1 y CA-17.5 sobre toda la respuesta (salvo el rótulo literal de los rangos)."""
    text = response.model_dump_json().lower()
    for phrase in messages.ALLOWED_PHRASES:
        text = text.replace(phrase.lower(), "")
    for term in messages.FORBIDDEN_TERMS:
        assert term not in text, term
