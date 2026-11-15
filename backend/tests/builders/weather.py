"""Clima sintético con semilla para las pruebas de invariantes (T021).

Genera una serie diaria de lluvia y ET₀ con casos extremos: lluvias exponenciales en días
aleatorios, un día de 300 mm y una sequía de 120 días sin lluvia, con ET₀ entre 0 y 9 mm/día.
Es determinista: la misma semilla produce siempre la misma serie. No usa archivos ni red.
"""

from __future__ import annotations

import random

EXTREME_DAY_RAIN_MM = 300.0
DROUGHT_DAYS = 120
RAIN_PROBABILITY = 0.18
MEAN_RAIN_MM = 8.0
MAX_ET0_MM = 9.0


def synthetic_weather(seed: int, n_days: int) -> tuple[list[float], list[float]]:
    """Devuelve (lluvia_mm, et0_mm) con ``n_days`` valores cada una."""
    if n_days <= DROUGHT_DAYS + 1:
        raise ValueError("La serie debe tener más días que la sequía sintética.")
    rng = random.Random(seed)
    rain = [
        rng.expovariate(1.0 / MEAN_RAIN_MM) if rng.random() < RAIN_PROBABILITY else 0.0
        for _ in range(n_days)
    ]
    drought_start = rng.randrange(0, n_days - DROUGHT_DAYS)
    for day in range(drought_start, drought_start + DROUGHT_DAYS):
        rain[day] = 0.0
    outside_drought = [
        day for day in range(n_days) if not drought_start <= day < drought_start + DROUGHT_DAYS
    ]
    rain[rng.choice(outside_drought)] = EXTREME_DAY_RAIN_MM
    et0 = [rng.uniform(0.0, MAX_ET0_MM) for _ in range(n_days)]
    return rain, et0
