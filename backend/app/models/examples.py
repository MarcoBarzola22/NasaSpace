"""Ejemplos de solicitud y respuesta para la documentación OpenAPI (CA-15.6, RNF-13; T048).

Son los ejemplos del plan §5.2 y §5.3, guardados como archivos JSON junto al código. Los números
solo ilustran el formato: no son valores validados ni resultados reales. Una prueba comprueba que
ambos sigan validando contra los modelos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "examples"


def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))


REQUEST_EXAMPLE: dict[str, Any] = _load("simulation_request.json")
RESPONSE_EXAMPLE: dict[str, Any] = _load("simulation_response.json")
