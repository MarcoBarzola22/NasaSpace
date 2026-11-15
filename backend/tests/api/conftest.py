"""Fábrica de clientes de prueba de la API con NASA POWER simulada y el reloj fijado."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.dependencies import get_now, get_power_client, get_today
from app.main import create_app
from app.services.power_client import PowerClient
from tests.builders.simulation import SETTINGS, TODAY, Power

NOW = datetime(2026, 11, 15, 14, 3, 22, tzinfo=UTC)

ClientFactory = Callable[..., tuple[TestClient, Power]]


def make_client(
    power: Power | Callable[[httpx.Request], httpx.Response] | None = None,
    settings: Settings = SETTINGS,
) -> tuple[TestClient, Power]:
    """Cliente con ``transport`` simulado. Los errores internos salen como 500, no se relanzan."""
    server = power if power is not None else Power()
    app = create_app()
    transport = httpx.MockTransport(server)
    app.dependency_overrides[get_power_client] = lambda: PowerClient(
        settings, transport=transport, clock=lambda: NOW
    )
    app.dependency_overrides[get_today] = lambda: TODAY
    app.dependency_overrides[get_now] = lambda: NOW
    return TestClient(app, raise_server_exceptions=False), server  # type: ignore[return-value]


@pytest.fixture
def client_factory() -> ClientFactory:
    return make_client


@pytest.fixture
def client() -> TestClient:
    return make_client()[0]


def is_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False
