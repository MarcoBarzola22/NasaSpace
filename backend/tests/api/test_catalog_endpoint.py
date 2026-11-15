"""Pruebas de ``GET /api/v1/catalog`` (T032).

Cubren CA-2.1 (cultivos con valores y citas), CA-2.2 (sin Ym, precios ni costos), CA-2.3
(«sin referencia»), CA-2.5 (rótulo FAO), CA-2.6 (Kc de barbecho y regla de rastrojo) y CA-11.5
(regla del proxy de viento).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.catalog import CatalogResponse


def test_catalog_returns_the_documented_blocks(client: TestClient) -> None:
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "contract_version",
        "catalog_version",
        "catalog_label",
        "crops",
        "fallow",
        "wind_proxy",
        "window_defaults",
        "limits",
    }
    CatalogResponse.model_validate(body)


def test_fallow_defaults_and_rules_with_their_sources(client: TestClient) -> None:
    fallow = client.get("/api/v1/catalog").json()["fallow"]
    assert fallow["kc_base_default"] == 0.2
    assert fallow["evaporation_layer_m"] == 0.15
    assert "equipo AgroDSS" in fallow["kc_base_source"]
    assert "0,05" in fallow["residue_rule"] and fallow["residue_rule_source"].startswith("FAO-56")


def test_wind_proxy_rule(client: TestClient) -> None:
    wind = client.get("/api/v1/catalog").json()["wind_proxy"]
    assert wind["variable"] == "WS2M_MAX" and wind["threshold_ms"] == 8.0
    assert "8,0 m/s" in wind["rule"] and "sin cultivo vivo" in wind["rule"]
    assert "no calibrado para erosión local" in wind["source"]


def test_limits_and_window_defaults(client: TestClient) -> None:
    body = client.get("/api/v1/catalog").json()
    assert body["limits"] == {
        "max_rotations": 3,
        "max_start_years": 10,
        "max_effective_depth_m": 3.0,
    }
    assert body["window_defaults"] == {"start_day": 1, "start_month": 7}


def test_every_crop_has_a_label_and_the_five_catalog_crops_are_present(client: TestClient) -> None:
    crops = client.get("/api/v1/catalog").json()["crops"]
    assert [crop["crop_code"] for crop in crops] == [
        "maize",
        "soybean_first",
        "soybean_second",
        "wheat",
        "rye_cover",
    ]
    assert all(crop["label"] for crop in crops)


def test_every_value_has_a_source_or_a_status_without_reference(client: TestClient) -> None:
    for crop in client.get("/api/v1/catalog").json()["crops"]:
        assert len(crop["reference_values"]) == 8
        for name, entry in crop["reference_values"].items():
            if entry["value"] is not None:
                assert entry["source"], (crop["crop_code"], name)
            else:
                assert entry["status"] in ("sin referencia", "no aplica"), (crop["crop_code"], name)


def test_labels_distinguish_complete_crops_from_those_needing_user_values(
    client: TestClient,
) -> None:
    by_code = {c["crop_code"]: c for c in client.get("/api/v1/catalog").json()["crops"]}
    assert by_code["maize"]["label"] == "Valor tabulado FAO, no calibrado para el lote."
    assert by_code["rye_cover"]["label"] == "Los valores «sin referencia» deben ingresarse."
    assert by_code["rye_cover"]["reference_values"]["ky"]["status"] == "no aplica"


def test_catalog_has_no_yield_prices_or_costs(client: TestClient) -> None:
    """CA-2.2."""
    text = client.get("/api/v1/catalog").text.lower()
    for forbidden in ("ym_t_ha", "price", "direct_costs", "precio"):
        assert forbidden not in text


def test_catalog_does_not_call_nasa_power() -> None:
    from tests.api.conftest import make_client

    client, server = make_client()
    client.get("/api/v1/catalog")
    assert server.requests == []
