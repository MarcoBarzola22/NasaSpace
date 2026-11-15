"""Prueba de reproducibilidad (T049).

Cubre RNF-1: con la misma solicitud, la misma respuesta de NASA POWER y la misma versión del
modelo, los resultados son idénticos. Lo único que cambia entre dos llamadas es ``request_id``
(un UUID nuevo por solicitud); el instante de la consulta sale del reloj inyectado.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tests.api.conftest import make_client
from tests.builders.requests import plan_request
from tests.builders.simulation import Power

RAIN_GAP = {"PRECTOTCORR": [date(2018, 3, 4)], "ALLSKY_SFC_SW_DWN": [date(2009, 1, 17)]}


def call(**options: Any) -> tuple[dict[str, Any], str]:
    client, _ = make_client(Power(**options))
    response = client.post("/api/v1/simulations", json=plan_request())
    assert response.status_code == 200
    return response.json(), response.headers["x-request-id"]


def without_request_id(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if key != "request_id"}


def test_two_identical_requests_give_identical_json_except_the_request_id() -> None:
    first, first_id = call(fill_dates=RAIN_GAP)
    second, second_id = call(fill_dates=RAIN_GAP)
    assert first_id != second_id
    assert first["request_id"] == first_id and second["request_id"] == second_id
    assert without_request_id(first) == without_request_id(second)


def test_the_same_client_gives_identical_results_on_repeated_calls() -> None:
    client, _ = make_client(Power(fill_dates=RAIN_GAP))
    first = client.post("/api/v1/simulations", json=plan_request()).json()
    second = client.post("/api/v1/simulations", json=plan_request()).json()
    assert without_request_id(first) == without_request_id(second)


def test_a_different_source_series_gives_a_different_result() -> None:
    """Control: la igualdad de arriba no es trivial; con otra serie el resultado cambia."""
    base, _ = call()
    other, _ = call(values={"PRECTOTCORR": 0.5})
    assert without_request_id(base) != without_request_id(other)
    assert (
        base["results"][0]["water_balance"]["precipitation_mm"]
        != (other["results"][0]["water_balance"]["precipitation_mm"])
    )


def test_the_answer_does_not_depend_on_the_order_of_the_start_years() -> None:
    client, _ = make_client(Power())
    ascending = plan_request()
    shuffled = plan_request()
    shuffled["window"]["start_years"] = [2017, 2008, 2011]
    a = client.post("/api/v1/simulations", json=ascending).json()
    b = client.post("/api/v1/simulations", json=shuffled).json()
    assert without_request_id(a) == without_request_id(b)


def test_the_provenance_explains_differences_between_dates() -> None:
    """RNF-1: versión de la fuente y fecha y hora de la consulta quedan en la respuesta."""
    body, _ = call()
    provenance = body["provenance"]
    assert provenance["source_version"] == "v2.10.3"
    assert provenance["queried_at"].startswith("2026-11-15T14:03:22")
    assert body["model_version"] == "0.1.0"
