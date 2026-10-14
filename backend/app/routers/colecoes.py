"""Endpoints de coleções e dos vínculos coleção ↔ criação."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.outros import (
    ColecaoCreate,
    ColecaoItemIn,
    ColecaoOrdemIn,
    ColecaoOut,
    ColecaoUpdate,
)
from app.services.outros_service import ColecoesService

router = APIRouter(prefix="/colecoes", tags=["colecoes"])


def _service(db: DbSession, user: CurrentUser) -> ColecoesService:
    """Service escopado na usuária autenticada."""
    return ColecoesService(db, user.id)


Service = Annotated[ColecoesService, Depends(_service)]


@router.get("", response_model=list[ColecaoOut])
def listar(svc: Service):
    """Coleções da usuária com seus itens."""
    return [svc.saida(c) for c in svc.listar()]


@router.post("", response_model=ColecaoOut, status_code=status.HTTP_201_CREATED)
def criar(payload: ColecaoCreate, svc: Service):
    """Cria uma coleção vazia."""
    return svc.saida(svc.criar(payload))


@router.get("/{colecao_id}", response_model=ColecaoOut)
def obter(colecao_id: int, svc: Service):
    """Uma coleção."""
    return svc.saida(svc.obter(colecao_id))


@router.put("/{colecao_id}", response_model=ColecaoOut)
def atualizar(colecao_id: int, payload: ColecaoUpdate, svc: Service):
    """Edita nome/descrição."""
    return svc.saida(svc.atualizar(colecao_id, payload))


@router.delete("/{colecao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(colecao_id: int, svc: Service):
    """Apaga a coleção (as criações continuam existindo)."""
    svc.apagar(colecao_id)


@router.post("/{colecao_id}/criacoes", response_model=ColecaoOut, status_code=status.HTTP_201_CREATED)
def adicionar(colecao_id: int, payload: ColecaoItemIn, svc: Service):
    """Adiciona uma criação aprovada à coleção."""
    return svc.saida(svc.adicionar(colecao_id, payload))


@router.delete("/{colecao_id}/criacoes/{criacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(colecao_id: int, criacao_id: int, svc: Service):
    """Tira a criação da coleção."""
    svc.remover(colecao_id, criacao_id)


@router.put("/{colecao_id}/ordem", response_model=ColecaoOut)
def reordenar(colecao_id: int, payload: ColecaoOrdemIn, svc: Service):
    """Redefine a ordem das criações na coleção."""
    return svc.saida(svc.reordenar(colecao_id, payload.criacao_ids))
