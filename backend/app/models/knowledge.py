"""Models da CAMADA DE CONHECIMENTO (`knowledge_*`).

Esta camada é compartilhada: é a mesma para todas as usuárias e não tem dono
(nenhuma tabela aqui tem `user_id`). A API pública só a lê — a escrita
acontece exclusivamente pelo seed / migrations (ver `app/seed`).

Regra central do produto: nada daqui é "repertório" de ninguém. Uma nota de
referência (`KnowledgeNote`) descreve o que se sabe sobre um material; uma
essência da aluna (`app.models.repertorio.Essencia`) pode apontar para ela via
`knowledge_note_id`, mas nunca é substituída por ela.

Escolhas de tipo para MySQL:
- JSON nativo (MySQL >= 5.7.8) no lugar do JSONB do Postgres.
- Valores de enum como VARCHAR + CHECK (enforçado pelo MySQL >= 8.0.16) em vez
  de ENUM nativo: adicionar um valor novo é só trocar o CHECK numa migration,
  sem reescrever a coluna.
- Colunas JSON não têm server_default (o MySQL só aceita default de expressão
  em JSON a partir do 8.0.13); o default é aplicado pelo Python.
- Vetores como FLOAT: são heurísticas numa escala 0–10, não valores
  monetários — precisão de ponto flutuante é suficiente e simplifica o motor.
"""

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TIPOS_REFERENCIA = ("simples", "composta", "desconhecida")
NIVEIS_CONFIANCA = ("alta", "media", "baixa")
TIPOS_RELACAO = ("classico", "complementar", "atencao", "contraste")
CATEGORIAS_MAPA = ("familia", "piramide", "eixo")
# Os TIPOS de regra são fixos (o motor precisa saber o que consultar), mas as
# REGRAS em si — quais territórios, públicos, movimentos existem — são linhas
# no banco. Um território novo é um INSERT, não um deploy.
TIPOS_REGRA = (
    "correlacao_territorio",
    "vetor_movimento",
    "emocao",
    "preferencia",
    "peso_score",
    "territorio",
    "publico",
)


def in_check(column: str, values: tuple[str, ...]) -> str:
    """Monta a expressão SQL `coluna IN ('a','b',...)` para um CheckConstraint.

    Compartilhada com `app.models.repertorio` para que os CHECKs das duas
    camadas sejam gerados do mesmo jeito (e as migrations fiquem previsíveis).
    """
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class KnowledgeFamily(Base):
    """Família (ou subfamília, via `parent_id`) olfativa.

    `slug` é a chave estável usada em regras e no motor; `nome` é só exibição
    e pode ser renomeado sem quebrar nada.
    """

    __tablename__ = "knowledge_families"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    descricao: Mapped[str | None] = mapped_column(Text)
    # Auto-relacionamento: subfamília aponta para a família-mãe.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_families.id", ondelete="SET NULL"), index=True
    )
    cor: Mapped[str | None] = mapped_column(String(20))
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    parent: Mapped["KnowledgeFamily | None"] = relationship(
        remote_side=[id], back_populates="subfamilias"
    )
    subfamilias: Mapped[list["KnowledgeFamily"]] = relationship(back_populates="parent")


class KnowledgeDescriptor(Base):
    """Vocabulário controlado de descritores (ex.: "cremoso", "verde").

    `categoria` só organiza a exibição — o motor nunca calcula nada a partir
    dela.
    """

    __tablename__ = "knowledge_descriptors"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    categoria: Mapped[str | None] = mapped_column(String(80))


class KnowledgeCompositionFunction(Base):
    """Função na pirâmide olfativa: saída, coração, fundo."""

    __tablename__ = "knowledge_composition_functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str | None] = mapped_column(Text)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class KnowledgeNote(Base):
    """Nota de referência — o que se sabe tecnicamente sobre um material.

    Usada APENAS para sugerir classificação quando a aluna cadastra uma
    essência com nome parecido. Nunca é tratada como estoque de ninguém.

    `nome` é único para que o reconhecimento de essências e o seed idempotente
    tenham uma chave natural estável.
    """

    __tablename__ = "knowledge_notes"
    __table_args__ = (
        CheckConstraint(in_check("tipo_referencia", TIPOS_REFERENCIA), name="tipo_referencia"),
        CheckConstraint(
            in_check("confianca_referencia", NIVEIS_CONFIANCA), name="confianca_referencia"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    # Lista de strings: outros nomes/grafias pelos quais o material é conhecido.
    sinonimos: Mapped[list[str]] = mapped_column(JSON, default=list)
    family_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_families.id", ondelete="SET NULL"), index=True
    )
    # "composta" = acorde/efeito comercial (ex.: "Âmbar"). Nunca afirmamos a
    # composição interna de um fornecedor sem evidência.
    tipo_referencia: Mapped[str] = mapped_column(
        String(20), default="desconhecida", server_default="desconhecida"
    )
    # {"saida": 0..1, "coracao": 0..1, "fundo": 0..1}
    papel_tipico: Mapped[dict[str, float] | None] = mapped_column(JSON)
    # Eixos do vetor olfativo de referência (escala 0–10, ver app/engine/axes.py).
    # Não existe v5_ref: complexidade estrutural depende da essência concreta
    # da aluna (fornecedor, diluição), não do material genérico.
    # v6_ref = floralidade de referência.
    v1_ref: Mapped[float | None] = mapped_column(Float)
    v2_ref: Mapped[float | None] = mapped_column(Float)
    v3_ref: Mapped[float | None] = mapped_column(Float)
    v4_ref: Mapped[float | None] = mapped_column(Float)
    v6_ref: Mapped[float | None] = mapped_column(Float)
    # Se "baixa", o sistema avisa a aluna em vez de afirmar com certeza.
    confianca_referencia: Mapped[str] = mapped_column(
        String(10), default="baixa", server_default="baixa"
    )
    fonte: Mapped[str | None] = mapped_column(Text)
    descritores: Mapped[list[str]] = mapped_column(JSON, default=list)
    observacoes: Mapped[str | None] = mapped_column(Text)

    family: Mapped[KnowledgeFamily | None] = relationship()


class KnowledgeFamilyRelation(Base):
    """Relação entre duas famílias (clássico, complementar, atenção, contraste).

    O par é tratado como não-ordenado pelo motor (A–B == B–A); a unique
    evita cadastrar a mesma direção duas vezes.
    """

    __tablename__ = "knowledge_family_relations"
    __table_args__ = (
        UniqueConstraint("family_a_id", "family_b_id"),
        CheckConstraint(in_check("tipo_relacao", TIPOS_RELACAO), name="tipo_relacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    family_a_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_families.id", ondelete="CASCADE")
    )
    family_b_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_families.id", ondelete="CASCADE"), index=True
    )
    tipo_relacao: Mapped[str] = mapped_column(String(20))
    # Intensidade da relação, 0..1 — multiplica o peso do tipo no score.
    peso: Mapped[float] = mapped_column(Float, default=1.0, server_default="1")
    descricao: Mapped[str | None] = mapped_column(Text)

    family_a: Mapped[KnowledgeFamily] = relationship(foreign_keys=[family_a_id])
    family_b: Mapped[KnowledgeFamily] = relationship(foreign_keys=[family_b_id])


class KnowledgeMap(Base):
    """Mapa/território olfativo (por família, pirâmide ou eixo).

    O backend não desenha nada: `conteudo` e `relacoes` são JSON livre com a
    estrutura (pontos, rótulos, posições) que o frontend vai renderizar.
    """

    __tablename__ = "knowledge_maps"
    __table_args__ = (
        CheckConstraint(in_check("categoria", CATEGORIAS_MAPA), name="categoria"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160), unique=True)
    categoria: Mapped[str] = mapped_column(String(20))
    family_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_families.id", ondelete="SET NULL"), index=True
    )
    conteudo: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    relacoes: Mapped[Any | None] = mapped_column(JSON)
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class KnowledgeEngineRule(Base):
    """Regra/heurística parametrizável do motor olfativo.

    Tudo o que o motor usa como "número mágico" de domínio mora aqui, e não no
    Python: pesos de score, vetores de movimento, emoções → vetor, territórios,
    públicos. Ajustar o comportamento do motor é mudar dados, não código.

    `(tipo, chave)` é único: é a chave de busca usada pelo motor
    (ex.: tipo="vetor_movimento", chave="mais_fresco"). O formato de `valor`
    por tipo está documentado em `app/seed/data.py`.
    """

    __tablename__ = "knowledge_engine_rules"
    __table_args__ = (
        UniqueConstraint("tipo", "chave"),
        CheckConstraint(in_check("tipo", TIPOS_REGRA), name="tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40))
    chave: Mapped[str] = mapped_column(String(80))
    valor: Mapped[Any] = mapped_column(JSON)
    descricao: Mapped[str | None] = mapped_column(Text)
    # Desativar em vez de apagar preserva o histórico de calibração.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
