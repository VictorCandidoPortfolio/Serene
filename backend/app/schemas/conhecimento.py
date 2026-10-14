"""Schemas de saída da camada de conhecimento (só leitura)."""

from typing import Any

from app.schemas.common import ORMModel


class FamiliaOut(ORMModel):
    """Família ou subfamília olfativa."""

    id: int
    slug: str
    nome: str
    descricao: str | None
    parent_id: int | None
    cor: str | None
    ordem: int


class DescritorOut(ORMModel):
    """Descritor sensorial."""

    id: int
    nome: str
    categoria: str | None


class FuncaoOut(ORMModel):
    """Função da pirâmide."""

    id: int
    slug: str
    nome: str
    descricao: str | None
    ordem: int


class NotaOut(ORMModel):
    """Nota de referência (conhecimento — não é essência de ninguém)."""

    id: int
    nome: str
    sinonimos: list[str] = []
    family_id: int | None
    tipo_referencia: str
    papel_tipico: dict | None
    v1_ref: float | None
    v2_ref: float | None
    v3_ref: float | None
    v4_ref: float | None
    v6_ref: float | None = None
    confianca_referencia: str
    fonte: str | None
    descritores: list[str] = []
    observacoes: str | None


class RelacaoOut(ORMModel):
    """Relação entre duas famílias."""

    id: int
    family_a_id: int
    family_b_id: int
    tipo_relacao: str
    peso: float
    descricao: str | None


class MapaOut(ORMModel):
    """Mapa/território olfativo (estrutura para o frontend desenhar)."""

    id: int
    titulo: str
    categoria: str
    family_id: int | None
    conteudo: dict[str, Any]
    relacoes: Any | None
    ordem: int


class RegraOut(ORMModel):
    """Regra do motor."""

    id: int
    tipo: str
    chave: str
    valor: Any
    descricao: str | None
    ativo: bool
