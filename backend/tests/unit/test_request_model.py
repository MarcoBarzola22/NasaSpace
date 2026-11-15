"""Pruebas de los modelos de la solicitud, validación estructural (T033).

Cubren CA-1.1–CA-1.5 (parcela), CA-3.1, CA-3.2, CA-3.9 (rotaciones y cultivos), CA-4.1 (años) y
CA-10.5 (datos económicos). Cada caso fuera de rango corresponde a una fila de la tabla del plan
§5.2 y debe fallar en la ruta de campo esperada.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.models.request import SimulationRequest
from tests.builders.requests import plan_request


def set_path(request: dict[str, Any], path: tuple[str | int, ...], value: Any) -> dict[str, Any]:
    node: Any = request
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return request


def error_locations(request: dict[str, Any]) -> list[tuple[str | int, ...]]:
    with pytest.raises(ValidationError) as caught:
        SimulationRequest.model_validate(request)
    return [tuple(error["loc"]) for error in caught.value.errors()]


def test_plan_example_request_is_valid() -> None:
    request = SimulationRequest.model_validate(plan_request())
    assert [rotation.id for rotation in request.rotations] == ["A", "B"]
    assert request.window.start_years == [2008, 2011, 2017]
    assert request.parcel.fallow_kc_base is None


def test_defaults_are_applied_when_optional_fields_are_omitted() -> None:
    payload = plan_request()
    del payload["window"]["start_day"], payload["window"]["start_month"]
    del payload["parcel"]["fallow_kc_base"]
    request = SimulationRequest.model_validate(payload)
    assert (request.window.start_day, request.window.start_month) == (1, 7)
    assert request.rotations[1].initial_residue_cover_pct == 0.0
    assert request.rotations[1].crops[1].residue_cover_after_pct == 0.0


OUT_OF_RANGE = [
    (("parcel", "latitude_deg"), 90.5),  # CA-1.2
    (("parcel", "latitude_deg"), -90.5),
    (("parcel", "longitude_deg"), 180.5),
    (("parcel", "theta_fc_m3_m3"), 0),  # CA-1.3
    (("parcel", "theta_fc_m3_m3"), 1.2),
    (("parcel", "theta_wp_m3_m3"), -0.01),
    (("parcel", "theta_wp_m3_m3"), 1),
    (("parcel", "effective_depth_m"), 0),  # CA-1.4
    (("parcel", "effective_depth_m"), 3.5),
    (("parcel", "initial_available_water_pct"), -1),  # CA-1.5
    (("parcel", "initial_available_water_pct"), 101),
    (("parcel", "fallow_kc_base"), 0),  # CA-1.10
    (("parcel", "fallow_kc_base"), 1.5),
    (("parcel", "name"), "x" * 101),
    (("window", "start_day"), 32),
    (("window", "start_month"), 13),
    (("window", "start_years"), []),  # CA-4.1
    (("window", "start_years"), list(range(2000, 2011))),  # 11 años
    (("window", "start_years", 0), 1800),
    (("currency",), "usd"),  # CA-10.6: 3 letras mayúsculas
    (("currency",), "USDX"),
    (("rotations",), []),  # CA-3.1
    (("rotations", 0, "id"), "D"),
    (("rotations", 0, "initial_residue_cover_pct"), 101),  # CA-3.12
    (("rotations", 0, "crops"), []),
    (("rotations", 0, "crops", 0, "sowing", "window_year"), 3),  # CA-3.8
    (("rotations", 0, "crops", 0, "sowing", "month"), 13),
    (("rotations", 0, "crops", 0, "stage_lengths_days", "mid"), 0),  # CA-3.9
    (("rotations", 0, "crops", 0, "stage_lengths_days", "late"), 366),
    (("rotations", 0, "crops", 0, "stage_lengths_days", "initial"), 20.5),
    (("rotations", 0, "crops", 0, "kc_mid"), 2.1),
    (("rotations", 0, "crops", 0, "kc_initial"), -0.1),
    (("rotations", 0, "crops", 0, "root_depth_initial_m"), 0),
    (("rotations", 0, "crops", 0, "root_depth_max_m"), -1),
    (("rotations", 0, "crops", 1, "depletion_fraction_p"), 1),
    (("rotations", 0, "crops", 1, "depletion_fraction_p"), 0),
    (("rotations", 0, "crops", 0, "ky"), 2.5),
    (("rotations", 0, "crops", 0, "ym_t_ha"), 0),
    (("rotations", 0, "crops", 0, "ym_t_ha"), 31),
    (("rotations", 0, "crops", 0, "residue_cover_after_pct"), -5),
    (("rotations", 0, "crops", 0, "economics", "price_per_t"), -1),  # CA-10.5
    (("rotations", 0, "crops", 0, "economics", "direct_costs_per_ha"), -1),
]


@pytest.mark.parametrize(
    ("path", "value"), OUT_OF_RANGE, ids=[str(case[0]) for case in OUT_OF_RANGE]
)
def test_out_of_range_value_fails_at_its_field_path(
    path: tuple[str | int, ...], value: Any
) -> None:
    request = set_path(plan_request(), path, value)
    assert any(loc[: len(path)] == path for loc in error_locations(request))


def test_there_are_at_least_fifteen_out_of_range_cases() -> None:
    assert len(OUT_OF_RANGE) >= 15


def test_four_rotations_are_rejected() -> None:
    payload = plan_request()
    payload["rotations"] = [payload["rotations"][0]] * 4
    assert ("rotations",) in error_locations(payload)


def test_unknown_field_fails() -> None:
    payload = plan_request()
    payload["parcel"]["color"] = "rojo"
    assert ("parcel", "color") in error_locations(payload)


def test_irrigation_field_is_unknown_and_fails() -> None:
    """CA-1.8: un dato de riego es un campo desconocido; el mensaje específico es de T034."""
    payload = plan_request()
    payload["parcel"]["irrigation_mm"] = 10
    assert ("parcel", "irrigation_mm") in error_locations(payload)


def test_stage_lengths_with_three_of_four_keys_fails() -> None:
    payload = plan_request()
    del payload["rotations"][0]["crops"][0]["stage_lengths_days"]["late"]
    assert ("rotations", 0, "crops", 0, "stage_lengths_days", "late") in error_locations(payload)


@pytest.mark.parametrize(
    "missing",
    [
        ("parcel",),
        ("window",),
        ("rotations",),
        ("parcel", "latitude_deg"),
        ("parcel", "theta_fc_m3_m3"),
        ("window", "start_years"),
        ("rotations", 0, "crops", 0, "crop_code"),
        ("rotations", 0, "crops", 0, "sowing"),
    ],
)
def test_required_field_missing_fails(missing: tuple[str | int, ...]) -> None:
    payload = plan_request()
    node: Any = payload
    for key in missing[:-1]:
        node = node[key]
    del node[missing[-1]]
    assert missing in error_locations(payload)


def test_a_wrong_type_fails() -> None:
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = "treinta"
    assert ("parcel", "latitude_deg") in error_locations(payload)


def test_boundary_values_are_accepted() -> None:
    payload = plan_request()
    parcel = payload["parcel"]
    parcel.update(
        latitude_deg=90,
        longitude_deg=-180,
        theta_fc_m3_m3=1,
        theta_wp_m3_m3=0,
        effective_depth_m=3.0,
        initial_available_water_pct=100,
        fallow_kc_base=1.0,
    )
    SimulationRequest.model_validate(payload)
