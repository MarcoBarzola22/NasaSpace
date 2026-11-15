"""Modelos Pydantic de la respuesta ``200 OK`` de ``POST /api/v1/simulations`` (T042).

Siguen el contrato del plan §5.3 con sus 13 claves de primer nivel. Convenciones (plan §5.1):

- claves en inglés y ``snake_case`` con la unidad en el nombre (``_mm``, ``_t_ha``, ``_per_ha``,
  ``_ms``, ``_m``, ``_pct``, ``_days``, ``_ratio``, ``_deg``, ``_m3_m3``); los pocos campos
  adimensionales (posiciones, años, conteos y los extremos de un rango) están listados en la
  prueba de contrato (CA-15.3);
- textos visibles en español;
- ``null`` explícito cuando algo no aplica, con su nota;
- sin series diarias del balance ni del clima (CA-15.5): solo totales, fechas puntuales y rangos.

Los campos opcionales que agrega esta versión sobre el ejemplo del plan (``n`` de cada rango,
``status`` y ``note`` de la economía de un cultivo, ``first_date`` y ``last_date`` de un bloqueo)
tienen valor por defecto: el ejemplo del plan sigue siendo una respuesta válida.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.models.common import StrictModel

ScenarioStatus = Literal["computed", "blocked"]


class ParameterOut(StrictModel):
    """Parámetro resuelto: valor efectivo, origen, cita y nota (plan §5.1)."""

    value: float | int | str | dict[str, int] | None
    origin: Literal["user", "fao_reference", "team_default", "system_default"]
    source: str | None = None
    note: str | None = None


# --- Entrada resuelta (CA-15.1a) ---


class ParcelOut(StrictModel):
    name: str | None = None
    latitude_deg: float
    longitude_deg: float
    theta_fc_m3_m3: float
    theta_wp_m3_m3: float
    effective_depth_m: float
    profile_capacity_mm: float
    initial_available_water_pct: float
    initial_storage_mm: float
    fallow_kc_base: ParameterOut
    fallow_evaporation_layer_m: ParameterOut


class WindowOut(StrictModel):
    start_day: int
    start_month: int
    start_years: list[int]


class CropInputOut(StrictModel):
    position: int
    crop_code: str
    crop_name: str
    crop_type: Literal["grain", "cover"]
    calibrated: bool = False
    parameters: dict[str, ParameterOut]


class RotationInputOut(StrictModel):
    id: str
    name: str | None = None
    initial_residue_cover_pct: ParameterOut
    crops: list[CropInputOut]


class ResolvedInputOut(StrictModel):
    parcel: ParcelOut
    window: WindowOut
    rotations: list[RotationInputOut]


# --- Procedencia (CA-13.1, CA-13.2) ---


class LocationOut(StrictModel):
    latitude_deg: float
    longitude_deg: float


class SourceLocationOut(LocationOut):
    elevation_m: float


class DateRangeOut(StrictModel):
    start: date
    end: date


class VariableProvenanceOut(StrictModel):
    code: str
    name: str
    unit: str
    use: str
    missing_days: int


class ProvenanceOut(StrictModel):
    source: str
    service: str
    retrieval: str
    queried_at: datetime
    source_version: str | None = None
    requested_location: LocationOut
    source_location: SourceLocationOut
    spatial_note: str
    date_range: DateRangeOut
    variables: list[VariableProvenanceOut]
    label: str


# --- Escenarios (CA-15.1c, CA-6.7) ---


class BlockedReasonOut(StrictModel):
    code: str
    variable: str | None = None
    dates: list[date] = Field(default_factory=list)
    first_date: date | None = None
    last_date: date | None = None
    message: str


class SubstitutionOut(StrictModel):
    variable: str
    method: str
    count: int
    dates: list[date]


class ScenarioOut(StrictModel):
    start_year: int
    window_start: date
    window_end: date
    days: int
    status: ScenarioStatus
    blocked_reasons: list[BlockedReasonOut] = Field(default_factory=list)
    substituted_days: list[SubstitutionOut] = Field(default_factory=list)
    precipitation_total_mm: float | None = None
    et0_total_mm: float | None = None


# --- Resultados por rotación y escenario (CA-15.1d, CA-15.2) ---


class WaterBalanceOut(StrictModel):
    initial_storage_mm: float
    final_storage_mm: float
    precipitation_mm: float
    et0_mm: float
    crop_eta_mm: float
    fallow_evaporation_mm: float
    excess_lost_mm: float
    mass_balance_error_mm: float


class CropEconomicsOut(StrictModel):
    status: Literal["computed", "not_computed"] = "computed"
    income_per_ha: float | None = None
    direct_costs_per_ha: float | None = None
    gross_margin_per_ha: float | None = None
    gross_margin_label: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    note: str | None = None
    reason: str | None = None


class CropResultOut(StrictModel):
    position: int
    crop_code: str
    crop_type: Literal["grain", "cover"]
    sowing_date: date
    cycle_end_date: date
    storage_at_sowing_mm: float
    storage_at_end_mm: float
    etm_mm: float
    eta_mm: float
    eta_etm_ratio: float | None = None
    stress_days: int
    yield_t_ha: float | None = None
    relative_yield: float | None = None
    yield_note: str | None = None
    economics: CropEconomicsOut


class MissingEconomicsOut(StrictModel):
    position: int
    crop_code: str
    missing_fields: list[str] = Field(default_factory=list)
    reason: str


class RotationEconomicsOut(StrictModel):
    status: Literal["computed", "not_computed"]
    income_per_ha: float | None = None
    direct_costs_per_ha: float | None = None
    gross_margin_per_ha: float | None = None
    gross_margin_label: str | None = None
    crops_missing_economics: list[MissingEconomicsOut] = Field(default_factory=list)


class SoilExposureOut(StrictModel):
    window_days: int
    live_crop_days: int
    no_live_crop_days: int
    strong_wind_days_without_live_crop: int
    no_wind_data_days_without_live_crop: int
    wind_variable: str
    threshold_ms: float
    rule: str
    threshold_source: str
    note: str


class ResultOut(StrictModel):
    rotation_id: str
    start_year: int
    water_balance: WaterBalanceOut
    crops: list[CropResultOut]
    rotation_economics: RotationEconomicsOut
    soil_exposure: SoilExposureOut


# --- Rangos y comparaciones (CA-12.1–CA-12.5, CA-15.4) ---


class RangeOut(StrictModel):
    """Mínimo, mediana y máximo; la unidad la da el campo que lo contiene."""

    min: float
    median: float
    max: float
    n: int | None = None
    no_range: bool = False


class CropRangesOut(StrictModel):
    position: int
    crop_code: str
    yield_t_ha: RangeOut | None = None
    eta_etm_ratio: RangeOut | None = None


class RotationRangesOut(StrictModel):
    rotation_id: str
    n_scenarios: int
    scenarios_included: list[int]
    scenarios_excluded: list[int]
    crops: list[CropRangesOut]
    gross_margin_per_ha: RangeOut | None = None
    margin_not_computed_years: list[int] = Field(default_factory=list)
    strong_wind_days_without_live_crop: RangeOut | None = None
    label: str


class ComparisonOut(StrictModel):
    start_year: int
    minuend_rotation_id: str
    subtrahend_rotation_id: str
    gross_margin_difference_per_ha: float
    label: str


# --- Supuestos y advertencias (RF-14, RF-17) ---


class AssumptionScopeOut(StrictModel):
    level: Literal["request", "rotation", "crop", "fallow", "scenario", "date"]
    rotation_id: str | None = None
    position: int | None = None
    parameter: str | None = None
    start_year: int | None = None
    after_position: int | None = None


class AssumptionOut(StrictModel):
    code: str
    scope: AssumptionScopeOut
    description: str
    value: float | int | str | None = None
    unit: str | None = None
    origin: Literal["user", "fao_reference", "team_default", "system_default"]
    source: str | None = None
    count: int | None = None
    dates: list[date] | None = None


class WarningOut(StrictModel):
    code: str
    message: str


# --- Respuesta completa: 13 claves de primer nivel ---


class SimulationResponse(StrictModel):
    contract_version: str
    model_version: str
    request_id: str
    computed_at: datetime
    currency: str | None = None
    resolved_input: ResolvedInputOut
    provenance: ProvenanceOut | None = None
    scenarios: list[ScenarioOut]
    results: list[ResultOut]
    ranges: list[RotationRangesOut]
    comparisons: list[ComparisonOut]
    assumptions: list[AssumptionOut]
    warnings: list[WarningOut]
