"""Pruebas de la validación semántica de la solicitud (T035 y T036).

Cubren CA-1.3, CA-1.12 (parcela y latitud), CA-2.3 (parámetros «sin referencia»), CA-3.2, CA-3.6,
CA-3.7, CA-3.8, CA-3.9, CA-3.13 (cultivos y calendario), CA-4.3, CA-4.4 (ventana), CA-10.6 y
CA-16.1 (todos los errores en una sola llamada). El reloj se fija en 2026-11-15.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from app.core.exceptions import InputValidationError
from app.models.request import SimulationRequest
from app.services import validation as v
from app.services.catalog_service import (
    STATUS_NO_REFERENCE,
    Catalog,
    ReferenceValue,
    load_catalog,
)
from app.services.validation import ValidationIssue, raise_if_invalid, validate_request
from tests.builders.requests import plan_request

TODAY = date(2026, 11, 15)
CATALOG = load_catalog()


def issues_of(payload: dict[str, Any], catalog: Catalog = CATALOG) -> list[ValidationIssue]:
    return validate_request(SimulationRequest.model_validate(payload), catalog, today=TODAY)


def codes(issues: list[ValidationIssue]) -> list[str]:
    return [issue.code for issue in issues]


def without_reference(catalog: Catalog, crop_code: str, parameter: str) -> Catalog:
    """Copia del catálogo donde un parámetro del cultivo figura «sin referencia»."""
    missing = ReferenceValue(
        value=None,
        unit="",
        status=STATUS_NO_REFERENCE,
        origin=None,
        source=None,
        note=None,
    )
    crops = []
    for crop in catalog.crops:
        if crop.crop_code == crop_code:
            crop = replace(crop, reference_values={**crop.reference_values, parameter: missing})
        crops.append(crop)
    return replace(catalog, crops=tuple(crops))


# --- Solicitud válida ---


def test_plan_example_request_gives_zero_errors() -> None:
    assert issues_of(plan_request()) == []


def test_raise_if_invalid_is_silent_for_a_valid_request() -> None:
    raise_if_invalid(SimulationRequest.model_validate(plan_request()), CATALOG, today=TODAY)


# --- T035: parcela y cultivos ---


def test_parcel_and_crop_errors_are_all_reported_in_a_single_call() -> None:
    """CA-16.1: θPMP ≥ θCC, Ym ausente en grano y precio en cobertura dan exactamente 3 errores."""
    payload = plan_request()
    payload["parcel"]["theta_wp_m3_m3"] = 0.30  # ≥ θCC = 0.28
    del payload["rotations"][0]["crops"][0]["ym_t_ha"]  # maíz sin Ym
    payload["rotations"][0]["crops"][1]["economics"]["price_per_t"] = 150  # centeno con precio
    issues = issues_of(payload)
    assert len(issues) == 3
    assert {issue.field for issue in issues} == {
        "parcel.theta_wp_m3_m3",
        "rotations[0].crops[0].ym_t_ha",
        "rotations[0].crops[1].economics.price_per_t",
    }
    assert set(codes(issues)) == {
        v.CODE_THETA_INCOHERENT,
        v.CODE_YM_REQUIRED,
        v.CODE_FORBIDDEN_FOR_COVER,
    }


def test_parcel_theta_equal_is_also_incoherent() -> None:
    payload = plan_request()
    payload["parcel"]["theta_wp_m3_m3"] = payload["parcel"]["theta_fc_m3_m3"]
    assert codes(issues_of(payload)) == [v.CODE_THETA_INCOHERENT]


def test_unknown_crop_code_is_one_error_that_lists_the_options() -> None:
    payload = plan_request()
    payload["rotations"][1]["crops"][1]["crop_code"] = "quinoa"
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_UNKNOWN_CROP]
    assert issues[0].field == "rotations[1].crops[1].crop_code"
    assert "quinoa" in issues[0].message and "maize" in issues[0].message


def test_missing_reference_kc_of_a_cover_crop_is_one_error() -> None:
    """CA-2.3: si el catálogo no tiene Kc del centeno y el usuario lo omite, se le exige."""
    payload = plan_request()
    del payload["rotations"][0]["crops"][1]["kc_mid"]
    catalog = without_reference(CATALOG, "rye_cover", "kc_mid")
    issues = issues_of(payload, catalog)
    assert codes(issues) == [v.CODE_MISSING_REFERENCE]
    assert issues[0].field == "rotations[0].crops[1].kc_mid"


def test_a_user_value_covers_a_missing_reference() -> None:
    catalog = without_reference(CATALOG, "rye_cover", "kc_mid")
    assert issues_of(plan_request(), catalog) == []  # el ejemplo ya trae kc_mid del centeno


def test_crop_missing_stage_lengths_are_required_when_the_catalog_has_none() -> None:
    """El catálogo no tiene duraciones para el centeno ni la soja de segunda (V-2)."""
    payload = plan_request()
    del payload["rotations"][0]["crops"][1]["stage_lengths_days"]
    del payload["rotations"][1]["crops"][2]["stage_lengths_days"]
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_MISSING_REFERENCE, v.CODE_MISSING_REFERENCE]
    assert {issue.field for issue in issues} == {
        "rotations[0].crops[1].stage_lengths_days",
        "rotations[1].crops[2].stage_lengths_days",
    }


def test_crop_missing_ky_of_a_grain_crop_is_required_only_when_the_catalog_has_none() -> None:
    payload = plan_request()
    catalog = without_reference(CATALOG, "wheat", "ky")
    issues = issues_of(payload, catalog)
    assert codes(issues) == [v.CODE_MISSING_REFERENCE]
    assert issues[0].field == "rotations[1].crops[1].ky"


def test_crop_initial_root_depth_above_the_maximum_is_one_error() -> None:
    payload = plan_request()
    payload["rotations"][0]["crops"][1]["root_depth_initial_m"] = 1.0  # máxima 0.8
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_ROOT_DEPTH_ORDER]
    assert issues[0].field == "rotations[0].crops[1].root_depth_initial_m"


def test_crop_root_depth_is_compared_against_the_catalog_maximum_when_the_user_omits_it() -> None:
    payload = plan_request()
    crop = payload["rotations"][1]["crops"][0]  # maíz sin Zr máxima: usa la del catálogo
    crop["root_depth_initial_m"] = 5.0
    assert codes(issues_of(payload)) == [v.CODE_ROOT_DEPTH_ORDER]


def test_cover_crop_rejects_ym_ky_and_price() -> None:
    """CA-3.13: Ym, Ky y precio están prohibidos en un cultivo de cobertura."""
    payload = plan_request()
    rye = payload["rotations"][0]["crops"][1]
    rye.update(ym_t_ha=2.0, ky=0.5)
    rye["economics"]["price_per_t"] = 100
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_FORBIDDEN_FOR_COVER] * 3


def test_cover_crop_accepts_direct_costs() -> None:
    """CA-3.13: la cobertura sí admite costos directos (el ejemplo ya los trae)."""
    assert issues_of(plan_request()) == []


def test_crop_economic_data_without_currency_is_one_error() -> None:
    """CA-10.6."""
    payload = plan_request()
    payload["currency"] = None
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_CURRENCY_REQUIRED]
    assert issues[0].field == "currency"


def test_crop_no_economic_data_needs_no_currency() -> None:
    payload = plan_request()
    payload["currency"] = None
    for rotation in payload["rotations"]:
        for crop in rotation["crops"]:
            crop.pop("economics", None)
    assert issues_of(payload) == []


def test_crop_repeated_rotation_id_is_one_error() -> None:
    payload = plan_request()
    payload["rotations"][1]["id"] = "A"
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_DUPLICATE_ROTATION]
    assert issues[0].field == "rotations[1].id"


def test_repeating_a_crop_and_identical_rotations_are_allowed() -> None:
    """CA-3.14: maíz → maíz y rotaciones idénticas son válidas (si no se solapan)."""
    payload = plan_request()
    payload["rotations"][1] = {**payload["rotations"][0], "id": "B"}
    assert issues_of(payload) == []


# --- T036: latitud ---


@pytest.mark.parametrize("latitude", [-61, 75, 60.01, -90])
def test_latitude_outside_plus_minus_60_is_rejected(latitude: float) -> None:
    """CA-1.12."""
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = latitude
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_LATITUDE_OUT_OF_RANGE]
    assert issues[0].field == "parcel.latitude_deg"
    assert "San Luis" in issues[0].message


@pytest.mark.parametrize("latitude", [-33.68, -60, 60, 0])
def test_latitude_inside_the_limits_is_accepted(latitude: float) -> None:
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = latitude
    assert issues_of(payload) == []


# --- T036: ventana ---


def test_start_year_2025_is_rejected_because_its_window_ends_after_today() -> None:
    """CA-4.4: la ventana de 2025 termina el 2027-06-30."""
    payload = plan_request()
    payload["window"]["start_years"] = [2008, 2025]
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_WINDOW_ENDS_AFTER_TODAY]
    assert "2025" in issues[0].message and "30-06-2027" in issues[0].message


def test_window_start_year_2024_is_the_last_accepted() -> None:
    payload = plan_request()
    payload["window"]["start_years"] = [2024]
    assert issues_of(payload) == []


def test_window_repeated_start_years_are_rejected_naming_the_year() -> None:
    """CA-4.3."""
    payload = plan_request()
    payload["window"]["start_years"] = [2008, 2011, 2008]
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_DUPLICATE_YEARS]
    assert "2008" in issues[0].message and "2011" not in issues[0].message


def test_window_start_date_on_february_29_is_rejected() -> None:
    """CA-4.3: el 29 de febrero no existe en todos los años."""
    payload = plan_request()
    payload["window"].update(start_day=29, start_month=2)
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_START_DATE_INVALID]
    assert issues[0].field == "window.start_day"


def test_window_nonexistent_start_date_is_rejected() -> None:
    payload = plan_request()
    payload["window"].update(start_day=31, start_month=4)
    assert codes(issues_of(payload)) == [v.CODE_START_DATE_INVALID]


def test_window_overlapping_start_years_are_allowed() -> None:
    """CA-4.7: 2010 y 2011 comparten un año de ventana y son escenarios independientes."""
    payload = plan_request()
    payload["window"]["start_years"] = [2010, 2011]
    assert issues_of(payload) == []


def test_window_years_before_coverage_are_not_rejected() -> None:
    """CA-4.5: ese escenario se bloquea más adelante con su motivo; no es un error de entrada."""
    payload = plan_request()
    payload["window"]["start_years"] = [1983, 1990]
    assert issues_of(payload) == []


# --- T036: calendario por escenario ---


def test_calendar_sowing_on_february_29_is_rejected() -> None:
    """CA-3.8."""
    payload = plan_request()
    payload["rotations"][0]["crops"][1]["sowing"].update(day=29, month=2)
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_SOWING_DATE_INVALID]
    assert issues[0].field == "rotations[0].crops[1].sowing.day"


def two_crop_rotation(first_total_days: int) -> dict[str, Any]:
    """Maíz sembrado el 1-dic y trigo sembrado el 1-mar, ambos en el año 1 de la ventana."""
    template = plan_request()["rotations"][1]["crops"]
    maize = template[0]
    maize["sowing"] = {"window_year": 1, "day": 1, "month": 12}
    maize["stage_lengths_days"] = {
        "initial": 20,
        "development": 30,
        "mid": 25,
        "late": first_total_days - 75,
    }
    wheat = template[1]
    wheat["sowing"] = {"window_year": 1, "day": 1, "month": 3}
    wheat["stage_lengths_days"] = {"initial": 20, "development": 30, "mid": 25, "late": 15}
    return {"id": "A", "crops": [maize, wheat]}


def test_calendar_overlap_present_only_in_some_scenarios_names_those_years() -> None:
    """CA-3.6: el maíz (91 días desde el 1-dic) termina el 1-mar en años sin 29-feb y el 29-feb
    en años bisiestos; el trigo se siembra el 1-mar. Solo se solapan 2008 y 2017."""
    payload = plan_request()
    payload["rotations"] = [two_crop_rotation(first_total_days=91)]
    payload["window"]["start_years"] = [2008, 2011, 2017]
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_CALENDAR_OVERLAP]
    message = issues[0].message
    assert "2008" in message and "2017" in message and "2011" not in message
    assert "maize" in message and "wheat" in message and "rotación A" in message
    assert issues[0].field == "rotations[0].crops[1].sowing"


def test_calendar_no_overlap_when_the_first_cycle_is_one_day_shorter() -> None:
    payload = plan_request()
    payload["rotations"] = [two_crop_rotation(first_total_days=90)]
    assert issues_of(payload) == []


def test_calendar_cycle_outside_the_window_names_crop_and_year() -> None:
    """CA-3.7: una siembra al final del año 2 de la ventana termina fuera de ella."""
    payload = plan_request()
    payload["window"]["start_years"] = [2008, 2011]
    del payload["rotations"][1]["crops"][2]  # sin la soja, para aislar el trigo
    wheat = payload["rotations"][1]["crops"][1]
    wheat["sowing"] = {"window_year": 2, "day": 15, "month": 6}
    issues = issues_of(payload)
    assert codes(issues) == [v.CODE_CALENDAR_OUTSIDE_WINDOW]
    message = issues[0].message
    assert "wheat" in message and "2008" in message and "2011" in message
    assert issues[0].field == "rotations[1].crops[1].sowing"


def test_calendar_out_of_order_crops_are_reported_as_overlap() -> None:
    payload = plan_request()
    crops = payload["rotations"][1]["crops"]
    crops[0], crops[1] = crops[1], crops[0]  # trigo (jun) antes que maíz (oct): orden invertido
    issues = issues_of(payload)
    assert v.CODE_CALENDAR_OVERLAP in codes(issues)


def test_calendar_is_skipped_for_a_rotation_with_an_unusable_crop() -> None:
    """Si falta la duración de un cultivo ya se informó; no se razona sobre su calendario."""
    payload = plan_request()
    del payload["rotations"][1]["crops"][2]["stage_lengths_days"]  # soja de segunda sin duración
    assert codes(issues_of(payload)) == [v.CODE_MISSING_REFERENCE]


# --- Reunión de errores y excepción ---


def test_errors_from_every_layer_are_collected_together() -> None:
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = 75
    payload["window"]["start_years"] = [2008, 2008, 2025]
    payload["currency"] = None
    payload["rotations"][1]["crops"][0]["crop_code"] = "quinoa"
    assert set(codes(issues_of(payload))) == {
        v.CODE_LATITUDE_OUT_OF_RANGE,
        v.CODE_DUPLICATE_YEARS,
        v.CODE_WINDOW_ENDS_AFTER_TODAY,
        v.CODE_CURRENCY_REQUIRED,
        v.CODE_UNKNOWN_CROP,
    }


def test_raise_if_invalid_carries_every_issue_with_field_message_and_code() -> None:
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = -61
    payload["parcel"]["theta_wp_m3_m3"] = 0.5
    with pytest.raises(InputValidationError) as caught:
        raise_if_invalid(SimulationRequest.model_validate(payload), CATALOG, today=TODAY)
    error = caught.value
    assert error.code == "invalid_input"
    assert {detail["field"] for detail in error.details} == {
        "parcel.latitude_deg",
        "parcel.theta_wp_m3_m3",
    }
    assert all(detail["message"] and detail["code"] for detail in error.details)


def test_messages_are_in_spanish_and_validation_does_no_io() -> None:
    """Los mensajes no usan los textos en inglés de Pydantic."""
    payload = plan_request()
    payload["parcel"]["latitude_deg"] = 75
    payload["window"]["start_years"] = [2025]
    for issue in issues_of(payload):
        for english in ("Field required", "Input should", "Extra inputs"):
            assert english not in issue.message
