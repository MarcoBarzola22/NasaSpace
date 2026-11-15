"""Pruebas del parser de la respuesta de NASA POWER y de la procedencia (T040).

Cubren CA-5.2 (la serie no se guarda), CA-5.5 (formato inesperado, variable ausente o unidad
distinta), CA-6.1 (relleno y fechas ausentes son faltantes), CA-6.2 (sin interpolación), CA-13.1
(campos de la procedencia) y CA-13.2 (rótulo de celda).
"""

from __future__ import annotations

import builtins
import json
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.core.exceptions import PowerBadResponseError
from app.services.climate_parser import parse_power_response
from app.services.power_client import PowerQuery, PowerRawResponse
from tests.builders.power_payload import DEFAULT_ELEVATION_M, power_payload

START = date(2020, 1, 1)
END = date(2020, 1, 10)
QUERY = PowerQuery(latitude_deg=-33.68, longitude_deg=-65.47, start=START, end=END)
QUERIED_AT = datetime(2026, 11, 15, 14, 3, 19, tzinfo=UTC)


def raw(payload: dict[str, Any] | bytes) -> PowerRawResponse:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return PowerRawResponse(body=body, requested_at=QUERIED_AT, status_code=200)


def parse(**options: Any):
    return parse_power_response(raw(power_payload(START, END, **options)), QUERY)


def test_complete_payload_gives_one_record_per_date_in_order() -> None:
    series = parse()
    assert [day.day for day in series.days] == [START + timedelta(days=i) for i in range(10)]
    first = series.days[0]
    assert (first.precipitation_mm, first.t_max_c, first.t_min_c, first.dew_point_c) == (
        1.5,
        28.0,
        14.0,
        12.0,
    )
    assert (first.wind_mean_ms, first.wind_max_ms, first.solar_radiation_mj_m2) == (2.5, 5.0, 20.0)
    assert series.elevation_m == pytest.approx(DEFAULT_ELEVATION_M)


def test_fill_value_becomes_none() -> None:
    """CA-6.1: −999 es faltante."""
    series = parse(fill_dates={"PRECTOTCORR": [date(2020, 1, 4)]})
    assert series.days[3].precipitation_mm is None
    assert series.days[3].t_max_c == 28.0
    assert series.days[2].precipitation_mm == 1.5


def test_absent_date_becomes_none_in_every_variable() -> None:
    """CA-6.1: un día ausente de la respuesta es faltante."""
    series = parse(missing_dates=[date(2020, 1, 6)])
    absent = series.days[5]
    assert absent.day == date(2020, 1, 6)
    assert all(
        getattr(absent, field) is None
        for field in (
            "precipitation_mm",
            "t_max_c",
            "t_min_c",
            "dew_point_c",
            "wind_mean_ms",
            "wind_max_ms",
            "solar_radiation_mj_m2",
        )
    )


def test_missing_days_are_never_filled_from_neighbours() -> None:
    """CA-6.2: el vecino no se copia ni se promedia."""
    series = parse(fill_dates={"T2M_MAX": [date(2020, 1, 5)]}, values={"T2M_MAX": 30.0})
    assert series.days[4].t_max_c is None
    assert series.days[3].t_max_c == series.days[5].t_max_c == 30.0


def test_declared_fill_value_other_than_999_is_honoured() -> None:
    payload = power_payload(START, END)
    payload["header"]["fill_value"] = -9999.0
    payload["properties"]["parameter"]["PRECTOTCORR"]["20200103"] = -9999.0
    payload["properties"]["parameter"]["PRECTOTCORR"]["20200104"] = -999.0  # ahora es un dato
    series = parse_power_response(raw(payload), QUERY)
    assert series.days[2].precipitation_mm is None
    assert series.days[3].precipitation_mm == -999.0


def test_missing_fill_value_declaration_defaults_to_minus_999() -> None:
    series = parse(declare_fill_value=False, fill_dates={"WS2M": [date(2020, 1, 2)]})
    assert series.days[1].wind_mean_ms is None


def test_nan_is_treated_as_missing() -> None:
    payload = power_payload(START, END)
    payload["properties"]["parameter"]["T2M_MIN"]["20200102"] = float("nan")
    assert parse_power_response(raw(payload), QUERY).days[1].t_min_c is None


def test_trailing_fill_values_are_kept_as_missing_for_the_coverage_rules() -> None:
    series = parse(trailing_fill=3)
    assert all(day.precipitation_mm is None for day in series.days[-3:])
    assert series.days[-4].precipitation_mm == 1.5


@pytest.mark.parametrize(
    "body",
    [b"esto no es json", b"", b"[1, 2, 3]", b"\xff\xfe"],
    ids=["text", "empty", "list", "bytes"],
)
def test_body_that_is_not_a_json_object_is_a_bad_response(body: bytes) -> None:
    with pytest.raises(PowerBadResponseError):
        parse_power_response(raw(body), QUERY)


def test_missing_properties_parameter_is_a_bad_response() -> None:
    payload = power_payload(START, END)
    del payload["properties"]["parameter"]
    with pytest.raises(PowerBadResponseError):
        parse_power_response(raw(payload), QUERY)


@pytest.mark.parametrize(
    "variable",
    ["PRECTOTCORR", "T2M_MAX", "T2M_MIN", "T2MDEW", "WS2M", "WS2M_MAX", "ALLSKY_SFC_SW_DWN"],
)
def test_a_missing_variable_is_a_bad_response(variable: str) -> None:
    """CA-5.5: omitir por completo una variable requerida (por ejemplo WS2M_MAX)."""
    with pytest.raises(PowerBadResponseError):
        parse(drop_parameter=variable)


@pytest.mark.parametrize(
    ("variable", "unit"),
    [("WS2M", "km/h"), ("PRECTOTCORR", "mm/hr"), ("T2M_MAX", "K"), ("ALLSKY_SFC_SW_DWN", "W/m^2")],
)
def test_a_different_unit_is_a_bad_response_and_is_never_converted(
    variable: str, unit: str
) -> None:
    with pytest.raises(PowerBadResponseError) as caught:
        parse(units_override={variable: unit})
    assert variable in str(caught.value)


def test_missing_elevation_is_a_bad_response() -> None:
    with pytest.raises(PowerBadResponseError):
        parse(without_elevation=True)


def test_non_numeric_daily_value_is_a_bad_response() -> None:
    payload = power_payload(START, END)
    payload["properties"]["parameter"]["T2M_MAX"]["20200102"] = "caluroso"
    with pytest.raises(PowerBadResponseError):
        parse_power_response(raw(payload), QUERY)


def test_missing_units_block_is_a_bad_response() -> None:
    payload = power_payload(START, END)
    del payload["parameters"]
    with pytest.raises(PowerBadResponseError):
        parse_power_response(raw(payload), QUERY)


def test_dates_outside_the_query_range_are_ignored() -> None:
    payload = power_payload(START - timedelta(days=3), END + timedelta(days=3))
    series = parse_power_response(raw(payload), QUERY)
    assert (series.days[0].day, series.days[-1].day) == (START, END)


def test_provenance_has_every_field_of_ca_13_1() -> None:
    provenance = parse().provenance
    assert provenance.source == "NASA POWER"
    assert "API diaria de punto" in provenance.service and "AG" in provenance.service
    assert provenance.retrieval == "Consulta en vivo"
    assert provenance.queried_at == QUERIED_AT
    assert provenance.source_version == "v2.10.3"
    assert (provenance.requested_latitude_deg, provenance.requested_longitude_deg) == (
        -33.68,
        -65.47,
    )
    assert (provenance.source_latitude_deg, provenance.source_longitude_deg) == (-33.68, -65.47)
    assert provenance.elevation_m == pytest.approx(DEFAULT_ELEVATION_M)
    assert (provenance.date_start, provenance.date_end) == (START, END)
    assert "celda" in provenance.spatial_note


def test_provenance_label_is_the_exact_ca_13_2_text() -> None:
    label = "dato de modelo/reanálisis de NASA POWER a escala de celda; no es una medición del lote"
    assert parse().provenance.label == label


def test_provenance_lists_the_seven_variables_with_unit_use_and_missing_days() -> None:
    payload_options = {
        "fill_dates": {
            "PRECTOTCORR": [date(2020, 1, 3)],
            "ALLSKY_SFC_SW_DWN": [date(2020, 1, 5), date(2020, 1, 6)],
        },
        "missing_dates": [date(2020, 1, 9)],
    }
    variables = {v.code: v for v in parse(**payload_options).provenance.variables}
    assert list(variables) == [
        "PRECTOTCORR",
        "T2M_MAX",
        "T2M_MIN",
        "T2MDEW",
        "WS2M",
        "WS2M_MAX",
        "ALLSKY_SFC_SW_DWN",
    ]
    assert variables["PRECTOTCORR"].missing_days == 2  # un relleno y una fecha ausente
    assert variables["T2M_MAX"].missing_days == 1  # solo la fecha ausente
    assert variables["ALLSKY_SFC_SW_DWN"].missing_days == 3
    assert variables["WS2M_MAX"].use == "Proxy de viento fuerte"
    assert variables["PRECTOTCORR"].unit == "mm/día"
    assert variables["ALLSKY_SFC_SW_DWN"].unit == "MJ/m²/día"


def test_provenance_version_is_none_when_the_source_does_not_report_it() -> None:
    assert parse(api_version=None).provenance.source_version is None


def test_parsing_writes_nothing_to_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """CA-5.2: con ``open`` en modo escritura bloqueado, el parseo termina sin error."""
    real_open = builtins.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("el parser no debe escribir archivos")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    parse(fill_dates={"PRECTOTCORR": [START]})


def test_payload_is_not_modified_by_parsing() -> None:
    payload = power_payload(START, END)
    snapshot = deepcopy(payload)
    parse_power_response(raw(payload), QUERY)
    assert payload == snapshot
