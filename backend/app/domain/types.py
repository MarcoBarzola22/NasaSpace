"""Tipos del dominio: estructuras inmutables de Python puro (T008).

Todo el dominio trabaja con estas dataclasses. No hay Pydantic, FastAPI ni E/S aquí: la
traducción desde y hacia el contrato JSON la hace la capa de servicios. Las unidades van en
el nombre de cada campo (``et0_mm``, ``wind_max_ms``, ``yield_t_ha``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.constants import FALLOW_KC_BASE_DEFAULT


@dataclass(frozen=True, slots=True)
class Stages:
    """Duración de las cuatro etapas de FAO-56, en días."""

    initial: int
    development: int
    mid: int
    late: int

    @property
    def total_days(self) -> int:
        return self.initial + self.development + self.mid + self.late


@dataclass(frozen=True, slots=True)
class SowingSpec:
    """Siembra: año de la ventana (1 o 2), día y mes."""

    window_year: int
    day: int
    month: int


@dataclass(frozen=True, slots=True)
class CropSpec:
    """Cultivo ya resuelto (parámetros efectivos) dentro de una rotación."""

    crop_code: str
    crop_type: str  # "grain" o "cover"
    sowing: SowingSpec
    stages: Stages
    kc_initial: float
    kc_mid: float
    kc_end: float
    root_depth_initial_m: float
    root_depth_max_m: float
    depletion_fraction_p: float
    ky: float | None = None
    ym_t_ha: float | None = None
    residue_cover_after_pct: float = 0.0
    price_per_t: float | None = None
    direct_costs_per_ha: float | None = None


@dataclass(frozen=True, slots=True)
class RotationSpec:
    rotation_id: str
    crops: tuple[CropSpec, ...]
    initial_residue_cover_pct: float = 0.0
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ParcelSpec:
    latitude_deg: float
    longitude_deg: float
    theta_fc_m3_m3: float
    theta_wp_m3_m3: float
    effective_depth_m: float
    initial_available_water_pct: float
    fallow_kc_base: float = FALLOW_KC_BASE_DEFAULT


@dataclass(frozen=True, slots=True)
class Window:
    """Ventana continua de dos años de un escenario."""

    start_year: int
    first_day: date
    last_day: date

    @property
    def n_days(self) -> int:
        return (self.last_day - self.first_day).days + 1


@dataclass(frozen=True, slots=True)
class DailyClimate:
    """Día de NASA POWER tal como llega; ``None`` marca un dato faltante (nunca se rellena)."""

    day: date
    precipitation_mm: float | None = None  # PRECTOTCORR
    t_max_c: float | None = None  # T2M_MAX
    t_min_c: float | None = None  # T2M_MIN
    dew_point_c: float | None = None  # T2MDEW
    wind_mean_ms: float | None = None  # WS2M
    wind_max_ms: float | None = None  # WS2M_MAX
    solar_radiation_mj_m2: float | None = None  # ALLSKY_SFC_SW_DWN


@dataclass(frozen=True, slots=True)
class Weather:
    """Día completo para calcular la ET₀, después de las sustituciones FAO-56 declaradas."""

    day: date
    precipitation_mm: float
    t_max_c: float
    t_min_c: float
    dew_point_c: float
    wind_2m_ms: float
    solar_radiation_mj_m2: float
    extraterrestrial_radiation_mj_m2: float
    clear_sky_radiation_mj_m2: float


@dataclass(frozen=True, slots=True)
class CropSegment:
    """Tramo de la línea de tiempo con un cultivo activo (de la siembra al fin de ciclo)."""

    crop: CropSpec
    start: date
    end: date

    is_crop = True

    @property
    def n_days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class FallowSegment:
    """Tramo de barbecho, con la cobertura de rastrojo que se le aplica."""

    start: date
    end: date
    residue_cover_pct: float = 0.0

    is_crop = False

    @property
    def n_days(self) -> int:
        return (self.end - self.start).days + 1


Segment = CropSegment | FallowSegment


@dataclass(frozen=True, slots=True)
class Timeline:
    """Segmentos consecutivos que cubren cada día de la ventana una sola vez."""

    segments: tuple[Segment, ...]

    @property
    def n_days(self) -> int:
        return sum(segment.n_days for segment in self.segments)
