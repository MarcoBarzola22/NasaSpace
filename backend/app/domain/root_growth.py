"""Crecimiento radicular dentro del perfil fijo (RF-8; T015).

La profundidad radicular crece en forma lineal desde la Zr inicial, el día de la siembra, hasta
la Zr máxima, al final de la etapa de desarrollo; después se mantiene hasta el fin del ciclo
(supuesto ``LINEAR_ROOT_GROWTH``, aprobado el 2026-11-15). Nunca supera la profundidad efectiva
del perfil, que es la profundidad del suelo simulado (CA-3.10, CA-8.4).
"""

from __future__ import annotations

from app.domain.types import CropSpec


def root_depth_m(crop: CropSpec, day_in_cycle: int, effective_depth_m: float) -> float:
    """Profundidad radicular Zr (m) del día ``day_in_cycle`` (1 = siembra)."""
    if not 1 <= day_in_cycle <= crop.stages.total_days:
        raise ValueError(
            f"El día del ciclo debe estar entre 1 y {crop.stages.total_days} "
            f"(recibido: {day_in_cycle})."
        )
    if effective_depth_m <= 0:
        raise ValueError("La profundidad efectiva debe ser mayor que 0.")
    growth_days = crop.stages.initial + crop.stages.development
    if growth_days <= 1:
        fraction = 1.0
    else:
        fraction = min(1.0, (day_in_cycle - 1) / (growth_days - 1))
    depth_m = crop.root_depth_initial_m + fraction * (
        crop.root_depth_max_m - crop.root_depth_initial_m
    )
    return min(effective_depth_m, depth_m)
