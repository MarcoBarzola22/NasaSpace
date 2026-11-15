"""Pruebas del cliente de NASA POWER con ``httpx.MockTransport`` (T039).

Ninguna prueba toca la red. Cubren CA-5.1 (una consulta), CA-5.4 (fallas con su error),
CA-5.6 (timeouts de ``Settings``), CA-5.7 (solo coordenadas, fechas y variables), RNF-11 y RNF-12.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date
from urllib.parse import parse_qs

import httpx
import pytest

from app.core.config import POWER_VARIABLES, Settings
from app.core.dependencies import get_power_client
from app.core.exceptions import (
    PowerBadResponseError,
    PowerError,
    PowerRateLimitedError,
    PowerTimeoutError,
    PowerUnreachableError,
)
from app.services.power_client import (
    DAILY_POINT_PATH,
    USER_AGENT,
    PowerClient,
    PowerQuery,
    build_query_params,
)
from tests.builders.power_payload import power_payload

QUERY = PowerQuery(
    latitude_deg=-33.68, longitude_deg=-65.47, start=date(2008, 7, 1), end=date(2010, 6, 30)
)


class Recorder:
    """Transporte simulado que registra cada pedido y responde con ``respond``."""

    def __init__(self, respond: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []
        self._respond = respond

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._respond(request)


def ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=power_payload(date(2008, 7, 1), date(2008, 7, 5)))


def fetch(recorder: Recorder, settings: Settings | None = None):
    client = PowerClient(settings or Settings(), transport=httpx.MockTransport(recorder))
    return asyncio.run(client.fetch_daily(QUERY))


def raising(error: Exception) -> Callable[[httpx.Request], httpx.Response]:
    def respond(request: httpx.Request) -> httpx.Response:
        raise error

    return respond


def test_query_has_exactly_the_documented_parameters() -> None:
    """CA-5.1, CA-5.7: solo parámetros, comunidad, coordenadas, fechas, formato y estándar."""
    recorder = Recorder(ok_response)
    fetch(recorder)
    request = recorder.requests[0]
    assert request.method == "GET"
    assert request.url.host == "power.larc.nasa.gov"
    assert request.url.path == DAILY_POINT_PATH == "/api/temporal/daily/point"
    params = {key: values[0] for key, values in parse_qs(request.url.query.decode()).items()}
    assert params == {
        "parameters": "PRECTOTCORR,T2M_MAX,T2M_MIN,T2MDEW,WS2M,WS2M_MAX,ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "latitude": "-33.6800",
        "longitude": "-65.4700",
        "start": "20080701",
        "end": "20100630",
        "format": "JSON",
        "time-standard": "LST",
    }
    assert params["parameters"].split(",") == list(POWER_VARIABLES)


def test_query_params_use_settings_for_community_and_time_standard() -> None:
    custom = Settings(power_community="RE", power_time_standard="UTC")
    params = build_query_params(QUERY, custom)
    assert (params["community"], params["time-standard"]) == ("RE", "UTC")


def test_base_url_comes_from_settings() -> None:
    recorder = Recorder(ok_response)
    fetch(recorder, Settings(power_base_url="http://power.test"))
    assert str(recorder.requests[0].url).startswith("http://power.test/api/temporal/daily/point?")


def test_user_agent_is_generic_without_personal_data() -> None:
    """CA-5.7: el User-Agent no contiene correo ni nombre de usuario."""
    recorder = Recorder(ok_response)
    fetch(recorder)
    agent = recorder.requests[0].headers["user-agent"]
    assert agent == USER_AGENT == "AgroDSS/0.1 (NASA Space Apps)"
    assert "@" not in agent
    for personal in ("mauro", "aguilar", "gmail"):
        assert personal not in agent.lower()


def test_only_the_user_agent_and_standard_headers_are_sent() -> None:
    recorder = Recorder(ok_response)
    fetch(recorder)
    names = {name.lower() for name in recorder.requests[0].headers}
    assert not names & {"authorization", "cookie", "x-api-key", "referer", "from"}


@pytest.mark.parametrize(
    "respond",
    [
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(429),
        raising(httpx.ConnectError("sin red")),
        raising(httpx.ReadTimeout("lento")),
    ],
    ids=["500", "429", "connect-error", "read-timeout"],
)
def test_one_single_call_without_retries_even_when_it_fails(respond) -> None:
    """CA-5.1, RNF-12: una consulta por solicitud; el usuario es quien reintenta."""
    recorder = Recorder(respond)
    with pytest.raises(PowerError):
        fetch(recorder)
    assert len(recorder.requests) == 1


def test_success_returns_the_raw_body_and_the_query_instant_in_utc() -> None:
    recorder = Recorder(ok_response)
    result = fetch(recorder)
    assert result.status_code == 200
    assert result.requested_at.tzinfo is UTC
    body = json.loads(result.body)
    assert set(body["properties"]["parameter"]) == set(POWER_VARIABLES)


def test_connect_error_is_unreachable() -> None:
    with pytest.raises(PowerUnreachableError) as caught:
        fetch(Recorder(raising(httpx.ConnectError("dns"))))
    assert caught.value.retryable is True
    assert caught.value.category == "nasa_power"


def test_network_read_error_is_unreachable() -> None:
    with pytest.raises(PowerUnreachableError):
        fetch(Recorder(raising(httpx.ReadError("conexión cortada"))))


def test_read_timeout_is_a_timeout_error_with_the_configured_read_seconds() -> None:
    settings = Settings(power_connect_timeout_s=7.0, power_read_timeout_s=45.0)
    with pytest.raises(PowerTimeoutError) as caught:
        fetch(Recorder(raising(httpx.ReadTimeout("lento"))), settings)
    assert caught.value.timeout_s == 45.0
    assert caught.value.code == "power_timeout"


def test_connect_timeout_is_a_timeout_error_with_the_configured_connect_seconds() -> None:
    settings = Settings(power_connect_timeout_s=7.0, power_read_timeout_s=45.0)
    with pytest.raises(PowerTimeoutError) as caught:
        fetch(Recorder(raising(httpx.ConnectTimeout("sin respuesta"))), settings)
    assert caught.value.timeout_s == 7.0


def test_status_429_is_rate_limited() -> None:
    with pytest.raises(PowerRateLimitedError) as caught:
        fetch(Recorder(lambda request: httpx.Response(429)))
    assert caught.value.code == "power_rate_limited"
    assert caught.value.retryable is True


@pytest.mark.parametrize("status", [500, 502, 503, 404, 422, 301])
def test_other_non_200_statuses_are_bad_responses_with_the_code(status: int) -> None:
    with pytest.raises(PowerBadResponseError) as caught:
        fetch(Recorder(lambda request: httpx.Response(status)))
    assert caught.value.status_code == status
    assert caught.value.code == "power_bad_response"


def test_other_transport_failures_are_bad_responses() -> None:
    with pytest.raises(PowerBadResponseError) as caught:
        fetch(Recorder(raising(httpx.RemoteProtocolError("corte a mitad de respuesta"))))
    assert caught.value.status_code is None


def test_timeouts_used_are_the_ones_in_settings() -> None:
    """CA-5.6: conexión y lectura salen de ``Settings`` (10 s y 60 s por defecto)."""
    seen: list[dict[str, float | None]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.extensions["timeout"]))
        return ok_response(request)

    fetch(Recorder(respond))
    assert seen[0]["connect"] == 10.0
    assert seen[0]["read"] == 60.0

    seen.clear()
    fetch(Recorder(respond), Settings(power_connect_timeout_s=3.0, power_read_timeout_s=20.0))
    assert seen[0]["connect"] == 3.0
    assert seen[0]["read"] == 20.0


def test_redirects_are_not_followed() -> None:
    recorder = Recorder(lambda request: httpx.Response(302, headers={"location": "http://x.test"}))
    with pytest.raises(PowerBadResponseError) as caught:
        fetch(recorder)
    assert caught.value.status_code == 302
    assert len(recorder.requests) == 1


def test_query_with_end_before_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        PowerQuery(-33.68, -65.47, date(2010, 1, 2), date(2010, 1, 1))


def test_dependency_builds_a_client_with_the_given_settings() -> None:
    client = get_power_client(Settings())
    assert isinstance(client, PowerClient)
