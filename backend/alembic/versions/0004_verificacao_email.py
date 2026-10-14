"""Verificação de email por código: colunas em `users` + tabela `verificacoes_email`.

Contas que já existiam antes desta migration são marcadas como verificadas:
elas foram criadas quando ainda não havia verificação, e sem isso ficariam
trancadas para fora (o login passa a exigir email confirmado).

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona `email_verificado(_em)` e cria `verificacoes_email`."""
    op.add_column(
        "users",
        sa.Column("email_verificado", sa.Boolean(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("email_verificado_em", sa.DateTime(), nullable=True))
    # Contas antigas: consideradas verificadas (ver docstring do módulo).
    op.execute("UPDATE users SET email_verificado = 1, email_verificado_em = criado_em")

    op.create_table(
        "verificacoes_email",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("codigo_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("tentativas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("enviado_em", sa.DateTime(), nullable=False),
        sa.Column("janela_inicio", sa.DateTime(), nullable=False),
        sa.Column("envios_na_janela", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_verificacoes_email_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verificacoes_email")),
        sa.UniqueConstraint("user_id", name=op.f("uq_verificacoes_email_user_id")),
    )


def downgrade() -> None:
    """Remove a tabela e as colunas (as contas voltam a não ter verificação)."""
    op.drop_table("verificacoes_email")
    op.drop_column("users", "email_verificado_em")
    op.drop_column("users", "email_verificado")
