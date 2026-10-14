"""Tabela `limites_requisicao`: contadores do limite de tentativas por IP/email.

Fica no banco porque no Vercel não há memória compartilhada entre as
instâncias da função (ver app/core/rate_limit.py).

Revision ID: 0005
Revises: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria `limites_requisicao`."""
    op.create_table(
        "limites_requisicao",
        sa.Column("chave", sa.String(length=100), nullable=False),
        sa.Column("janela_inicio", sa.DateTime(), nullable=False),
        sa.Column("contador", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("chave", name=op.f("pk_limites_requisicao")),
    )


def downgrade() -> None:
    """Remove `limites_requisicao`."""
    op.drop_table("limites_requisicao")
