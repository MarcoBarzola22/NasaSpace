"""Solicitud de ejemplo del plan §5.2 como diccionario JSON, para las pruebas de entrada.

Los valores numéricos solo ilustran el formato: no son valores validados ni recomendados.
"""

from __future__ import annotations

import copy
from typing import Any

_PLAN_REQUEST: dict[str, Any] = {
    "parcel": {
        "name": "Lote 7 — Villa Mercedes",
        "latitude_deg": -33.68,
        "longitude_deg": -65.47,
        "theta_fc_m3_m3": 0.28,
        "theta_wp_m3_m3": 0.12,
        "effective_depth_m": 1.2,
        "initial_available_water_pct": 50,
        "fallow_kc_base": None,
    },
    "window": {"start_day": 1, "start_month": 7, "start_years": [2008, 2011, 2017]},
    "currency": "USD",
    "rotations": [
        {
            "id": "A",
            "name": "Maíz → centeno de cobertura → soja",
            "initial_residue_cover_pct": 30,
            "crops": [
                {
                    "crop_code": "maize",
                    "sowing": {"window_year": 1, "day": 15, "month": 10},
                    "stage_lengths_days": {
                        "initial": 30,
                        "development": 40,
                        "mid": 50,
                        "late": 30,
                    },
                    "kc_initial": 0.30,
                    "kc_mid": 1.20,
                    "kc_end": 0.35,
                    "root_depth_initial_m": 0.15,
                    "root_depth_max_m": 1.5,
                    "depletion_fraction_p": None,
                    "ky": None,
                    "ym_t_ha": 9.0,
                    "residue_cover_after_pct": 60,
                    "economics": {"price_per_t": 180, "direct_costs_per_ha": 620},
                },
                {
                    "crop_code": "rye_cover",
                    "sowing": {"window_year": 1, "day": 1, "month": 4},
                    "stage_lengths_days": {
                        "initial": 20,
                        "development": 40,
                        "mid": 40,
                        "late": 20,
                    },
                    "kc_initial": 0.30,
                    "kc_mid": 1.00,
                    "kc_end": 0.80,
                    "root_depth_initial_m": 0.15,
                    "root_depth_max_m": 0.8,
                    "depletion_fraction_p": 0.55,
                    "residue_cover_after_pct": 80,
                    "economics": {"direct_costs_per_ha": 95},
                },
                {
                    "crop_code": "soybean_first",
                    "sowing": {"window_year": 2, "day": 15, "month": 11},
                    "stage_lengths_days": {
                        "initial": 20,
                        "development": 30,
                        "mid": 60,
                        "late": 25,
                    },
                    "root_depth_initial_m": 0.15,
                    "ym_t_ha": 3.2,
                    "residue_cover_after_pct": 30,
                    "economics": {"price_per_t": 300, "direct_costs_per_ha": 380},
                },
            ],
        },
        {
            "id": "B",
            "name": "Maíz → trigo → soja de segunda",
            "crops": [
                {
                    "crop_code": "maize",
                    "sowing": {"window_year": 1, "day": 15, "month": 10},
                    "stage_lengths_days": {
                        "initial": 30,
                        "development": 40,
                        "mid": 50,
                        "late": 30,
                    },
                    "ym_t_ha": 9.0,
                    "residue_cover_after_pct": 60,
                    "economics": {"price_per_t": 180, "direct_costs_per_ha": 620},
                },
                {
                    "crop_code": "wheat",
                    "sowing": {"window_year": 1, "day": 1, "month": 6},
                    "stage_lengths_days": {
                        "initial": 25,
                        "development": 55,
                        "mid": 70,
                        "late": 35,
                    },
                    "ym_t_ha": 3.5,
                    "economics": {"price_per_t": 200, "direct_costs_per_ha": 420},
                },
                {
                    "crop_code": "soybean_second",
                    "sowing": {"window_year": 2, "day": 3, "month": 12},
                    "stage_lengths_days": {
                        "initial": 15,
                        "development": 25,
                        "mid": 50,
                        "late": 20,
                    },
                    "ym_t_ha": 2.0,
                    "economics": {"price_per_t": 300, "direct_costs_per_ha": 300},
                },
            ],
        },
    ],
}


def plan_request() -> dict[str, Any]:
    """Copia profunda de la solicitud del plan §5.2 (se puede modificar sin afectar a otras)."""
    return copy.deepcopy(_PLAN_REQUEST)
