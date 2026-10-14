"""Endpoints de testes/avaliações de uma criação (versionados, sem PUT/DELETE)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.criacoes import TesteCreate, TesteOut
from app.services.criacoes_service import TestesService

router = APIRouter(prefix="/criacoes/{criacao_id}/testes", tags=["testes"])


def _service(db: DbSession, user: CurrentUser) -> TestesService:
    """Service escopado na usuária autenticada."""
    return TestesService(db, user.id)


Service = Annotated[TestesService, Depends(_service)]


@router.get("", response_model=list[TesteOut])
def listar(criacao_id: int, svc: Service):
    """Histórico de testes da criação."""
    return svc.listar(criacao_id)


@router.post("", response_model=TesteOut, status_code=status.HTTP_201_CREATED)
def criar(criacao_id: int, payload: TesteCreate, svc: Service):
    """Registra um novo teste (nova versão)."""
    return svc.criar(criacao_id, payload)


@router.get("/{teste_id}", response_model=TesteOut)
def obter(criacao_id: int, teste_id: int, svc: Service):
    """Um teste específico."""
    return svc.obter(criacao_id, teste_id)
