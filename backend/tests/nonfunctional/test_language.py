"""Prueba de lenguaje: textos en español y sin términos prohibidos (T029).

Cubre CA-10.7 («Margen bruto negativo», nunca «pérdida neta»), CA-16.6 (todo mensaje visible en
español, en un solo lugar), CA-17.1 (sin probabilidades ni medidas de precisión) y CA-17.5
(sin rotulaciones de «recomendada», «óptima» o «mejor»).

Recorre ``app.core.messages`` y los textos de las notas del dominio (el dominio no puede
importar ``messages``). T049 amplía la prueba a la respuesta completa del endpoint.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.core import messages

BACKEND_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = BACKEND_DIR / "app" / "services"
DOMAIN_MODULES = (
    "app.domain.economics",
    "app.domain.yield_response",
    "app.domain.wind_proxy",
    "app.domain.stats",
    "app.domain.missing_data",
    "app.domain.calendar",
)
# Valores de estado del archivo del catálogo: son datos, no mensajes.
CATALOG_DATA_LITERALS = {"decisión del equipo", "sin referencia", "no aplica"}
EXEMPT_NAMES = {"FORBIDDEN_TERMS", "ALLOWED_PHRASES"}


def walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, tuple | list):
        for item in value:
            yield from walk_strings(item)


def message_texts() -> list[str]:
    texts: list[str] = []
    for name, value in vars(messages).items():
        if name.startswith("_") or name in EXEMPT_NAMES:
            continue
        texts.extend(walk_strings(value))
    return texts


def domain_texts() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for module_name in DOMAIN_MODULES:
        module = importlib.import_module(module_name)
        for name, value in vars(module).items():
            if name.isupper() and isinstance(value, str) and " " in value:
                found.append((f"{module_name}.{name}", value))
    return found


def forbidden_in(text: str) -> list[str]:
    lowered = text.lower()
    for phrase in messages.ALLOWED_PHRASES:
        lowered = lowered.replace(phrase.lower(), "")
    return [term for term in messages.FORBIDDEN_TERMS if term in lowered]


def test_there_are_texts_to_check() -> None:
    assert len(message_texts()) > 80
    assert domain_texts()


def test_no_message_contains_a_forbidden_term() -> None:
    offenders = {text: forbidden_in(text) for text in message_texts() if forbidden_in(text)}
    assert offenders == {}


def test_no_domain_note_contains_a_forbidden_term() -> None:
    offenders = {name: forbidden_in(text) for name, text in domain_texts() if forbidden_in(text)}
    assert offenders == {}


def test_negative_margin_is_labelled_gross_margin_never_net_loss() -> None:
    """CA-10.7."""
    from app.domain.economics import LABEL_NEGATIVE_MARGIN

    assert LABEL_NEGATIVE_MARGIN == "Margen bruto negativo"
    assert "pérdida" not in LABEL_NEGATIVE_MARGIN.lower()


@pytest.mark.parametrize(
    "text",
    [
        "Esto es lo mejor para su lote",
        "Rotación recomendada",
        "Rotación óptima",
        "Probabilidad de 80 %",
        "pérdida neta de 100",
        "Precisión del 95 %",
    ],
)
def test_checker_detects_each_forbidden_term(text: str) -> None:
    assert forbidden_in(text)


def test_checker_accepts_the_literal_range_label_but_not_other_uses_of_probability() -> None:
    assert forbidden_in(messages.RANGE_LABEL) == []
    assert forbidden_in("Hay una probabilidad alta de lluvia")
    assert forbidden_in(messages.RANGE_LABEL + " Probabilidad de acierto: 90 %")


def test_user_texts_are_in_spanish_not_in_pydantic_english() -> None:
    english = ("Field required", "Input should", "Extra inputs", "Traceback")
    for text in message_texts():
        assert not any(phrase in text for phrase in english), text


def user_text_literals(path: Path) -> list[str]:
    """Literales de texto en español de un módulo (excluye docstrings y datos del catálogo)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    texts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if id(node) in docstrings or value in CATALOG_DATA_LITERALS:
                continue
            if " " in value and any(char.isalpha() for char in value):
                texts.append(value)
    return texts


@pytest.mark.parametrize("module", ["validation.py", "catalog_service.py"])
def test_services_keep_no_user_text_outside_messages(module: str) -> None:
    """T029: los mensajes de validación y del catálogo viven en ``core.messages``."""
    assert user_text_literals(SERVICES_DIR / module) == []


def test_the_detector_finds_a_text_literal(tmp_path: Path) -> None:
    sample = tmp_path / "sample_literal.py"
    sample.write_text('"""Docstring que se ignora."""\nX = "Esto es un mensaje"\nY = "codigo"\n')
    assert user_text_literals(sample) == ["Esto es un mensaje"]


# --- Respuesta completa del endpoint (T049) ---


def response_strings(node: Any) -> Iterator[str]:
    """Todos los textos de un JSON, sin las claves ni los códigos técnicos de una sola palabra."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from response_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from response_strings(item)


def full_response_body() -> dict[str, Any]:
    """Respuesta con todo a la vez: sustituciones, bloqueo, coordenadas fuera de San Luis."""
    from datetime import date

    from tests.api.conftest import make_client
    from tests.builders.requests import plan_request
    from tests.builders.simulation import Power

    payload = plan_request()
    payload["parcel"].update(latitude_deg=-31.42, longitude_deg=-64.18)
    gaps = {"PRECTOTCORR": [date(2018, 3, 4)], "ALLSKY_SFC_SW_DWN": [date(2009, 1, 17)]}
    client, _ = make_client(Power(fill_dates=gaps))
    response = client.post("/api/v1/simulations", json=payload)
    assert response.status_code == 200
    return response.json()


def test_the_complete_response_contains_no_forbidden_term() -> None:
    """CA-17.1 y CA-17.5 sobre todos los textos de la respuesta del endpoint."""
    body = full_response_body()
    codes = {warning["code"] for warning in body["warnings"]}
    assert codes == {
        "HISTORICAL_DESCRIPTIVE",
        "UNCALIBRATED_PARAMETERS",
        "CELL_SCALE_DATA",
        "NOT_A_RECOMMENDATION",
        "SUBSTITUTIONS_PRESENT",
        "SCENARIOS_BLOCKED",
        "OUTSIDE_SAN_LUIS",
    }
    offenders = {text: forbidden_in(text) for text in response_strings(body) if forbidden_in(text)}
    assert offenders == {}


def test_the_complete_response_has_the_required_warning_and_range_labels() -> None:
    body = full_response_body()
    texts = {warning["message"] for warning in body["warnings"]}
    assert messages.WARNINGS["HISTORICAL_DESCRIPTIVE"] in texts  # CA-17.2
    assert messages.WARNINGS["UNCALIBRATED_PARAMETERS"] in texts  # CA-17.3
    assert all(ranges["label"] == messages.RANGE_LABEL for ranges in body["ranges"])  # CA-12.5
    assert body["provenance"]["label"] == messages.CELL_SCALE_LABEL  # CA-13.2


def test_error_responses_contain_no_forbidden_term() -> None:
    import httpx

    from tests.api.conftest import make_client
    from tests.builders.requests import plan_request

    invalid = plan_request()
    invalid["parcel"]["latitude_deg"] = 75
    invalid["parcel"]["irrigation_mm"] = 1
    bodies = []
    client, _ = make_client()
    bodies.append(client.post("/api/v1/simulations", json=invalid).json())
    for failure in (httpx.ConnectError("x"), httpx.ReadTimeout("x")):

        def refuse(request: httpx.Request, failure: Exception = failure) -> httpx.Response:
            raise failure

        failing, _ = make_client(refuse)
        bodies.append(failing.post("/api/v1/simulations", json=plan_request()).json())
    for body in bodies:
        offenders = [text for text in response_strings(body) if forbidden_in(text)]
        assert offenders == []
