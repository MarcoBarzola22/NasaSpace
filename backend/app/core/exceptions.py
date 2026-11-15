"""Jerarquía de excepciones del servicio (T006).

Separa tres orígenes de falla, que el frontend distingue por ``category`` (CA-16.4):

- ``input``: la solicitud del usuario es inválida (``InputValidationError``).
- ``nasa_power``: falla de infraestructura al consultar la fuente (``InfrastructureError``).
- ``internal``: un control de consistencia del cálculo no se cumplió (``DomainError``).

Las excepciones no llevan texto para el usuario ni código HTTP: los mensajes en español van en
``core.messages`` y la traducción a HTTP en ``core.error_handlers``. Este módulo no importa nada
del proyecto, para que ``domain`` pueda lanzar ``CalculationIntegrityError``.
"""

from __future__ import annotations

from typing import ClassVar


class AgroDSSError(Exception):
    """Base de todos los errores propios del servicio."""

    category: ClassVar[str] = "internal"
    code: ClassVar[str] = "unexpected_error"
    retryable: ClassVar[bool] = False


# --- Entrada del usuario ---


class InputValidationError(AgroDSSError):
    """La solicitud tiene datos inválidos; ``details`` reúne todos los defectos encontrados."""

    category: ClassVar[str] = "input"
    code: ClassVar[str] = "invalid_input"

    def __init__(self, details: list[dict[str, str]], code: str | None = None) -> None:
        self.details = list(details)
        if code is not None:
            self.code = code
        super().__init__(f"{len(self.details)} error(es) de validación")


# --- Errores de dominio (cálculo) ---


class DomainError(AgroDSSError):
    """Falla de una regla del modelo agronómico; nunca es culpa del usuario ni de la fuente."""

    category: ClassVar[str] = "internal"


class CalculationIntegrityError(DomainError):
    """Un control de consistencia falló (cierre de masa, límites, NaN, Ya fuera de [0, Ym])."""

    code: ClassVar[str] = "calculation_integrity"

    def __init__(
        self,
        message: str,
        *,
        closure_mm: float | None = None,
        rotation_id: str | None = None,
        start_year: int | None = None,
    ) -> None:
        self.closure_mm = closure_mm
        self.rotation_id = rotation_id
        self.start_year = start_year
        super().__init__(message)


# --- Errores de infraestructura (NASA POWER) ---


class InfrastructureError(AgroDSSError):
    """Falla de un servicio externo; el usuario puede reintentar."""

    retryable: ClassVar[bool] = True


class PowerError(InfrastructureError):
    """Falla al consultar NASA POWER; no se calcula ningún escenario."""

    category: ClassVar[str] = "nasa_power"


class PowerUnreachableError(PowerError):
    """Sin conexión o sin resolución de nombres hacia NASA POWER."""

    code: ClassVar[str] = "power_unreachable"


class PowerTimeoutError(PowerError):
    """NASA POWER no respondió dentro del tiempo máximo declarado."""

    code: ClassVar[str] = "power_timeout"


class PowerRateLimitedError(PowerError):
    """NASA POWER rechazó la consulta por exceso de pedidos (HTTP 429)."""

    code: ClassVar[str] = "power_rate_limited"


class PowerBadResponseError(PowerError):
    """Estado HTTP de error, formato inesperado, variable ausente o unidades distintas."""

    code: ClassVar[str] = "power_bad_response"
