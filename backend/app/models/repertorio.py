"""Models da CAMADA DE REPERTÓRIO PESSOAL.

Tudo aqui pertence a UMA usuária. Há dois formatos de posse:

- **Posse direta**: a tabela tem `user_id` (essencias, criacoes, referencias,
  perfis_olfativos, colecoes).
- **Posse transitiva**: a tabela pertence a uma criação/coleção, e a dona é a
  dona do pai (acordes/testes → criacoes.user_id; colecao_criacoes →
  colecoes.user_id).

ATENÇÃO — isolamento: o MySQL não tem Row Level Security. Nada neste arquivo
impede, por si só, que uma query leia dados de outra usuária. Quem garante o
isolamento é `app.repositories.base`; nunca faça `session.get(Essencia, id)`
ou `select(Essencia)` sem passar por um repositório.

Uma usuária nova nasce com todas estas tabelas vazias para ela: nenhum seed
escreve aqui, e nenhuma nota de `knowledge_notes` é copiada para cá.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.knowledge import NIVEIS_CONFIANCA, TIPOS_REFERENCIA, in_check

ORIGENS_VALOR = ("informado", "tecnico", "inferido", "estimado")
PERCEPCOES = ("fria", "neutra", "quente")
STATUS_CRIACAO = ("rascunho", "em_ajuste", "aprovada", "arquivada")
NIVEIS_PERCEPCAO = ("baixa", "media", "alta")


def _criado_em() -> Mapped[datetime]:
    """Coluna de criação preenchida pelo próprio banco (relógio único)."""
    return mapped_column(DateTime, server_default=func.now())


def _atualizado_em() -> Mapped[datetime]:
    """Coluna de atualização: default no INSERT e `onupdate` em todo UPDATE."""
    return mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    """Conta de uma aluna. A senha só existe aqui como hash bcrypt.

    `email_verificado` começa False: a conta só pode entrar depois de digitar
    o código enviado para o email (ver `app.models.conta.VerificacaoEmail`).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    nome: Mapped[str] = mapped_column(String(120))
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    email_verificado_em: Mapped[datetime | None] = mapped_column(DateTime)
    # Sobe a cada redefinição de senha: tokens com versão menor deixam de valer.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Foto de perfil hospedada no Cloudinary (ver app/core/cloudinary.py).
    # `foto_public_id` é o nome do arquivo lá: necessário para apagar a foto
    # antiga quando ela é trocada ou removida.
    foto_url: Mapped[str | None] = mapped_column(String(500))
    foto_public_id: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = _criado_em()


class Essencia(Base):
    """Essência/matéria-prima que a aluna REALMENTE possui.

    É a matéria-prima de todo o motor: sugestões, acordes e lacunas são
    calculados só a partir destas linhas (filtradas pela dona).

    Eixos (escala 0–10): v1 temperatura (frio→quente), v2 profundidade
    (peso/persistência), v3 doçura, v4 intensidade (presença), v5 complexidade,
    v6 floralidade. `None`
    significa "não sabemos" — o motor nunca troca `None` por um chute.
    """

    __tablename__ = "essencias"
    __table_args__ = (
        CheckConstraint(in_check("tipo", TIPOS_REFERENCIA), name="tipo"),
        CheckConstraint(in_check("confianca", NIVEIS_CONFIANCA), name="confianca"),
        CheckConstraint(in_check("origem", ORIGENS_VALOR), name="origem"),
        CheckConstraint("percepcao IS NULL OR " + in_check("percepcao", PERCEPCOES), name="percepcao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Dona do registro — filtro obrigatório em toda query (ver repositories).
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Link opcional para a referência de conhecimento. SET NULL: se a SÉRENÉ
    # remover a nota da base, a essência da aluna continua existindo.
    knowledge_note_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_notes.id", ondelete="SET NULL"), index=True
    )
    # True quando a aluna alterou algum valor vindo da referência: o sistema
    # nunca deve "re-sincronizar" por cima da correção dela.
    editado_da_referencia: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    nome: Mapped[str] = mapped_column(String(160))
    # Minúsculas, sem acento, espaços colapsados (ver app/core/text.py).
    nome_canonico: Mapped[str] = mapped_column(String(160), index=True)
    familia: Mapped[str | None] = mapped_column(String(120))
    subfamilia: Mapped[str | None] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(
        String(20), default="desconhecida", server_default="desconhecida"
    )
    # Sensação que a aluna informa (fria | neutra | quente). Os valores técnicos
    # (v1..v5, papel...) são DEDUZIDOS pelo servidor a partir dela e da família.
    percepcao: Mapped[str | None] = mapped_column(String(10))
    papel: Mapped[dict[str, float] | None] = mapped_column(JSON)
    v1: Mapped[float | None] = mapped_column(Float)
    v2: Mapped[float | None] = mapped_column(Float)
    v3: Mapped[float | None] = mapped_column(Float)
    v4: Mapped[float | None] = mapped_column(Float)
    v5: Mapped[float | None] = mapped_column(Float)
    v6: Mapped[float | None] = mapped_column(Float)
    confianca: Mapped[str] = mapped_column(String(10), default="baixa", server_default="baixa")
    origem: Mapped[str] = mapped_column(
        String(20), default="informado", server_default="informado"
    )
    fornecedor: Mapped[str | None] = mapped_column(String(160))
    descritores: Mapped[list[str]] = mapped_column(JSON, default=list)
    observacoes: Mapped[str | None] = mapped_column(Text)
    # Ficha técnica: {identificacao, notas{saida,coracao,fundo}, documentacao{tipo,referencia},
    # limites_uso{categoria:{max_pct_produto,fonte}}, restricoes{categorias_nao_indicadas,observacoes}}.
    # Nulo = nada informado. Só o que está aqui conta como "documentado"; eixos v1–v6
    # e descritores são avaliação sensorial; o que falta é DESCONHECIDO (nunca preenchido).
    ficha: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    favorito: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()


class Criacao(Base):
    """"Guarda-chuva" de uma fragrância em desenvolvimento.

    É também a âncora de posse de `acordes` e `testes`: quem é dona da
    criação é dona de todas as versões dela.
    """

    __tablename__ = "criacoes"
    __table_args__ = (CheckConstraint(in_check("status", STATUS_CRIACAO), name="status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    objetivo: Mapped[str | None] = mapped_column(Text)
    # {vetor_alvo, territorios, emocoes, publico, texto, perfil_id}
    direcao: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="rascunho", server_default="rascunho")
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    # passive_deletes: deixa o ON DELETE CASCADE do banco apagar os filhos,
    # sem o ORM carregar todas as versões na memória antes.
    acordes: Mapped[list["Acorde"]] = relationship(
        back_populates="criacao", cascade="all, delete-orphan", passive_deletes=True
    )
    testes: Mapped[list["Teste"]] = relationship(
        back_populates="criacao", cascade="all, delete-orphan", passive_deletes=True
    )


class Acorde(Base):
    """UMA versão de composição dentro de uma criação.

    Versionamento: cada ajuste é uma nova linha com `versao` = anterior + 1.
    Não existe UPDATE de acorde na API — o histórico precisa ser reconstruível.
    A unique `(criacao_id, versao)` impede duas versões iguais mesmo sob
    requisições concorrentes.

    `itens[].peso` é proporção RELATIVA dentro do acorde (pouco/medio/bastante),
    nunca a concentração da essência no produto final.
    """

    __tablename__ = "acordes"
    __table_args__ = (UniqueConstraint("criacao_id", "versao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Posse transitiva: a dona é criacoes.user_id.
    criacao_id: Mapped[int] = mapped_column(ForeignKey("criacoes.id", ondelete="CASCADE"))
    versao: Mapped[int] = mapped_column(Integer)
    # [{essencia_id, nome, peso}] — `nome` é um snapshot: se a essência for
    # renomeada/apagada depois, a versão histórica continua legível.
    itens: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # {"valores": {v1..v5}, "eixos_sem_dado": [...]}
    vetor: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    papel: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    familia_resultante: Mapped[str | None] = mapped_column(String(120))
    # {"score": 0..100 | null, "pares": [...], "alertas": [...]}
    compatibilidade: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # O que mudou nesta versão e por quê (ex.: "Ajuste mais fresco: adicionar
    # Bergamota"). Sem isso, o histórico mostrava O QUE mudou, mas não o motivo.
    motivo: Mapped[str | None] = mapped_column(String(300))
    # Fórmula calculada para esta versão (produto, concentração, volume, quantidades,
    # base). Nulo = a versão não tem formulação. Nunca é "validada" pelo sistema.
    formulacao: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = _criado_em()

    criacao: Mapped[Criacao] = relationship(back_populates="acordes")


class Teste(Base):
    """Registro de uma experimentação/avaliação, também versionado."""

    __tablename__ = "testes"
    __table_args__ = (
        UniqueConstraint("criacao_id", "versao"),
        CheckConstraint("nota IS NULL OR (nota >= 0 AND nota <= 10)", name="nota"),
        CheckConstraint(
            "persistencia_percebida IS NULL OR "
            + in_check("persistencia_percebida", NIVEIS_PERCEPCAO),
            name="persistencia_percebida",
        ),
        CheckConstraint(
            "intensidade_percebida IS NULL OR "
            + in_check("intensidade_percebida", NIVEIS_PERCEPCAO),
            name="intensidade_percebida",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    criacao_id: Mapped[int] = mapped_column(ForeignKey("criacoes.id", ondelete="CASCADE"))
    # SET NULL: o teste continua no histórico mesmo que o acorde suma.
    acorde_id: Mapped[int | None] = mapped_column(
        ForeignKey("acordes.id", ondelete="SET NULL"), index=True
    )
    versao: Mapped[int] = mapped_column(Integer)
    resultado_percebido: Mapped[str | None] = mapped_column(Text)
    persistencia_percebida: Mapped[str | None] = mapped_column(String(10))
    intensidade_percebida: Mapped[str | None] = mapped_column(String(10))
    o_que_ficou_bom: Mapped[str | None] = mapped_column(Text)
    o_que_precisa_mudar: Mapped[str | None] = mapped_column(Text)
    nota: Mapped[int | None] = mapped_column(Integer)
    proximo_ajuste: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _criado_em()

    criacao: Mapped[Criacao] = relationship(back_populates="testes")


class Referencia(Base):
    """Fragrância externa usada como BÚSSOLA, nunca como estoque.

    Nenhum cálculo do motor lê esta tabela como fonte de essências: ela não
    tem vetores nem papel justamente para não poder ser confundida com uma.
    """

    __tablename__ = "referencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    notas_conhecidas: Mapped[list[str]] = mapped_column(JSON, default=list)
    familia_percebida: Mapped[str | None] = mapped_column(String(120))
    caracteristicas: Mapped[list[str]] = mapped_column(JSON, default=list)
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _criado_em()


class PerfilOlfativo(Base):
    """Respostas do questionário + vetor-alvo derivado pelo motor."""

    __tablename__ = "perfis_olfativos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    respostas: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    vetor_alvo: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = _criado_em()


class Colecao(Base):
    """Coleção/linha de criações aprovadas (ex.: "Linha de verão")."""

    __tablename__ = "colecoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    descricao: Mapped[str | None] = mapped_column(Text)
    # Calculado futuramente (média das criações); não obrigatório no esqueleto.
    identidade_geral: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = _atualizado_em()

    itens: Mapped[list["ColecaoCriacao"]] = relationship(
        back_populates="colecao",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ColecaoCriacao.ordem",
    )


class ColecaoCriacao(Base):
    """Associação N:N coleção ↔ criação, com a posição dentro da coleção.

    N:N porque a mesma criação existe individualmente e pode estar em mais de
    uma coleção. Posse transitiva por `colecoes.user_id` — e o service também
    confere que a criação adicionada é da mesma dona.
    """

    __tablename__ = "colecao_criacoes"
    __table_args__ = (UniqueConstraint("colecao_id", "criacao_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    colecao_id: Mapped[int] = mapped_column(ForeignKey("colecoes.id", ondelete="CASCADE"))
    criacao_id: Mapped[int] = mapped_column(
        ForeignKey("criacoes.id", ondelete="CASCADE"), index=True
    )
    ordem: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    colecao: Mapped[Colecao] = relationship(back_populates="itens")
    criacao: Mapped[Criacao] = relationship()
