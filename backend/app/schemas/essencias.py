"""Schemas de essências (repertório pessoal)."""

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import (
    Confianca,
    EdicaoModel,
    EntradaModel,
    Eixo,
    ListaEtiquetas,
    ORMModel,
    Papel,
    TextoLongo,
    TipoReferencia,
)

Origem = Literal["informado", "tecnico", "inferido", "estimado"]


class _EssenciaCampos(EntradaModel):
    """Campos editáveis pela aluna (todos opcionais aqui)."""

    familia: str | None = Field(default=None, max_length=120)
    subfamilia: str | None = Field(default=None, max_length=120)
    tipo: TipoReferencia | None = None
    papel: Papel | None = None
    v1: Eixo | None = None
    v2: Eixo | None = None
    v3: Eixo | None = None
    v4: Eixo | None = None
    v5: Eixo | None = None
    v6: Eixo | None = None
    confianca: Confianca | None = None
    origem: Origem | None = None
    fornecedor: str | None = Field(default=None, max_length=160)
    descritores: ListaEtiquetas | None = None
    observacoes: TextoLongo | None = None
    favorito: bool | None = None
    tags: ListaEtiquetas | None = None
    knowledge_note_id: int | None = None
    aplicar_referencia: bool = Field(
        default=False,
        description=(
            "Só com knowledge_note_id: a aluna CONFIRMA a sugestão, e os campos que ela "
            "não informou são preenchidos com os valores da referência."
        ),
    )


class EssenciaCreate(_EssenciaCampos):
    """Cadastro de uma essência que a aluna possui."""

    nome: str = Field(min_length=1, max_length=160)


class EssenciaUpdate(_EssenciaCampos, EdicaoModel):
    """Edição parcial: só os campos enviados são alterados.

    `descritores`/`tags` aceitam null (vira lista vazia); os demais
    obrigatórios no banco, não.
    """

    campos_nao_nulos = ("nome", "tipo", "confianca", "origem", "favorito")

    nome: str | None = Field(default=None, min_length=1, max_length=160)


class EssenciaOut(ORMModel):
    """Essência como devolvida pela API."""

    id: int
    nome: str
    nome_canonico: str
    knowledge_note_id: int | None
    editado_da_referencia: bool
    familia: str | None
    subfamilia: str | None
    tipo: str
    papel: dict | None
    v1: float | None
    v2: float | None
    v3: float | None
    v4: float | None
    v5: float | None
    v6: float | None = None
    confianca: str
    origem: str
    fornecedor: str | None
    descritores: list[str] = []
    observacoes: str | None
    favorito: bool
    tags: list[str] = []
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


class SugestaoReferencia(ORMModel):
    """Uma nota de conhecimento que PODE corresponder à essência.

    É só sugestão: para aplicar, a aluna reenvia com `knowledge_note_id` e
    `aplicar_referencia=true`.
    """

    nota_id: int
    nome: str
    correspondencia: Literal["exata", "parcial"]
    termo: str
    familia: str | None
    subfamilia: str | None
    tipo: str
    papel: dict | None
    v1: float | None
    v2: float | None
    v3: float | None
    v4: float | None
    v6: float | None = None
    confianca_referencia: str
    fonte: str | None
    avisos: list[str] = []


class EssenciaCriadaOut(EssenciaOut):
    """Resposta do cadastro: a essência + sugestões de referência, se houver."""

    sugestoes_referencia: list[SugestaoReferencia] = []


class CompatibilidadeIn(EntradaModel):
    """Essências DO REPERTÓRIO a analisar juntas (sem gravar nada)."""

    essencia_ids: list[int] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def _sem_repetidas(self) -> "CompatibilidadeIn":
        if len(self.essencia_ids) != len(set(self.essencia_ids)):
            raise ValueError("cada essência só pode aparecer uma vez")
        return self


class CompatibilidadeOut(ORMModel):
    """Compatibilidade do grupo: nota 0–100 (ou null), cada par e os alertas."""

    score: int | None
    pares: list[dict]
    alertas: list[str]
