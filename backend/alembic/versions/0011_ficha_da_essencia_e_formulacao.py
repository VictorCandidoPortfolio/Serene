"""Ficha técnica da essência e formulação da versão do acorde.

- `essencias.ficha` (JSON, nulo): identificação do produto, notas de saída/
  coração/fundo, documentação técnica, limites de uso DOCUMENTADOS e restrições.
  Nulo = nada informado (o sistema não preenche por conta própria).
- `acordes.formulacao` (JSON, nulo): fotografia da fórmula calculada para a
  versão (produto, concentração, volume, proporções, quantidades, base).

Só ADICIONA colunas anuláveis; nenhuma linha existente é alterada.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona as duas colunas JSON."""
    op.add_column("essencias", sa.Column("ficha", sa.JSON(), nullable=True))
    op.add_column("acordes", sa.Column("formulacao", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove as colunas (a ficha e as fórmulas gravadas são perdidas)."""
    op.drop_column("acordes", "formulacao")
    op.drop_column("essencias", "ficha")
