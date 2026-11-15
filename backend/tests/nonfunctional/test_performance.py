"""Prueba de rendimiento (T049; marcada ``slow``).

Cubre RNF-3 y RNF-4: una vez recibida la respuesta de NASA POWER, el procesamiento de 3
rotaciones × 10 escenarios se completa en 5 s o menos, y la respuesta se limita a resúmenes.
La espera de red queda fuera de la medición: la respuesta simulada se genera antes y el
transporte la devuelve al instante.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from app.models.request import SimulationRequest
from app.services.power_client import PowerClient
from app.services.response_builder import build_response
from app.services.simulation_service import simulate
from tests.api.conftest import NOW
from tests.builders.scale import SCALE_YEARS, scale_body, scale_request
from tests.builders.simulation import CATALOG, SETTINGS, TODAY

pytestmark = pytest.mark.slow

LIMIT_SECONDS = 5.0


def test_three_rotations_by_ten_scenarios_are_processed_within_five_seconds() -> None:
    body = scale_body()  # generada fuera de la medición
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    request = SimulationRequest.model_validate(scale_request())
    client = PowerClient(SETTINGS, transport=transport, clock=lambda: NOW)

    started = time.perf_counter()
    outcome = asyncio.run(
        simulate(request, catalog=CATALOG, settings=SETTINGS, power_client=client, today=TODAY)
    )
    response = build_response(outcome, request_id="rendimiento", computed_at=NOW)
    elapsed = time.perf_counter() - started

    assert len(outcome.runs) == 30 and len(response.results) == 30
    assert elapsed <= LIMIT_SECONDS, f"{elapsed:.2f} s superan el límite de {LIMIT_SECONDS} s"


def test_every_run_of_the_scale_request_closes_the_mass_balance() -> None:
    body = scale_body()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    request = SimulationRequest.model_validate(scale_request())
    outcome = asyncio.run(
        simulate(
            request,
            catalog=CATALOG,
            settings=SETTINGS,
            power_client=PowerClient(SETTINGS, transport=transport),
            today=TODAY,
        )
    )
    assert {run.start_year for run in outcome.runs} == set(SCALE_YEARS)
    assert {run.rotation_id for run in outcome.runs} == {"A", "B", "C"}
    assert all(abs(run.balance.closure_mm) <= 0.01 for run in outcome.runs)


def test_the_response_stays_a_summary_with_thirty_results() -> None:
    """RNF-4: 30 resultados caben en una respuesta de decenas de kilobytes, sin series diarias."""
    body = scale_body()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    request = SimulationRequest.model_validate(scale_request())
    outcome = asyncio.run(
        simulate(
            request,
            catalog=CATALOG,
            settings=SETTINGS,
            power_client=PowerClient(SETTINGS, transport=transport),
            today=TODAY,
        )
    )
    text = build_response(outcome, request_id="tamano", computed_at=NOW).model_dump_json()
    assert len(text) < 1_000_000
    assert len(json.loads(text)["results"]) == 30
