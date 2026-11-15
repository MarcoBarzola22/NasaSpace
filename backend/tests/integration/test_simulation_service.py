"""Pruebas de integración del servicio de simulación con ``httpx.MockTransport`` (T043, T044).

Cubren CA-4.5 (cobertura), CA-5.1 (una sola consulta), CA-5.3 (solicitud inválida sin consulta),
CA-6.3 y CA-6.7 (bloqueo y sustituciones por escenario), CA-7.2, CA-8.16 (cierre de masa),
CA-11.4 (viento sin dato), CA-12.4 (escenarios excluidos de los rangos), CA-15.4 (diferencias de
margen), CA-16.2 y CA-16.3 (escenarios bloqueados) y CA-16.5 (sin resultados parciales).
El reloj se fija en 2026-11-15; las series son sintéticas.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import CalculationIntegrityError, InputValidationError
from app.domain import missing_data as md
from app.models.request import SimulationRequest
from app.services import simulation_service as service
from app.services.catalog_service import load_catalog
from app.services.power_client import PowerClient
from app.services.simulation_service import SimulationOutcome, simulate
from tests.builders.power_payload import power_payload
from tests.builders.requests import plan_request

TODAY = date(2026, 11, 15)
CATALOG = load_catalog()
SETTINGS = Settings()


class Power:
    """Servidor simulado de NASA POWER: devuelve el rango pedido con las opciones indicadas."""

    def __init__(self, **options: Any) -> None:
        self.options = options
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = request.url.params
        start = date.fromisoformat(
            f"{params['start'][:4]}-{params['start'][4:6]}-{params['start'][6:]}"
        )
        end = date.fromisoformat(f"{params['end'][:4]}-{params['end'][4:6]}-{params['end'][6:]}")
        return httpx.Response(200, json=power_payload(start, end, **self.options))


def run(
    payload: dict[str, Any] | None = None, power: Callable[..., Any] | None = None, **options: Any
) -> tuple[SimulationOutcome, Power]:
    server = power if isinstance(power, Power) else Power(**options)
    client = PowerClient(SETTINGS, transport=httpx.MockTransport(server))
    request = SimulationRequest.model_validate(payload or plan_request())
    outcome = asyncio.run(
        simulate(request, catalog=CATALOG, settings=SETTINGS, power_client=client, today=TODAY)
    )
    return outcome, server


RAIN_GAP = {"PRECTOTCORR": [date(2018, 3, 4)], "ALLSKY_SFC_SW_DWN": [date(2009, 1, 17)]}


def by_year(outcome: SimulationOutcome) -> dict[int, service.ScenarioOutcome]:
    return {scenario.start_year: scenario for scenario in outcome.scenarios}


# --- T043: escenarios ---


def test_scenarios_blocked_computed_and_substituted() -> None:
    """2017 queda bloqueado por la lluvia; 2008 se calcula con 1 sustitución de radiación."""
    outcome, _ = run(fill_dates=RAIN_GAP)
    scenarios = by_year(outcome)
    blocked = scenarios[2017]
    assert blocked.status == "blocked"
    (block,) = blocked.blocks
    assert block.code == "MISSING_PRECIPITATION"
    assert block.dates == (date(2018, 3, 4),)
    assert blocked.precipitation_total_mm is None and blocked.et0_total_mm is None

    computed = scenarios[2008]
    assert computed.status == "computed"
    (substitution,) = computed.substitutions
    assert substitution.variable == "ALLSKY_SFC_SW_DWN"
    assert substitution.dates == (date(2009, 1, 17),)
    assert computed.precipitation_total_mm == pytest.approx(730 * 1.5)

    assert scenarios[2011].status == "computed"
    assert scenarios[2011].n_days == 731
    assert scenarios[2008].n_days == 730 and scenarios[2017].n_days == 730


def test_scenarios_a_single_call_covers_every_window() -> None:
    """CA-5.1: una consulta, de la ventana más temprana a la más tardía."""
    outcome, server = run(fill_dates=RAIN_GAP)
    assert len(server.requests) == 1
    params = server.requests[0].url.params
    assert (params["start"], params["end"]) == ("20080701", "20190630")
    assert params["latitude"] == "-33.6800" and params["longitude"] == "-65.4700"
    assert outcome.provenance is not None
    assert (outcome.provenance.date_start, outcome.provenance.date_end) == (
        date(2008, 7, 1),
        date(2019, 6, 30),
    )


def test_scenarios_et0_is_computed_once_per_scenario_even_with_two_rotations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original = service.compute_et0_series

    def counting(weather: Any, elevation_m: float) -> Any:
        calls.append(len(weather))
        return original(weather, elevation_m)

    monkeypatch.setattr(service, "compute_et0_series", counting)
    outcome, _ = run(fill_dates=RAIN_GAP)
    assert len(plan_request()["rotations"]) == 2
    assert calls == [730, 731]  # 2008 y 2011; 2017 está bloqueado
    assert len(outcome.runs) == 4


def test_provenance_counts_the_missing_days_per_variable() -> None:
    outcome, _ = run(fill_dates=RAIN_GAP)
    assert outcome.provenance is not None
    missing = {v.code: v.missing_days for v in outcome.provenance.variables}
    assert missing["PRECTOTCORR"] == 1 and missing["ALLSKY_SFC_SW_DWN"] == 1
    assert missing["T2M_MAX"] == 0


def test_scenarios_invalid_request_is_rejected_without_calling_nasa() -> None:
    """CA-5.3."""
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = 75
    server = Power()
    with pytest.raises(InputValidationError):
        run(payload, power=server)
    assert server.requests == []


def test_a_scenario_before_the_source_coverage_is_blocked_and_not_requested() -> None:
    """CA-4.5: 1983 empieza antes de la radiación (1984-01-01); la consulta no lo pide."""
    payload = plan_request()
    payload["window"]["start_years"] = [1983, 1984]
    outcome, server = run(payload)
    scenarios = by_year(outcome)
    assert scenarios[1983].status == "blocked"
    assert {block.code for block in scenarios[1983].blocks} == {md.BLOCK_BEFORE_COVERAGE}
    assert [block.variable for block in scenarios[1983].blocks] == ["ALLSKY_SFC_SW_DWN"]
    assert scenarios[1984].status == "computed"
    assert server.requests[0].url.params["start"] == "19840701"


def test_when_no_window_is_covered_nothing_is_requested() -> None:
    payload = plan_request()
    payload["window"]["start_years"] = [1982, 1983]
    outcome, server = run(payload)
    assert server.requests == []
    assert outcome.provenance is None
    assert outcome.all_blocked
    assert outcome.runs == () and all(r.n_scenarios == 0 for r in outcome.ranges)


def test_data_not_yet_published_blocks_the_windows_that_include_it() -> None:
    """Racha final de faltantes: la ventana 2017 termina el último día de la serie."""
    outcome, _ = run(trailing_fill=3)
    scenarios = by_year(outcome)
    assert scenarios[2017].status == "blocked"
    assert {block.code for block in scenarios[2017].blocks} == {md.BLOCK_UNPUBLISHED}
    assert scenarios[2008].status == "computed" and scenarios[2011].status == "computed"


def test_inconsistent_temperatures_block_the_scenario() -> None:
    """CA-6.10."""
    server = Power(values={"T2M_MAX": 10.0, "T2M_MIN": 14.0})
    outcome, _ = run(power=server)
    assert outcome.all_blocked
    assert {block.code for block in outcome.scenarios[0].blocks} == {
        md.BLOCK_INCONSISTENT_TEMPERATURE
    }


def test_substitutions_are_recorded_as_assumptions_with_their_dates() -> None:
    outcome, _ = run(fill_dates=RAIN_GAP)
    entries = {(a.code, a.scope_id): a for a in outcome.assumptions}
    radiation = entries[("SUBST_RADIATION_HARGREAVES", "2008")]
    assert radiation.count == 1 and radiation.dates == (date(2009, 1, 17),)
    assert ("SUBST_RADIATION_HARGREAVES", "2017") not in entries  # bloqueado: no se sustituye
    assert ("RAINFED_NO_IRRIGATION", None) in entries
    assert ("FALLOW_EVAPORATION_LAYER", None) in entries


# --- T044: corridas, resultados, rangos y comparaciones ---


def test_runs_have_one_result_per_rotation_and_computed_scenario_with_closed_mass_balance() -> None:
    outcome, _ = run(fill_dates=RAIN_GAP)
    assert len(outcome.runs) == 4
    assert {(r.rotation_id, r.start_year) for r in outcome.runs} == {
        ("A", 2008),
        ("A", 2011),
        ("B", 2008),
        ("B", 2011),
    }
    assert all(abs(r.balance.closure_mm) <= 0.01 for r in outcome.runs)
    for result in outcome.runs:
        assert result.balance.initial_storage_mm == pytest.approx(96.0)


def test_runs_crop_results_carry_dates_storage_yield_and_economics() -> None:
    outcome, _ = run(fill_dates=RAIN_GAP)
    run_a = next(r for r in outcome.runs if (r.rotation_id, r.start_year) == ("A", 2008))
    maize, rye, soybean = run_a.crops
    assert (maize.position, maize.crop_code, maize.crop_type) == (1, "maize", "grain")
    assert maize.sowing_date == date(2008, 10, 15) and maize.cycle_end_date == date(2009, 3, 13)
    assert rye.crop_type == "cover" and rye.yield_result.yield_t_ha is None
    assert rye.economics.gross_margin_per_ha == -95.0
    assert rye.economics.gross_margin_label == "Margen bruto negativo"
    assert soybean.sowing_date == date(2009, 11, 15)
    assert 0 <= maize.yield_result.yield_t_ha <= 9.0
    assert maize.segment.storage_at_start_mm >= 0
    assert run_a.economics.status == "computed"
    assert run_a.exposure.window_days == 730


def test_wind_proxy_uses_the_raw_series_and_counts_missing_wind_as_no_data() -> None:
    """CA-6.8 y CA-11.4: un WS2M_MAX faltante en barbecho es «sin dato», no se sustituye."""
    outcome, _ = run(fill_dates={"WS2M_MAX": [date(2008, 7, 5)]})
    run_a = next(r for r in outcome.runs if (r.rotation_id, r.start_year) == ("A", 2008))
    assert run_a.exposure.no_wind_data_days_without_live_crop == 1
    assert run_a.exposure.strong_wind_days_without_live_crop == 0
    assert all(not s.substitutions for s in outcome.scenarios)  # WS2M_MAX no se sustituye


def test_strong_wind_counts_only_days_without_a_live_crop() -> None:
    outcome, _ = run(values={"WS2M_MAX": 9.0})
    run_a = next(r for r in outcome.runs if (r.rotation_id, r.start_year) == ("A", 2008))
    exposure = run_a.exposure
    assert exposure.strong_wind_days_without_live_crop == exposure.no_live_crop_days
    assert exposure.live_crop_days + exposure.no_live_crop_days == 730


def test_runs_ranges_use_the_computed_scenarios_and_list_the_blocked_one() -> None:
    """CA-12.4."""
    outcome, _ = run(fill_dates=RAIN_GAP)
    by_rotation = {r.rotation_id: r for r in outcome.ranges}
    assert set(by_rotation) == {"A", "B"}
    for ranges in by_rotation.values():
        assert ranges.n_scenarios == 2
        assert ranges.scenarios_included == (2008, 2011)
        assert ranges.scenarios_excluded == (2017,)
        assert ranges.gross_margin_per_ha is not None and ranges.gross_margin_per_ha.n == 2
    assert [crop.crop_code for crop in by_rotation["A"].crops] == [
        "maize",
        "rye_cover",
        "soybean_first",
    ]


def test_runs_margin_differences_b_minus_a_for_each_computed_scenario() -> None:
    outcome, _ = run(fill_dates=RAIN_GAP)
    assert [
        (c.start_year, c.minuend_rotation_id, c.subtrahend_rotation_id) for c in outcome.comparisons
    ] == [
        (2008, "B", "A"),
        (2011, "B", "A"),
    ]
    margins = {(r.rotation_id, r.start_year): r.economics.gross_margin_per_ha for r in outcome.runs}
    expected = margins[("B", 2008)] - margins[("A", 2008)]
    assert outcome.comparisons[0].gross_margin_difference_per_ha == pytest.approx(expected)


def test_runs_with_every_scenario_blocked_there_are_no_results_and_no_exception() -> None:
    """CA-16.3."""
    outcome, _ = run(
        fill_dates={"PRECTOTCORR": [date(2008, 7, 5), date(2011, 7, 5), date(2017, 7, 5)]}
    )
    assert outcome.all_blocked
    assert outcome.runs == () and outcome.comparisons == ()
    assert [s.status for s in outcome.scenarios] == ["blocked"] * 3
    assert all(
        r.n_scenarios == 0 and r.scenarios_excluded == (2008, 2011, 2017) for r in outcome.ranges
    )
    assert outcome.provenance is not None  # se consultó y se informa qué se recibió


def test_runs_an_integrity_failure_propagates_without_partial_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA-16.5: ninguna corrida parcial se entrega."""
    real = service.run_daily_balance
    counter = {"calls": 0}

    def failing(*args: Any, **kwargs: Any) -> Any:
        counter["calls"] += 1
        if counter["calls"] == 3:
            raise CalculationIntegrityError("cierre de masa fuera de tolerancia", closure_mm=0.5)
        return real(*args, **kwargs)

    monkeypatch.setattr(service, "run_daily_balance", failing)
    with pytest.raises(CalculationIntegrityError):
        run(fill_dates=RAIN_GAP)


def test_the_service_is_deterministic() -> None:
    first, _ = run(fill_dates=RAIN_GAP)
    second, _ = run(fill_dates=RAIN_GAP)
    assert [r.balance.closure_mm for r in first.runs] == [r.balance.closure_mm for r in second.runs]
    assert first.assumptions == second.assumptions
    assert first.comparisons == second.comparisons


def test_the_service_writes_nothing_to_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    import builtins

    real_open = builtins.open

    def guarded(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("la simulación no debe escribir archivos")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded)
    run(fill_dates=RAIN_GAP)
    assert list(tmp_path.iterdir()) == []
