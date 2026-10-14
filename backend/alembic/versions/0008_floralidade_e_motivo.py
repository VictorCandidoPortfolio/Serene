"""Eixo de floralidade (v6) e motivo das versões de acorde.

- `essencias.v6` e `knowledge_notes.v6_ref`: a floralidade passa a ser um
  eixo do motor, como frescor, doçura e intensidade. `NULL` = não sabemos.
- `acordes.motivo`: o que mudou naquela versão e por quê (evolução).

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona as três colunas (todas opcionais: nada existente quebra)."""
    op.add_column("essencias", sa.Column("v6", sa.Float(), nullable=True))
    op.add_column("knowledge_notes", sa.Column("v6_ref", sa.Float(), nullable=True))
    op.add_column("acordes", sa.Column("motivo", sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Remove as colunas."""
    op.drop_column("acordes", "motivo")
    op.drop_column("knowledge_notes", "v6_ref")
    op.drop_column("essencias", "v6")
