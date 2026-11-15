"""Vista del catálogo para ``GET /api/v1/catalog`` (RF-2, CA-2.1, CA-2.5, CA-2.6, CA-11.5; T032).

Reúne los valores de referencia FAO con su cita y los parámetros del modelo que el usuario debe
conocer: Kc base de barbecho y regla de rastrojo con su fuente, la regla del proxy de viento y
los límites de la solicitud. No incluye Ym, precios ni costos (CA-2.2).
"""

from __future__ import annotations

from app.core import messages
from app.core.constants import (
    CONTRACT_VERSION,
    DEFAULT_WINDOW_START_DAY,
    DEFAULT_WINDOW_START_MONTH,
    FALLOW_EVAPORATION_LAYER_M,
    FALLOW_KC_BASE_DEFAULT,
    MAX_EFFECTIVE_DEPTH_M,
    MAX_ROTATIONS,
    MAX_START_YEARS,
    WIND_STRONG_THRESHOLD_MS,
    WIND_STRONG_VARIABLE,
)
from app.models.catalog import (
    CatalogCropOut,
    CatalogResponse,
    FallowOut,
    LimitsOut,
    ReferenceValueOut,
    WindowDefaultsOut,
    WindProxyOut,
)
from app.services.catalog_service import STATUS_NO_REFERENCE, Catalog, CropReference


def _crop_label(crop: CropReference) -> str:
    """Rótulo del cultivo: «valor tabulado FAO, no calibrado» o aviso de valores a ingresar."""
    if any(entry.status == STATUS_NO_REFERENCE for entry in crop.reference_values.values()):
        return messages.CATALOG_LABEL_MISSING
    return messages.CATALOG_LABEL_REFERENCE


def build_catalog_response(catalog: Catalog) -> CatalogResponse:
    crops = [
        CatalogCropOut(
            crop_code=crop.crop_code,
            name=crop.name,
            crop_type=crop.crop_type,  # type: ignore[arg-type]
            reference_values={
                parameter: ReferenceValueOut(
                    value=entry.value,
                    unit=entry.unit or None,
                    source=entry.source,
                    status=entry.status,
                    origin=entry.origin,
                    note=entry.note,
                )
                for parameter, entry in crop.reference_values.items()
            },
            label=_crop_label(crop),
        )
        for crop in catalog.crops
    ]
    return CatalogResponse(
        contract_version=CONTRACT_VERSION,
        catalog_version=catalog.version,
        catalog_label=catalog.label,
        crops=crops,
        fallow=FallowOut(
            kc_base_default=FALLOW_KC_BASE_DEFAULT,
            kc_base_source=messages.ASSUMPTION_DESCRIPTIONS["FALLOW_KC_BASE_DEFAULT"],
            residue_rule=messages.RESIDUE_RULE,
            residue_rule_source=messages.RESIDUE_RULE_SOURCE,
            evaporation_layer_m=FALLOW_EVAPORATION_LAYER_M,
        ),
        wind_proxy=WindProxyOut(
            variable=WIND_STRONG_VARIABLE,
            threshold_ms=WIND_STRONG_THRESHOLD_MS,
            rule=messages.WIND_RULE.format(
                threshold=f"{WIND_STRONG_THRESHOLD_MS:.1f}".replace(".", ",")
            ),
            source=messages.WIND_THRESHOLD_SOURCE,
        ),
        window_defaults=WindowDefaultsOut(
            start_day=DEFAULT_WINDOW_START_DAY, start_month=DEFAULT_WINDOW_START_MONTH
        ),
        limits=LimitsOut(
            max_rotations=MAX_ROTATIONS,
            max_start_years=MAX_START_YEARS,
            max_effective_depth_m=MAX_EFFECTIVE_DEPTH_M,
        ),
    )
