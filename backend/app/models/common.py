"""Base común de los modelos Pydantic del contrato (T033)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Todo campo desconocido es un error 422 (plan §5.2)."""

    model_config = ConfigDict(extra="forbid")
