"""``POST /api/v1/simulations``: comparación completa de rotaciones (RF-1…RF-17; T046).

El router solo conecta las piezas: el cuerpo ya validado estructuralmente por Pydantic pasa al
servicio de simulación (validación semántica, consulta única a NASA POWER, cálculo) y su salida se
arma con el constructor de la respuesta. No contiene lógica agronómica (RNF-7). Los errores salen
por los manejadores de ``core.error_handlers``.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, Request

from app.core.config import Settings, get_settings
from app.core.dependencies import get_catalog, get_now, get_power_client, get_today
from app.core.request_context import request_id_of
from app.models.errors import ErrorResponse
from app.models.examples import REQUEST_EXAMPLE, RESPONSE_EXAMPLE
from app.models.request import SimulationRequest
from app.models.response import SimulationResponse
from app.services.catalog_service import Catalog
from app.services.power_client import PowerClient
from app.services.response_builder import build_response
from app.services.simulation_service import simulate

router = APIRouter(tags=["simulaciones"])

_ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Solicitud con datos inválidos."},
    500: {"model": ErrorResponse, "description": "Error interno de cálculo o inesperado."},
    502: {
        "model": ErrorResponse,
        "description": "NASA POWER devolvió un error o un formato inesperado.",
    },
    503: {"model": ErrorResponse, "description": "NASA POWER no disponible o limitando consultas."},
    504: {"model": ErrorResponse, "description": "NASA POWER no respondió a tiempo."},
}


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    responses={
        200: {
            "description": "Comparación calculada (puede traer escenarios bloqueados).",
            "content": {"application/json": {"example": RESPONSE_EXAMPLE}},
        },
        **_ERROR_RESPONSES,
    },
    summary="Comparar rotaciones con series históricas de NASA POWER",
)
async def create_simulation(
    request: Request,
    body: SimulationRequest = Body(  # noqa: B008
        openapi_examples={
            "plan": {
                "summary": "Dos rotaciones de tres cultivos, tres escenarios",
                "value": REQUEST_EXAMPLE,
            }
        }
    ),
    settings: Settings = Depends(get_settings),  # noqa: B008
    catalog: Catalog = Depends(get_catalog),  # noqa: B008
    power_client: PowerClient = Depends(get_power_client),  # noqa: B008
    today: date = Depends(get_today),  # noqa: B008
    now: datetime = Depends(get_now),  # noqa: B008
) -> SimulationResponse:
    outcome = await simulate(
        body, catalog=catalog, settings=settings, power_client=power_client, today=today
    )
    return build_response(outcome, request_id=request_id_of(request), computed_at=now)
