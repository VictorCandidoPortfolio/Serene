"""Repositório SOMENTE LEITURA da camada de conhecimento.

Não existe método de escrita aqui de propósito: a API pública nunca altera
`knowledge_*`. Quem escreve é o seed (`app/seed`), que usa a sessão direto.

Não recebe `user_id`: o conhecimento é o mesmo para todas as usuárias.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import (
    KnowledgeCompositionFunction,
    KnowledgeDescriptor,
    KnowledgeEngineRule,
    KnowledgeFamily,
    KnowledgeFamilyRelation,
    KnowledgeMap,
    KnowledgeNote,
)


class KnowledgeRepository:
    """Leituras da base de conhecimento compartilhada."""

    def __init__(self, db: Session):
        self.db = db

    def familias(self) -> Sequence[KnowledgeFamily]:
        """Famílias e subfamílias, na ordem de exibição."""
        stmt = select(KnowledgeFamily).order_by(KnowledgeFamily.ordem, KnowledgeFamily.id)
        return self.db.scalars(stmt).all()

    def descritores(self) -> Sequence[KnowledgeDescriptor]:
        """Vocabulário de descritores."""
        stmt = select(KnowledgeDescriptor).order_by(
            KnowledgeDescriptor.categoria, KnowledgeDescriptor.nome
        )
        return self.db.scalars(stmt).all()

    def funcoes(self) -> Sequence[KnowledgeCompositionFunction]:
        """Funções da pirâmide (saída/coração/fundo)."""
        stmt = select(KnowledgeCompositionFunction).order_by(KnowledgeCompositionFunction.ordem)
        return self.db.scalars(stmt).all()

    def notas(self) -> Sequence[KnowledgeNote]:
        """Todas as notas de referência.

        Carregar todas é aceitável: a base é curada (dezenas de notas, não
        milhões) e o reconhecimento por sinônimo (JSON) é muito mais simples
        e portável em Python do que com funções JSON específicas do MySQL.
        """
        return self.db.scalars(select(KnowledgeNote).order_by(KnowledgeNote.nome)).all()

    def nota(self, nota_id: int) -> KnowledgeNote | None:
        """Uma nota por id (seguro: conhecimento não tem dona)."""
        return self.db.get(KnowledgeNote, nota_id)

    def relacoes(self) -> Sequence[KnowledgeFamilyRelation]:
        """Relações entre famílias."""
        return self.db.scalars(select(KnowledgeFamilyRelation)).all()

    def mapas(self) -> Sequence[KnowledgeMap]:
        """Mapas/territórios de estudo."""
        stmt = select(KnowledgeMap).order_by(KnowledgeMap.ordem, KnowledgeMap.id)
        return self.db.scalars(stmt).all()

    def regras(self, tipo: str | None = None, apenas_ativas: bool = True) -> Sequence[KnowledgeEngineRule]:
        """Regras do motor, opcionalmente filtradas por tipo."""
        stmt = select(KnowledgeEngineRule).order_by(
            KnowledgeEngineRule.tipo, KnowledgeEngineRule.chave
        )
        if tipo:
            stmt = stmt.where(KnowledgeEngineRule.tipo == tipo)
        if apenas_ativas:
            stmt = stmt.where(KnowledgeEngineRule.ativo.is_(True))
        return self.db.scalars(stmt).all()

    def regras_por_tipo(self, *tipos: str) -> dict[str, dict[str, Any]]:
        """{tipo: {chave: valor}} das regras ATIVAS dos tipos pedidos."""
        stmt = select(KnowledgeEngineRule).where(
            KnowledgeEngineRule.tipo.in_(tipos), KnowledgeEngineRule.ativo.is_(True)
        )
        out: dict[str, dict[str, Any]] = {t: {} for t in tipos}
        for regra in self.db.scalars(stmt):
            out[regra.tipo][regra.chave] = regra.valor
        return out

    def regra(self, tipo: str, chave: str) -> KnowledgeEngineRule | None:
        """Uma regra ATIVA específica, ou None."""
        stmt = select(KnowledgeEngineRule).where(
            KnowledgeEngineRule.tipo == tipo,
            KnowledgeEngineRule.chave == chave,
            KnowledgeEngineRule.ativo.is_(True),
        )
        return self.db.scalar(stmt)
