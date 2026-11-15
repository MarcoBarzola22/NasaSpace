"""Ayudas para ejecutar el servicio de simulación contra una NASA POWER simulada (pruebas)."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx

from app.core.config import Settings
from app.models.request import SimulationRequest
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
    payload: dict[str, Any] | None = None, power: Power | None = None, **options: Any
) -> tuple[SimulationOutcome, Power]:
    """Ejecuta ``simulate`` con el reloj en 2026-11-15; devuelve el resultado y el servidor."""
    server = power if power is not None else Power(**options)
    client = PowerClient(SETTINGS, transport=httpx.MockTransport(server))
    request = SimulationRequest.model_validate(payload or plan_request())
    outcome = asyncio.run(
        simulate(request, catalog=CATALOG, settings=SETTINGS, power_client=client, today=TODAY)
    )
    return outcome, server
