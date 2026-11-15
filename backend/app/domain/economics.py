"""Ingreso y margen bruto por cultivo y por rotación (RF-10; T023).

- ``ingreso = rendimiento (t/ha) × precio manual (moneda/t)``.
- ``margen bruto = ingreso − costos directos (moneda/ha)``.
- Un margen bruto negativo se rotula «Margen bruto negativo»; nunca «pérdida» (CA-10.7), porque el
  margen bruto no incluye estructura, administración ni arrendamiento.
- Un cultivo de cobertura no genera ingreso por grano: ingreso 0 y margen igual a menos sus costos
  (CA-10.2).
- Si el rendimiento de un cultivo de grano no se pudo calcular (Ya = ``None``, porque ETm = 0), el
  ingreso no se toma como 0: el cultivo queda «no calculado» con una nota visible. Un 0 inventado
  se leería como un margen negativo que nunca se estimó.
- Si a algún cultivo de la rotación le faltan datos económicos o su rendimiento no se calculó, el
  margen de la rotación no se calcula y se listan esos cultivos con su motivo: nunca se suponen
  valores en cero (CA-10.4).
- Los precios y costos son entradas del usuario; no son históricos ni pronosticados (CA-10.8).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.types import CropSpec
from app.domain.yield_response import YieldResult

STATUS_COMPUTED = "computed"
STATUS_NOT_COMPUTED = "not_computed"

LABEL_NEGATIVE_MARGIN = "Margen bruto negativo"
NOTE_COVER_CROP = "Cultivo de cobertura: no genera ingreso por grano."
NOTE_YIELD_FAILED = (
    "No se pudo calcular el margen porque hubo un fallo en la estimación de rendimiento (ETm = 0)"
)

FIELD_PRICE = "price_per_t"
FIELD_COSTS = "direct_costs_per_ha"

REASON_MISSING_DATA = "missing_economic_data"
REASON_YIELD_NOT_COMPUTED = "yield_not_computed"


@dataclass(frozen=True, slots=True)
class CropEconomics:
    """Economía de un cultivo; los valores son ``None`` si no se pudo calcular."""

    status: str
    income_per_ha: float | None
    direct_costs_per_ha: float | None
    gross_margin_per_ha: float | None
    gross_margin_label: str | None
    missing_fields: tuple[str, ...] = ()
    note: str | None = None
    reason: str | None = None  # por qué no se calculó (solo si ``not_computed``)


@dataclass(frozen=True, slots=True)
class MissingEconomics:
    """Cultivo que impide calcular el margen de la rotación."""

    position: int  # posición del cultivo en la rotación, desde 1
    crop_code: str
    missing_fields: tuple[str, ...]
    reason: str = REASON_MISSING_DATA


@dataclass(frozen=True, slots=True)
class RotationEconomics:
    status: str
    income_per_ha: float | None
    direct_costs_per_ha: float | None
    gross_margin_per_ha: float | None
    gross_margin_label: str | None
    crops_missing_economics: tuple[MissingEconomics, ...]
    crops: tuple[CropEconomics, ...]


def _margin_label(gross_margin: float) -> str | None:
    return LABEL_NEGATIVE_MARGIN if gross_margin < 0 else None


def crop_economics(crop: CropSpec, yield_result: YieldResult) -> CropEconomics:
    """Ingreso y margen bruto de un cultivo a partir de su rendimiento estimado."""
    if crop.price_per_t is not None and crop.price_per_t < 0:
        raise ValueError("El precio no puede ser negativo.")
    if crop.direct_costs_per_ha is not None and crop.direct_costs_per_ha < 0:
        raise ValueError("Los costos directos no pueden ser negativos.")
    is_cover = crop.crop_type == "cover"
    if is_cover and crop.price_per_t is not None:
        raise ValueError("Un cultivo de cobertura no admite precio.")

    missing: list[str] = []
    if not is_cover and crop.price_per_t is None:
        missing.append(FIELD_PRICE)
    if crop.direct_costs_per_ha is None:
        missing.append(FIELD_COSTS)
    if missing:
        return CropEconomics(
            STATUS_NOT_COMPUTED,
            None,
            None,
            None,
            None,
            missing_fields=tuple(missing),
            reason=REASON_MISSING_DATA,
        )
    assert crop.direct_costs_per_ha is not None  # garantizado por la comprobación anterior

    note: str | None = None
    if is_cover:
        income, note = 0.0, NOTE_COVER_CROP
    elif yield_result.yield_t_ha is None:
        # No hay rendimiento estimado: no se inventa un ingreso de 0 ni un margen negativo.
        return CropEconomics(
            STATUS_NOT_COMPUTED,
            None,
            None,
            None,
            None,
            note=NOTE_YIELD_FAILED,
            reason=REASON_YIELD_NOT_COMPUTED,
        )
    else:
        assert crop.price_per_t is not None
        income = yield_result.yield_t_ha * crop.price_per_t
    margin = income - crop.direct_costs_per_ha
    return CropEconomics(
        status=STATUS_COMPUTED,
        income_per_ha=income,
        direct_costs_per_ha=crop.direct_costs_per_ha,
        gross_margin_per_ha=margin,
        gross_margin_label=_margin_label(margin),
        note=note,
    )


def rotation_economics(
    crops: Sequence[CropSpec], yields: Sequence[YieldResult]
) -> RotationEconomics:
    """Suma la economía de los cultivos de la rotación (CA-10.3) o informa cuáles faltan."""
    if len(crops) != len(yields):
        raise ValueError(f"Hay {len(crops)} cultivos y {len(yields)} resultados de rendimiento.")
    results = tuple(
        crop_economics(crop, yield_result) for crop, yield_result in zip(crops, yields, strict=True)
    )
    missing = tuple(
        MissingEconomics(
            position, crop.crop_code, result.missing_fields, result.reason or REASON_MISSING_DATA
        )
        for position, (crop, result) in enumerate(zip(crops, results, strict=True), start=1)
        if result.status == STATUS_NOT_COMPUTED
    )
    if missing:
        return RotationEconomics(STATUS_NOT_COMPUTED, None, None, None, None, missing, results)
    income = sum(result.income_per_ha for result in results if result.income_per_ha is not None)
    costs = sum(
        result.direct_costs_per_ha for result in results if result.direct_costs_per_ha is not None
    )
    margin = income - costs
    return RotationEconomics(
        status=STATUS_COMPUTED,
        income_per_ha=income,
        direct_costs_per_ha=costs,
        gross_margin_per_ha=margin,
        gross_margin_label=_margin_label(margin),
        crops_missing_economics=(),
        crops=results,
    )
