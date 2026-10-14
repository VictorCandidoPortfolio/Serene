"""Schemas dos recursos secundários: referências, perfis e coleções."""

from datetime import datetime
from typing import Any

import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import (
    EdicaoModel,
    EntradaModel,
    ListaEtiquetas,
    ListaItens,
    ORMModel,
    TextoLongo,
)


# --------------------------------------------------------------- referências
class ReferenciaCreate(EntradaModel):
    """Fragrância externa de referência (bússola, nunca estoque)."""

    nome: str = Field(min_length=1, max_length=160)
    notas_conhecidas: ListaItens = []
    familia_percebida: str | None = Field(default=None, max_length=120)
    caracteristicas: ListaItens = []
    observacoes: TextoLongo | None = None


class ReferenciaUpdate(EdicaoModel):
    """Edição parcial de referência."""

    campos_nao_nulos = ("nome", "notas_conhecidas", "caracteristicas")

    nome: str | None = Field(default=None, min_length=1, max_length=160)
    notas_conhecidas: ListaItens | None = None
    familia_percebida: str | None = Field(default=None, max_length=120)
    caracteristicas: ListaItens | None = None
    observacoes: TextoLongo | None = None


class ReferenciaOut(ORMModel):
    """Referência como devolvida pela API."""

    id: int
    nome: str
    notas_conhecidas: list[str] = []
    familia_percebida: str | None
    caracteristicas: list[str] = []
    observacoes: str | None
    criado_em: datetime | None = None


# ------------------------------------------------------------------- perfis
RESPOSTAS_MAX_BYTES = 10_000


class RespostasPerfil(BaseModel):
    """Questionário do perfil olfativo.

    Campos conhecidos são tipados; `extra="allow"` guarda respostas novas do
    front sem quebrar a API (elas ficam em `respostas`, só não influenciam o
    motor até existir regra para elas).
    """

    model_config = ConfigDict(extra="allow")

    emocoes: ListaEtiquetas = []
    territorios: ListaEtiquetas = []
    preferencias: ListaEtiquetas = []
    intensidade: float | None = Field(default=None, ge=0, le=10)
    publico: str | None = Field(default=None, max_length=60)
    idade: int | None = Field(default=None, ge=0, le=120)
    # Insumo flexível; nunca trava família alguma (regra de negócio 7).
    genero: str | None = Field(default=None, max_length=60)
    perfume_referencia: str | None = Field(default=None, max_length=160)
    # Um perfume da tela "Referências" DELA: a direção estimada dele entra
    # no alvo (só como direção — referência nunca vira estoque).
    referencia_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _tamanho_total(self) -> "RespostasPerfil":
        # `extra="allow"` guardaria qualquer coisa: um perfil com 3 MB de
        # lixo foi aceito na auditoria. Limita o JSON inteiro.
        if len(json.dumps(self.model_dump(), ensure_ascii=False)) > RESPOSTAS_MAX_BYTES:
            raise ValueError(f"respostas muito grandes (máximo {RESPOSTAS_MAX_BYTES} caracteres)")
        return self


class PerfilCreate(EntradaModel):
    """Criação/atualização de perfil: só as respostas; o alvo é calculado."""

    respostas: RespostasPerfil


class PerfilOut(ORMModel):
    """Perfil com o vetor-alvo calculado e a trilha de cálculo."""

    id: int
    respostas: dict[str, Any]
    vetor_alvo: dict[str, Any] | None
    criado_em: datetime | None = None


class EssenciaRecomendadaOut(ORMModel):
    """Essência DO REPERTÓRIO pontuada contra o alvo."""

    essencia_id: int
    nome: str
    familia: str | None
    score: int
    eixos_comparados: list[str]
    explicacao: str


class RecomendacoesOut(BaseModel):
    """Ranking do repertório + avisos (ex.: repertório vazio)."""

    vetor_alvo: dict[str, float | None]
    recomendacoes: list[EssenciaRecomendadaOut]
    nao_avaliadas: list[str]
    avisos: list[str]


# ------------------------------------------------------------------ coleções
class ColecaoCreate(EntradaModel):
    """Nova coleção."""

    nome: str = Field(min_length=1, max_length=160)
    descricao: TextoLongo | None = None


class ColecaoUpdate(EdicaoModel):
    """Edição parcial de coleção."""

    campos_nao_nulos = ("nome",)

    nome: str | None = Field(default=None, min_length=1, max_length=160)
    descricao: TextoLongo | None = None


class ColecaoItemIn(EntradaModel):
    """Adicionar uma criação (aprovada) à coleção."""

    criacao_id: int
    ordem: int | None = Field(default=None, ge=0)


class ColecaoOrdemIn(EntradaModel):
    """Nova ordem: lista completa dos ids de criação da coleção."""

    criacao_ids: list[int] = Field(max_length=100)


class ColecaoItemOut(ORMModel):
    """Item de coleção com o resumo da criação."""

    criacao_id: int
    ordem: int
    nome: str
    status: str


class ColecaoOut(ORMModel):
    """Coleção com seus itens ordenados."""

    id: int
    nome: str
    descricao: str | None
    identidade_geral: dict[str, Any] | None
    itens: list[ColecaoItemOut] = []
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


class CaminhosReferenciaOut(BaseModel):
    """O que uma referência ensina: direção estimada e o que a aluna tem para ir nela."""

    vetor_estimado: dict[str, float | None]
    notas_reconhecidas: list[dict[str, Any]]
    notas_desconhecidas: list[str]
    familias_presentes: list[str]
    familias_ausentes: list[str]
    avisos: list[str]
    recomendacoes: RecomendacoesOut
