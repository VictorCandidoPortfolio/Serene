"""Endpoint do Mapa Olfativo (dados estruturados para o frontend desenhar)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DbSession
from app.services.mapa_service import MapaService

router = APIRouter(prefix="/mapa", tags=["mapa"])


class MapaOut(BaseModel):
    """Pontos da usuária (essências, criações) + territórios e caminhos da base."""

    eixos: list[dict[str, Any]]
    essencias: list[dict[str, Any]]
    criacoes: list[dict[str, Any]]
    territorios: list[dict[str, Any]]
    familias: list[dict[str, Any]]
    relacoes: list[dict[str, Any]]
    mapas: list[dict[str, Any]]


def _service(db: DbSession, user: CurrentUser) -> MapaService:
    """Service escopado na usuária autenticada."""
    return MapaService(db, user.id)


@router.get("", response_model=MapaOut)
def mapa(svc: Annotated[MapaService, Depends(_service)]):
    """Tudo o que o Mapa Olfativo precisa posicionar, numa resposta só."""
    return svc.montar()
