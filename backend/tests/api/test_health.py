"""Pruebas de la aplicación base: salud, CORS e identificador de solicitud (T007).

Cubren RNF-13 (documentación navegable) y CA-16.4 (identificador de solicitud en toda respuesta).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import is_uuid

ORIGIN = "http://localhost:5173"


def test_health_returns_ok_with_versions(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_version"]
    assert body["contract_version"] == "1.0"


def test_every_response_carries_a_valid_uuid_request_id(client: TestClient) -> None:
    assert is_uuid(client.get("/api/v1/health").headers["x-request-id"])
    assert is_uuid(client.get("/api/v1/catalog").headers["x-request-id"])


def test_request_ids_are_unique_per_request(client: TestClient) -> None:
    ids = {client.get("/api/v1/health").headers["x-request-id"] for _ in range(5)}
    assert len(ids) == 5


def test_a_client_supplied_request_id_is_not_trusted(client: TestClient) -> None:
    sent = "00000000-0000-4000-8000-000000000000"
    response = client.get("/api/v1/health", headers={"X-Request-ID": sent})
    assert response.headers["x-request-id"] != sent


def test_cors_preflight_from_the_dev_frontend_is_allowed(client: TestClient) -> None:
    response = client.options(
        "/api/v1/simulations",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_cors_does_not_allow_other_origins(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_exposes_the_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": ORIGIN})
    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


def test_docs_and_openapi_are_served(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/simulations" in schema.json()["paths"]


def test_health_does_not_call_nasa_power() -> None:
    from tests.api.conftest import make_client

    client, server = make_client()
    client.get("/api/v1/health")
    assert server.requests == []


def test_unknown_route_uses_the_error_format_in_spanish(client: TestClient) -> None:
    response = client.get("/api/v1/nada")
    assert response.status_code == 404
    error = response.json()["error"]
    assert (error["category"], error["code"], error["retryable"]) == ("input", "not_found", False)
    assert error["request_id"] == response.headers["x-request-id"]
