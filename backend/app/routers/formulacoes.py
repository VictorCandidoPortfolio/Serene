"""Formulação: produtos, cálculo de quantidades e proposta a partir da descrição."""

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.formulacao import FormulacaoIn, FormulacaoOut, ProdutoOut, PropostaIn, PropostaOut
from app.services.formulacao_service import FormulacaoService

router = APIRouter(prefix="/formulacoes", tags=["formulacoes"])


@router.get("/produtos", response_model=list[ProdutoOut])
def produtos(db: DbSession, user: CurrentUser):
    """Produtos, concentrações permitidas e composição da base (vêm do banco)."""
    return FormulacaoService(db, user.id).produtos()


@router.post("/calcular", response_model=FormulacaoOut)
def calcular(payload: FormulacaoIn, db: DbSession, user: CurrentUser):
    """Quantidades de uma formulação. Não grava nada; usa só o repertório da usuária."""
    return FormulacaoService(db, user.id).calcular(payload)


@router.post("/propor", response_model=PropostaOut)
def propor(payload: PropostaIn, db: DbSession, user: CurrentUser):
    """Descrição em linguagem natural -> acorde (só repertório) -> fórmula, se houver fundamento."""
    return FormulacaoService(db, user.id).propor(payload)
