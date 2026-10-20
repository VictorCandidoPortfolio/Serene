"""Endpoints de criações (o "guarda-chuva" de cada fragrância)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.criacoes import CriacaoCreate, CriacaoOut, CriacaoUpdate
from app.schemas.outros import RecomendacoesOut
from app.schemas.sugestao import OpcoesSugestaoOut, SugestaoIn, SugestaoOut
from app.services.criacoes_service import CriacoesService
from app.services.sugestao_service import SugestaoService

router = APIRouter(prefix="/criacoes", tags=["criacoes"])


def _service(db: DbSession, user: CurrentUser) -> CriacoesService:
    """Service escopado na usuária autenticada."""
    return CriacoesService(db, user.id)


Service = Annotated[CriacoesService, Depends(_service)]


@router.get("", response_model=list[CriacaoOut])
def listar(svc: Service):
    """Criações da usuária."""
    return svc.listar()


@router.get("/sugerir/opcoes", response_model=OpcoesSugestaoOut)
def opcoes_sugestao(db: DbSession, user: CurrentUser):
    """Emoções, preferências, gêneros e faixas de idade do formulário (vêm do banco)."""
    return SugestaoService(db, user.id).opcoes()


@router.post("/sugerir", response_model=SugestaoOut)
def sugerir(payload: SugestaoIn, db: DbSession, user: CurrentUser):
    """Prévia: identidade + acorde sugerido só com o repertório da usuária. Não grava."""
    return SugestaoService(db, user.id).sugerir(payload)


@router.post("", response_model=CriacaoOut, status_code=status.HTTP_201_CREATED)
def criar(payload: CriacaoCreate, svc: Service):
    """Cria uma criação (opcionalmente com a direção de um perfil)."""
    return svc.criar(payload)


@router.get("/{criacao_id}", response_model=CriacaoOut)
def obter(criacao_id: int, svc: Service):
    """Uma criação da usuária."""
    return svc.obter(criacao_id)


@router.get("/{criacao_id}/recomendacoes", response_model=RecomendacoesOut)
def recomendacoes(criacao_id: int, svc: Service):
    """Essências do repertório da usuária mais próximas da direção da criação."""
    return svc.recomendacoes(criacao_id)


@router.put("/{criacao_id}", response_model=CriacaoOut)
def atualizar(criacao_id: int, payload: CriacaoUpdate, svc: Service):
    """Atualiza nome, objetivo, status ou direção (via perfil)."""
    return svc.atualizar(criacao_id, payload)


@router.delete("/{criacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(criacao_id: int, svc: Service):
    """Apaga a criação e todo o seu histórico de versões e testes."""
    svc.apagar(criacao_id)
