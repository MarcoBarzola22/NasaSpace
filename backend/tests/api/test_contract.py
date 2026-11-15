"""Contrato OpenAPI: ejemplos del plan e instantánea del esquema (T048).

Cubren CA-15.6 (contrato documentado y estable) y RNF-13 (documentación navegable).

Si el esquema cambia a propósito, se regenera la instantánea con
``UPDATE_SNAPSHOTS=1 pytest tests/api/test_contract.py`` y se revisa el cambio:

- agregar un campo opcional: se actualiza la instantánea;
- quitar o renombrar un campo, o volver obligatorio uno opcional: cambia la versión mayor del
  contrato (``CONTRACT_VERSION``).
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from app.models.examples import REQUEST_EXAMPLE, RESPONSE_EXAMPLE
from app.models.request import SimulationRequest
from app.models.response import SimulationResponse

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "openapi_v1.json"
OPERATION = ("/api/v1/simulations", "post")


def current_schema() -> dict[str, Any]:
    return json.loads(json.dumps(create_app().openapi()))


def schema_differences(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Rutas donde ``actual`` difiere de ``expected`` (campo que falta, sobra o cambia)."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        found: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            where = f"{path}/{key}"
            if key not in actual:
                found.append(f"falta {where}")
            elif key not in expected:
                found.append(f"sobra {where}")
            else:
                found.extend(schema_differences(expected[key], actual[key], where))
        return found
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"distinta longitud en {path}"]
        return [
            diff
            for index, (a, b) in enumerate(zip(expected, actual, strict=True))
            for diff in schema_differences(a, b, f"{path}[{index}]")
        ]
    return [] if expected == actual else [f"cambia {path}"]


def operation(schema: dict[str, Any]) -> dict[str, Any]:
    path, method = OPERATION
    return schema["paths"][path][method]


def test_the_plan_examples_validate_against_the_models() -> None:
    SimulationRequest.model_validate(REQUEST_EXAMPLE)
    SimulationResponse.model_validate(RESPONSE_EXAMPLE)


def test_openapi_includes_the_request_and_response_examples() -> None:
    post = operation(current_schema())
    request_examples = post["requestBody"]["content"]["application/json"]["examples"]
    assert request_examples["plan"]["value"] == REQUEST_EXAMPLE
    response_example = post["responses"]["200"]["content"]["application/json"]["example"]
    assert response_example == RESPONSE_EXAMPLE


def test_openapi_documents_every_error_status_with_the_spanish_error_model() -> None:
    post = operation(current_schema())
    assert set(post["responses"]) == {"200", "422", "500", "502", "503", "504"}
    for status in ("422", "500", "502", "503", "504"):
        ref = post["responses"][status]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse")
    assert "HTTPValidationError" not in json.dumps(current_schema())


def test_openapi_lists_the_three_endpoints_and_the_contract_version() -> None:
    schema = current_schema()
    assert {"/api/v1/health", "/api/v1/catalog", "/api/v1/simulations"} <= set(schema["paths"])
    assert schema["info"]["summary"] == "Contrato 1.0"


def test_the_schema_matches_the_saved_snapshot() -> None:
    schema = current_schema()
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT_PATH.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    differences = schema_differences(expected, schema)
    assert differences == [], (
        "El contrato cambió. Si fue a propósito: agregar un campo opcional actualiza la "
        "instantánea; quitar o renombrar uno cambia la versión mayor. Diferencias: "
        + "; ".join(differences[:10])
    )


def test_snapshot_detects_removed_field() -> None:
    """La comparación informa la diferencia cuando a una copia del esquema le falta un campo."""
    schema = current_schema()
    modified = copy.deepcopy(schema)
    removed = modified["components"]["schemas"]["SimulationResponse"]["properties"]
    del removed["warnings"]
    assert schema_differences(schema, modified) == [
        "falta /components/schemas/SimulationResponse/properties/warnings"
    ]
    assert schema_differences(modified, schema) == [
        "sobra /components/schemas/SimulationResponse/properties/warnings"
    ]


def test_snapshot_detects_a_changed_type() -> None:
    schema = current_schema()
    modified = copy.deepcopy(schema)
    modified["components"]["schemas"]["ParcelOut"]["properties"]["latitude_deg"]["type"] = "string"
    assert schema_differences(schema, modified)


def test_snapshot_file_exists_and_is_current_json() -> None:
    assert SNAPSHOT_PATH.exists()
    json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_update_is_off_by_default() -> None:
    assert os.environ.get("UPDATE_SNAPSHOTS") != "1", "No dejar UPDATE_SNAPSHOTS=1 en el entorno."


@pytest.mark.parametrize("key", ["x-api-key", "authorization"])
def test_the_contract_declares_no_authentication(key: str) -> None:
    assert key not in json.dumps(current_schema()).lower()
