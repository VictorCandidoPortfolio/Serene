"""Endpoints de acordes (versões) de uma criação + motor de ajuste.

Sem PUT/DELETE de propósito: versionar, nunca sobrescrever (regra 6).
Para "editar" um acorde, crie a próxima versão.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.criacoes import AcordeCreate, AcordeOut, AjusteIn, AjusteOut, IdentidadeOut
from app.services.criacoes_service import AcordesService

router = APIRouter(prefix="/criacoes/{criacao_id}/acordes", tags=["acordes"])


def _service(db: DbSession, user: CurrentUser) -> AcordesService:
    """Service escopado na usuária autenticada."""
    return AcordesService(db, user.id)


Service = Annotated[AcordesService, Depends(_service)]


@router.get("", response_model=list[AcordeOut])
def listar(criacao_id: int, svc: Service):
    """Histórico de versões da criação."""
    return svc.listar(criacao_id)


@router.post("", response_model=AcordeOut, status_code=status.HTTP_201_CREATED)
def criar(criacao_id: int, payload: AcordeCreate, svc: Service):
    """Nova versão: calcula vetor, papel, família resultante e compatibilidade."""
    return svc.criar(criacao_id, payload)


@router.get("/{acorde_id}", response_model=AcordeOut)
def obter(criacao_id: int, acorde_id: int, svc: Service):
    """Uma versão específica."""
    return svc.obter(criacao_id, acorde_id)


@router.get("/{acorde_id}/identidade", response_model=IdentidadeOut)
def identidade(criacao_id: int, acorde_id: int, svc: Service):
    """Territórios que esta versão do acorde transmite (o perfil "ao contrário")."""
    return svc.identidade(criacao_id, acorde_id)


@router.post("/{acorde_id}/ajuste", response_model=AjusteOut)
def ajustar(criacao_id: int, acorde_id: int, payload: AjusteIn, svc: Service):
    """Sugere ajustes ("mais_fresco", "mais_doce"...) só com o repertório da usuária.

    Não grava nada. Quando o movimento não é alcançável, devolve a lacuna
    (a categoria que falta), nunca uma essência que ela não possui.
    """
    return svc.ajustar(criacao_id, acorde_id, payload.movimento)
