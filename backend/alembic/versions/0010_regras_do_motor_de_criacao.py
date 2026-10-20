"""Tipos de regra do motor de criação (emoção, preferência, idade, território, vocabulário).

Só amplia o CHECK de `knowledge_engine_rules.tipo`; nenhuma linha existente
é alterada. As regras novas entram pelo seed (`python -m app.seed`).

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ANTIGOS = ("correlacao_territorio", "vetor_movimento", "emocao", "preferencia", "peso_score",
           "territorio", "publico")
NOVOS = ("criacao_emocao", "criacao_preferencia", "criacao_idade", "criacao_territorio",
         "criacao_vocabulario")
CHECK = "ck_knowledge_engine_rules_tipo"


def _expr(tipos: tuple[str, ...]) -> str:
    return "tipo IN (" + ", ".join(f"'{t}'" for t in tipos) + ")"


def upgrade() -> None:
    """Troca o CHECK por um que aceita os tipos novos."""
    op.drop_constraint(op.f(CHECK), "knowledge_engine_rules", type_="check")
    op.create_check_constraint(op.f(CHECK), "knowledge_engine_rules", _expr(ANTIGOS + NOVOS))


def downgrade() -> None:
    """Volta ao CHECK antigo. As regras dos tipos novos são removidas (não cabem nele)."""
    op.execute("DELETE FROM knowledge_engine_rules WHERE tipo IN ("
               + ", ".join(f"'{t}'" for t in NOVOS) + ")")
    op.drop_constraint(op.f(CHECK), "knowledge_engine_rules", type_="check")
    op.create_check_constraint(op.f(CHECK), "knowledge_engine_rules", _expr(ANTIGOS))
