"""Dependencias de FastAPI (T039, T046).

Se usan con ``Depends`` en los routers y se reemplazan en las pruebas con
``app.dependency_overrides`` para inyectar un transporte simulado de NASA POWER y fijar el reloj.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.catalog_service import Catalog, load_catalog
from app.services.power_client import PowerClient
from app.services.window_service import utc_today


def get_power_client(settings: Settings = Depends(get_settings)) -> PowerClient:  # noqa: B008
    """Cliente de NASA POWER con la configuración vigente (sin estado entre solicitudes)."""
    return PowerClient(settings)


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Catálogo de cultivos: archivo estático versionado con el código (no son datos climáticos)."""
    return load_catalog()


def get_today() -> date:
    """Fecha de hoy en UTC (CA-4.4)."""
    return utc_today()


def get_now() -> datetime:
    """Instante actual en UTC, para ``computed_at``."""
    return datetime.now(UTC)
