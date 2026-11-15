"""Pruebas del generador de respuestas sintéticas de NASA POWER (T038; RF-5, RF-6)."""

from __future__ import annotations

import builtins
from datetime import date, timedelta

import pytest

from app.core.config import POWER_VARIABLES
from tests.builders.power_payload import FILL_VALUE, UNITS, power_payload

START = date(2020, 1, 1)
END = date(2020, 1, 10)


def test_default_payload_has_seven_variables_with_exact_units() -> None:
    payload = power_payload(START, END)
    assert set(payload["properties"]["parameter"]) == set(POWER_VARIABLES)
    assert {name: info["units"] for name, info in payload["parameters"].items()} == UNITS
    assert UNITS["PRECTOTCORR"] == "mm/day"
    assert UNITS["ALLSKY_SFC_SW_DWN"] == "MJ/m^2/day"
    assert payload["header"]["fill_value"] == FILL_VALUE
    assert payload["header"]["api"]["version"] == "v2.10.3"
    assert payload["geometry"]["coordinates"][2] == pytest.approx(699.34)  # lon, lat, elevación


def test_default_payload_dates_are_contiguous() -> None:
    days = list(power_payload(START, END)["properties"]["parameter"]["T2M_MAX"])
    expected = [(START + timedelta(days=i)).strftime("%Y%m%d") for i in range(10)]
    assert days == expected


def test_fill_dates_put_the_fill_value_only_in_that_variable() -> None:
    payload = power_payload(START, END, fill_dates={"PRECTOTCORR": [date(2020, 1, 4)]})
    rain = payload["properties"]["parameter"]["PRECTOTCORR"]
    assert rain["20200104"] == FILL_VALUE
    assert payload["properties"]["parameter"]["T2M_MAX"]["20200104"] != FILL_VALUE


def test_drop_parameter_removes_the_variable_and_its_units() -> None:
    payload = power_payload(START, END, drop_parameter="ALLSKY_SFC_SW_DWN")
    assert "ALLSKY_SFC_SW_DWN" not in payload["properties"]["parameter"]
    assert "ALLSKY_SFC_SW_DWN" not in payload["parameters"]
    assert len(payload["properties"]["parameter"]) == 6


def test_units_override_changes_only_that_variable() -> None:
    payload = power_payload(START, END, units_override={"WS2M": "km/h"})
    assert payload["parameters"]["WS2M"]["units"] == "km/h"
    assert payload["parameters"]["WS2M_MAX"]["units"] == "m/s"


def test_without_elevation_leaves_two_coordinates() -> None:
    assert len(power_payload(START, END, without_elevation=True)["geometry"]["coordinates"]) == 2


def test_trailing_fill_marks_the_last_days_in_every_variable() -> None:
    payload = power_payload(START, END, trailing_fill=3)
    for series in payload["properties"]["parameter"].values():
        values = list(series.values())
        assert values[-3:] == [FILL_VALUE] * 3
        assert FILL_VALUE not in values[:-3]


def test_missing_dates_are_absent_from_every_variable() -> None:
    payload = power_payload(START, END, missing_dates=[date(2020, 1, 5)])
    for series in payload["properties"]["parameter"].values():
        assert "20200105" not in series
        assert len(series) == 9


def test_optional_header_fields_can_be_omitted() -> None:
    header = power_payload(START, END, api_version=None, declare_fill_value=False)["header"]
    assert "api" not in header
    assert "fill_value" not in header


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        power_payload(END, START)


def test_builder_does_not_open_files(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("el generador no debe abrir archivos")

    monkeypatch.setattr(builtins, "open", blocked)
    power_payload(START, END, trailing_fill=2, fill_dates={"T2M_MIN": [START]})
