"""Pruebas de los manejadores de errores de NASA POWER, integridad e inesperados (T041).

Sobre una aplicación de prueba que lanza cada excepción. Cubren CA-5.4 (falla de la fuente),
CA-16.4 (tres categorías), CA-16.5 (sin detalles técnicos ni resultados parciales) y CA-16.6.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import messages
from app.core.error_handlers import register_error_handlers
from app.core.exceptions import (
    CalculationIntegrityError,
    CatalogError,
    InputValidationError,
    PowerBadResponseError,
    PowerRateLimitedError,
    PowerTimeoutError,
    PowerUnreachableError,
)
from app.core.request_context import install_request_id
from tests.api.conftest import is_uuid

RAISES: dict[str, Callable[[], Exception]] = {
    "unreachable": lambda: PowerUnreachableError("sin red: dns app.services.power_client"),
    "timeout": lambda: PowerTimeoutError("lento", timeout_s=60.0),
    "rate": lambda: PowerRateLimitedError("429"),
    "bad_status": lambda: PowerBadResponseError("estado 500", status_code=500),
    "bad_format": lambda: PowerBadResponseError("falta WS2M_MAX"),
    "integrity": lambda: CalculationIntegrityError(
        "cierre −365 mm en app.domain.water_balance",
        closure_mm=-365.0,
        rotation_id="A",
        start_year=2008,
    ),
    "unexpected": lambda: RuntimeError("secreto interno en app.services.x línea 42"),
    "catalog": lambda: CatalogError(["falta el campo «label»"]),
    "semantic": lambda: InputValidationError(
        [
            {
                "field": "parcel.latitude_deg",
                "message": "Latitud fuera de rango.",
                "code": "latitude_out_of_range",
            }
        ]
    ),
}


def build_app() -> FastAPI:
    app = FastAPI()
    install_request_id(app)
    register_error_handlers(app)

    def make_route(name: str) -> Callable[[], None]:
        def route() -> None:
            raise RAISES[name]()

        return route

    for name in RAISES:
        app.add_api_route(f"/raise/{name}", make_route(name))
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app(), raise_server_exceptions=False)


EXPECTED = [
    ("unreachable", 503, "nasa_power", "power_unreachable", True),
    ("timeout", 504, "nasa_power", "power_timeout", True),
    ("rate", 503, "nasa_power", "power_rate_limited", True),
    ("bad_status", 502, "nasa_power", "power_bad_response", True),
    ("bad_format", 502, "nasa_power", "power_bad_response", True),
    ("integrity", 500, "internal", "calculation_integrity", False),
    ("unexpected", 500, "internal", "unexpected_error", False),
    ("catalog", 500, "internal", "invalid_catalog", False),
    ("semantic", 422, "input", "invalid_input", False),
]


@pytest.mark.parametrize(("name", "status", "category", "code", "retryable"), EXPECTED)
def test_each_exception_maps_to_its_status_category_code_and_retry_flag(
    client: TestClient, name: str, status: int, category: str, code: str, retryable: bool
) -> None:
    response = client.get(f"/raise/{name}")
    assert response.status_code == status
    error = response.json()["error"]
    assert (error["category"], error["code"], error["retryable"]) == (category, code, retryable)


@pytest.mark.parametrize("name", [item[0] for item in EXPECTED])
def test_every_error_carries_the_request_id_of_the_header(client: TestClient, name: str) -> None:
    response = client.get(f"/raise/{name}")
    request_id = response.json()["error"]["request_id"]
    assert is_uuid(request_id) and request_id == response.headers["x-request-id"]


@pytest.mark.parametrize("name", [item[0] for item in EXPECTED])
def test_no_error_body_exposes_technical_details(client: TestClient, name: str) -> None:
    text = client.get(f"/raise/{name}").text
    for leak in ("Traceback", "app.", "línea 42", "secreto", "−365", "water_balance", "dns"):
        assert leak not in text, (name, leak)


def test_timeout_message_includes_the_configured_seconds(client: TestClient) -> None:
    """CA-5.6: «NASA POWER no respondió dentro de 60 s»."""
    message = client.get("/raise/timeout").json()["error"]["message"]
    assert "60 s" in message and message == messages.POWER_TIMEOUT.format(seconds=60.0)


def test_timeout_message_uses_the_seconds_carried_by_the_exception() -> None:
    app = FastAPI()
    install_request_id(app)
    register_error_handlers(app)

    @app.get("/slow")
    def slow() -> None:
        raise PowerTimeoutError("lento", timeout_s=10.0)

    body = TestClient(app, raise_server_exceptions=False).get("/slow").json()
    assert "10 s" in body["error"]["message"]


def test_bad_response_with_status_cites_the_code_and_without_it_the_format(
    client: TestClient,
) -> None:
    with_status = client.get("/raise/bad_status").json()["error"]["message"]
    without = client.get("/raise/bad_format").json()["error"]["message"]
    assert "(500)" in with_status
    assert without == messages.POWER_BAD_FORMAT


def test_nasa_errors_say_no_scenario_was_calculated_and_can_be_retried(client: TestClient) -> None:
    for name in ("unreachable", "timeout", "bad_status", "bad_format"):
        message = client.get(f"/raise/{name}").json()["error"]["message"]
        assert "No se calculó ningún escenario" in message, name
    assert "Reintente" in client.get("/raise/rate").json()["error"]["message"]


def test_integrity_and_unexpected_messages_are_the_fixed_spanish_texts(client: TestClient) -> None:
    assert (
        client.get("/raise/integrity").json()["error"]["message"] == messages.CALCULATION_INTEGRITY
    )
    assert client.get("/raise/unexpected").json()["error"]["message"] == messages.UNEXPECTED_ERROR


def test_errors_have_no_partial_results(client: TestClient) -> None:
    for name in ("integrity", "unexpected", "timeout"):
        assert set(client.get(f"/raise/{name}").json()) == {"error"}


def test_semantic_errors_keep_their_details(client: TestClient) -> None:
    (detail,) = client.get("/raise/semantic").json()["error"]["details"]
    assert detail == {
        "field": "parcel.latitude_deg",
        "message": "Latitud fuera de rango.",
        "code": "latitude_out_of_range",
    }


def test_technical_details_go_to_the_server_log_with_the_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="agrodss"):
        response = client.get("/raise/integrity")
    request_id = response.json()["error"]["request_id"]
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert request_id in logged and "water_balance" in logged and "2008" in logged
