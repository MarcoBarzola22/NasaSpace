"""Formato único de error de la API (plan §5.5, RF-16; T034).

``category`` distingue tres casos (CA-16.4): ``input`` (datos de la solicitud), ``nasa_power``
(falla o indisponibilidad de la fuente) e ``internal`` (error interno de cálculo o inesperado).
"""

from __future__ import annotations

from typing import Literal

from app.models.common import StrictModel


class ErrorDetail(StrictModel):
    """Un defecto puntual: ruta del campo (``rotations[0].crops[1].ym_t_ha``) y su motivo."""

    field: str
    message: str
    code: str | None = None


class ErrorBody(StrictModel):
    category: Literal["input", "nasa_power", "internal"]
    code: str
    message: str
    retryable: bool
    request_id: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(StrictModel):
    error: ErrorBody
