"""Pruebas de la resolución de parámetros efectivos y su origen (T037).

Cubren CA-1.6 (capacidad del perfil), CA-1.9 (Kc de barbecho), CA-3.3 y CA-3.4 (referencia FAO o
valor del usuario), CA-3.10 (Zr limitada a la profundidad efectiva), CA-3.12 (rastrojo omitido),
D-6 (inicio de ventana por defecto) y CA-14.3 (supuestos cuando ocurren).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models.request import SimulationRequest
from app.services.assumptions import Assumption, AssumptionRegistry
from app.services.catalog_service import load_catalog
from app.services.parameter_resolver import (
    ResolvedInput,
    crop_scope_id,
    fallow_scope_id,
    resolve_parameters,
)
from tests.builders.requests import plan_request

CATALOG = load_catalog()


def resolve(payload: dict[str, Any]) -> tuple[ResolvedInput, list[Assumption]]:
    registry = AssumptionRegistry()
    resolved = resolve_parameters(SimulationRequest.model_validate(payload), CATALOG, registry)
    return resolved, registry.entries()


def find(entries: list[Assumption], code: str, scope_id: str | None = None) -> list[Assumption]:
    return [
        entry
        for entry in entries
        if entry.code == code and (scope_id is None or entry.scope_id == scope_id)
    ]


def test_reference_ky_has_fao_origin_catalog_source_and_assumption() -> None:
    resolved, entries = resolve(plan_request())
    ky = resolved.rotations[0].crops[0].parameters["ky"]
    reference = CATALOG.get("maize").reference_values["ky"]
    assert (ky.value, ky.origin, ky.source) == (1.25, "fao_reference", reference.source)
    assert ky.note == "Valor tabulado FAO, no calibrado para el lote."
    (assumption,) = find(entries, "FAO_REFERENCE_VALUE", "A/1/ky")
    assert (assumption.scope, assumption.value, assumption.origin) == (
        "crop",
        1.25,
        "fao_reference",
    )
    assert assumption.source == reference.source
    assert crop_scope_id("A", 1, "ky") == "A/1/ky"


def test_user_value_has_user_origin_and_no_reference_assumption() -> None:
    resolved, entries = resolve(plan_request())
    kc_mid = resolved.rotations[0].crops[0].parameters["kc_mid"]
    assert (kc_mid.value, kc_mid.origin, kc_mid.source) == (1.2, "user", None)
    assert not find(entries, "FAO_REFERENCE_VALUE", "A/1/kc_mid")


def test_root_depth_above_the_effective_depth_is_limited_with_note_and_assumption() -> None:
    """CA-3.10: la Zr máxima ingresada (1,5 m) se limita a la profundidad efectiva (1,2 m)."""
    resolved, entries = resolve(plan_request())
    zr = resolved.rotations[0].crops[0].parameters["root_depth_max_m"]
    assert zr.value == 1.2
    assert zr.origin == "user"
    assert zr.note is not None and "1.5" in zr.note and "ingresado" in zr.note
    (assumption,) = find(entries, "ROOT_DEPTH_LIMITED", "A/1/root_depth_max_m")
    assert assumption.value == 1.2
    assert resolved.rotations[0].crops[0].spec.root_depth_max_m == 1.2


def test_reference_root_depth_is_also_limited_and_labelled_as_reference() -> None:
    payload = plan_request()
    payload["parcel"]["effective_depth_m"] = 0.5
    resolved, entries = resolve(payload)
    zr = resolved.rotations[1].crops[0].parameters["root_depth_max_m"]  # maíz B: catálogo 1,2 m
    assert zr.value == 0.5 and zr.origin == "team_default"
    assert zr.note is not None and "valor de referencia" in zr.note
    assert find(entries, "ROOT_DEPTH_LIMITED", "B/1/root_depth_max_m")


def test_initial_root_depth_from_catalog_is_a_team_decision_with_its_assumption() -> None:
    resolved, entries = resolve(plan_request())
    zr = resolved.rotations[1].crops[0].parameters["root_depth_initial_m"]  # maíz B: sin ingresar
    assert (zr.value, zr.origin) == (0.25, "team_default")
    (assumption,) = find(entries, "INITIAL_ROOT_DEPTH_TEAM", "B/1/root_depth_initial_m")
    assert assumption.origin == "team_default"


def test_other_team_decisions_use_the_team_reference_code() -> None:
    _, entries = resolve(plan_request())  # Zr máxima del maíz B: decisión del equipo (1,2 m)
    (assumption,) = find(entries, "TEAM_REFERENCE_VALUE", "B/1/root_depth_max_m")
    assert assumption.value == 1.2


def test_omitted_initial_residue_is_zero_with_the_no_residue_assumption() -> None:
    """CA-3.12: la rotación B no declara rastrojo inicial."""
    resolved, entries = resolve(plan_request())
    residue = resolved.rotations[1].initial_residue_cover_pct
    assert (residue.value, residue.origin) == (0.0, "system_default")
    (assumption,) = find(entries, "NO_RESIDUE_DECLARED", fallow_scope_id("B", 0))
    assert (assumption.scope, assumption.value, assumption.unit) == ("fallow", 0.0, "%")
    assert resolved.rotations[1].spec.initial_residue_cover_pct == 0.0


def test_declared_residue_is_a_user_value_without_assumption() -> None:
    resolved, entries = resolve(plan_request())
    assert resolved.rotations[0].initial_residue_cover_pct.origin == "user"
    assert resolved.rotations[0].initial_residue_cover_pct.value == 30
    assert not find(entries, "NO_RESIDUE_DECLARED", "A/0")


def test_residue_after_each_crop_is_declared_or_assumed_zero() -> None:
    resolved, entries = resolve(plan_request())
    assert resolved.rotations[1].crops[0].spec.residue_cover_after_pct == 60  # maíz B: ingresado
    assert resolved.rotations[1].crops[1].spec.residue_cover_after_pct == 0.0  # trigo B: omitido
    assert find(entries, "NO_RESIDUE_DECLARED", "B/2") and find(
        entries, "NO_RESIDUE_DECLARED", "B/3"
    )
    assert not find(entries, "NO_RESIDUE_DECLARED", "B/1")


def test_an_explicit_zero_residue_is_a_user_value_not_an_omission() -> None:
    payload = plan_request()
    payload["rotations"][1]["initial_residue_cover_pct"] = 0
    resolved, entries = resolve(payload)
    assert resolved.rotations[1].initial_residue_cover_pct.origin == "user"
    assert not find(entries, "NO_RESIDUE_DECLARED", "B/0")


def test_default_fallow_kc_is_020_team_decision_with_assumption() -> None:
    """CA-1.9."""
    resolved, entries = resolve(plan_request())
    kc_base = resolved.parcel.fallow_kc_base
    assert (kc_base.value, kc_base.origin) == (0.20, "team_default")
    assert resolved.parcel.spec.fallow_kc_base == 0.20
    (assumption,) = find(entries, "FALLOW_KC_BASE_DEFAULT")
    assert assumption.value == 0.20


def test_user_fallow_kc_is_used_without_the_default_assumption() -> None:
    payload = plan_request()
    payload["parcel"]["fallow_kc_base"] = 0.15
    resolved, entries = resolve(payload)
    assert (resolved.parcel.fallow_kc_base.value, resolved.parcel.fallow_kc_base.origin) == (
        0.15,
        "user",
    )
    assert not find(entries, "FALLOW_KC_BASE_DEFAULT")


def test_fallow_evaporation_layer_is_015_m_system_default() -> None:
    layer = resolve(plan_request())[0].parcel.fallow_evaporation_layer_m
    assert (layer.value, layer.origin) == (0.15, "system_default")


def test_profile_capacity_and_initial_storage() -> None:
    """CA-1.6: 1000 · (0,28 − 0,12) · 1,2 = 192 mm; el 50 % es 96 mm."""
    parcel = resolve(plan_request())[0].parcel
    assert parcel.profile_capacity_mm == pytest.approx(192.0)
    assert parcel.initial_storage_mm == pytest.approx(96.0)


def test_window_start_defaults_to_july_first_with_assumption() -> None:
    payload = plan_request()
    del payload["window"]["start_day"], payload["window"]["start_month"]
    resolved, entries = resolve(payload)
    assert (resolved.window.start_day, resolved.window.start_month) == (1, 7)
    assert resolved.window.start_defaulted
    assert find(entries, "WINDOW_START_DEFAULT")


def test_explicit_window_start_has_no_default_assumption() -> None:
    resolved, entries = resolve(plan_request())
    assert not resolved.window.start_defaulted
    assert not find(entries, "WINDOW_START_DEFAULT")


def test_start_years_are_sorted_and_unique() -> None:
    payload = plan_request()
    payload["window"]["start_years"] = [2017, 2008, 2011]
    assert resolve(payload)[0].window.start_years == (2008, 2011, 2017)


def test_effective_specs_carry_resolved_values_for_the_domain() -> None:
    resolved, _ = resolve(plan_request())
    maize = resolved.rotations[0].crops[0]
    assert maize.crop_name == "Maíz (grano)"
    spec = maize.spec
    assert spec.stages.total_days == 150
    assert (spec.kc_initial, spec.kc_mid, spec.kc_end) == (0.30, 1.20, 0.35)
    assert (spec.ky, spec.ym_t_ha, spec.depletion_fraction_p) == (1.25, 9.0, 0.55)
    assert (spec.price_per_t, spec.direct_costs_per_ha) == (180, 620)
    assert (spec.sowing.window_year, spec.sowing.day, spec.sowing.month) == (1, 15, 10)


def test_cover_crop_has_no_ky_or_ym_and_keeps_its_costs() -> None:
    resolved, _ = resolve(plan_request())
    rye = resolved.rotations[0].crops[1]
    assert rye.spec.crop_type == "cover"
    assert rye.spec.ky is None and rye.spec.ym_t_ha is None
    assert "ky" not in rye.parameters and "ym_t_ha" not in rye.parameters
    assert rye.spec.direct_costs_per_ha == 95 and rye.spec.price_per_t is None


def test_stage_lengths_are_user_or_catalog_with_their_origin() -> None:
    resolved, _ = resolve(plan_request())
    user_stages = resolved.rotations[0].crops[0].parameters["stage_lengths_days"]
    assert user_stages.origin == "user"
    assert user_stages.value == {"initial": 30, "development": 40, "mid": 50, "late": 30}
    payload = plan_request()
    del payload["rotations"][1]["crops"][0]["stage_lengths_days"]  # maíz B: del catálogo
    catalog_stages = resolve(payload)[0].rotations[1].crops[0].parameters["stage_lengths_days"]
    assert catalog_stages.origin == "fao_reference"
    assert catalog_stages.value == {"initial": 25, "development": 40, "mid": 45, "late": 30}
    assert catalog_stages.source and "Tabla 11" in catalog_stages.source


def test_a_missing_value_without_reference_is_an_error_not_a_made_up_number() -> None:
    """La validación debía detener la solicitud: el resolvedor nunca inventa un valor."""
    payload = plan_request()
    del payload["rotations"][0]["crops"][1]["stage_lengths_days"]  # centeno: sin referencia
    with pytest.raises(ValueError):
        resolve(payload)


def test_assumption_scope_ids_are_readable() -> None:
    assert crop_scope_id("A", 2, "kc_mid") == "A/2/kc_mid"
    assert fallow_scope_id("B", 3) == "B/3"
