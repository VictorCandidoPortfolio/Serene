"""Percepção (fria/neutra/quente) da essência, para o cadastro simples.

- Adiciona `essencias.percepcao` (anulável) com CHECK fria|neutra|quente.
- Migração de DADOS: essências existentes ganham a percepção derivada de `v1`
  pelos mesmos limiares do cadastro simples (<= 3,5 fria; <= 6,5 neutra; senão
  quente). Sem `v1`, fica nula. Nenhum outro valor é alterado.

Reversível: o downgrade remove a coluna (a percepção é sempre rederivável de v1).

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mesmos limiares do seed (`peso_score/percepcao`). Ficam aqui porque a migration
# precisa funcionar antes de qualquer seed.
FRIA_ATE = 3.5
NEUTRA_ATE = 6.5


def upgrade() -> None:
    """Cria a coluna e preenche a percepção das essências existentes a partir de v1."""
    op.add_column("essencias", sa.Column("percepcao", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        op.f("ck_essencias_percepcao"),
        "essencias",
        "percepcao IS NULL OR percepcao IN ('fria', 'neutra', 'quente')",
    )
    essencias = sa.table(
        "essencias", sa.column("v1", sa.Float), sa.column("percepcao", sa.String)
    )
    for valor, condicao in (
        ("fria", essencias.c.v1 <= FRIA_ATE),
        ("neutra", sa.and_(essencias.c.v1 > FRIA_ATE, essencias.c.v1 <= NEUTRA_ATE)),
        ("quente", essencias.c.v1 > NEUTRA_ATE),
    ):
        op.execute(essencias.update().where(condicao).values(percepcao=valor))


def downgrade() -> None:
    """Remove a coluna (e o CHECK)."""
    op.drop_constraint(op.f("ck_essencias_percepcao"), "essencias", type_="check")
    op.drop_column("essencias", "percepcao")
