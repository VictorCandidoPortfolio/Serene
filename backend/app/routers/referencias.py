"""Endpoints de fragrâncias de referência (bússola, nunca estoque)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.outros import CaminhosReferenciaOut, ReferenciaCreate, ReferenciaOut, ReferenciaUpdate
from app.services.outros_service import ReferenciasService

router = APIRouter(prefix="/referencias", tags=["referencias"])


def _service(db: DbSession, user: CurrentUser) -> ReferenciasService:
    """Service escopado na usuária autenticada."""
    return ReferenciasService(db, user.id)


Service = Annotated[ReferenciasService, Depends(_service)]


@router.get("", response_model=list[ReferenciaOut])
def listar(svc: Service):
    """Referências da usuária."""
    return svc.listar()


@router.post("", response_model=ReferenciaOut, status_code=status.HTTP_201_CREATED)
def criar(payload: ReferenciaCreate, svc: Service):
    """Cadastra uma referência."""
    return svc.criar(payload)


@router.get("/{referencia_id}", response_model=ReferenciaOut)
def obter(referencia_id: int, svc: Service):
    """Uma referência."""
    return svc.obter(referencia_id)


@router.get("/{referencia_id}/caminhos", response_model=CaminhosReferenciaOut)
def caminhos(referencia_id: int, svc: Service):
    """Direção estimada da referência, famílias que a aluna tem/não tem e essências dela na mesma direção."""
    return svc.caminhos(referencia_id)


@router.put("/{referencia_id}", response_model=ReferenciaOut)
def atualizar(referencia_id: int, payload: ReferenciaUpdate, svc: Service):
    """Edição parcial."""
    return svc.atualizar(referencia_id, payload)


@router.delete("/{referencia_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(referencia_id: int, svc: Service):
    """Remove a referência."""
    svc.apagar(referencia_id)
