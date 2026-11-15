"""Dependencias de FastAPI (T039).

Se usan con ``Depends`` en los routers y se reemplazan en las pruebas con
``app.dependency_overrides`` para inyectar un transporte simulado de NASA POWER.
"""

from __future__ import annotations

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.power_client import PowerClient


def get_power_client(settings: Settings = Depends(get_settings)) -> PowerClient:  # noqa: B008
    """Cliente de NASA POWER con la configuración vigente (sin estado entre solicitudes)."""
    return PowerClient(settings)
