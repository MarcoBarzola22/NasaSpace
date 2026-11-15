"""Cliente asíncrono de NASA POWER con httpx (RF-5; T039).

Hace **una sola** consulta por solicitud, sin reintentos (CA-5.1, RNF-12), al endpoint diario de
punto, con las siete variables, la comunidad AG y el estándar de tiempo LST (research.md V-1).
Solo envía coordenadas, fechas y nombres de variables (CA-5.7). No guarda nada en disco ni en
memoria entre solicitudes (CA-5.2): cada consulta abre y cierra su propio cliente HTTP.

Las fallas de red se traducen a los errores de infraestructura de ``core.exceptions``:

| Situación                                         | Excepción                  |
|---------------------------------------------------|----------------------------|
| sin conexión o error de DNS (``ConnectError``)    | ``PowerUnreachableError``  |
| tiempo agotado (conexión, lectura, escritura…)    | ``PowerTimeoutError``      |
| HTTP 429                                          | ``PowerRateLimitedError``  |
| cualquier otro estado distinto de 200             | ``PowerBadResponseError``  |
| otros fallos de transporte (corte a mitad, proxy) | ``PowerBadResponseError``  |

Este módulo devuelve el cuerpo sin interpretar: el análisis del JSON, las unidades y la procedencia
son de ``climate_parser`` (T040).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from app.core.config import POWER_VARIABLES, Settings
from app.core.exceptions import (
    PowerBadResponseError,
    PowerRateLimitedError,
    PowerTimeoutError,
    PowerUnreachableError,
)

DAILY_POINT_PATH = "/api/temporal/daily/point"
# Genérico y sin datos personales (CA-5.7, plan §6.3).
USER_AGENT = "AgroDSS/0.1 (NASA Space Apps)"
HTTP_OK = 200
HTTP_TOO_MANY_REQUESTS = 429


@dataclass(frozen=True, slots=True)
class PowerQuery:
    """Lo único que se envía a NASA POWER: ubicación y rango de fechas."""

    latitude_deg: float
    longitude_deg: float
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("La fecha final de la consulta no puede ser anterior a la inicial.")


@dataclass(frozen=True, slots=True)
class PowerRawResponse:
    """Respuesta de NASA POWER sin interpretar, con el instante de la consulta (UTC)."""

    body: bytes
    requested_at: datetime
    status_code: int


def build_query_params(query: PowerQuery, settings: Settings) -> dict[str, str]:
    """Parámetros exactos de la consulta (plan §6.3)."""
    return {
        "parameters": ",".join(POWER_VARIABLES),
        "community": settings.power_community,
        "latitude": f"{query.latitude_deg:.4f}",
        "longitude": f"{query.longitude_deg:.4f}",
        "start": query.start.strftime("%Y%m%d"),
        "end": query.end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": settings.power_time_standard,
    }


def build_timeout(settings: Settings) -> httpx.Timeout:
    """Timeouts de ``Settings`` (CA-5.6): conexión y lectura configurables."""
    return httpx.Timeout(
        connect=settings.power_connect_timeout_s,
        read=settings.power_read_timeout_s,
        write=settings.power_connect_timeout_s,
        pool=settings.power_connect_timeout_s,
    )


class PowerClient:
    """Consulta en vivo a NASA POWER. ``transport`` permite simularla en las pruebas."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    async def fetch_daily(self, query: PowerQuery) -> PowerRawResponse:
        """Una consulta, sin reintentos. Lanza ``PowerError`` si no se obtiene un 200."""
        settings = self._settings
        requested_at = datetime.now(UTC)
        try:
            async with httpx.AsyncClient(
                base_url=settings.power_base_url,
                timeout=build_timeout(settings),
                headers={"User-Agent": USER_AGENT},
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    DAILY_POINT_PATH, params=build_query_params(query, settings)
                )
        except httpx.TimeoutException as error:
            raise PowerTimeoutError(
                "NASA POWER no respondió a tiempo.", timeout_s=self._timeout_for(error)
            ) from error
        except httpx.NetworkError as error:
            raise PowerUnreachableError("No se pudo conectar con NASA POWER.") from error
        except httpx.TransportError as error:
            raise PowerBadResponseError("La conexión con NASA POWER se interrumpió.") from error

        if response.status_code == HTTP_TOO_MANY_REQUESTS:
            raise PowerRateLimitedError("NASA POWER limitó la frecuencia de consultas (429).")
        if response.status_code != HTTP_OK:
            raise PowerBadResponseError(
                f"NASA POWER respondió con el estado {response.status_code}.",
                status_code=response.status_code,
            )
        return PowerRawResponse(
            body=response.content, requested_at=requested_at, status_code=response.status_code
        )

    def _timeout_for(self, error: httpx.TimeoutException) -> float:
        """Segundos configurados de la fase que venció (lectura por defecto)."""
        if isinstance(error, httpx.ConnectTimeout):
            return self._settings.power_connect_timeout_s
        if isinstance(error, httpx.ReadTimeout):
            return self._settings.power_read_timeout_s
        return self._settings.power_connect_timeout_s
