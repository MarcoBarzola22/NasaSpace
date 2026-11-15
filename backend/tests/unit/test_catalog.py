"""Pruebas del catálogo de cultivos FAO (T031).

Criterios que verifica: CA-2.1 (parámetros con unidad y cita), CA-2.2 (sin Ym, precios ni
costos), CA-2.3 (parámetros «sin referencia» declarados), CA-2.4 (cultivos mínimos) y
CA-2.5 (leyenda «no calibrado»).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.services.catalog_service import (
    DEFAULT_CATALOG_PATH,
    PARAMETER_CODES,
    CatalogError,
    load_catalog,
)

EXPECTED_CROPS = {"maize", "soybean_first", "soybean_second", "wheat", "rye_cover"}
FORBIDDEN_KEY_FRAGMENTS = ("ym", "price", "precio", "cost", "costo")


@pytest.fixture(name="raw")
def raw_catalog() -> dict:
    return json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))


def write_catalog(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "crop_catalog.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def all_keys(node: object) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {key for child in node.values() for key in all_keys(child)}
    if isinstance(node, list):
        return {key for child in node for key in all_keys(child)}
    return set()


def test_catalog_has_the_five_approved_crops() -> None:
    catalog = load_catalog()
    assert set(catalog.crop_codes) == EXPECTED_CROPS
    assert len(catalog.crops) == 5


def test_every_crop_declares_the_eight_parameters() -> None:
    catalog = load_catalog()
    for crop in catalog.crops:
        assert set(crop.reference_values) == set(PARAMETER_CODES), crop.crop_code


def test_every_valued_entry_has_a_source_and_a_unit() -> None:
    catalog = load_catalog()
    for crop in catalog.crops:
        for name, entry in crop.reference_values.items():
            if entry.value is not None:
                assert entry.source and entry.source.strip(), f"{crop.crop_code}.{name}"
                assert entry.unit, f"{crop.crop_code}.{name}"


def test_missing_values_are_declared_not_filled() -> None:
    catalog = load_catalog()
    for crop in catalog.crops:
        for name, entry in crop.reference_values.items():
            if entry.value is None:
                assert entry.status in {"sin referencia", "no aplica"}, f"{crop.crop_code}.{name}"
    assert catalog.get("soybean_second").reference_values["stage_lengths_days"].value is None
    assert catalog.get("rye_cover").reference_values["stage_lengths_days"].value is None
    assert catalog.get("rye_cover").reference_values["ky"].status == "no aplica"


def test_catalog_has_no_yield_price_or_cost_fields(raw: dict) -> None:
    for key in all_keys(raw):
        assert not any(fragment in key.lower() for fragment in FORBIDDEN_KEY_FRAGMENTS), key


def test_catalog_label_and_review_are_recorded() -> None:
    catalog = load_catalog()
    assert catalog.label == "Valor tabulado FAO, no calibrado para el lote."
    assert catalog.reviewed_by == "Mauro"


def test_approved_reference_values() -> None:
    """Fija los valores aprobados el 2026-11-15 (research.md, V-2)."""
    catalog = load_catalog()
    value = {
        code: {name: entry.value for name, entry in catalog.get(code).reference_values.items()}
        for code in EXPECTED_CROPS
    }
    assert value["maize"]["stage_lengths_days"] == {
        "initial": 25,
        "development": 40,
        "mid": 45,
        "late": 30,
    }
    assert value["maize"]["root_depth_max_m"] == 1.2
    assert value["wheat"]["kc_initial"] == 0.70
    assert value["wheat"]["kc_end"] == 0.25
    assert value["soybean_first"]["kc_initial"] == 0.40
    assert value["maize"]["ky"] == 1.25
    # Decisión técnica del equipo: Zr inicial de 0,25 m para los cinco cultivos.
    for code in EXPECTED_CROPS:
        entry = catalog.get(code).reference_values["root_depth_initial_m"]
        assert entry.value == 0.25, code
        assert entry.origin == "team_default", code


def test_rye_source_states_assimilation_to_small_cereals() -> None:
    entry = load_catalog().get("rye_cover").reference_values["kc_mid"]
    assert "asimilado a cereales menores (avena/cebada)" in (entry.source or "")


def test_missing_source_fails_load(tmp_path: Path, raw: dict) -> None:
    broken = copy.deepcopy(raw)
    maize = next(crop for crop in broken["crops"] if crop["crop_code"] == "maize")
    maize["reference_values"]["kc_mid"]["source"] = ""
    with pytest.raises(CatalogError) as error:
        load_catalog(write_catalog(tmp_path, broken))
    assert "maize.kc_mid" in str(error.value)
    assert "cita" in str(error.value)


def test_yield_field_is_rejected(tmp_path: Path, raw: dict) -> None:
    broken = copy.deepcopy(raw)
    broken["crops"][0]["reference_values"]["ym_t_ha"] = {
        "value": 9.0,
        "unit": "t/ha",
        "status": "referencia",
        "origin": "fao_reference",
        "source": "x",
        "note": None,
    }
    with pytest.raises(CatalogError) as error:
        load_catalog(write_catalog(tmp_path, broken))
    assert "ym_t_ha" in str(error.value)


def test_initial_root_depth_above_maximum_fails(tmp_path: Path, raw: dict) -> None:
    broken = copy.deepcopy(raw)
    wheat = next(crop for crop in broken["crops"] if crop["crop_code"] == "wheat")
    wheat["reference_values"]["root_depth_initial_m"]["value"] = 2.0
    with pytest.raises(CatalogError) as error:
        load_catalog(write_catalog(tmp_path, broken))
    assert "Zr inicial" in str(error.value)


def test_cover_crop_with_ky_fails(tmp_path: Path, raw: dict) -> None:
    broken = copy.deepcopy(raw)
    rye = next(crop for crop in broken["crops"] if crop["crop_code"] == "rye_cover")
    rye["reference_values"]["ky"] = {
        "value": 1.0,
        "unit": "adimensional",
        "status": "referencia",
        "origin": "fao_reference",
        "source": "x",
        "note": None,
    }
    with pytest.raises(CatalogError) as error:
        load_catalog(write_catalog(tmp_path, broken))
    assert "rye_cover.ky" in str(error.value)


def test_all_defects_are_reported_together(tmp_path: Path, raw: dict) -> None:
    broken = copy.deepcopy(raw)
    broken["crops"][0]["reference_values"]["kc_mid"]["source"] = ""
    broken["crops"][1]["reference_values"]["ky"]["value"] = -1
    with pytest.raises(CatalogError) as error:
        load_catalog(write_catalog(tmp_path, broken))
    assert len(error.value.problems) >= 2


def test_unreadable_file_fails_with_explicit_error(tmp_path: Path) -> None:
    with pytest.raises(CatalogError):
        load_catalog(tmp_path / "does_not_exist.json")
