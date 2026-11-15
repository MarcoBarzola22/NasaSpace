"""Solicitud de tres rotaciones y diez escenarios, para las pruebas de escala y de persistencia."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from tests.builders.power_payload import power_payload
from tests.builders.requests import plan_request

MAIZE_STAGES = {"initial": 30, "development": 40, "mid": 50, "late": 30}
SCALE_YEARS = list(range(2008, 2018))  # 10 escenarios; ventanas hasta 2019-06-30


def maize_crop(window_year: int) -> dict[str, Any]:
    return {
        "crop_code": "maize",
        "sowing": {"window_year": window_year, "day": 15, "month": 10},
        "stage_lengths_days": dict(MAIZE_STAGES),
        "ym_t_ha": 9.0,
        "economics": {"price_per_t": 180, "direct_costs_per_ha": 620},
    }


def scale_request() -> dict[str, Any]:
    """Rotaciones A y B del plan más C (maíz → maíz, CA-3.14), sobre diez años de inicio."""
    payload = plan_request()
    payload["rotations"].append({"id": "C", "crops": [maize_crop(1), maize_crop(2)]})
    payload["window"]["start_years"] = list(SCALE_YEARS)
    return payload


def scale_body() -> bytes:
    """Respuesta de NASA POWER simulada que cubre las diez ventanas (generada una sola vez)."""
    return json.dumps(power_payload(date(2008, 7, 1), date(2019, 6, 30))).encode()
