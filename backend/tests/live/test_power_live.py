"""Prueba en vivo contra la API real de NASA POWER (T050; marcada ``live``).

Requiere internet y se excluye por defecto: ``pytest -m live -s``. Completa una solicitud de
3 rotaciones × 3 escenarios en un punto de San Luis, por la API completa y sin simulaciones.
Verifica CA-5.1 (una consulta real), CA-8.16 (cierre de masa) y el riesgo R-5 del plan (cuántos
días de viento fuerte hay en la práctica), e imprime un resumen **sin valores de las series
diarias** para pegarlo en ``research.md`` («Prueba en vivo»).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.builders.requests import plan_request
from tests.builders.scale import maize_crop

pytestmark = pytest.mark.live

LATITUDE_DEG = -33.68
LONGITUDE_DEG = -65.47
START_YEARS = [2010, 2015, 2020]


def live_request() -> dict[str, Any]:
    """Rotaciones A y B del plan más C (maíz → maíz), en un punto genérico de San Luis."""
    payload = plan_request()
    payload["rotations"].append({"id": "C", "crops": [maize_crop(1), maize_crop(2)]})
    payload["parcel"].update(latitude_deg=LATITUDE_DEG, longitude_deg=LONGITUDE_DEG)
    payload["window"]["start_years"] = list(START_YEARS)
    return payload


def test_live_request_completes_three_rotations_by_three_scenarios(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = TestClient(create_app(), raise_server_exceptions=False)
    started = time.perf_counter()
    response = client.post("/api/v1/simulations", json=live_request())
    elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text[:500]
    body = response.json()
    computed = [s for s in body["scenarios"] if s["status"] == "computed"]
    assert computed, "ningún escenario se pudo calcular con los datos reales"
    assert len(body["results"]) == 3 * len(computed)
    closures = [abs(r["water_balance"]["mass_balance_error_mm"]) for r in body["results"]]
    assert max(closures) <= 0.01
    assert body["provenance"]["source"] == "NASA POWER"
    assert body["provenance"]["queried_at"]

    with capsys.disabled():
        print("\n--- RESUMEN DE LA PRUEBA EN VIVO (sin series diarias) ---")
        print(f"fecha: {datetime.now(UTC):%Y-%m-%d} (UTC)")
        print(f"coordenadas: {LATITUDE_DEG}, {LONGITUDE_DEG}; años de inicio: {START_YEARS}")
        print(f"HTTP: {response.status_code}; duración total: {elapsed:.1f} s")
        print(f"versión de la fuente: {body['provenance']['source_version']}")
        print(f"rango consultado: {body['provenance']['date_range']}")
        print(f"escenarios: {[(s['start_year'], s['status']) for s in body['scenarios']]}")
        print(f"máximo |cierre|: {max(closures):.6f} mm")
        for result in body["results"]:
            exposure = result["soil_exposure"]
            print(
                f"{result['rotation_id']} {result['start_year']}: "
                f"días sin cultivo vivo {exposure['no_live_crop_days']}, "
                f"con WS2M_MAX > 8 m/s {exposure['strong_wind_days_without_live_crop']}, "
                f"sin dato de viento {exposure['no_wind_data_days_without_live_crop']}"
            )
        missing = {v["code"]: v["missing_days"] for v in body["provenance"]["variables"]}
        print(f"días faltantes por variable: {missing}")
