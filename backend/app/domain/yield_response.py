"""Rendimiento bajo déficit hídrico, FAO-33 (RF-9; T022).

Relación aprobada: ``1 − Ya/Ym = Ky × (1 − ETa/ETm)`` con el Ky del ciclo completo, es decir
``Ya = Ym × [1 − Ky × (1 − ETa/ETm)]``. ETm es la suma de ETc entre la siembra y el fin del ciclo
y ETa la suma de la evapotranspiración real del mismo período; ambas salen del balance hídrico
(``SegmentBalance.demand_mm`` y ``SegmentBalance.actual_mm``).

El resultado es un escenario histórico descriptivo con parámetros no calibrados (spec §1.4): no
es un pronóstico. Casos límite:

- Un cultivo de cobertura no tiene Ym ni Ky: no se calcula rendimiento (CA-9.7).
- Si ETm = 0 no hay cociente ETa/ETm: no se calcula rendimiento (CA-9.5).
- Si la fórmula da un Ya negativo (Ky > 1 con déficit severo) se informa 0 y se marca el recorte
  como supuesto (CA-9.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.core.constants import DAILY_EPSILON_MM
from app.core.exceptions import CalculationIntegrityError
from app.domain.types import CropSpec, RotationSpec
from app.domain.water_balance import BalanceRun, SegmentBalance

NOTE_COVER_CROP = "No aplica (cultivo de cobertura)."
NOTE_ETM_ZERO = "ETm = 0: no se calcula el rendimiento."
REASON_COVER_CROP = "cover_crop"
REASON_ETM_ZERO = "etm_zero"

_RATIO_TOLERANCE = 1e-9  # ETa/ETm puede superar 1 por redondeo de punto flotante, no más


@dataclass(frozen=True, slots=True)
class YieldResult:
    """Resultado de un cultivo; ``yield_t_ha`` es ``None`` si no corresponde calcularlo."""

    etm_mm: float
    eta_mm: float
    eta_etm_ratio: float | None
    yield_t_ha: float | None
    relative_yield: float | None
    clipped_to_zero: bool
    reason: str | None = None  # código estable cuando no hay rendimiento
    note: str | None = None  # texto para el usuario cuando no hay rendimiento


def relative_yield_fao33(ky: float, eta_etm_ratio: float) -> tuple[float, bool]:
    """Ya/Ym = 1 − Ky (1 − ETa/ETm), acotado a [0, 1]; devuelve (valor, hubo recorte a 0)."""
    if ky < 0:
        raise ValueError("Ky no puede ser negativo.")
    if not 0.0 <= eta_etm_ratio <= 1.0:
        raise ValueError("ETa/ETm debe estar entre 0 y 1.")
    relative = 1.0 - ky * (1.0 - eta_etm_ratio)
    if relative < 0.0:
        return 0.0, True
    return min(relative, 1.0), False


def crop_yield(crop: CropSpec, etm_mm: float, eta_mm: float) -> YieldResult:
    """Rendimiento de un cultivo a partir de su ETm y ETa del ciclo (mm)."""
    if etm_mm < 0 or eta_mm < 0:
        raise ValueError("ETm y ETa no pueden ser negativas.")
    ratio: float | None = None
    if etm_mm > 0:
        raw_ratio = eta_mm / etm_mm
        if raw_ratio > 1.0 + _RATIO_TOLERANCE and eta_mm - etm_mm > DAILY_EPSILON_MM:
            raise CalculationIntegrityError(
                f"ETa ({eta_mm:.3f} mm) supera a ETm ({etm_mm:.3f} mm) en {crop.crop_code}."
            )
        ratio = min(raw_ratio, 1.0)

    if crop.crop_type == "cover":
        return YieldResult(
            etm_mm, eta_mm, ratio, None, None, False, REASON_COVER_CROP, NOTE_COVER_CROP
        )
    if crop.ym_t_ha is None or crop.ym_t_ha <= 0:
        raise ValueError(f"El cultivo de grano {crop.crop_code} requiere Ym mayor que 0.")
    if crop.ky is None:
        raise ValueError(f"El cultivo de grano {crop.crop_code} requiere Ky.")
    if ratio is None:
        return YieldResult(etm_mm, eta_mm, None, None, None, False, REASON_ETM_ZERO, NOTE_ETM_ZERO)

    relative, clipped = relative_yield_fao33(crop.ky, ratio)
    yield_t_ha = crop.ym_t_ha * relative
    if not 0.0 <= yield_t_ha <= crop.ym_t_ha:
        raise CalculationIntegrityError(f"Ya fuera de [0, Ym] en {crop.crop_code}.")
    return YieldResult(etm_mm, eta_mm, ratio, yield_t_ha, relative, clipped)


def crop_yield_from_balance(crop: CropSpec, segment: SegmentBalance) -> YieldResult:
    """Rendimiento de un cultivo con los totales de su segmento del balance hídrico."""
    if not segment.is_crop or segment.crop_code != crop.crop_code:
        raise ValueError(f"El segmento no corresponde al cultivo {crop.crop_code}.")
    return crop_yield(crop, etm_mm=segment.demand_mm, eta_mm=segment.actual_mm)


def crop_yields(run: BalanceRun, rotation: RotationSpec) -> list[YieldResult]:
    """Rendimiento de cada cultivo de la rotación, en orden, a partir de una corrida del balance."""
    crop_segments = [segment for segment in run.segments if segment.is_crop]
    return _pair_yields(rotation.crops, crop_segments)


def _pair_yields(
    crops: Sequence[CropSpec], segments: Sequence[SegmentBalance]
) -> list[YieldResult]:
    if len(crops) != len(segments):
        raise ValueError(
            f"La rotación tiene {len(crops)} cultivos y el balance {len(segments)} segmentos."
        )
    pairs = zip(crops, segments, strict=True)
    return [crop_yield_from_balance(crop, segment) for crop, segment in pairs]
