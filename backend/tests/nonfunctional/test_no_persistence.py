"""Prueba de que el backend no guarda nada en disco durante una simulación (T049).

Cubre RNF-8 y CA-5.2: ni series climáticas, ni solicitudes, ni resultados se escriben en archivos
ni en bases de datos. Durante una simulación completa por la API se bloquean las aperturas de
archivo para escritura (``open``, ``io.open``, ``Path.open`` y ``os.open``) y la creación de bases
SQLite o de archivos temporales; además, el directorio de trabajo queda sin archivos nuevos.
"""

from __future__ import annotations

import builtins
import io
import os
import sqlite3
import tempfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.api.conftest import make_client
from tests.builders.requests import plan_request
from tests.builders.simulation import Power

WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
RAIN_GAP = {"PRECTOTCORR": [date(2018, 3, 4)], "ALLSKY_SFC_SW_DWN": [date(2009, 1, 17)]}


class WriteAttempt(AssertionError):
    """Se intentó escribir en disco."""


def is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in "wax+")


@pytest.fixture
def forbid_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[list[str]]:
    """Bloquea toda escritura a disco y registra los intentos."""
    attempts: list[str] = []
    real_open = builtins.open
    real_os_open = os.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if is_write_mode(mode):
            attempts.append(f"open({file!r}, {mode!r})")
            raise WriteAttempt(f"escritura bloqueada: {file!r}")
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if flags & WRITE_FLAGS:
            attempts.append(f"os.open({path!r})")
            raise WriteAttempt(f"escritura bloqueada: {path!r}")
        return real_os_open(path, flags, *args, **kwargs)

    def refuse(name: str) -> Any:
        def blocked(*args: Any, **kwargs: Any) -> Any:
            attempts.append(name)
            raise WriteAttempt(f"{name} bloqueado")

        return blocked

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    monkeypatch.setattr(sqlite3, "connect", refuse("sqlite3.connect"))
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", refuse("NamedTemporaryFile"))
    monkeypatch.setattr(tempfile, "TemporaryFile", refuse("TemporaryFile"))
    monkeypatch.setattr(tempfile, "mkstemp", refuse("mkstemp"))
    monkeypatch.chdir(tmp_path)
    yield attempts


def listing(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*")}


def test_a_full_simulation_writes_nothing_to_disk(forbid_writes: list[str], tmp_path: Path) -> None:
    client, server = make_client(Power(fill_dates=RAIN_GAP))
    before = listing(tmp_path)
    response = client.post("/api/v1/simulations", json=plan_request())
    assert response.status_code == 200 and len(response.json()["results"]) == 4
    assert len(server.requests) == 1
    assert forbid_writes == []
    assert listing(tmp_path) == before == set()


def test_failed_and_invalid_requests_write_nothing_either(
    forbid_writes: list[str], tmp_path: Path
) -> None:
    client, _ = make_client(Power(drop_parameter="WS2M_MAX"))
    assert client.post("/api/v1/simulations", json=plan_request()).status_code == 502
    invalid = plan_request()
    invalid["parcel"]["latitude_deg"] = 75
    assert client.post("/api/v1/simulations", json=invalid).status_code == 422
    assert client.get("/api/v1/catalog").status_code == 200
    assert forbid_writes == []
    assert listing(tmp_path) == set()


def test_the_guard_actually_detects_a_write(forbid_writes: list[str], tmp_path: Path) -> None:
    """Control de la propia prueba: si alguien escribiera, el guardia lo vería."""
    with pytest.raises(WriteAttempt):
        (tmp_path / "serie.json").write_text("{}")
    with pytest.raises(WriteAttempt):
        open(tmp_path / "otra.txt", "w")  # noqa: SIM115
    with pytest.raises(WriteAttempt):
        os.open(tmp_path / "tercera.txt", os.O_WRONLY | os.O_CREAT)
    with pytest.raises(WriteAttempt):
        sqlite3.connect(":memory:")
    assert len(forbid_writes) == 4


def test_reading_files_is_still_allowed(forbid_writes: list[str], tmp_path: Path) -> None:
    """El catálogo y los ejemplos son archivos de solo lectura versionados con el código."""
    assert Path(__file__).read_text(encoding="utf-8")
    assert forbid_writes == []


def test_the_application_code_has_no_write_calls() -> None:
    """Revisión estática de ``app/``: ninguna llamada de escritura, base de datos o caché."""
    import ast

    root = Path(__file__).resolve().parents[2] / "app"
    suspicious = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "dump", "connect"}
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                names = [alias.name for alias in node.names] + [getattr(node, "module", "") or ""]
                if any(
                    name.split(".")[0] in {"sqlite3", "shelve", "pickle", "dbm"} for name in names
                ):
                    offenders.append(f"{path.name}: importa {names}")
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Attribute) and function.attr in suspicious:
                    offenders.append(f"{path.name}:{node.lineno} {function.attr}")
                if isinstance(function, ast.Name) and function.id == "open":
                    mode = node.args[1] if len(node.args) > 1 else None
                    if mode is not None:
                        offenders.append(f"{path.name}:{node.lineno} open con modo")
    assert offenders == []
