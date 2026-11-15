"""Pruebas del registro de supuestos (T030).

Cubren CA-14.1 (código, descripción, alcance, valor, unidad y origen), CA-14.2 (supuestos
siempre presentes), CA-14.3 (supuestos cuando ocurren), CA-14.4 (agrupación con conteo y fechas),
CA-6.7 (sustituciones por fecha) y RNF-1 (misma secuencia, misma lista).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core import messages
from app.domain.missing_data import (
    SUBST_DEW_POINT,
    SUBST_RADIATION,
    SUBST_WIND,
    Substitution,
)
from app.services.assumptions import ALWAYS_ON, AssumptionRegistry

# Lista «siempre» de CA-14.2 más los siempre vigentes del plan §11 (escrita aquí a propósito).
EXPECTED_ALWAYS_ON = [
    "RAINFED_NO_IRRIGATION",  # secano con riego = 0
    "TOP_DOWN_INFILTRATION",  # toda la lluvia infiltra; sin escorrentía por intensidad
    "EXCESS_LOST",  # el excedente se pierde
    "NO_CAPILLARY_RISE",  # ascenso capilar = 0
    "INITIAL_MOISTURE_UNIFORM",  # humedad inicial uniforme en el perfil
    "INITIAL_MOISTURE_EACH_SCENARIO",  # igual en cada escenario (CA-4.6)
    "FIXED_DEPTH_PROFILE",  # perfil de profundidad fija
    "CONSTANT_PRICES_COSTS",  # precios y costos constantes
    "PARAMETERS_NOT_CALIBRATED",  # parámetros no calibrados
    "CELL_SCALE_CLIMATE",  # dato climático de celda
    "UNIFORM_REDISTRIBUTION",  # plan §11
    "LINEAR_ROOT_GROWTH",  # plan §11
    "AVAILABLE_WATER_LIMITS",  # plan §11
    "HUMIDITY_FROM_DEW_POINT",  # plan §11
    "NO_KC_CLIMATE_ADJUSTMENT",  # plan §11
]

DAY = date(2020, 3, 1)


def test_add_always_on_produces_exactly_the_documented_codes() -> None:
    registry = AssumptionRegistry()
    registry.add_always_on()
    codes = [entry.code for entry in registry.entries()]
    assert sorted(codes) == sorted(EXPECTED_ALWAYS_ON)
    assert len(codes) == len(set(codes))
    assert tuple(EXPECTED_ALWAYS_ON) == ALWAYS_ON


def test_always_on_entries_carry_description_scope_and_origin() -> None:
    registry = AssumptionRegistry()
    registry.add_always_on()
    for entry in registry.entries():
        assert entry.description == messages.ASSUMPTION_DESCRIPTIONS[entry.code]
        assert entry.scope == "request" and entry.scope_id is None
        assert entry.origin in {"user", "fao_reference", "team_default", "system_default"}
        assert entry.count == 1 and entry.dates == ()


def test_always_on_does_not_include_the_conditional_assumptions() -> None:
    conditional = {
        "FALLOW_EVAPORATION_LAYER",
        "SUBST_RADIATION_HARGREAVES",
        "ET0_NEGATIVE_CLAMPED",
        "NO_RESIDUE_DECLARED",
        "WINDOW_START_DEFAULT",
    }
    assert not conditional & set(ALWAYS_ON)


def test_three_daily_records_with_the_same_code_and_scope_make_one_entry() -> None:
    """CA-14.4: una entrada con ``count == 3`` y las fechas en orden."""
    registry = AssumptionRegistry()
    for day in (DAY + timedelta(days=5), DAY, DAY + timedelta(days=2)):
        registry.add("ET0_NEGATIVE_CLAMPED", scope="scenario", scope_id="2008", day=day)
    (entry,) = registry.entries()
    assert entry.count == 3
    assert entry.dates == (DAY, DAY + timedelta(days=2), DAY + timedelta(days=5))


def test_different_scope_or_value_keeps_separate_entries() -> None:
    registry = AssumptionRegistry()
    registry.add("ET0_NEGATIVE_CLAMPED", scope="scenario", scope_id="2008", day=DAY)
    registry.add("ET0_NEGATIVE_CLAMPED", scope="scenario", scope_id="2011", day=DAY)
    registry.add("FAO_REFERENCE_VALUE", scope="crop", scope_id="A/1", value=1.25, unit="Ky")
    registry.add("FAO_REFERENCE_VALUE", scope="crop", scope_id="A/1", value=1.20, unit="Kc")
    assert len(registry.entries()) == 4


def test_same_sequence_gives_identical_lists() -> None:
    """RNF-1: determinismo."""

    def build() -> list:
        registry = AssumptionRegistry()
        registry.add_always_on()
        registry.add("WINDOW_START_DEFAULT", value="1 de julio")
        for offset in (3, 1, 2):
            registry.add(
                "ET0_NEGATIVE_CLAMPED",
                scope="scenario",
                scope_id="2008",
                day=DAY + timedelta(days=offset),
            )
        return registry.entries()

    assert build() == build()


def test_entries_keep_the_order_of_first_appearance() -> None:
    registry = AssumptionRegistry()
    registry.add("WINDOW_START_DEFAULT")
    registry.add("NO_RESIDUE_DECLARED", scope="rotation", scope_id="B")
    registry.add("WINDOW_START_DEFAULT")
    assert [entry.code for entry in registry.entries()] == [
        "WINDOW_START_DEFAULT",
        "NO_RESIDUE_DECLARED",
    ]
    assert registry.entries()[0].count == 2


def test_fao_reference_value_has_value_unit_origin_and_scope() -> None:
    """CA-3.3 y CA-14.1: rotación, cultivo, parámetro, valor y cita."""
    registry = AssumptionRegistry()
    registry.add(
        "FAO_REFERENCE_VALUE",
        scope="crop",
        scope_id="A/1/ky",
        value=1.25,
        unit="adimensional",
        source="FAO-33, tabla 2",
    )
    (entry,) = registry.entries()
    assert (entry.value, entry.unit, entry.origin, entry.source) == (
        1.25,
        "adimensional",
        "fao_reference",
        "FAO-33, tabla 2",
    )


def test_the_default_source_comes_from_the_message_table() -> None:
    registry = AssumptionRegistry()
    registry.add("HUMIDITY_FROM_DEW_POINT")
    assert registry.entries()[0].source == "FAO-56, ec. 14"


def test_user_value_origin_can_be_overridden() -> None:
    registry = AssumptionRegistry()
    registry.add("FALLOW_KC_BASE_DEFAULT", origin="team_default", value=0.2, unit="adimensional")
    assert registry.entries()[0].origin == "team_default"


def test_substitutions_are_recorded_per_date_with_value_and_unit() -> None:
    """CA-6.4–CA-6.7: variable, método, valor y fecha de cada sustitución."""
    registry = AssumptionRegistry()
    registry.add_substitutions(
        "2008",
        [
            Substitution("ALLSKY_SFC_SW_DWN", SUBST_RADIATION, (DAY, DAY + timedelta(days=4))),
            Substitution("T2MDEW", SUBST_DEW_POINT, (DAY,)),
            Substitution("WS2M", SUBST_WIND, (DAY + timedelta(days=1),)),
        ],
    )
    by_code = {entry.code: entry for entry in registry.entries()}
    radiation = by_code[SUBST_RADIATION]
    assert radiation.count == 2 and radiation.dates == (DAY, DAY + timedelta(days=4))
    assert (radiation.value, radiation.scope, radiation.scope_id) == (0.16, "scenario", "2008")
    assert by_code[SUBST_DEW_POINT].value == 2.0
    assert by_code[SUBST_WIND].value == 2.0 and by_code[SUBST_WIND].unit == "m/s"
    assert all(entry.origin == "fao_reference" for entry in by_code.values())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code": "NOT_A_CODE"},
        {"code": "EXCESS_LOST", "scope": "planet"},
        {"code": "EXCESS_LOST", "origin": "somebody"},
    ],
)
def test_unknown_code_scope_or_origin_is_rejected(kwargs: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        AssumptionRegistry().add(**kwargs)


def test_registry_starts_empty_and_is_per_instance() -> None:
    first, second = AssumptionRegistry(), AssumptionRegistry()
    first.add_always_on()
    assert len(first) == len(ALWAYS_ON)
    assert len(second) == 0 and second.entries() == []
