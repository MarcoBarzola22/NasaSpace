"""Pruebas de la configuración (T005).

Criterios que verifica: CA-5.6 (timeouts declarados) y CA-4.5 (inicio de cobertura por
variable, base del bloqueo por datos no cubiertos).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import (
    POWER_VARIABLES,
    RADIATION_COVERAGE_START,
    get_settings,
    load_settings,
)


def test_settings_defaults() -> None:
    settings = load_settings({})
    assert settings.power_base_url == "https://power.larc.nasa.gov"
    assert settings.power_community == "AG"
    assert settings.power_time_standard == "LST"
    assert settings.power_connect_timeout_s == 10.0
    assert settings.power_read_timeout_s == 60.0
    assert settings.cors_origins == ("http://localhost:5173",)


def test_coverage_start_matches_verification_v1() -> None:
    coverage = load_settings({}).variable_coverage_start
    assert set(coverage) == set(POWER_VARIABLES)
    assert len(POWER_VARIABLES) == 7
    assert coverage["ALLSKY_SFC_SW_DWN"] == date(1984, 1, 1)
    assert RADIATION_COVERAGE_START == date(1984, 1, 1)
    for code in POWER_VARIABLES:
        if code != "ALLSKY_SFC_SW_DWN":
            assert coverage[code] == date(1981, 1, 1), code


def test_coverage_start_is_read_only() -> None:
    coverage = load_settings({}).variable_coverage_start
    with pytest.raises(TypeError):
        coverage["T2M_MAX"] = date(2000, 1, 1)  # type: ignore[index]


def test_settings_env_override() -> None:
    settings = load_settings(
        {
            "AGRODSS_POWER_BASE_URL": "http://localhost:9999/",
            "AGRODSS_POWER_CONNECT_TIMEOUT_S": "3",
            "AGRODSS_POWER_READ_TIMEOUT_S": "15.5",
            "AGRODSS_CORS_ORIGINS": "http://a.example, http://b.example",
        }
    )
    assert settings.power_base_url == "http://localhost:9999"
    assert settings.power_connect_timeout_s == 3.0
    assert settings.power_read_timeout_s == 15.5
    assert settings.cors_origins == ("http://a.example", "http://b.example")


def test_settings_read_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGRODSS_POWER_READ_TIMEOUT_S", "42")
    assert get_settings().power_read_timeout_s == 42.0
    monkeypatch.delenv("AGRODSS_POWER_READ_TIMEOUT_S")
    assert get_settings().power_read_timeout_s == 60.0


@pytest.mark.parametrize("value", ["0", "-5", "abc", "nan", "inf"])
def test_invalid_timeout_is_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="AGRODSS_POWER_READ_TIMEOUT_S"):
        load_settings({"AGRODSS_POWER_READ_TIMEOUT_S": value})


def test_invalid_base_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="AGRODSS_POWER_BASE_URL"):
        load_settings({"AGRODSS_POWER_BASE_URL": "power.larc.nasa.gov"})


def test_blank_values_fall_back_to_defaults() -> None:
    settings = load_settings({"AGRODSS_POWER_BASE_URL": "  ", "AGRODSS_CORS_ORIGINS": " , "})
    assert settings.power_base_url == "https://power.larc.nasa.gov"
    assert settings.cors_origins == ("http://localhost:5173",)
