"""Modelos de ``GET /api/v1/catalog`` (plan §5.4, RF-2; T032)."""

from __future__ import annotations

from typing import Literal

from app.models.common import StrictModel


class ReferenceValueOut(StrictModel):
    """Un valor de referencia con su cita, o ``status`` «sin referencia» o «no aplica»."""

    value: float | int | dict[str, int] | None = None
    unit: str | None = None
    source: str | None = None
    status: str
    origin: str | None = None
    note: str | None = None


class CatalogCropOut(StrictModel):
    crop_code: str
    name: str
    crop_type: Literal["grain", "cover"]
    reference_values: dict[str, ReferenceValueOut]
    label: str


class FallowOut(StrictModel):
    kc_base_default: float
    kc_base_source: str
    residue_rule: str
    residue_rule_source: str
    evaporation_layer_m: float


class WindProxyOut(StrictModel):
    variable: str
    threshold_ms: float
    rule: str
    source: str


class WindowDefaultsOut(StrictModel):
    start_day: int
    start_month: int


class LimitsOut(StrictModel):
    max_rotations: int
    max_start_years: int
    max_effective_depth_m: float


class CatalogResponse(StrictModel):
    contract_version: str
    catalog_version: str
    catalog_label: str
    crops: list[CatalogCropOut]
    fallow: FallowOut
    wind_proxy: WindProxyOut
    window_defaults: WindowDefaultsOut
    limits: LimitsOut
