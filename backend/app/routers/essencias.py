"""Endpoints do repertório de essências (recurso de referência do projeto).

Padrão de todos os routers pessoais: a dependency `_service` recebe a
usuária de `get_current_user` e constrói o service já escopado nela. O router
nunca lê `user_id` de lugar nenhum além disso.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.common import LacunaOut
from app.schemas.essencias import (
    CompatibilidadeIn,
    CompatibilidadeOut,
    EssenciaCreate,
    EssenciaCriadaOut,
    EssenciaOut,
    EssenciaUpdate,
    FichaIn,
    OpcoesCadastroOut,
    SugestaoNomeOut,
    SugestaoReferencia,
)
from app.services.essencias_service import EssenciasService

router = APIRouter(prefix="/essencias", tags=["essencias"])


def _service(db: DbSession, user: CurrentUser) -> EssenciasService:
    """Service escopado na usuária autenticada."""
    return EssenciasService(db, user.id)


Service = Annotated[EssenciasService, Depends(_service)]


@router.get("", response_model=list[EssenciaOut])
def listar(svc: Service):
    """Essências da usuária (vazio para conta nova)."""
    return svc.listar()


@router.post("", response_model=EssenciaCriadaOut, status_code=status.HTTP_201_CREATED)
def criar(payload: EssenciaCreate, svc: Service):
    """Cadastra uma essência. Devolve sugestões de referência quando não vinculada."""
    return svc.criar(payload)


# Rotas fixas ANTES de "/{essencia_id}" para não serem capturadas por ela.
@router.get("/sugestao-classificacao", response_model=list[SugestaoReferencia])
def sugestao_classificacao(svc: Service, nome: Annotated[str, Query(min_length=1, max_length=160)]):
    """Notas de conhecimento que podem corresponder ao nome (nada é gravado)."""
    return svc.sugerir_classificacao(nome)


@router.get("/opcoes", response_model=OpcoesCadastroOut)
def opcoes(svc: Service):
    """Chips do cadastro: os 8 grupos de cheiro (do banco) e as 3 percepções."""
    return svc.opcoes_cadastro()


@router.get("/sugestao", response_model=SugestaoNomeOut)
def sugestao(svc: Service, nome: Annotated[str, Query(min_length=1, max_length=160)]):
    """Reconhece o nome na base e SUGERE família e percepção (nada é gravado)."""
    return svc.sugerir_por_nome(nome)


@router.post("/compatibilidade", response_model=CompatibilidadeOut)
def compatibilidade(payload: CompatibilidadeIn, svc: Service):
    """Analisa como 2 a 20 essências do repertório trabalham juntas (nada é gravado)."""
    return svc.compatibilidade(payload.essencia_ids)


@router.get("/lacunas", response_model=list[LacunaOut])
def lacunas(svc: Service):
    """O que falta no repertório (famílias, estrutura, amplitude)."""
    return [LacunaOut.model_validate(lac.__dict__) for lac in svc.lacunas()]


@router.get("/{essencia_id}", response_model=EssenciaOut)
def obter(essencia_id: int, svc: Service):
    """Uma essência da usuária (404 se não existir ou for de outra)."""
    return svc.obter(essencia_id)


@router.put("/{essencia_id}", response_model=EssenciaOut)
def atualizar(essencia_id: int, payload: EssenciaUpdate, svc: Service):
    """Atualiza os campos enviados (os omitidos ficam como estão)."""
    return svc.atualizar(essencia_id, payload)


@router.put("/{essencia_id}/ficha", response_model=EssenciaOut)
def definir_ficha(essencia_id: int, payload: FichaIn | None, svc: Service):
    """Grava a ficha técnica documentada (limites de uso, restrições...). Corpo vazio/nulo limpa."""
    return svc.definir_ficha(essencia_id, payload.model_dump(exclude_none=True) if payload else None)


@router.delete("/{essencia_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(essencia_id: int, svc: Service):
    """Remove a essência do repertório."""
    svc.apagar(essencia_id)
