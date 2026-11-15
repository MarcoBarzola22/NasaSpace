"""Pruebas de las constantes y de la jerarquía de excepciones (T006).

Criterios que verifica: CA-1.9 (Kc base de barbecho), CA-8.10 (rastrojo), CA-8.16 (cierre de
masa), CA-11.1 (umbral de viento), CA-3.9 y límites de CA-1.4 y CA-4.1 (rangos físicos),
CA-1.11 (caja de San Luis) y CA-16.4 (tres categorías de error).
"""

from __future__ import annotations

import pytest

from app.core import constants as c
from app.core.exceptions import (
    AgroDSSError,
    CalculationIntegrityError,
    DomainError,
    InfrastructureError,
    InputValidationError,
    PowerBadResponseError,
    PowerError,
    PowerRateLimitedError,
    PowerTimeoutError,
    PowerUnreachableError,
)
from app.services.catalog_service import load_catalog


def test_constants_match_approved_decisions() -> None:
    # Proxy de viento: WS2M_MAX > 8 m/s (decisión 10, revisión 3).
    assert c.WIND_STRONG_VARIABLE == "WS2M_MAX"
    assert c.WIND_STRONG_THRESHOLD_MS == 8.0
    # Barbecho y rastrojo.
    assert c.FALLOW_KC_BASE_DEFAULT == 0.20
    assert c.FALLOW_EVAPORATION_LAYER_M == 0.15
    assert c.RESIDUE_EVAPORATION_REDUCTION_PER_10PCT == 0.05
    # Zr inicial de referencia (T-26).
    assert c.DEFAULT_INITIAL_ROOT_DEPTH_M == 0.25
    # Controles de masa.
    assert c.MASS_CLOSURE_TOLERANCE_MM == 0.01
    assert c.DAILY_EPSILON_MM == 1e-9
    # Sustituciones y parámetros de FAO-56.
    assert c.HARGREAVES_KRS == 0.16
    assert c.DEW_POINT_SEMIARID_OFFSET_C == 2.0
    assert c.DEFAULT_WIND_2M_MS == 2.0
    assert c.ALBEDO == 0.23
    assert c.STEFAN_BOLTZMANN_MJ_K4_M2_DAY == 4.903e-9
    assert c.KELVIN_OFFSET == 273.16
    # Límites de validación.
    assert c.MAX_ROTATIONS == 3
    assert c.MAX_START_YEARS == 10
    assert c.MAX_EFFECTIVE_DEPTH_M == 3.0
    assert c.MAX_KC == 2.0
    assert c.MAX_KY == 2.0
    assert c.MAX_YM_T_HA == 30.0
    assert c.MAX_STAGE_DAYS == 365
    assert c.MAX_FALLOW_KC_BASE == 1.0
    assert c.MAX_ABS_LATITUDE_DEG == 60.0  # CA-1.12 (decisión del equipo, 2026-11-15)
    assert (c.CONTRACT_VERSION, c.MODEL_VERSION) == ("1.0", "0.1.0")  # CA-13.3, CA-15.6
    # Ventana por defecto (1 de julio) y caja de San Luis.
    assert (c.DEFAULT_WINDOW_START_DAY, c.DEFAULT_WINDOW_START_MONTH) == (1, 7)
    assert (c.SAN_LUIS_LAT_MIN_DEG, c.SAN_LUIS_LAT_MAX_DEG) == (-36.0, -31.8)
    assert (c.SAN_LUIS_LON_MIN_DEG, c.SAN_LUIS_LON_MAX_DEG) == (-67.6, -64.8)


def test_initial_root_depth_matches_the_catalog() -> None:
    """La Zr inicial del catálogo y la constante del código son la misma decisión (T-26)."""
    for crop in load_catalog().crops:
        entry = crop.reference_values["root_depth_initial_m"]
        assert entry.value == c.DEFAULT_INITIAL_ROOT_DEPTH_M, crop.crop_code


def test_fallow_defaults_are_physically_consistent() -> None:
    assert 0 < c.FALLOW_KC_BASE_DEFAULT <= c.MAX_FALLOW_KC_BASE
    assert 0 < c.FALLOW_EVAPORATION_LAYER_M < c.MAX_EFFECTIVE_DEPTH_M
    assert c.SAN_LUIS_LAT_MIN_DEG < c.SAN_LUIS_LAT_MAX_DEG
    assert c.SAN_LUIS_LON_MIN_DEG < c.SAN_LUIS_LON_MAX_DEG


def test_exception_hierarchy() -> None:
    power_errors = (
        PowerUnreachableError,
        PowerTimeoutError,
        PowerRateLimitedError,
        PowerBadResponseError,
    )
    for error in power_errors:
        assert issubclass(error, PowerError), error
        assert issubclass(error, InfrastructureError), error
    for error in (InputValidationError, CalculationIntegrityError, PowerError):
        assert issubclass(error, AgroDSSError), error


def test_domain_and_infrastructure_errors_are_separate() -> None:
    assert issubclass(CalculationIntegrityError, DomainError)
    assert not issubclass(CalculationIntegrityError, InfrastructureError)
    assert not issubclass(PowerTimeoutError, DomainError)
    assert not issubclass(InputValidationError, DomainError | InfrastructureError)


def test_error_categories_codes_and_retryable() -> None:
    expected = {
        InputValidationError: ("input", "invalid_input", False),
        CalculationIntegrityError: ("internal", "calculation_integrity", False),
        PowerUnreachableError: ("nasa_power", "power_unreachable", True),
        PowerTimeoutError: ("nasa_power", "power_timeout", True),
        PowerRateLimitedError: ("nasa_power", "power_rate_limited", True),
        PowerBadResponseError: ("nasa_power", "power_bad_response", True),
        AgroDSSError: ("internal", "unexpected_error", False),
    }
    for error, (category, code, retryable) in expected.items():
        assert (error.category, error.code, error.retryable) == (category, code, retryable), error


def test_input_validation_error_keeps_all_details() -> None:
    details = [
        {"field": "parcel.theta_wp_m3_m3", "message": "El punto de marchitez debe ser menor."},
        {"field": "rotations[0].crops[1].ym_t_ha", "message": "Ym es obligatorio."},
    ]
    error = InputValidationError(details)
    assert error.details == details
    assert error.code == "invalid_input"
    irrigation = InputValidationError(details, code="irrigation_not_supported")
    assert irrigation.code == "irrigation_not_supported"
    assert InputValidationError.code == "invalid_input"  # no contamina la clase


def test_calculation_integrity_error_carries_context() -> None:
    error = CalculationIntegrityError(
        "cierre de masa fuera de tolerancia", closure_mm=0.5, rotation_id="A", start_year=2008
    )
    assert (error.closure_mm, error.rotation_id, error.start_year) == (0.5, "A", 2008)
    assert "cierre de masa" in str(error)
    with pytest.raises(AgroDSSError):
        raise error
