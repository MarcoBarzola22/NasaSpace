"""Pruebas de los errores 422 en español y de la regla de riego (T034).

Cubren CA-1.8 (riego), CA-16.1 (todos los errores, con campo y motivo), CA-16.4 (categoría y
reintento) y CA-16.6 (mensajes en español). Se envían cuerpos a ``POST /api/v1/simulations``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core import messages
from app.core.error_handlers import field_path, spanish_message
from app.models.errors import ErrorResponse
from tests.api.conftest import is_uuid, make_client
from tests.builders.requests import plan_request

URL = "/api/v1/simulations"
ENGLISH_PHRASES = ("Field required", "Input should", "Extra inputs", "value_error", "validation")


def post(client: TestClient, payload: Any) -> Any:
    return client.post(URL, json=payload)


def invalid_payload() -> dict[str, Any]:
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = 120
    payload["rotations"][0]["crops"][1]["ym_t_ha"] = 0
    del payload["rotations"][0]["crops"][2]["sowing"]
    payload["window"]["start_years"] = []
    return payload


def test_invalid_body_returns_422_with_the_error_envelope(client: TestClient) -> None:
    response = post(client, invalid_payload())
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["category"] == "input" and error["code"] == "invalid_input"
    assert error["retryable"] is False
    assert is_uuid(error["request_id"]) and error["request_id"] == response.headers["x-request-id"]
    assert error["message"] == messages.INPUT_INVALID
    ErrorResponse.model_validate(response.json())


def test_every_error_is_reported_with_its_field_path(client: TestClient) -> None:
    """CA-16.1: todos los errores, no solo el primero."""
    details = post(client, invalid_payload()).json()["error"]["details"]
    fields = {item["field"] for item in details}
    assert fields == {
        "parcel.latitude_deg",
        "rotations[0].crops[1].ym_t_ha",
        "rotations[0].crops[2].sowing",
        "window.start_years",
    }


def test_field_paths_use_brackets_and_dots() -> None:
    assert (
        field_path(("body", "rotations", 0, "crops", 1, "ym_t_ha"))
        == "rotations[0].crops[1].ym_t_ha"
    )
    assert field_path(("body", "window", "start_years", 2)) == "window.start_years[2]"
    assert field_path(("body",)) == messages.BODY_FIELD


def test_messages_are_in_spanish_never_pydantic_english(client: TestClient) -> None:
    details = post(client, invalid_payload()).json()["error"]["details"]
    for item in details:
        assert item["message"]
        for phrase in ENGLISH_PHRASES:
            assert phrase not in item["message"], item
    assert "Falta este campo obligatorio." in {item["message"] for item in details}


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("parcel", "latitude_deg"), 91, "menor o igual que 90"),
        (("parcel", "theta_fc_m3_m3"), 0, "mayor que 0"),
        (("parcel", "effective_depth_m"), 3.5, "menor o igual que 3"),
        (("parcel", "latitude_deg"), "norte", "Debe ser un número."),
        (("window", "start_day"), 40, "menor o igual que 31"),
        (("window", "start_years"), [], "al menos 1 elemento"),
        (("window", "start_years", 0), 1800, "mayor o igual que 1900"),
        (("currency",), "usd", "Formato inválido"),
        (("rotations", 0, "id"), "Z", "Valor no permitido"),
        (("rotations", 0, "crops"), [], "al menos 1 elemento"),
        (("rotations", 0, "crops", 0, "sowing", "window_year"), 3, "menor o igual que 2"),
        (("rotations", 0, "crops", 0, "stage_lengths_days", "mid"), 1.5, "número entero"),
        (("parcel", "name"), "x" * 101, "como máximo 100 caracteres"),
        (("rotations", 0, "crops", 0, "crop_code"), 7, "texto"),
        (("rotations",), "no es lista", "lista"),
        (("parcel",), 5, "objeto"),
    ],
)
def test_each_kind_of_structural_error_has_a_specific_spanish_message(
    client: TestClient, path: tuple[str | int, ...], value: Any, expected: str
) -> None:
    payload = plan_request()
    node: Any = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    response = post(client, payload)
    assert response.status_code == 422
    messages_found = [item["message"] for item in response.json()["error"]["details"]]
    assert any(expected in text for text in messages_found), messages_found


def test_unknown_field_is_reported_with_its_name(client: TestClient) -> None:
    payload = plan_request()
    payload["parcel"]["color"] = "rojo"
    details = post(client, payload).json()["error"]["details"]
    assert details == [
        {
            "field": "parcel.color",
            "message": "Campo no permitido: «color».",
            "code": "extra_forbidden",
        }
    ]


def test_irrigation_key_returns_the_specific_code_and_message(client: TestClient) -> None:
    """CA-1.8."""
    payload = plan_request()
    payload["parcel"]["irrigation_mm"] = 20
    response = post(client, payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "irrigation_not_supported"
    assert error["message"] == "El MVP solo evalúa secano; no se admiten datos de riego."
    assert error["category"] == "input" and error["retryable"] is False
    assert error["details"][0]["field"] == "parcel.irrigation_mm"
    assert "riego" in error["details"][0]["message"]


@pytest.mark.parametrize("key", ["riego_mm", "irrigation", "Irrigation_depth", "dias_de_riego"])
def test_any_key_containing_irrig_or_riego_counts_as_irrigation(
    client: TestClient, key: str
) -> None:
    payload = plan_request()
    payload["window"][key] = 1
    assert post(client, payload).json()["error"]["code"] == "irrigation_not_supported"


def test_irrigation_takes_precedence_but_other_errors_are_still_listed(
    client: TestClient,
) -> None:
    payload = plan_request()
    payload["parcel"]["irrigation_mm"] = 1
    payload["parcel"]["latitude_deg"] = 200
    error = post(client, payload).json()["error"]
    assert error["code"] == "irrigation_not_supported"
    assert {item["field"] for item in error["details"]} == {
        "parcel.irrigation_mm",
        "parcel.latitude_deg",
    }


def test_a_body_that_is_not_json_is_reported_in_spanish(client: TestClient) -> None:
    response = client.post(
        URL, content=b"{esto no es json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    (detail,) = response.json()["error"]["details"]
    assert detail["message"] == messages.BODY_NOT_JSON


def test_an_empty_body_lists_the_missing_blocks(client: TestClient) -> None:
    details = post(client, {}).json()["error"]["details"]
    assert {item["field"] for item in details} == {"parcel", "window", "rotations"}


def test_semantic_errors_are_returned_together_in_the_same_envelope() -> None:
    """Errores semánticos (θ, cultivo, latitud): 422, todos juntos y sin consultar a NASA."""
    client, server = make_client()
    payload = plan_request()
    payload["parcel"]["theta_wp_m3_m3"] = 0.3
    payload["parcel"]["latitude_deg"] = 75
    payload["rotations"][0]["crops"][0]["crop_code"] = "quinoa"
    response = post(client, payload)
    assert response.status_code == 422
    error = response.json()["error"]
    assert (error["category"], error["code"], error["retryable"]) == (
        "input",
        "invalid_input",
        False,
    )
    assert {item["code"] for item in error["details"]} == {
        "theta_incoherent",
        "latitude_out_of_range",
        "unknown_crop",
    }
    assert server.requests == []


def test_spanish_message_falls_back_for_unknown_types() -> None:
    assert spanish_message({"type": "algo_nuevo", "loc": ("body", "x")}) == messages.VALUE_INVALID


def test_a_missing_ctx_does_not_break_the_translation() -> None:
    assert spanish_message({"type": "greater_than", "loc": ("body", "x"), "ctx": {}}) == (
        messages.VALUE_INVALID
    )
