"""Pruebas del contrato de la respuesta (T042).

Cubren CA-15.1 (bloques de la respuesta), CA-15.3 (toda cifra con su unidad), CA-15.5 (sin series
diarias) y CA-12.1 (rangos con ``n``). El ejemplo de respuesta del plan §5.3 se lee de
``plan.md`` y debe seguir siendo una respuesta válida.
"""

from __future__ import annotations

import json
import re
import types
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from app.models import response as models
from app.models.response import SimulationResponse

PLAN_PATH = Path(__file__).resolve().parents[3] / "specs" / "001-agrodss-backend" / "plan.md"

TOP_LEVEL_KEYS = {
    "contract_version",
    "model_version",
    "request_id",
    "computed_at",
    "currency",
    "resolved_input",
    "provenance",
    "scenarios",
    "results",
    "ranges",
    "comparisons",
    "assumptions",
    "warnings",
}

# Sufijos de unidad del plan §9.5, más los de entradas del lote que la respuesta devuelve.
UNIT_SUFFIXES = (
    "_mm",
    "_t_ha",
    "_per_ha",
    "_ms",
    "_m",
    "_pct",
    "_days",
    "_ratio",
    "_deg",  # coordenadas en grados (no figura en la lista del plan §9.5)
    "_m3_m3",  # humedades volumétricas θCC y θPMP (ídem)
)

# Cifras sin unidad: posiciones, años, conteos y extremos de un rango (la unidad la da el campo
# que contiene el rango). Escrita a propósito: un campo numérico nuevo obliga a revisarla.
ALLOWED_DIMENSIONLESS = {
    "position",
    "after_position",
    "start_year",
    "start_years",
    "start_day",
    "start_month",
    "scenarios_included",
    "scenarios_excluded",
    "margin_not_computed_years",
    "n",
    "n_scenarios",
    "count",
    "min",
    "median",
    "max",
    "value",  # valor de un parámetro o supuesto; su unidad va en `unit` o en su nombre
    # Conteos de días con el nombre del plan §5.3 (el nombre no termina en `_days`).
    "strong_wind_days_without_live_crop",
    "no_wind_data_days_without_live_crop",
    "relative_yield",  # Ya/Ym, adimensional (nombre del plan §5.3)
}


@pytest.fixture
def plan_example() -> dict:
    text = PLAN_PATH.read_text(encoding="utf-8")
    block = text.split("**Ejemplo de respuesta**", 1)[1]
    body = re.search(r"```json\n(.*?)\n```", block, flags=re.S)
    assert body is not None
    return json.loads(body.group(1))


def all_models() -> list[type[BaseModel]]:
    return [
        value
        for value in vars(models).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == models.__name__
    ]


def numeric_types(annotation: object) -> bool:
    """¿La anotación contiene ``int`` o ``float`` (también dentro de listas, uniones y dicts)?"""
    if annotation in (int, float):
        return True
    origin = typing.get_origin(annotation)
    if origin is None:
        return False
    if origin is types.UnionType or origin is typing.Union:
        return any(numeric_types(arg) for arg in typing.get_args(annotation))
    if origin in (list, tuple, dict):
        return any(numeric_types(arg) for arg in typing.get_args(annotation))
    return False


def has_unit(name: str) -> bool:
    return any(name.endswith(suffix) or name == suffix.lstrip("_") for suffix in UNIT_SUFFIXES)


def test_the_plan_example_validates_against_the_response_model(plan_example: dict) -> None:
    response = SimulationResponse.model_validate(plan_example)
    assert response.contract_version == "1.0"
    assert response.results[0].crops[1].economics.gross_margin_label == "Margen bruto negativo"


def test_the_example_round_trips_without_losing_fields(plan_example: dict) -> None:
    response = SimulationResponse.model_validate(plan_example)
    again = SimulationResponse.model_validate(json.loads(response.model_dump_json()))
    assert again == response


def test_the_response_has_exactly_the_thirteen_top_level_keys() -> None:
    assert set(SimulationResponse.model_fields) == TOP_LEVEL_KEYS
    assert len(SimulationResponse.model_fields) == 13


def test_every_numeric_field_has_a_unit_suffix_or_is_listed_as_dimensionless() -> None:
    """CA-15.3."""
    offenders = []
    for model in all_models():
        for name, field in model.model_fields.items():
            if (
                numeric_types(field.annotation)
                and not has_unit(name)
                and name not in ALLOWED_DIMENSIONLESS
            ):
                offenders.append(f"{model.__name__}.{name}")
    assert offenders == []


def test_the_dimensionless_list_has_no_unused_entries() -> None:
    used = {
        name
        for model in all_models()
        for name, field in model.model_fields.items()
        if numeric_types(field.annotation)
    }
    assert ALLOWED_DIMENSIONLESS - used == set()


def test_the_checker_detects_a_numeric_field_without_unit() -> None:
    class Bad(BaseModel):
        wind_speed: float

    assert numeric_types(Bad.model_fields["wind_speed"].annotation)
    assert not has_unit("wind_speed")


def test_the_model_has_no_daily_series_fields() -> None:
    """CA-15.5: ni serie diaria del balance ni serie climática diaria."""
    for model in all_models():
        for name, field in model.model_fields.items():
            assert "daily" not in name and "series" not in name, f"{model.__name__}.{name}"
            args = typing.get_args(field.annotation)
            assert not (
                typing.get_origin(field.annotation) is list and float in args
            ), f"{model.__name__}.{name} es una lista de números (¿serie diaria?)"


def test_unknown_fields_are_rejected(plan_example: dict) -> None:
    plan_example["extra_block"] = {}
    with pytest.raises(ValidationError):
        SimulationResponse.model_validate(plan_example)


def test_a_range_carries_the_number_of_scenarios() -> None:
    """CA-12.1: junto a cada rango, el ``n``."""
    assert "n" in models.RangeOut.model_fields
    assert "no_range" in models.RangeOut.model_fields


def test_origins_are_restricted_to_the_four_known_values(plan_example: dict) -> None:
    plan_example["resolved_input"]["parcel"]["fallow_kc_base"]["origin"] = "somewhere"
    with pytest.raises(ValidationError):
        SimulationResponse.model_validate(plan_example)


def test_scenario_status_is_computed_or_blocked(plan_example: dict) -> None:
    plan_example["scenarios"][0]["status"] = "partial"
    with pytest.raises(ValidationError):
        SimulationResponse.model_validate(plan_example)


def test_provenance_may_be_null_when_nasa_was_not_queried(plan_example: dict) -> None:
    plan_example["provenance"] = None
    assert SimulationResponse.model_validate(plan_example).provenance is None
