"""Colunas `users.foto_url` e `users.foto_public_id`: foto de perfil no Cloudinary.

A imagem em si fica no Cloudinary; o banco guarda só o endereço público
(`foto_url`) e o identificador do arquivo lá (`foto_public_id`), usado para
apagar a foto antiga quando ela é trocada. Contas existentes ficam sem foto.

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona as duas colunas, nulas para todas as contas."""
    op.add_column("users", sa.Column("foto_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("foto_public_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove as colunas (as imagens no Cloudinary não são apagadas)."""
    op.drop_column("users", "foto_public_id")
    op.drop_column("users", "foto_url")
