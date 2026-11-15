"""``GET /api/v1/catalog``: cultivos, valores de referencia FAO y reglas del modelo (T032)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_catalog
from app.models.catalog import CatalogResponse
from app.services.catalog_response import build_catalog_response
from app.services.catalog_service import Catalog

router = APIRouter(tags=["catálogo"])


@router.get(
    "/catalog",
    response_model=CatalogResponse,
    summary="Catálogo de cultivos y reglas del modelo",
)
def read_catalog(catalog: Catalog = Depends(get_catalog)) -> CatalogResponse:  # noqa: B008
    return build_catalog_response(catalog)
