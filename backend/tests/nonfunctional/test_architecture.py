"""Regla de arquitectura del dominio (T009; plan §3 y decisión T-5; RNF-7).

``app/domain`` debe ser Python puro: sin FastAPI, Pydantic ni httpx, sin acceso a la red ni al
sistema de archivos, y sin depender de ``routers``, ``services``, ``models`` ni de la
configuración. Solo puede importar la biblioteca estándar (salvo los módulos de E/S de la lista
negra), ``app.domain.*``, ``app.core.constants`` y ``app.core.exceptions``.

Criterios que respaldan: RNF-7 (separación lógica/interfaz) y RNF-8 (sin persistencia).
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
DOMAIN_DIR = BACKEND_DIR / "app" / "domain"

ALLOWED_APP_MODULES = frozenset({"app.core.constants", "app.core.exceptions"})

# Módulos de la biblioteca estándar que dan acceso a la red, al sistema de archivos o a procesos.
FORBIDDEN_STDLIB = frozenset(
    {
        "os",
        "pathlib",
        "io",
        "builtins",
        "shutil",
        "tempfile",
        "glob",
        "fileinput",
        "socket",
        "ssl",
        "select",
        "selectors",
        "asyncio",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "xmlrpc",
        "socketserver",
        "subprocess",
        "multiprocessing",
        "sqlite3",
        "dbm",
        "shelve",
        "pickle",
        "marshal",
        "zipfile",
        "tarfile",
        "gzip",
        "bz2",
        "lzma",
        "ctypes",
        "webbrowser",
        "importlib",
    }
)
FORBIDDEN_CALLS = frozenset({"open", "__import__", "exec", "eval", "compile", "input"})


def _app_module_allowed(name: str) -> bool:
    return name == "app.domain" or name.startswith("app.domain.") or name in ALLOWED_APP_MODULES


def _check_module(name: str) -> str | None:
    root = name.split(".")[0]
    if root == "app":
        return None if _app_module_allowed(name) else f"importa «{name}», fuera de lo permitido"
    if root in sys.stdlib_module_names:
        return f"importa «{name}» (E/S o red)" if root in FORBIDDEN_STDLIB else None
    return f"importa «{name}» (dependencia que no es de la biblioteca estándar)"


def find_violations(source: str) -> list[str]:
    """Devuelve las violaciones de la regla de arquitectura en un fragmento de código."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                problem = _check_module(alias.name)
                if problem:
                    problems.append(f"línea {node.lineno}: {problem}")
        elif isinstance(node, ast.ImportFrom):
            problems.extend(_check_import_from(node))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        ):
            problems.append(f"línea {node.lineno}: llama a «{node.func.id}()»")
    return problems


def _check_import_from(node: ast.ImportFrom) -> list[str]:
    if node.level > 1:
        return [f"línea {node.lineno}: import relativo que sale de app.domain"]
    if node.level == 1:
        return []  # relativo dentro del propio paquete app.domain
    module = node.module or ""
    problem = _check_module(module)
    if problem is None:
        return []
    root = module.split(".")[0]
    if root == "app":
        # «from app.core import constants»: se evalúa cada nombre importado como submódulo.
        names = [f"{module}.{alias.name}" for alias in node.names]
        if all(_app_module_allowed(name) for name in names):
            return []
    return [f"línea {node.lineno}: {problem}"]


def test_domain_imports_allowed_only() -> None:
    files = sorted(DOMAIN_DIR.rglob("*.py"))
    assert DOMAIN_DIR / "types.py" in files
    for path in files:
        violations = find_violations(path.read_text(encoding="utf-8"))
        assert not violations, f"{path.relative_to(BACKEND_DIR)}: {violations}"


@pytest.mark.parametrize(
    "snippet",
    [
        "import fastapi",
        "from fastapi import FastAPI",
        "import httpx",
        "from pydantic import BaseModel",
        "import requests",
        "import socket",
        "import urllib.request",
        "from http import client",
        "from pathlib import Path",
        "import os",
        "import builtins",
        "import subprocess",
        "open('datos.csv')",
        "eval('1 + 1')",
        "from app.services.catalog_service import load_catalog",
        "from app.core.config import Settings",
        "from app.core import config",
        "from app.routers import health",
        "from ..core import constants",
    ],
)
def test_checker_rejects_forbidden_import(snippet: str) -> None:
    assert find_violations(snippet), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "from __future__ import annotations",
        "import math",
        "import statistics",
        "from datetime import date",
        "from dataclasses import dataclass",
        "from typing import Final",
        "from app.core.constants import ALBEDO",
        "from app.core import constants",
        "from app.core.exceptions import CalculationIntegrityError",
        "from app.domain.types import Stages",
        "from . import types",
        "from .types import Stages",
    ],
)
def test_checker_accepts_allowed_imports(snippet: str) -> None:
    assert find_violations(snippet) == [], snippet


def test_domain_imports_without_web_libraries() -> None:
    """Con fastapi, httpx y pydantic bloqueados, todo ``app.domain`` se importa igual."""
    code = textwrap.dedent(
        """
        import importlib, pkgutil, sys
        for name in ("fastapi", "starlette", "httpx", "pydantic", "uvicorn"):
            sys.modules[name] = None
        import app.domain
        for module in pkgutil.iter_modules(app.domain.__path__):
            importlib.import_module(f"app.domain.{module.name}")
        print("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
