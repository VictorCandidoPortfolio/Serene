"""Marca de conteúdo de exemplo e doçura em níveis na base de conhecimento.

- `ilustrativo` em famílias, notas, relações, mapas e regras: separa o que é
  EXEMPLO (ainda não validado pela SÉRENÉ) do que é conteúdo definido pela
  cliente. Tudo o que já existia nessas tabelas (exceto famílias e os
  territórios, que vêm da descrição do produto) veio do seed de demonstração,
  então é marcado como exemplo aqui mesmo, sem esperar um novo seed.
- `knowledge_descriptors.ativo`: retira um termo do vocabulário sem apagar a linha.
- `knowledge_notes.docura_nivel_ref`: intensidade da doçura (baixa | media | alta).

Só ADICIONA colunas; nenhuma linha é apagada e nenhum dado de aluna é tocado.

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELAS_COM_MARCA = (
    "knowledge_families",
    "knowledge_notes",
    "knowledge_family_relations",
    "knowledge_maps",
    "knowledge_engine_rules",
)


def upgrade() -> None:
    """Adiciona as colunas e marca o conteúdo já existente como exemplo."""
    for tabela in TABELAS_COM_MARCA:
        op.add_column(
            tabela,
            sa.Column("ilustrativo", sa.Boolean(), server_default="0", nullable=False),
        )
    op.add_column(
        "knowledge_descriptors",
        sa.Column("ativo", sa.Boolean(), server_default="1", nullable=False),
    )
    op.add_column(
        "knowledge_notes", sa.Column("docura_nivel_ref", sa.String(length=10), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_knowledge_notes_docura_nivel_ref"),
        "knowledge_notes",
        "docura_nivel_ref IS NULL OR docura_nivel_ref IN ('baixa', 'media', 'alta')",
    )

    # Conteúdo que já estava no banco veio do seed de demonstração.
    for tabela in ("knowledge_notes", "knowledge_family_relations", "knowledge_maps"):
        op.execute(sa.text(f"UPDATE {tabela} SET ilustrativo = 1"))
    op.execute(sa.text("UPDATE knowledge_engine_rules SET ilustrativo = 1 WHERE tipo <> 'territorio'"))


def downgrade() -> None:
    """Remove as colunas (a marca de exemplo é perdida; os dados continuam)."""
    op.drop_constraint(op.f("ck_knowledge_notes_docura_nivel_ref"), "knowledge_notes", type_="check")
    op.drop_column("knowledge_notes", "docura_nivel_ref")
    op.drop_column("knowledge_descriptors", "ativo")
    for tabela in reversed(TABELAS_COM_MARCA):
        op.drop_column(tabela, "ilustrativo")
