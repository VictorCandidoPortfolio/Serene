"""Coluna `users.token_version`: permite invalidar os tokens emitidos antes de uma troca de senha.

O JWT carrega a versão vigente quando foi emitido; ao redefinir a senha a
versão sobe, e todo token anterior deixa de valer. Contas existentes começam
em 0, igual aos tokens já emitidos (que não têm a claim e contam como 0).

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona `token_version` (0 para todas as contas)."""
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    """Remove a coluna."""
    op.drop_column("users", "token_version")
