"""Endpoints de perfis olfativos e recomendações do repertório."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.outros import PerfilCreate, PerfilOut, RecomendacoesOut
from app.services.perfis_service import PerfisService

router = APIRouter(prefix="/perfis", tags=["perfis"])


def _service(db: DbSession, user: CurrentUser) -> PerfisService:
    """Service escopado na usuária autenticada."""
    return PerfisService(db, user.id)


Service = Annotated[PerfisService, Depends(_service)]


@router.get("", response_model=list[PerfilOut])
def listar(svc: Service):
    """Perfis da usuária."""
    return svc.listar()


@router.post("", response_model=PerfilOut, status_code=status.HTTP_201_CREATED)
def criar(payload: PerfilCreate, svc: Service):
    """Grava o questionário e calcula o vetor-alvo."""
    return svc.criar(payload)


@router.get("/{perfil_id}", response_model=PerfilOut)
def obter(perfil_id: int, svc: Service):
    """Um perfil."""
    return svc.obter(perfil_id)


@router.put("/{perfil_id}", response_model=PerfilOut)
def atualizar(perfil_id: int, payload: PerfilCreate, svc: Service):
    """Substitui as respostas e recalcula o alvo."""
    return svc.atualizar(perfil_id, payload)


@router.delete("/{perfil_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(perfil_id: int, svc: Service):
    """Remove o perfil."""
    svc.apagar(perfil_id)


@router.get("/{perfil_id}/recomendacoes", response_model=RecomendacoesOut)
def recomendacoes(perfil_id: int, svc: Service):
    """Essências DO REPERTÓRIO da usuária ordenadas pela proximidade com o alvo."""
    return svc.recomendacoes(perfil_id)
