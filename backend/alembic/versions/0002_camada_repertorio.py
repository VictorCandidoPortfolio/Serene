"""Camada de REPERTÓRIO PESSOAL: usuárias e tudo que pertence a cada uma.

Isolamento: o MySQL não tem RLS; o filtro por dona é imposto em
app/repositories/base.py. As FKs com ON DELETE CASCADE garantem que apagar
uma conta apaga todo o repertório dela.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as tabelas: users, essencias, criacoes, acordes, testes, referencias, perfis_olfativos."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('senha_hash', sa.String(length=255), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('criacoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('objetivo', sa.Text(), nullable=True),
    sa.Column('direcao', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='rascunho', nullable=False),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('rascunho', 'em_ajuste', 'aprovada', 'arquivada')", name=op.f('ck_criacoes_status')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_criacoes_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_criacoes'))
    )
    op.create_index(op.f('ix_criacoes_user_id'), 'criacoes', ['user_id'], unique=False)
    op.create_table('perfis_olfativos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('respostas', sa.JSON(), nullable=False),
    sa.Column('vetor_alvo', sa.JSON(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_perfis_olfativos_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_perfis_olfativos'))
    )
    op.create_index(op.f('ix_perfis_olfativos_user_id'), 'perfis_olfativos', ['user_id'], unique=False)
    op.create_table('referencias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('notas_conhecidas', sa.JSON(), nullable=False),
    sa.Column('familia_percebida', sa.String(length=120), nullable=True),
    sa.Column('caracteristicas', sa.JSON(), nullable=False),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_referencias_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_referencias'))
    )
    op.create_index(op.f('ix_referencias_user_id'), 'referencias', ['user_id'], unique=False)
    op.create_table('acordes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('criacao_id', sa.Integer(), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('itens', sa.JSON(), nullable=False),
    sa.Column('vetor', sa.JSON(), nullable=True),
    sa.Column('papel', sa.JSON(), nullable=True),
    sa.Column('familia_resultante', sa.String(length=120), nullable=True),
    sa.Column('compatibilidade', sa.JSON(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['criacao_id'], ['criacoes.id'], name=op.f('fk_acordes_criacao_id_criacoes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_acordes')),
    sa.UniqueConstraint('criacao_id', 'versao', name=op.f('uq_acordes_criacao_id_versao'))
    )
    op.create_table('essencias',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('knowledge_note_id', sa.Integer(), nullable=True),
    sa.Column('editado_da_referencia', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('nome_canonico', sa.String(length=160), nullable=False),
    sa.Column('familia', sa.String(length=120), nullable=True),
    sa.Column('subfamilia', sa.String(length=120), nullable=True),
    sa.Column('tipo', sa.String(length=20), server_default='desconhecida', nullable=False),
    sa.Column('papel', sa.JSON(), nullable=True),
    sa.Column('v1', sa.Float(), nullable=True),
    sa.Column('v2', sa.Float(), nullable=True),
    sa.Column('v3', sa.Float(), nullable=True),
    sa.Column('v4', sa.Float(), nullable=True),
    sa.Column('v5', sa.Float(), nullable=True),
    sa.Column('confianca', sa.String(length=10), server_default='baixa', nullable=False),
    sa.Column('origem', sa.String(length=20), server_default='informado', nullable=False),
    sa.Column('fornecedor', sa.String(length=160), nullable=True),
    sa.Column('descritores', sa.JSON(), nullable=False),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.Column('favorito', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("confianca IN ('alta', 'media', 'baixa')", name=op.f('ck_essencias_confianca')),
    sa.CheckConstraint("origem IN ('informado', 'tecnico', 'inferido', 'estimado')", name=op.f('ck_essencias_origem')),
    sa.CheckConstraint("tipo IN ('simples', 'composta', 'desconhecida')", name=op.f('ck_essencias_tipo')),
    sa.ForeignKeyConstraint(['knowledge_note_id'], ['knowledge_notes.id'], name=op.f('fk_essencias_knowledge_note_id_knowledge_notes'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_essencias_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_essencias'))
    )
    op.create_index(op.f('ix_essencias_knowledge_note_id'), 'essencias', ['knowledge_note_id'], unique=False)
    op.create_index(op.f('ix_essencias_nome_canonico'), 'essencias', ['nome_canonico'], unique=False)
    op.create_index(op.f('ix_essencias_user_id'), 'essencias', ['user_id'], unique=False)
    op.create_table('testes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('criacao_id', sa.Integer(), nullable=False),
    sa.Column('acorde_id', sa.Integer(), nullable=True),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('resultado_percebido', sa.Text(), nullable=True),
    sa.Column('persistencia_percebida', sa.String(length=10), nullable=True),
    sa.Column('intensidade_percebida', sa.String(length=10), nullable=True),
    sa.Column('o_que_ficou_bom', sa.Text(), nullable=True),
    sa.Column('o_que_precisa_mudar', sa.Text(), nullable=True),
    sa.Column('nota', sa.Integer(), nullable=True),
    sa.Column('proximo_ajuste', sa.Text(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("intensidade_percebida IS NULL OR intensidade_percebida IN ('baixa', 'media', 'alta')", name=op.f('ck_testes_intensidade_percebida')),
    sa.CheckConstraint("persistencia_percebida IS NULL OR persistencia_percebida IN ('baixa', 'media', 'alta')", name=op.f('ck_testes_persistencia_percebida')),
    sa.CheckConstraint('nota IS NULL OR (nota >= 0 AND nota <= 10)', name=op.f('ck_testes_nota')),
    sa.ForeignKeyConstraint(['acorde_id'], ['acordes.id'], name=op.f('fk_testes_acorde_id_acordes'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['criacao_id'], ['criacoes.id'], name=op.f('fk_testes_criacao_id_criacoes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_testes')),
    sa.UniqueConstraint('criacao_id', 'versao', name=op.f('uq_testes_criacao_id_versao'))
    )
    op.create_index(op.f('ix_testes_acorde_id'), 'testes', ['acorde_id'], unique=False)


def downgrade() -> None:
    """Remove as tabelas na ordem inversa das dependências.

    Só `drop_table`: o MySQL recusa apagar isoladamente um índice que sustenta
    uma FK, e apagar a tabela já remove os índices dela.
    """
    op.drop_table('testes')
    op.drop_table('essencias')
    op.drop_table('acordes')
    op.drop_table('referencias')
    op.drop_table('perfis_olfativos')
    op.drop_table('criacoes')
    op.drop_table('users')
