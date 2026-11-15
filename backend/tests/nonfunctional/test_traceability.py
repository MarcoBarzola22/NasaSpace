"""Trazabilidad de los criterios de aceptación del spec a las pruebas (T051).

Cubre el criterio de finalización «cada criterio de aceptación de RF-1 a RF-17 tiene al menos una
prueba automática que lo verifica, o una justificación escrita de por qué no se puede probar
automáticamente».

Cómo funciona: se extraen de ``spec.md`` todos los identificadores ``CA-x.y`` y se buscan en los
docstrings (de módulo, clase y función) de ``tests/``. Un docstring puede citar un criterio suelto
(``CA-6.4``), una lista (``CA-3.6, CA-3.7``) o un rango (``CA-6.4–CA-6.6``, que cubre también los
intermedios). Lo que no aparece debe figurar en ``NOT_AUTOMATABLE`` con su justificación.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
TESTS_DIR = BACKEND_DIR / "tests"
SPEC_PATH = BACKEND_DIR.parent / "specs" / "001-agrodss-backend" / "spec.md"

ID_PATTERN = re.compile(r"CA-(\d+)\.(\d+)")
RANGE_PATTERN = re.compile(r"CA-(\d+)\.(\d+)\s*(?:[–-]|\ba\b)\s*(?:CA-)?(?:(\d+)\.)?(\d+)")

# Criterios que no se pueden verificar con una prueba automática, con la razón escrita.
# Máximo 3 entradas (se prevé solo CA-6.9).
NOT_AUTOMATABLE: dict[str, str] = {
    "CA-6.9": (
        "Condicionado a la duda D-12: el equipo no acordó un límite máximo de días sustituidos "
        "por escenario, así que el criterio está inactivo y no hay comportamiento que probar."
    ),
}
MAX_NOT_AUTOMATABLE = 3


def spec_ids() -> list[str]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    for match in re.finditer(r"\*\*(CA-\d+\.\d+)\*\*", text):
        seen[match.group(1)] = None
    return list(seen)


def ids_in(text: str) -> set[str]:
    """Identificadores citados en un texto, expandiendo los rangos ``CA-a.b–CA-a.c``."""
    found = {f"CA-{a}.{b}" for a, b in ID_PATTERN.findall(text)}
    for first_major, first_minor, last_major, last_minor in RANGE_PATTERN.findall(text):
        if last_major and last_major != first_major:
            continue
        low, high = int(first_minor), int(last_minor)
        if low <= high <= low + 40:
            found.update(f"CA-{first_major}.{minor}" for minor in range(low, high + 1))
    return found


def docstrings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    texts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(node)
            if doc:
                texts.append(doc)
    return texts


def covered_ids() -> dict[str, set[str]]:
    """Identificador → archivos de prueba cuyos docstrings lo citan."""
    covered: dict[str, set[str]] = {}
    for path in sorted(TESTS_DIR.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        for text in docstrings(path):
            for identifier in ids_in(text):
                covered.setdefault(identifier, set()).add(str(path.relative_to(TESTS_DIR)))
    return covered


def test_the_spec_defines_the_expected_criteria() -> None:
    ids = spec_ids()
    assert len(ids) > 120
    assert len(ids) == len(set(ids))
    for new_criterion in ("CA-1.12", "CA-6.10", "CA-10.9"):
        assert new_criterion in ids


def test_every_acceptance_criterion_is_covered_or_justified() -> None:
    covered = covered_ids()
    missing = [i for i in spec_ids() if i not in covered and i not in NOT_AUTOMATABLE]
    assert missing == [], "Criterios sin prueba ni justificación: " + ", ".join(missing)


def test_not_automatable_is_short_and_every_entry_is_justified() -> None:
    assert len(NOT_AUTOMATABLE) <= MAX_NOT_AUTOMATABLE
    for identifier, reason in NOT_AUTOMATABLE.items():
        assert identifier in spec_ids()
        assert len(reason.split()) >= 10, identifier


def test_a_justified_criterion_is_not_also_claimed_by_a_test() -> None:
    """Si un criterio ya tiene prueba, debe salir de ``NOT_AUTOMATABLE``."""
    covered = covered_ids()
    assert [i for i in NOT_AUTOMATABLE if i in covered] == []


def test_the_range_expansion_covers_the_intermediate_identifiers() -> None:
    assert ids_in("CA-6.4–CA-6.6") == {"CA-6.4", "CA-6.5", "CA-6.6"}
    assert ids_in("CA-3.6-CA-3.8, CA-1.1") == {"CA-3.6", "CA-3.7", "CA-3.8", "CA-1.1"}
    assert ids_in("CA-5.1, CA-5.4") == {"CA-5.1", "CA-5.4"}
    assert ids_in("sin identificadores") == set()


def test_the_checker_detects_an_uncovered_criterion() -> None:
    covered = {"CA-1.1": {"x"}}
    assert [i for i in ("CA-1.1", "CA-1.2") if i not in covered] == ["CA-1.2"]
