"""Endpoints SOMENTE LEITURA da base de conhecimento compartilhada.

Só existem GETs neste router — e o repositório por trás não tem método de
escrita. Qualquer POST/PUT/DELETE aqui responde 405 (testado em
`tests/test_isolamento.py`). A base é alimentada pelo seed.

Exige autenticação como o resto da API (é conteúdo do curso), mas a
resposta é a mesma para todas as usuárias.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, get_current_user
from app.models.knowledge import TIPOS_REGRA
from app.schemas.conhecimento import (
    DescritorOut,
    FamiliaOut,
    FuncaoOut,
    MapaOut,
    NotaOut,
    RegraOut,
    RelacaoOut,
)
from app.services.outros_service import ConhecimentoService

router = APIRouter(
    prefix="/conhecimento", tags=["conhecimento"], dependencies=[Depends(get_current_user)]
)


def _service(db: DbSession) -> ConhecimentoService:
    """Service de leitura (o conhecimento não tem dona)."""
    return ConhecimentoService(db)


Service = Annotated[ConhecimentoService, Depends(_service)]


@router.get("/familias", response_model=list[FamiliaOut])
def familias(svc: Service):
    """Famílias e subfamílias olfativas."""
    return svc.familias()


@router.get("/descritores", response_model=list[DescritorOut])
def descritores(svc: Service):
    """Vocabulário de descritores."""
    return svc.descritores()


@router.get("/funcoes", response_model=list[FuncaoOut])
def funcoes(svc: Service):
    """Funções da pirâmide (saída/coração/fundo)."""
    return svc.funcoes()


@router.get("/notas", response_model=list[NotaOut])
def notas(svc: Service):
    """Notas de referência (conhecimento — não são essências de ninguém)."""
    return svc.notas()


@router.get("/relacoes", response_model=list[RelacaoOut])
def relacoes(svc: Service):
    """Relações entre famílias."""
    return svc.relacoes()


@router.get("/mapas", response_model=list[MapaOut])
def mapas(svc: Service):
    """Estrutura dos mapas/territórios olfativos."""
    return svc.mapas()


@router.get("/regras", response_model=list[RegraOut])
def regras(
    svc: Service,
    tipo: Annotated[
        str | None, Query(max_length=40, description=f"Um de: {', '.join(TIPOS_REGRA)}")
    ] = None,
):
    """Regras ativas do motor."""
    return svc.regras(tipo)


@router.get("/territorios", response_model=list[dict[str, Any]])
def territorios(svc: Service):
    """Territórios olfativos cadastrados (vêm do banco, não do código)."""
    return svc.catalogo("territorio")


@router.get("/publicos", response_model=list[dict[str, Any]])
def publicos(svc: Service):
    """Públicos/identidades cadastrados (Kids, Teen, Adulta...)."""
    return svc.catalogo("publico")
