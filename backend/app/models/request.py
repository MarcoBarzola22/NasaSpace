"""Modelos Pydantic de la solicitud ``POST /api/v1/simulations`` (validación estructural; T033).

Solo tipos, campos obligatorios, rangos de cada campo (plan §5.2) y campos desconocidos
prohibidos. Las reglas que cruzan campos o consultan el catálogo (θPMP < θCC, grano/cobertura,
calendario por escenario) están en ``app.services.validation``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.core.constants import (
    DEFAULT_WINDOW_START_DAY,
    DEFAULT_WINDOW_START_MONTH,
    MAX_EFFECTIVE_DEPTH_M,
    MAX_FALLOW_KC_BASE,
    MAX_KC,
    MAX_KY,
    MAX_ROTATIONS,
    MAX_STAGE_DAYS,
    MAX_START_YEARS,
    MAX_YM_T_HA,
)
from app.models.common import StrictModel

MIN_START_YEAR = 1900
MAX_START_YEAR = 2200


class ParcelIn(StrictModel):
    name: str | None = Field(default=None, max_length=100)
    latitude_deg: float = Field(ge=-90, le=90)  # [-60, 60] se valida en services/validation
    longitude_deg: float = Field(ge=-180, le=180)
    theta_fc_m3_m3: float = Field(gt=0, le=1)
    theta_wp_m3_m3: float = Field(ge=0, lt=1)
    effective_depth_m: float = Field(gt=0, le=MAX_EFFECTIVE_DEPTH_M)
    initial_available_water_pct: float = Field(ge=0, le=100)
    fallow_kc_base: float | None = Field(default=None, gt=0, le=MAX_FALLOW_KC_BASE)


class WindowIn(StrictModel):
    start_day: int = Field(default=DEFAULT_WINDOW_START_DAY, ge=1, le=31)
    start_month: int = Field(default=DEFAULT_WINDOW_START_MONTH, ge=1, le=12)
    # Años plausibles: evita desbordes de fecha. Un año anterior a la cobertura de la fuente es
    # válido y su escenario se bloquea con su motivo (CA-4.5).
    start_years: list[Annotated[int, Field(ge=MIN_START_YEAR, le=MAX_START_YEAR)]] = Field(
        min_length=1, max_length=MAX_START_YEARS
    )


class SowingIn(StrictModel):
    window_year: int = Field(ge=1, le=2)
    day: int = Field(ge=1, le=31)
    month: int = Field(ge=1, le=12)


class StageLengthsIn(StrictModel):
    """Las cuatro duraciones o ninguna (CA-3.9): las cuatro claves son obligatorias."""

    initial: int = Field(ge=1, le=MAX_STAGE_DAYS)
    development: int = Field(ge=1, le=MAX_STAGE_DAYS)
    mid: int = Field(ge=1, le=MAX_STAGE_DAYS)
    late: int = Field(ge=1, le=MAX_STAGE_DAYS)


class EconomicsIn(StrictModel):
    price_per_t: float | None = Field(default=None, ge=0)
    direct_costs_per_ha: float | None = Field(default=None, ge=0)


class CropIn(StrictModel):
    crop_code: str = Field(min_length=1, max_length=50)
    sowing: SowingIn
    stage_lengths_days: StageLengthsIn | None = None
    kc_initial: float | None = Field(default=None, ge=0, le=MAX_KC)
    kc_mid: float | None = Field(default=None, ge=0, le=MAX_KC)
    kc_end: float | None = Field(default=None, ge=0, le=MAX_KC)
    root_depth_initial_m: float | None = Field(default=None, gt=0)
    root_depth_max_m: float | None = Field(default=None, gt=0)
    depletion_fraction_p: float | None = Field(default=None, gt=0, lt=1)
    ky: float | None = Field(default=None, ge=0, le=MAX_KY)
    ym_t_ha: float | None = Field(default=None, gt=0, le=MAX_YM_T_HA)
    residue_cover_after_pct: float = Field(default=0.0, ge=0, le=100)
    economics: EconomicsIn | None = None


class RotationIn(StrictModel):
    id: Literal["A", "B", "C"]
    name: str | None = Field(default=None, max_length=100)
    initial_residue_cover_pct: float = Field(default=0.0, ge=0, le=100)
    crops: list[CropIn] = Field(min_length=1)


class SimulationRequest(StrictModel):
    parcel: ParcelIn
    window: WindowIn
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    rotations: list[RotationIn] = Field(min_length=1, max_length=MAX_ROTATIONS)
