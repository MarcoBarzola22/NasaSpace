"""Balance hídrico diario continuo sobre un perfil de profundidad fija (RF-8; T016–T020).

Modelo (plan §7.4, decisiones T-6 a T-10):

- Un único perfil de profundidad ``D`` (la profundidad efectiva) durante toda la ventana, dividido
  en dos compartimentos: la **zona activa** (de profundidad ``z_active``) y la **zona inferior**
  (el resto hasta ``D``). Con cultivo, la zona activa es la zona radicular (Zr del día, creciente);
  en barbecho es la capa evaporable de 0,15 m. El agua se mide como agua útil, en mm sobre el
  punto de marchitez permanente, con contenido uniforme dentro de cada compartimento.
- El límite entre zonas se mueve (las raíces crecen, se pasa de cultivo a barbecho) y el agua solo
  se **redistribuye**, nunca se reinicia: el agua con la que termina un segmento es exactamente la
  del primer día del siguiente (CA-8.6).
- La lluvia llena primero la zona activa y luego la inferior; lo que no cabe se pierde ese mismo
  día como excedente (escorrentía o percolación, sin distinguirlas) y no se acumula (CA-8.13).
- El cultivo extrae solo de la zona activa, con el coeficiente de estrés Ks de FAO-56 calculado con
  el estado al inicio del día (ec. 84). El barbecho evapora ``Kc_base × factor_rastrojo × ET₀``
  solo de la capa de 0,15 m (CA-8.10). Riego, ascenso capilar y escorrentía por intensidad: 0.
- Controles diarios y de cierre de masa (CA-8.14 a CA-8.17): ante cualquier violación se lanza
  ``CalculationIntegrityError`` y no se entrega resultado.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.constants import (
    DAILY_EPSILON_MM,
    FALLOW_EVAPORATION_LAYER_M,
    MASS_CLOSURE_TOLERANCE_MM,
    RESIDUE_EVAPORATION_REDUCTION_PER_10PCT,
)
from app.core.exceptions import CalculationIntegrityError
from app.domain.kc_curve import kc_for_crop
from app.domain.root_growth import root_depth_m
from app.domain.types import CropSegment, ParcelSpec, Segment, Timeline

# --- Resultados ---


@dataclass(frozen=True, slots=True)
class SegmentBalance:
    """Resultado de un segmento (cultivo o barbecho) de la línea de tiempo."""

    is_crop: bool
    crop_code: str | None
    start: date
    end: date
    storage_at_start_mm: float
    storage_at_end_mm: float
    demand_mm: float  # cultivo: ETm = ΣETc; barbecho: evaporación demandada
    actual_mm: float  # cultivo: ETa; barbecho: evaporación real
    stress_days: int  # días con Ks < 1 (siempre 0 en barbecho)


@dataclass(frozen=True, slots=True)
class DailyRecord:
    """Estado de un día; solo se produce con ``record_days=True`` (auditoría y pruebas)."""

    day: date
    segment_index: int
    is_crop: bool
    rain_mm: float
    et0_mm: float
    demand_mm: float  # ETc del cultivo o evaporación demandada del barbecho
    actual_mm: float  # ETa o evaporación real
    available_mm: float  # agua de la zona activa tras la lluvia, antes de consumir
    excess_mm: float
    ks: float | None
    active_depth_m: float
    active_storage_mm: float
    lower_storage_mm: float
    active_capacity_mm: float
    lower_capacity_mm: float
    storage_mm: float


@dataclass(frozen=True, slots=True)
class BalanceRun:
    initial_storage_mm: float
    final_storage_mm: float
    precipitation_mm: float
    crop_eta_mm: float
    fallow_evaporation_mm: float
    excess_lost_mm: float
    closure_mm: float
    segments: tuple[SegmentBalance, ...]
    daily: tuple[DailyRecord, ...] = ()


# --- Capacidades y funciones auxiliares ---


def layer_capacity_mm(parcel: ParcelSpec, thickness_m: float) -> float:
    """Agua útil máxima de un espesor de suelo: 1000 (θCC − θPMP) z, en mm."""
    return 1000.0 * (parcel.theta_fc_m3_m3 - parcel.theta_wp_m3_m3) * thickness_m


def profile_capacity_mm(parcel: ParcelSpec) -> float:
    """Capacidad del perfil completo (CA-1.6)."""
    return layer_capacity_mm(parcel, parcel.effective_depth_m)


def initial_storage_mm(parcel: ParcelSpec) -> float:
    """Agua del perfil el primer día: humedad inicial como porcentaje de la capacidad."""
    return parcel.initial_available_water_pct / 100.0 * profile_capacity_mm(parcel)


def residue_factor(cover_pct: float) -> float:
    """Factor de reducción de la evaporación por rastrojo: 1 − 0,05 × (cobertura % / 10)."""
    if not 0.0 <= cover_pct <= 100.0:
        raise ValueError("La cobertura de rastrojo debe estar entre 0 y 100 %.")
    return 1.0 - RESIDUE_EVAPORATION_REDUCTION_PER_10PCT * (cover_pct / 10.0)


def redistribute(
    w_active_mm: float, w_lower_mm: float, z_old_m: float, z_new_m: float, depth_m: float
) -> tuple[float, float]:
    """Mueve el límite entre zonas de ``z_old`` a ``z_new`` conservando el agua total.

    Con contenido uniforme en cada zona: al profundizar, la franja incorporada aporta su parte
    del agua de la zona inferior; al achicarse, la franja liberada pasa a la zona inferior.
    """
    if z_new_m > z_old_m and depth_m > z_old_m:
        moved_mm = w_lower_mm * (z_new_m - z_old_m) / (depth_m - z_old_m)
        return w_active_mm + moved_mm, w_lower_mm - moved_mm
    if z_new_m < z_old_m:
        moved_mm = w_active_mm * (z_old_m - z_new_m) / z_old_m
        return w_active_mm - moved_mm, w_lower_mm + moved_mm
    return w_active_mm, w_lower_mm


def _active_depth_m(segment: Segment, day_in_segment: int, depth_m: float) -> float:
    if isinstance(segment, CropSegment):
        return root_depth_m(segment.crop, day_in_segment, depth_m)
    return min(depth_m, FALLOW_EVAPORATION_LAYER_M)


def _stress_coefficient(w_active_mm: float, active_capacity_mm: float, p: float) -> float:
    """Ks de FAO-56 (ec. 84): 1 hasta agotar la fracción p y luego decrece hasta 0."""
    depletion_mm = active_capacity_mm - w_active_mm
    if depletion_mm <= p * active_capacity_mm:
        return 1.0
    return max(0.0, w_active_mm / ((1.0 - p) * active_capacity_mm))


def _fail(message: str, closure_mm: float | None = None) -> CalculationIntegrityError:
    return CalculationIntegrityError(message, closure_mm=closure_mm)


def _validate_inputs(
    timeline: Timeline, rain_mm: Sequence[float], et0_mm: Sequence[float], parcel: ParcelSpec
) -> None:
    if not timeline.segments:
        raise ValueError("La línea de tiempo no tiene segmentos.")
    if len(rain_mm) != timeline.n_days or len(et0_mm) != timeline.n_days:
        raise ValueError(
            f"Se esperaban {timeline.n_days} valores diarios de lluvia y de ET₀ "
            f"(recibidos: {len(rain_mm)} y {len(et0_mm)})."
        )
    if any(value < 0 for value in rain_mm):
        raise ValueError("La lluvia diaria no puede ser negativa.")
    if any(value < 0 for value in et0_mm):
        raise ValueError("La ET₀ diaria no puede ser negativa (hay que acotarla a 0 antes).")
    if not 0.0 <= parcel.theta_wp_m3_m3 < parcel.theta_fc_m3_m3 <= 1.0:
        raise ValueError("Se requiere 0 ≤ θPMP < θCC ≤ 1.")
    if parcel.effective_depth_m <= 0:
        raise ValueError("La profundidad efectiva debe ser mayor que 0.")
    if not 0.0 <= parcel.initial_available_water_pct <= 100.0:
        raise ValueError("La humedad inicial debe estar entre 0 y 100 %.")
    if not 0.0 < parcel.fallow_kc_base:
        raise ValueError("El Kc base de barbecho debe ser mayor que 0.")
    for segment in timeline.segments:
        if isinstance(segment, CropSegment) and segment.n_days != segment.crop.stages.total_days:
            raise ValueError(
                f"El cultivo {segment.crop.crop_code} dura {segment.crop.stages.total_days} días "
                f"pero su segmento tiene {segment.n_days}."
            )


# --- Balance diario ---


def run_daily_balance(
    timeline: Timeline,
    rain_mm: Sequence[float],
    et0_mm: Sequence[float],
    parcel: ParcelSpec,
    *,
    record_days: bool = False,
) -> BalanceRun:
    """Simula la ventana completa día a día y devuelve el balance con su cierre de masa.

    ``rain_mm`` y ``et0_mm`` traen un valor por día de la línea de tiempo, en orden.
    """
    _validate_inputs(timeline, rain_mm, et0_mm, parcel)
    depth_m = parcel.effective_depth_m
    capacity_per_m = layer_capacity_mm(parcel, 1.0)
    profile_capacity = profile_capacity_mm(parcel)

    # Estado inicial: humedad uniforme en todo el perfil (CA-8.3).
    w0_mm = initial_storage_mm(parcel)
    z_active = _active_depth_m(timeline.segments[0], 1, depth_m)
    w_active = w0_mm * z_active / depth_m
    w_lower = w0_mm - w_active

    total_rain = total_crop_eta = total_fallow_evap = total_excess = 0.0
    segment_results: list[SegmentBalance] = []
    daily: list[DailyRecord] = []
    index = 0  # posición del día dentro de la ventana

    for segment_index, segment in enumerate(timeline.segments):
        is_crop = isinstance(segment, CropSegment)
        storage_at_start = w_active + w_lower  # = agua final del segmento anterior (CA-8.6)
        seg_demand = seg_actual = 0.0
        stress_days = 0

        for day_in_segment in range(1, segment.n_days + 1):
            storage_before = w_active + w_lower

            # (1) Profundidad activa del día y redistribución sin pérdida de masa.
            z_new = _active_depth_m(segment, day_in_segment, depth_m)
            w_active, w_lower = redistribute(w_active, w_lower, z_active, z_new, depth_m)
            z_active = z_new
            cap_active = capacity_per_m * z_active
            cap_lower = profile_capacity - cap_active

            # (2) Estrés con el estado al inicio del día.
            ks: float | None = None
            if isinstance(segment, CropSegment):
                ks = _stress_coefficient(w_active, cap_active, segment.crop.depletion_fraction_p)

            # (3) Lluvia: llena de arriba hacia abajo; el resto se pierde ese día.
            rain = rain_mm[index]
            into_active = min(rain, max(cap_active - w_active, 0.0))
            w_active += into_active
            into_lower = min(rain - into_active, max(cap_lower - w_lower, 0.0))
            w_lower += into_lower
            excess = rain - into_active - into_lower
            available = w_active

            # (4) Consumo, solo desde la zona activa.
            et0 = et0_mm[index]
            if isinstance(segment, CropSegment):
                demand = kc_for_crop(segment.crop, day_in_segment) * et0
                assert ks is not None
                actual = min(ks * demand, w_active)
                if ks < 1.0:
                    stress_days += 1
                total_crop_eta += actual
            else:
                demand = parcel.fallow_kc_base * residue_factor(segment.residue_cover_pct) * et0
                actual = min(demand, w_active)
                total_fallow_evap += actual
            w_active -= actual
            seg_demand += demand
            seg_actual += actual
            total_rain += rain
            total_excess += excess

            # (5) Controles diarios.
            eps = DAILY_EPSILON_MM
            if not (-eps <= w_active <= cap_active + eps and -eps <= w_lower <= cap_lower + eps):
                raise _fail(
                    f"Almacenamiento fuera de límites el {segment.start} + {day_in_segment}."
                )
            if actual > demand + eps or actual > available + eps:
                raise _fail(f"El consumo supera la demanda o el agua disponible (día {index + 1}).")
            storage_after = w_active + w_lower
            day_closure = (storage_after - storage_before) - (rain - actual - excess)
            if abs(day_closure) > eps:
                raise _fail(f"El agua no se conserva en el día {index + 1}.", day_closure)

            if record_days:
                daily.append(
                    DailyRecord(
                        day=segment.start + timedelta(days=day_in_segment - 1),
                        segment_index=segment_index,
                        is_crop=is_crop,
                        rain_mm=rain,
                        et0_mm=et0,
                        demand_mm=demand,
                        actual_mm=actual,
                        available_mm=available,
                        excess_mm=excess,
                        ks=ks,
                        active_depth_m=z_active,
                        active_storage_mm=w_active,
                        lower_storage_mm=w_lower,
                        active_capacity_mm=cap_active,
                        lower_capacity_mm=cap_lower,
                        storage_mm=storage_after,
                    )
                )
            index += 1

        segment_results.append(
            SegmentBalance(
                is_crop=is_crop,
                crop_code=segment.crop.crop_code if isinstance(segment, CropSegment) else None,
                start=segment.start,
                end=segment.end,
                storage_at_start_mm=storage_at_start,
                storage_at_end_mm=w_active + w_lower,
                demand_mm=seg_demand,
                actual_mm=seg_actual,
                stress_days=stress_days,
            )
        )

    # (6) Cierre de masa de toda la corrida (CA-8.16, CA-8.17).
    final_storage = w_active + w_lower
    closure = (final_storage - w0_mm) - (
        total_rain - total_crop_eta - total_fallow_evap - total_excess
    )
    if abs(closure) > MASS_CLOSURE_TOLERANCE_MM:
        raise _fail("El cierre de masa de la corrida supera la tolerancia.", closure)
    return BalanceRun(
        initial_storage_mm=w0_mm,
        final_storage_mm=final_storage,
        precipitation_mm=total_rain,
        crop_eta_mm=total_crop_eta,
        fallow_evaporation_mm=total_fallow_evap,
        excess_lost_mm=total_excess,
        closure_mm=closure,
        segments=tuple(segment_results),
        daily=tuple(daily),
    )
