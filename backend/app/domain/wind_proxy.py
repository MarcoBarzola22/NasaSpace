"""Proxy de exposición del suelo: días de viento fuerte sin cultivo vivo (RF-11; T024).

Un día cuenta como «viento fuerte sin cultivo vivo» solo si se cumplen las dos condiciones:

1. el máximo diario del viento a 2 m (``WS2M_MAX`` de NASA POWER) es **estrictamente mayor** que
   8,0 m/s (decisión del equipo, revisión 3; no calibrado para erosión local), y
2. el día no está entre la siembra y el fin de ciclo de ningún cultivo de la rotación (los cultivos
   de cobertura cuentan como cultivo vivo): es decir, es un día de barbecho (CA-11.2).

Si falta el dato de ``WS2M_MAX`` en un día sin cultivo vivo, el día se cuenta como «sin dato de
viento» y no como fuerte ni calmo (CA-11.4). La función recibe únicamente la serie cruda de
``WS2M_MAX``: los 2 m/s que se sustituyen en ``WS2M`` para la ET₀ nunca llegan aquí (CA-6.8).

Es un conteo descriptivo. No se convierte en toneladas de suelo ni en pérdidas de nitrógeno o
carbono, y «días sin cultivo vivo» no equivale a «suelo desnudo», aunque haya rastrojo (CA-11.6).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.constants import WIND_STRONG_THRESHOLD_MS, WIND_STRONG_VARIABLE
from app.domain.types import CropSegment, Timeline


@dataclass(frozen=True, slots=True)
class SoilExposure:
    window_days: int
    live_crop_days: int
    no_live_crop_days: int
    strong_wind_days_without_live_crop: int
    no_wind_data_days_without_live_crop: int
    wind_variable: str = WIND_STRONG_VARIABLE
    threshold_ms: float = WIND_STRONG_THRESHOLD_MS


def is_strong_wind(wind_max_ms: float) -> bool:
    """Viento fuerte: estrictamente mayor que el umbral (8,0 m/s no cuenta)."""
    return wind_max_ms > WIND_STRONG_THRESHOLD_MS


def soil_exposure(timeline: Timeline, wind_max_ms: Sequence[float | None]) -> SoilExposure:
    """Cuenta los días con y sin cultivo vivo y los de viento fuerte entre estos últimos.

    ``wind_max_ms`` trae un valor de ``WS2M_MAX`` por día de la línea de tiempo, en orden;
    ``None`` marca un dato faltante.
    """
    if len(wind_max_ms) != timeline.n_days:
        raise ValueError(
            f"Se esperaban {timeline.n_days} valores de WS2M_MAX (recibidos: {len(wind_max_ms)})."
        )
    live_days = no_live_days = strong_days = no_data_days = 0
    index = 0
    for segment in timeline.segments:
        if isinstance(segment, CropSegment):
            live_days += segment.n_days
            index += segment.n_days
            continue
        for _ in range(segment.n_days):
            no_live_days += 1
            value = wind_max_ms[index]
            index += 1
            if value is None:
                no_data_days += 1
            elif math.isnan(value) or value < 0:
                raise ValueError("WS2M_MAX debe ser un número no negativo o None si falta.")
            elif is_strong_wind(value):
                strong_days += 1
    return SoilExposure(
        window_days=timeline.n_days,
        live_crop_days=live_days,
        no_live_crop_days=no_live_days,
        strong_wind_days_without_live_crop=strong_days,
        no_wind_data_days_without_live_crop=no_data_days,
    )
