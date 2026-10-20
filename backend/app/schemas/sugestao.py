"""Schemas do motor de criação: pedido ("O que você quer criar?") e sugestão.

A resposta NÃO carrega vetor nem score no corpo principal: `tecnico` existe
para o motor/auditoria e o frontend não o exibe.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import EntradaModel, ListaEtiquetas

Genero = Literal["feminino", "masculino", "unissex", "nao_definir"]
ModoSugestao = Literal["somente_minhas", "mostrar_lacunas"]
Confianca = Literal["alta", "media", "baixa"]
StatusSugestao = Literal["ok", "insuficiente"]
MAX_IDS_ESSENCIAS = 1000


class SugestaoIn(EntradaModel):
    """Entradas da tela "O que você quer criar?" (seção 3 da especificação).

    `idade` aceita número (convertido em faixa por regras do banco) ou a faixa
    pelo nome. `essencias_disponiveis` é sempre filtrado pelo repertório da
    usuária: id de outra pessoa responde 404.
    """

    para_quem: str | None = Field(default=None, max_length=160)
    genero: Genero = "nao_definir"
    idade: Annotated[int, Field(ge=0, le=120)] | Annotated[str, Field(max_length=40)] | None = None
    emocoes: ListaEtiquetas = []
    preferencias: ListaEtiquetas = []
    intensidade: float = Field(default=5, ge=0, le=10)
    perfume_referencia: str | None = Field(default=None, max_length=160)
    essencias_disponiveis: Literal["todas"] | Annotated[list[int], Field(max_length=MAX_IDS_ESSENCIAS)] = "todas"
    modo: ModoSugestao = "somente_minhas"


class IdentidadeOut(BaseModel):
    """A "personalidade" da fragrância, com o porquê."""

    nome_sugerido: str | None
    personalidade: list[str]
    direcao: str
    por_que: str


class ItemSugeridoOut(BaseModel):
    """Uma essência do repertório da usuária, com peso RELATIVO (nunca %)."""

    essencia_id: int
    nome: str
    peso: int
    rotulo_peso: str
    papel_na_criacao: str


class AcordeSugeridoOut(BaseModel):
    """Acorde enxuto sugerido."""

    itens: list[ItemSugeridoOut]
    familia_resultante: str | None
    piramide: dict[str, int] | None
    explicacao: str


class LacunaSugestaoOut(BaseModel):
    """Categoria que falta (nunca uma essência específica)."""

    tipo: str
    categoria: str | None = None
    mensagem: str


class SugestaoOut(BaseModel):
    """Resposta de `POST /criacoes/sugerir`."""

    status: StatusSugestao
    mensagem: str | None = None
    identidade: IdentidadeOut | None
    acorde: AcordeSugeridoOut | None
    avisos: list[str]
    lacunas: list[LacunaSugestaoOut]
    confianca: Confianca
    tecnico: dict[str, Any] = {}


class OpcaoOut(BaseModel):
    """Uma opção de chip (chave estável + rótulo de exibição)."""

    chave: str
    rotulo: str


class OpcoesSugestaoOut(BaseModel):
    """Listas que alimentam o formulário (vêm do banco, não do front)."""

    emocoes: list[OpcaoOut]
    preferencias: list[OpcaoOut]
    generos: list[OpcaoOut]
    faixas_idade: list[OpcaoOut]
