"""Schemas do motor de criação: pedido ("O que você quer criar?") e sugestão.

A resposta NÃO carrega vetor nem score no corpo principal: `tecnico` existe
para o motor/auditoria e o frontend não o exibe.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import EntradaModel, ListaEtiquetas

Genero = Literal["feminino", "masculino", "unissex", "nao_definir"]
ModoSugestao = Literal["somente_minhas", "mostrar_lacunas"]
# ok: identidade + acorde. insuficiente: repertorio vazio. dados_insuficientes: ha essencias, mas
# nenhuma com caracteristicas para comparar. pedido_incompleto: nenhuma emocao/preferencia com efeito.
StatusSugestao = Literal["ok", "insuficiente", "dados_insuficientes", "pedido_incompleto"]
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
    # None = usa a palavra de intensidade da descrição, se houver; senão o padrão do banco.
    intensidade: float | None = Field(default=None, ge=0, le=10)
    # Texto livre ("algo doce, floral e bem suave"): interpretado por palavras CADASTRADAS, sem IA.
    descricao: str | None = Field(default=None, max_length=600)
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
    # So fatos calculados; sem fato que sustente, vem vazio e a interface nao mostra.
    papel_na_criacao: str | None = None


class EntendimentoOut(BaseModel):
    """O que o laboratório entendeu da descrição (para a aluna conferir)."""

    emocoes: list[str]
    preferencias: list[str]
    intensidade: float | None
    negados: list[str]


class EssenciaPendenteOut(BaseModel):
    """Essência do repertório que ainda não pode entrar nos cálculos (falta Família e Percepção)."""

    id: int
    nome: str


class AcordeSugeridoOut(BaseModel):
    """Acorde enxuto sugerido."""

    itens: list[ItemSugeridoOut]
    familia_resultante: str | None
    piramide: dict[str, int] | None
    # Função de cada essência na composição, SÓ pelo papel que a aluna informou.
    funcoes: dict[str, list[str]] = {}
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
    dados_suficientes: bool
    entendimento: EntendimentoOut | None = None
    # Essências da aluna que ficaram de fora por falta de dados (ela completa e refaz a proposta).
    essencias_sem_dados: list[EssenciaPendenteOut] = []
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
