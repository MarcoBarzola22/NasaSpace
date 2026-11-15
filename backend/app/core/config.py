"""Configuración del servicio desde variables de entorno (T005).

Solo se leen variables con prefijo ``AGRODSS_``. Los valores por defecto salen de la
verificación V-1 (``specs/001-agrodss-backend/research.md``). No se escribe nada en disco.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType

ENV_POWER_BASE_URL = "AGRODSS_POWER_BASE_URL"
ENV_POWER_CONNECT_TIMEOUT_S = "AGRODSS_POWER_CONNECT_TIMEOUT_S"
ENV_POWER_READ_TIMEOUT_S = "AGRODSS_POWER_READ_TIMEOUT_S"
ENV_CORS_ORIGINS = "AGRODSS_CORS_ORIGINS"

# Variables diarias que se piden a NASA POWER (comunidad AG), en una sola consulta.
POWER_VARIABLES: tuple[str, ...] = (
    "PRECTOTCORR",
    "T2M_MAX",
    "T2M_MIN",
    "T2MDEW",
    "WS2M",
    "WS2M_MAX",
    "ALLSKY_SFC_SW_DWN",
)
RADIATION_VARIABLE = "ALLSKY_SFC_SW_DWN"

# Inicio de cobertura diaria (V-1): meteorología desde 1981; radiación desde 1984.
METEOROLOGY_COVERAGE_START = date(1981, 1, 1)
RADIATION_COVERAGE_START = date(1984, 1, 1)

# Valor de relleno de NASA POWER si la respuesta no declara ``header.fill_value`` (V-1).
POWER_FILL_VALUE_DEFAULT = -999.0


def _default_coverage_start() -> Mapping[str, date]:
    start = dict.fromkeys(POWER_VARIABLES, METEOROLOGY_COVERAGE_START)
    start[RADIATION_VARIABLE] = RADIATION_COVERAGE_START
    return MappingProxyType(start)


@dataclass(frozen=True)
class Settings:
    power_base_url: str = "https://power.larc.nasa.gov"
    power_community: str = "AG"
    power_time_standard: str = "LST"
    power_connect_timeout_s: float = 10.0
    power_read_timeout_s: float = 60.0
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    variable_coverage_start: Mapping[str, date] = field(default_factory=_default_coverage_start)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Construye la configuración; ``environ`` permite inyectar un entorno en las pruebas."""
    env = os.environ if environ is None else environ
    defaults = Settings()
    return Settings(
        power_base_url=_base_url(env, defaults.power_base_url),
        power_connect_timeout_s=_seconds(
            env, ENV_POWER_CONNECT_TIMEOUT_S, defaults.power_connect_timeout_s
        ),
        power_read_timeout_s=_seconds(env, ENV_POWER_READ_TIMEOUT_S, defaults.power_read_timeout_s),
        cors_origins=_origins(env, defaults.cors_origins),
    )


def get_settings() -> Settings:
    """Dependencia de FastAPI: lee el entorno en cada llamada (sin caché)."""
    return load_settings()


def _base_url(env: Mapping[str, str], default: str) -> str:
    raw = env.get(ENV_POWER_BASE_URL, "").strip()
    if not raw:
        return default
    if not raw.startswith(("http://", "https://")):
        raise ValueError(f"{ENV_POWER_BASE_URL} debe empezar con http:// o https://")
    return raw.rstrip("/")


def _seconds(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        seconds = float(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser un número de segundos mayor que 0") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} debe ser un número de segundos mayor que 0")
    return seconds


def _origins(env: Mapping[str, str], default: tuple[str, ...]) -> tuple[str, ...]:
    origins = tuple(
        item.strip() for item in env.get(ENV_CORS_ORIGINS, "").split(",") if item.strip()
    )
    return origins or default
