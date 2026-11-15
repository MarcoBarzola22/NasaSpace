"""``GET /api/v1/health``: estado del servicio y versiones; no consulta a NASA POWER (T007)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from app.core.constants import CONTRACT_VERSION, MODEL_VERSION
from app.models.common import StrictModel

router = APIRouter(tags=["salud"])


class HealthResponse(StrictModel):
    status: Literal["ok"]
    model_version: str
    contract_version: str


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok", model_version=MODEL_VERSION, contract_version=CONTRACT_VERSION
    )
