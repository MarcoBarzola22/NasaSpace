"""Constructor de la respuesta final: de los resultados del cálculo al contrato (RF-13…RF-17; T045).

Toma la salida del servicio de simulación y arma ``SimulationResponse`` (plan §5.3):

- **Redondeo solo al serializar** (plan §5.1): mm con 1 decimal, cocientes con 3, t/ha con 2 y
  moneda con 2. Los controles (por ejemplo el error de cierre) se calculan con los valores sin
  redondear; por eso sumar valores redondeados puede diferir en ±0,1 mm.
- **Integridad**: un ``NaN`` o infinito en cualquier valor, un almacenamiento fuera de
  ``[0, capacidad]`` o un rendimiento fuera de ``[0, Ym]`` es un ``CalculationIntegrityError``
  (500, sin resultados parciales; plan §6.2 y CA-16.5).
- **Alcances de supuestos**: los textos ``A/1/ky``, ``B/3`` o ``2008`` del registro pasan a
  objetos ``{level, rotation_id, position, …}``.
- **Advertencias**: cuatro fijas siempre (CA-17.2, CA-17.3, CA-13.2, CA-17.5) y tres condicionales
  (sustituciones, escenarios bloqueados y coordenadas fuera de San Luis, CA-1.11).
- Si no hubo consulta a NASA POWER (ninguna ventana cubierta), ``provenance`` es ``null``.

No agrega series diarias (CA-15.5) ni calcula nada agronómico nuevo: solo da forma a lo calculado.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.core import messages
from app.core.constants import (
    CONTRACT_VERSION,
    MODEL_VERSION,
    SAN_LUIS_LAT_MAX_DEG,
    SAN_LUIS_LAT_MIN_DEG,
    SAN_LUIS_LON_MAX_DEG,
    SAN_LUIS_LON_MIN_DEG,
)
from app.core.exceptions import CalculationIntegrityError
from app.domain.economics import CropEconomics, RotationEconomics
from app.domain.stats import MarginDifference, Range, RotationRanges
from app.domain.wind_proxy import SoilExposure
from app.models.response import (
    AssumptionOut,
    AssumptionScopeOut,
    BlockedReasonOut,
    ComparisonOut,
    CropEconomicsOut,
    CropInputOut,
    CropRangesOut,
    CropResultOut,
    DateRangeOut,
    LocationOut,
    MissingEconomicsOut,
    ParameterOut,
    ParcelOut,
    ProvenanceOut,
    RangeOut,
    ResolvedInputOut,
    ResultOut,
    RotationEconomicsOut,
    RotationInputOut,
    RotationRangesOut,
    ScenarioOut,
    SimulationResponse,
    SoilExposureOut,
    SourceLocationOut,
    SubstitutionOut,
    VariableProvenanceOut,
    WarningOut,
    WaterBalanceOut,
    WindowOut,
)
from app.services.assumptions import Assumption
from app.services.climate_parser import Provenance
from app.services.parameter_resolver import ResolvedInput, ResolvedValue
from app.services.simulation_service import (
    STATUS_BLOCKED,
    STATUS_COMPUTED,
    CropRun,
    RunResult,
    ScenarioOutcome,
    SimulationOutcome,
)

# Decimales de cada tipo de valor (plan §5.1).
DECIMALS_MM = 1
DECIMALS_RATIO = 3
DECIMALS_T_HA = 2
DECIMALS_MONEY = 2

# Tolerancia de los controles de límites antes de serializar (punto flotante, no redondeo).
_LIMIT_TOLERANCE = 1e-6


def _integrity(message: str, run: RunResult | None = None) -> CalculationIntegrityError:
    return CalculationIntegrityError(
        message,
        rotation_id=run.rotation_id if run else None,
        start_year=run.start_year if run else None,
    )


def _finite(value: float, label: str = "valor") -> float:
    if not math.isfinite(value):
        raise _integrity(f"El {label} no es un número finito ({value}).")
    return value


def _round(value: float | None, decimals: int, label: str) -> float | None:
    """Redondea un valor finito; ``None`` pasa sin cambios. Normaliza −0,0 a 0,0."""
    if value is None:
        return None
    return round(_finite(value, label), decimals) + 0.0


def round_mm(value: float, label: str = "valor en mm") -> float:
    return _round(value, DECIMALS_MM, label)  # type: ignore[return-value]


def round_money(value: float | None, label: str = "importe") -> float | None:
    return _round(value, DECIMALS_MONEY, label)


def round_t_ha(value: float | None, label: str = "rendimiento") -> float | None:
    return _round(value, DECIMALS_T_HA, label)


def round_ratio(value: float | None, label: str = "cociente") -> float | None:
    return _round(value, DECIMALS_RATIO, label)


# --- Entrada resuelta ---


def _parameter(resolved: ResolvedValue) -> ParameterOut:
    value = resolved.value
    if isinstance(value, float):
        value = _finite(value, "parámetro")
    return ParameterOut(
        value=value, origin=resolved.origin, source=resolved.source, note=resolved.note
    )


def _resolved_input(resolved: ResolvedInput) -> ResolvedInputOut:
    parcel = resolved.parcel
    spec = parcel.spec
    window = resolved.window
    return ResolvedInputOut(
        parcel=ParcelOut(
            name=parcel.name,
            latitude_deg=spec.latitude_deg,
            longitude_deg=spec.longitude_deg,
            theta_fc_m3_m3=spec.theta_fc_m3_m3,
            theta_wp_m3_m3=spec.theta_wp_m3_m3,
            effective_depth_m=spec.effective_depth_m,
            profile_capacity_mm=round_mm(parcel.profile_capacity_mm, "capacidad del perfil"),
            initial_available_water_pct=spec.initial_available_water_pct,
            initial_storage_mm=round_mm(parcel.initial_storage_mm, "almacenamiento inicial"),
            fallow_kc_base=_parameter(parcel.fallow_kc_base),
            fallow_evaporation_layer_m=_parameter(parcel.fallow_evaporation_layer_m),
        ),
        window=WindowOut(
            start_day=window.start_day,
            start_month=window.start_month,
            start_years=list(window.start_years),
        ),
        rotations=[
            RotationInputOut(
                id=rotation.rotation_id,
                name=rotation.name,
                initial_residue_cover_pct=_parameter(rotation.initial_residue_cover_pct),
                crops=[
                    CropInputOut(
                        position=crop.position,
                        crop_code=crop.spec.crop_code,
                        crop_name=crop.crop_name,
                        crop_type=crop.spec.crop_type,  # type: ignore[arg-type]
                        calibrated=False,
                        parameters={
                            name: _parameter(value) for name, value in crop.parameters.items()
                        },
                    )
                    for crop in rotation.crops
                ],
            )
            for rotation in resolved.rotations
        ],
    )


# --- Procedencia ---


def _provenance(provenance: Provenance | None) -> ProvenanceOut | None:
    if provenance is None:
        return None
    return ProvenanceOut(
        source=provenance.source,
        service=provenance.service,
        retrieval=provenance.retrieval,
        queried_at=provenance.queried_at,
        source_version=provenance.source_version,
        requested_location=LocationOut(
            latitude_deg=provenance.requested_latitude_deg,
            longitude_deg=provenance.requested_longitude_deg,
        ),
        source_location=SourceLocationOut(
            latitude_deg=provenance.source_latitude_deg,
            longitude_deg=provenance.source_longitude_deg,
            elevation_m=provenance.elevation_m,
        ),
        spatial_note=provenance.spatial_note,
        date_range=DateRangeOut(start=provenance.date_start, end=provenance.date_end),
        variables=[
            VariableProvenanceOut(
                code=item.code,
                name=item.name,
                unit=item.unit,
                use=item.use,
                missing_days=item.missing_days,
            )
            for item in provenance.variables
        ],
        label=provenance.label,
    )


# --- Escenarios ---


def _scenario(scenario: ScenarioOutcome) -> ScenarioOut:
    return ScenarioOut(
        start_year=scenario.start_year,
        window_start=scenario.first_day,
        window_end=scenario.last_day,
        days=scenario.n_days,
        status=scenario.status,  # type: ignore[arg-type]
        blocked_reasons=[
            BlockedReasonOut(
                code=block.code,
                variable=block.variable,
                dates=list(block.dates),
                first_date=block.first_date,
                last_date=block.last_date,
                message=messages.BLOCK_REASONS[block.code],
            )
            for block in scenario.blocks
        ],
        substituted_days=[
            SubstitutionOut(
                variable=item.variable,
                method=messages.SUBSTITUTION_METHODS[item.method],
                count=len(item.dates),
                dates=list(item.dates),
            )
            for item in scenario.substitutions
        ],
        precipitation_total_mm=(
            round_mm(scenario.precipitation_total_mm, "lluvia total")
            if scenario.precipitation_total_mm is not None
            else None
        ),
        et0_total_mm=(
            round_mm(scenario.et0_total_mm, "ET₀ total")
            if scenario.et0_total_mm is not None
            else None
        ),
    )


# --- Resultados ---


def _crop_economics(economics: CropEconomics) -> CropEconomicsOut:
    return CropEconomicsOut(
        status=economics.status,  # type: ignore[arg-type]
        income_per_ha=round_money(economics.income_per_ha, "ingreso"),
        direct_costs_per_ha=round_money(economics.direct_costs_per_ha, "costos directos"),
        gross_margin_per_ha=round_money(economics.gross_margin_per_ha, "margen bruto"),
        gross_margin_label=economics.gross_margin_label,
        missing_fields=list(economics.missing_fields),
        note=economics.note,
        reason=economics.reason,
    )


def _rotation_economics(economics: RotationEconomics) -> RotationEconomicsOut:
    return RotationEconomicsOut(
        status=economics.status,  # type: ignore[arg-type]
        income_per_ha=round_money(economics.income_per_ha, "ingreso de la rotación"),
        direct_costs_per_ha=round_money(economics.direct_costs_per_ha, "costos de la rotación"),
        gross_margin_per_ha=round_money(economics.gross_margin_per_ha, "margen de la rotación"),
        gross_margin_label=economics.gross_margin_label,
        crops_missing_economics=[
            MissingEconomicsOut(
                position=item.position,
                crop_code=item.crop_code,
                missing_fields=list(item.missing_fields),
                reason=item.reason,
            )
            for item in economics.crops_missing_economics
        ],
    )


def _soil_exposure(exposure: SoilExposure) -> SoilExposureOut:
    return SoilExposureOut(
        window_days=exposure.window_days,
        live_crop_days=exposure.live_crop_days,
        no_live_crop_days=exposure.no_live_crop_days,
        strong_wind_days_without_live_crop=exposure.strong_wind_days_without_live_crop,
        no_wind_data_days_without_live_crop=exposure.no_wind_data_days_without_live_crop,
        wind_variable=exposure.wind_variable,
        threshold_ms=exposure.threshold_ms,
        rule=messages.WIND_RULE.format(threshold=f"{exposure.threshold_ms:.1f}".replace(".", ",")),
        threshold_source=messages.WIND_THRESHOLD_SOURCE,
        note=messages.WIND_NOTE,
    )


def _crop_result(crop: CropRun, run: RunResult, capacity_mm: float) -> CropResultOut:
    outcome = crop.yield_result
    segment = crop.segment
    for storage in (segment.storage_at_start_mm, segment.storage_at_end_mm):
        if (
            not -_LIMIT_TOLERANCE
            <= _finite(storage, "almacenamiento")
            <= capacity_mm + _LIMIT_TOLERANCE
        ):
            raise _integrity("El almacenamiento de un cultivo salió de [0, capacidad].", run)
    if (
        outcome.yield_t_ha is not None
        and _finite(outcome.yield_t_ha, "rendimiento") < -_LIMIT_TOLERANCE
    ):
        raise _integrity("El rendimiento calculado es negativo.", run)
    if outcome.relative_yield is not None and not (
        -_LIMIT_TOLERANCE
        <= _finite(outcome.relative_yield, "rendimiento relativo")
        <= 1 + _LIMIT_TOLERANCE
    ):
        raise _integrity("El rendimiento relativo salió de [0, 1] (Ya fuera de [0, Ym]).", run)
    return CropResultOut(
        position=crop.position,
        crop_code=crop.crop_code,
        crop_type=crop.crop_type,  # type: ignore[arg-type]
        sowing_date=crop.sowing_date,
        cycle_end_date=crop.cycle_end_date,
        storage_at_sowing_mm=round_mm(segment.storage_at_start_mm, "almacenamiento a la siembra"),
        storage_at_end_mm=round_mm(segment.storage_at_end_mm, "almacenamiento al fin del ciclo"),
        etm_mm=round_mm(outcome.etm_mm, "ETm"),
        eta_mm=round_mm(outcome.eta_mm, "ETa"),
        eta_etm_ratio=round_ratio(outcome.eta_etm_ratio, "ETa/ETm"),
        stress_days=segment.stress_days,
        yield_t_ha=round_t_ha(outcome.yield_t_ha),
        relative_yield=round_ratio(outcome.relative_yield, "rendimiento relativo"),
        yield_note=outcome.note,
        economics=_crop_economics(crop.economics),
    )


def _result(run: RunResult, scenarios: dict[int, ScenarioOutcome], capacity_mm: float) -> ResultOut:
    balance = run.balance
    scenario = scenarios[run.start_year]
    for storage in (balance.initial_storage_mm, balance.final_storage_mm):
        if (
            not -_LIMIT_TOLERANCE
            <= _finite(storage, "almacenamiento")
            <= capacity_mm + _LIMIT_TOLERANCE
        ):
            raise _integrity("El almacenamiento del perfil salió de [0, capacidad].", run)
    return ResultOut(
        rotation_id=run.rotation_id,
        start_year=run.start_year,
        water_balance=WaterBalanceOut(
            initial_storage_mm=round_mm(balance.initial_storage_mm, "almacenamiento inicial"),
            final_storage_mm=round_mm(balance.final_storage_mm, "almacenamiento final"),
            precipitation_mm=round_mm(balance.precipitation_mm, "lluvia"),
            et0_mm=round_mm(scenario.et0_total_mm or 0.0, "ET₀"),
            crop_eta_mm=round_mm(balance.crop_eta_mm, "ETa de cultivos"),
            fallow_evaporation_mm=round_mm(balance.fallow_evaporation_mm, "evaporación"),
            excess_lost_mm=round_mm(balance.excess_lost_mm, "excedente"),
            # El cierre se calcula con valores sin redondear y se redondea al final.
            mass_balance_error_mm=round_mm(balance.closure_mm, "error de cierre"),
        ),
        crops=[_crop_result(crop, run, capacity_mm) for crop in run.crops],
        rotation_economics=_rotation_economics(run.economics),
        soil_exposure=_soil_exposure(run.exposure),
    )


# --- Rangos y comparaciones ---


def _range(value: Range | None, decimals: int, label: str) -> RangeOut | None:
    if value is None:
        return None
    return RangeOut(
        min=_round(value.minimum, decimals, label) or 0.0,
        median=_round(value.median, decimals, label) or 0.0,
        max=_round(value.maximum, decimals, label) or 0.0,
        n=value.n,
        no_range=value.no_range,
    )


def _rotation_ranges(ranges: RotationRanges) -> RotationRangesOut:
    return RotationRangesOut(
        rotation_id=ranges.rotation_id,
        n_scenarios=ranges.n_scenarios,
        scenarios_included=list(ranges.scenarios_included),
        scenarios_excluded=list(ranges.scenarios_excluded),
        crops=[
            CropRangesOut(
                position=crop.position,
                crop_code=crop.crop_code,
                yield_t_ha=_range(crop.yield_t_ha, DECIMALS_T_HA, "rango de rendimiento"),
                eta_etm_ratio=_range(crop.eta_etm_ratio, DECIMALS_RATIO, "rango de ETa/ETm"),
            )
            for crop in ranges.crops
        ],
        gross_margin_per_ha=_range(ranges.gross_margin_per_ha, DECIMALS_MONEY, "rango de margen"),
        margin_not_computed_years=list(ranges.margin_not_computed_years),
        strong_wind_days_without_live_crop=_range(
            ranges.strong_wind_days_without_live_crop, DECIMALS_MM, "rango de días de viento"
        ),
        label=messages.RANGE_LABEL,
    )


def _comparison(difference: MarginDifference) -> ComparisonOut:
    return ComparisonOut(
        start_year=difference.start_year,
        minuend_rotation_id=difference.minuend_rotation_id,
        subtrahend_rotation_id=difference.subtrahend_rotation_id,
        gross_margin_difference_per_ha=round_money(
            difference.gross_margin_difference_per_ha, "diferencia de margen"
        )
        or 0.0,
        label=messages.COMPARISON_LABEL.format(
            minuend=difference.minuend_rotation_id, subtrahend=difference.subtrahend_rotation_id
        ),
    )


# --- Supuestos ---


def assumption_scope(scope: str, scope_id: str | None) -> AssumptionScopeOut:
    """Convierte el alcance de texto del registro (``A/1/ky``, ``B/3``, ``2008``) en objeto."""
    try:
        if scope == "request":
            return AssumptionScopeOut(level="request")
        if scope == "crop" and scope_id:
            rotation_id, position, parameter = scope_id.split("/")
            start_year = None
            if "@" in parameter:
                parameter, year = parameter.split("@")
                parameter = "yield_t_ha" if parameter == "yield" else parameter
                start_year = int(year)
            return AssumptionScopeOut(
                level="crop",
                rotation_id=rotation_id,
                position=int(position),
                parameter=parameter,
                start_year=start_year,
            )
        if scope == "fallow" and scope_id:
            rotation_id, after_position = scope_id.split("/")
            return AssumptionScopeOut(
                level="fallow", rotation_id=rotation_id, after_position=int(after_position)
            )
        if scope == "scenario" and scope_id:
            return AssumptionScopeOut(level="scenario", start_year=int(scope_id))
        if scope == "rotation" and scope_id:
            return AssumptionScopeOut(level="rotation", rotation_id=scope_id)
        if scope == "date":
            return AssumptionScopeOut(level="date")
    except ValueError as error:
        raise _integrity(f"Alcance de supuesto ilegible: {scope}:{scope_id}") from error
    raise _integrity(f"Alcance de supuesto ilegible: {scope}:{scope_id}")


def _assumption(entry: Assumption) -> AssumptionOut:
    value = entry.value
    if isinstance(value, float):
        value = _finite(value, "valor de un supuesto")
    grouped = bool(entry.dates) or entry.count > 1
    return AssumptionOut(
        code=entry.code,
        scope=assumption_scope(entry.scope, entry.scope_id),
        description=entry.description,
        value=value,
        unit=entry.unit,
        origin=entry.origin,  # type: ignore[arg-type]
        source=entry.source,
        count=entry.count if grouped else None,
        dates=list(entry.dates) if entry.dates else None,
    )


# --- Advertencias ---

FIXED_WARNINGS: tuple[str, ...] = (
    "HISTORICAL_DESCRIPTIVE",
    "UNCALIBRATED_PARAMETERS",
    "CELL_SCALE_DATA",
    "NOT_A_RECOMMENDATION",
)


def is_outside_san_luis(latitude_deg: float, longitude_deg: float) -> bool:
    """Coordenadas fuera de la caja aproximada de San Luis (D-9; a verificar)."""
    return not (
        SAN_LUIS_LAT_MIN_DEG <= latitude_deg <= SAN_LUIS_LAT_MAX_DEG
        and SAN_LUIS_LON_MIN_DEG <= longitude_deg <= SAN_LUIS_LON_MAX_DEG
    )


def _years_text(scenarios: Sequence[ScenarioOutcome]) -> str:
    return ", ".join(str(scenario.start_year) for scenario in scenarios)


def build_warnings(outcome: SimulationOutcome) -> list[WarningOut]:
    """Advertencias fijas y condicionales, con los textos de ``core.messages``."""
    warnings = [WarningOut(code=code, message=messages.WARNINGS[code]) for code in FIXED_WARNINGS]
    substituted = [s for s in outcome.scenarios if s.status == STATUS_COMPUTED and s.substitutions]
    if substituted:
        detail = messages.WARNING_SUBSTITUTIONS_DETAIL.format(years=_years_text(substituted))
        warnings.append(
            WarningOut(
                code="SUBSTITUTIONS_PRESENT",
                message=f"{messages.WARNINGS['SUBSTITUTIONS_PRESENT']} {detail}",
            )
        )
    blocked = [s for s in outcome.scenarios if s.status == STATUS_BLOCKED]
    if blocked:
        detail = messages.WARNING_BLOCKED_DETAIL.format(years=_years_text(blocked))
        warnings.append(
            WarningOut(
                code="SCENARIOS_BLOCKED",
                message=f"{messages.WARNINGS['SCENARIOS_BLOCKED']} {detail}",
            )
        )
    parcel = outcome.resolved.parcel.spec
    if is_outside_san_luis(parcel.latitude_deg, parcel.longitude_deg):
        warnings.append(
            WarningOut(code="OUTSIDE_SAN_LUIS", message=messages.WARNINGS["OUTSIDE_SAN_LUIS"])
        )
    return warnings


# --- Respuesta completa ---


def _assert_finite_tree(node: Any, path: str = "") -> None:
    """La respuesta nunca contiene ``NaN`` ni infinitos (plan §5.1)."""
    if isinstance(node, float):
        _finite(node, f"campo {path or 'raíz'}")
    elif isinstance(node, dict):
        for key, value in node.items():
            _assert_finite_tree(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list | tuple):
        for index, value in enumerate(node):
            _assert_finite_tree(value, f"{path}[{index}]")


def build_response(
    outcome: SimulationOutcome, *, request_id: str, computed_at: datetime
) -> SimulationResponse:
    """Arma la respuesta final; lanza ``CalculationIntegrityError`` ante un valor inválido."""
    capacity_mm = outcome.resolved.parcel.profile_capacity_mm
    scenarios = {scenario.start_year: scenario for scenario in outcome.scenarios}
    response = SimulationResponse(
        contract_version=CONTRACT_VERSION,
        model_version=MODEL_VERSION,
        request_id=request_id,
        computed_at=computed_at,
        currency=outcome.resolved.currency,
        resolved_input=_resolved_input(outcome.resolved),
        provenance=_provenance(outcome.provenance),
        scenarios=[_scenario(scenario) for scenario in outcome.scenarios],
        results=[_result(run, scenarios, capacity_mm) for run in outcome.runs],
        ranges=[_rotation_ranges(ranges) for ranges in outcome.ranges],
        comparisons=[_comparison(difference) for difference in outcome.comparisons],
        assumptions=[_assumption(entry) for entry in outcome.assumptions],
        warnings=build_warnings(outcome),
    )
    _assert_finite_tree(response.model_dump())
    return response
