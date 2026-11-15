"""Pruebas de los textos centralizados en ``core.messages`` (T029).

Cubren CA-10.8 (precios y costos constantes), CA-1.9 (supuesto del Kc de barbecho), CA-11.5
(fuente del umbral), CA-12.5 (rótulo de los rangos), CA-13.2 (rótulo de la serie),
CA-14.1–CA-14.3 (supuestos), CA-16.6 (textos en español), CA-17.2, CA-17.3 y CA-17.5
(advertencias).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import messages
from app.domain import missing_data
from app.services.assumptions import DEFAULT_ORIGIN, ORIGINS

SPEC_PATH = Path(__file__).resolve().parents[3] / "specs" / "001-agrodss-backend" / "spec.md"

WARNING_CODES = {
    "HISTORICAL_DESCRIPTIVE",
    "UNCALIBRATED_PARAMETERS",
    "CELL_SCALE_DATA",
    "NOT_A_RECOMMENDATION",
    "SUBSTITUTIONS_PRESENT",
    "SCENARIOS_BLOCKED",
    "OUTSIDE_SAN_LUIS",
}

# CA-14.2 (siempre), CA-14.3 (cuando ocurren) y plan §11, más los de CA-3.3/CA-3.4/CA-1.9.
ASSUMPTION_CODES = {
    "RAINFED_NO_IRRIGATION",
    "TOP_DOWN_INFILTRATION",
    "EXCESS_LOST",
    "NO_CAPILLARY_RISE",
    "INITIAL_MOISTURE_UNIFORM",
    "INITIAL_MOISTURE_EACH_SCENARIO",
    "FIXED_DEPTH_PROFILE",
    "CONSTANT_PRICES_COSTS",
    "PARAMETERS_NOT_CALIBRATED",
    "CELL_SCALE_CLIMATE",
    "FAO_REFERENCE_VALUE",
    "TEAM_REFERENCE_VALUE",
    "FALLOW_KC_BASE_DEFAULT",
    "NO_RESIDUE_DECLARED",
    "RESIDUE_NO_DECOMPOSITION",
    "SUBST_RADIATION_HARGREAVES",
    "SUBST_HUMIDITY_TMIN",
    "SUBST_WIND_FAO56_DEFAULT",
    "ET0_NEGATIVE_CLAMPED",
    "YIELD_CLIPPED_TO_ZERO",
    "ROOT_DEPTH_LIMITED",
    "FALLOW_EVAPORATION_LAYER",
    "UNIFORM_REDISTRIBUTION",
    "LINEAR_ROOT_GROWTH",
    "INITIAL_ROOT_DEPTH_TEAM",
    "AVAILABLE_WATER_LIMITS",
    "HUMIDITY_FROM_DEW_POINT",
    "NO_KC_CLIMATE_ADJUSTMENT",
    "WINDOW_START_DEFAULT",
    "UNPUBLISHED_DATA_BLOCK",
}


@pytest.fixture(scope="module")
def spec_text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def test_the_seven_warning_codes_exist_with_a_text() -> None:
    assert set(messages.WARNINGS) == WARNING_CODES
    assert all(text.strip() for text in messages.WARNINGS.values())


def test_every_assumption_code_of_the_spec_and_plan_has_a_description() -> None:
    assert ASSUMPTION_CODES <= set(messages.ASSUMPTION_DESCRIPTIONS)
    assert set(messages.ASSUMPTION_DESCRIPTIONS) == ASSUMPTION_CODES


def test_every_assumption_has_a_valid_default_origin() -> None:
    assert set(DEFAULT_ORIGIN) == set(messages.ASSUMPTION_DESCRIPTIONS)
    assert set(DEFAULT_ORIGIN.values()) <= set(ORIGINS)


def test_sources_only_cite_known_assumptions() -> None:
    assert set(messages.ASSUMPTION_SOURCES) <= set(messages.ASSUMPTION_DESCRIPTIONS)


def test_warnings_use_the_literal_texts_of_the_spec(spec_text: str) -> None:
    """CA-17.2 y CA-13.2: las advertencias reproducen el texto exacto del spec."""
    assert messages.WARNINGS["HISTORICAL_DESCRIPTIVE"] in spec_text
    assert messages.WARNINGS["CELL_SCALE_DATA"] in spec_text


def test_labels_use_the_literal_texts_of_the_spec(spec_text: str) -> None:
    assert messages.RANGE_LABEL in spec_text  # CA-12.5
    assert messages.CELL_SCALE_LABEL in spec_text  # CA-13.2
    assert messages.WIND_THRESHOLD_SOURCE in spec_text  # CA-11.5
    assert messages.ASSUMPTION_DESCRIPTIONS["FALLOW_KC_BASE_DEFAULT"] in spec_text  # CA-1.9


def test_uncalibrated_warning_names_kc_ky_ym_and_soil() -> None:
    text = messages.WARNINGS["UNCALIBRATED_PARAMETERS"]
    assert all(term in text for term in ("Kc", "Ky", "Ym", "suelo"))


def test_not_a_recommendation_warning_lists_what_the_model_leaves_out() -> None:
    """CA-17.4 y CA-17.5."""
    text = messages.WARNINGS["NOT_A_RECOMMENDATION"]
    for omitted in ("nitrógeno", "malezas", "enfermedades", "erosión", "carbono"):
        assert omitted in text


def test_every_block_code_of_the_domain_has_a_reason() -> None:
    codes = {
        value
        for name, value in vars(missing_data).items()
        if name.startswith("BLOCK_") and isinstance(value, str)
    }
    assert codes and codes <= set(messages.BLOCK_REASONS)


def test_error_templates_include_their_parameters() -> None:
    assert "60 s" in messages.POWER_TIMEOUT.format(seconds=60.0)
    assert "(503)" in messages.POWER_BAD_STATUS.format(status=503)
    assert "secano" in messages.IRRIGATION_NOT_SUPPORTED


def test_error_messages_do_not_expose_technical_details() -> None:
    for text in (
        messages.CALCULATION_INTEGRITY,
        messages.UNEXPECTED_ERROR,
        messages.POWER_BAD_FORMAT,
    ):
        assert "Traceback" not in text and "app." not in text


def test_range_label_is_the_only_text_that_denies_probability() -> None:
    assert messages.ALLOWED_PHRASES == ("no es una probabilidad ni un pronóstico",)


def test_constant_prices_assumption_states_the_three_points_of_the_spec() -> None:
    """CA-10.8: sin cambios en los escenarios, ni históricos ni pronosticados, sin descuento."""
    text = messages.ASSUMPTION_DESCRIPTIONS["CONSTANT_PRICES_COSTS"]
    assert "sin cambios" in text
    assert "no son precios históricos ni pronosticados" in text
    assert "no se descuentan entre el año 1 y el año 2" in text
