"""Curva de Kc por etapas y demanda del cultivo ETc = Kc × ET₀ (RF-8; T015).

La curva sigue FAO-56 (ec. 66, Kc de un solo coeficiente): Kc inicial constante en la etapa
inicial; variación lineal hasta Kc medio en el desarrollo; Kc medio constante en la etapa media;
variación lineal hasta Kc final en la etapa final. El día 1 del ciclo es el de la siembra. No se
aplica el ajuste climático de Kc medio y final (supuesto ``NO_KC_CLIMATE_ADJUSTMENT``, D-13).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.types import CropSpec, Stages


def kc_for_day(
    stages: Stages, kc_initial: float, kc_mid: float, kc_end: float, day_in_cycle: int
) -> float:
    """Kc del día ``day_in_cycle`` (1 ≤ día ≤ duración total del ciclo)."""
    if not 1 <= day_in_cycle <= stages.total_days:
        raise ValueError(
            f"El día del ciclo debe estar entre 1 y {stages.total_days} (recibido: {day_in_cycle})."
        )
    end_initial = stages.initial
    end_development = end_initial + stages.development
    end_mid = end_development + stages.mid
    if day_in_cycle <= end_initial:
        return kc_initial
    if day_in_cycle <= end_development:
        return kc_initial + (day_in_cycle - end_initial) / stages.development * (
            kc_mid - kc_initial
        )
    if day_in_cycle <= end_mid:
        return kc_mid
    return kc_mid + (day_in_cycle - end_mid) / stages.late * (kc_end - kc_mid)


def kc_for_crop(crop: CropSpec, day_in_cycle: int) -> float:
    return kc_for_day(crop.stages, crop.kc_initial, crop.kc_mid, crop.kc_end, day_in_cycle)


def crop_evapotranspiration_mm(kc: float, et0_mm: float) -> float:
    """Demanda del cultivo ETc = Kc × ET₀ (mm/día)."""
    if kc < 0:
        raise ValueError("Kc no puede ser negativo.")
    if et0_mm < 0:
        raise ValueError("La ET₀ no puede ser negativa (hay que acotarla a 0 antes).")
    return kc * et0_mm


def daily_etc_mm(crop: CropSpec, et0_mm_by_cycle_day: Sequence[float]) -> list[float]:
    """ETc de cada día del ciclo completo; ``et0_mm_by_cycle_day[0]`` es el día de la siembra."""
    if len(et0_mm_by_cycle_day) != crop.stages.total_days:
        raise ValueError(
            f"Se esperaban {crop.stages.total_days} valores de ET₀ y llegaron "
            f"{len(et0_mm_by_cycle_day)}."
        )
    return [
        crop_evapotranspiration_mm(kc_for_crop(crop, day_in_cycle), et0_mm)
        for day_in_cycle, et0_mm in enumerate(et0_mm_by_cycle_day, start=1)
    ]
