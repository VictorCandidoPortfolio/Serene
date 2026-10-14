"""Camada de CONHECIMENTO (knowledge_*): compartilhada, só leitura pela API.

Populada pelo seed (python -m app.seed), nunca por endpoints públicos.

Revision ID: 0001
Revises: 
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as tabelas: knowledge_composition_functions, knowledge_descriptors, knowledge_engine_rules, knowledge_families, knowledge_family_relations, knowledge_maps, knowledge_notes."""
    op.create_table('knowledge_composition_functions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=40), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_composition_functions')),
    sa.UniqueConstraint('slug', name=op.f('uq_knowledge_composition_functions_slug'))
    )
    op.create_table('knowledge_descriptors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('categoria', sa.String(length=80), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_descriptors')),
    sa.UniqueConstraint('nome', name=op.f('uq_knowledge_descriptors_nome'))
    )
    op.create_table('knowledge_engine_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=40), nullable=False),
    sa.Column('chave', sa.String(length=80), nullable=False),
    sa.Column('valor', sa.JSON(), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('ativo', sa.Boolean(), server_default='1', nullable=False),
    sa.CheckConstraint("tipo IN ('correlacao_territorio', 'vetor_movimento', 'emocao', 'preferencia', 'peso_score', 'territorio', 'publico')", name=op.f('ck_knowledge_engine_rules_tipo')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_engine_rules')),
    sa.UniqueConstraint('tipo', 'chave', name=op.f('uq_knowledge_engine_rules_tipo_chave'))
    )
    op.create_table('knowledge_families',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('cor', sa.String(length=20), nullable=True),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['knowledge_families.id'], name=op.f('fk_knowledge_families_parent_id_knowledge_families'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_families')),
    sa.UniqueConstraint('slug', name=op.f('uq_knowledge_families_slug'))
    )
    op.create_index(op.f('ix_knowledge_families_parent_id'), 'knowledge_families', ['parent_id'], unique=False)
    op.create_table('knowledge_family_relations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('family_a_id', sa.Integer(), nullable=False),
    sa.Column('family_b_id', sa.Integer(), nullable=False),
    sa.Column('tipo_relacao', sa.String(length=20), nullable=False),
    sa.Column('peso', sa.Float(), server_default='1', nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.CheckConstraint("tipo_relacao IN ('classico', 'complementar', 'atencao', 'contraste')", name=op.f('ck_knowledge_family_relations_tipo_relacao')),
    sa.ForeignKeyConstraint(['family_a_id'], ['knowledge_families.id'], name=op.f('fk_knowledge_family_relations_family_a_id_knowledge_families'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['family_b_id'], ['knowledge_families.id'], name=op.f('fk_knowledge_family_relations_family_b_id_knowledge_families'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_family_relations')),
    sa.UniqueConstraint('family_a_id', 'family_b_id', name=op.f('uq_knowledge_family_relations_family_a_id_family_b_id'))
    )
    op.create_index(op.f('ix_knowledge_family_relations_family_b_id'), 'knowledge_family_relations', ['family_b_id'], unique=False)
    op.create_table('knowledge_maps',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=160), nullable=False),
    sa.Column('categoria', sa.String(length=20), nullable=False),
    sa.Column('family_id', sa.Integer(), nullable=True),
    sa.Column('conteudo', sa.JSON(), nullable=False),
    sa.Column('relacoes', sa.JSON(), nullable=True),
    sa.Column('ordem', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("categoria IN ('familia', 'piramide', 'eixo')", name=op.f('ck_knowledge_maps_categoria')),
    sa.ForeignKeyConstraint(['family_id'], ['knowledge_families.id'], name=op.f('fk_knowledge_maps_family_id_knowledge_families'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_maps')),
    sa.UniqueConstraint('titulo', name=op.f('uq_knowledge_maps_titulo'))
    )
    op.create_index(op.f('ix_knowledge_maps_family_id'), 'knowledge_maps', ['family_id'], unique=False)
    op.create_table('knowledge_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('sinonimos', sa.JSON(), nullable=False),
    sa.Column('family_id', sa.Integer(), nullable=True),
    sa.Column('tipo_referencia', sa.String(length=20), server_default='desconhecida', nullable=False),
    sa.Column('papel_tipico', sa.JSON(), nullable=True),
    sa.Column('v1_ref', sa.Float(), nullable=True),
    sa.Column('v2_ref', sa.Float(), nullable=True),
    sa.Column('v3_ref', sa.Float(), nullable=True),
    sa.Column('v4_ref', sa.Float(), nullable=True),
    sa.Column('confianca_referencia', sa.String(length=10), server_default='baixa', nullable=False),
    sa.Column('fonte', sa.Text(), nullable=True),
    sa.Column('descritores', sa.JSON(), nullable=False),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.CheckConstraint("confianca_referencia IN ('alta', 'media', 'baixa')", name=op.f('ck_knowledge_notes_confianca_referencia')),
    sa.CheckConstraint("tipo_referencia IN ('simples', 'composta', 'desconhecida')", name=op.f('ck_knowledge_notes_tipo_referencia')),
    sa.ForeignKeyConstraint(['family_id'], ['knowledge_families.id'], name=op.f('fk_knowledge_notes_family_id_knowledge_families'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_notes')),
    sa.UniqueConstraint('nome', name=op.f('uq_knowledge_notes_nome'))
    )
    op.create_index(op.f('ix_knowledge_notes_family_id'), 'knowledge_notes', ['family_id'], unique=False)


def downgrade() -> None:
    """Remove as tabelas na ordem inversa das dependências.

    Só `drop_table`: o MySQL recusa apagar isoladamente um índice que sustenta
    uma FK, e apagar a tabela já remove os índices dela.
    """
    op.drop_table('knowledge_notes')
    op.drop_table('knowledge_maps')
    op.drop_table('knowledge_family_relations')
    op.drop_table('knowledge_families')
    op.drop_table('knowledge_engine_rules')
    op.drop_table('knowledge_descriptors')
    op.drop_table('knowledge_composition_functions')
