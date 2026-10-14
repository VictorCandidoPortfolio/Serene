"""Coleções (funcionalidade 2.10) e a associação N:N coleção ↔ criação.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as tabelas: colecoes, colecao_criacoes."""
    op.create_table('colecoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('identidade_geral', sa.JSON(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_colecoes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_colecoes'))
    )
    op.create_index(op.f('ix_colecoes_user_id'), 'colecoes', ['user_id'], unique=False)
    op.create_table('colecao_criacoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('colecao_id', sa.Integer(), nullable=False),
    sa.Column('criacao_id', sa.Integer(), nullable=False),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['colecao_id'], ['colecoes.id'], name=op.f('fk_colecao_criacoes_colecao_id_colecoes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['criacao_id'], ['criacoes.id'], name=op.f('fk_colecao_criacoes_criacao_id_criacoes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_colecao_criacoes')),
    sa.UniqueConstraint('colecao_id', 'criacao_id', name=op.f('uq_colecao_criacoes_colecao_id_criacao_id'))
    )
    op.create_index(op.f('ix_colecao_criacoes_criacao_id'), 'colecao_criacoes', ['criacao_id'], unique=False)


def downgrade() -> None:
    """Remove as tabelas na ordem inversa das dependências.

    Só `drop_table`: o MySQL recusa apagar isoladamente um índice que sustenta
    uma FK, e apagar a tabela já remove os índices dela.
    """
    op.drop_table('colecao_criacoes')
    op.drop_table('colecoes')
