"""Schemas da calculadora de formulação (ver app/engine/formulacao.py)."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import EntradaModel, ListaEtiquetas
from app.schemas.criacoes import AcordeItemIn
from app.schemas.formulacao_pedido import Densidade, FormulacaoPedidoIn, Percentual, Positivo
from app.schemas.sugestao import Genero, ModoSugestao, SugestaoOut


class ItemFormulacaoIn(AcordeItemIn):
    """Essência do repertório + peso relativo; densidade opcional (g/ml) para dar a massa."""

    densidade_g_ml: Densidade | None = None


class FormulacaoIn(FormulacaoPedidoIn):
    """Pedido de cálculo. A origem das essências é UMA destas:

    - `criacao_id` (+ `acorde_id`, senão a última versão): o acorde da criação;
    - `itens`: essências do repertório com pesos, sem passar por uma criação.
    """

    criacao_id: int | None = Field(default=None, ge=1)
    acorde_id: int | None = Field(default=None, ge=1)
    itens: list[ItemFormulacaoIn] | None = Field(default=None, min_length=1, max_length=20)
    densidades: dict[int, Densidade] = {}

    @model_validator(mode="after")
    def _uma_origem(self) -> "FormulacaoIn":
        if (self.criacao_id is None) == (self.itens is None):
            raise ValueError("informe `criacao_id` OU `itens`, não os dois nem nenhum")
        if self.acorde_id is not None and self.criacao_id is None:
            raise ValueError("`acorde_id` exige `criacao_id`")
        if self.itens is not None:
            ids = [i.essencia_id for i in self.itens]
            if len(ids) != len(set(ids)):
                raise ValueError("cada essência só pode aparecer uma vez")
        return self


class PropostaIn(EntradaModel):
    """Fluxo completo: produto + concentração + volume + descrição em linguagem natural.

    As essências consultadas são SEMPRE as da própria aluna.
    """

    produto: str = Field(min_length=1, max_length=60)
    concentracao_pct: Percentual
    volume_ml: Positivo = Decimal(100)
    descricao: str = Field(min_length=1, max_length=600)
    emocoes: ListaEtiquetas = []
    preferencias: ListaEtiquetas = []
    intensidade: float | None = Field(default=None, ge=0, le=10)
    genero: Genero = "nao_definir"
    idade: Annotated[int, Field(ge=0, le=120)] | Annotated[str, Field(max_length=40)] | None = None
    essencias_disponiveis: Literal["todas"] | Annotated[list[int], Field(max_length=1000)] = "todas"
    modo: ModoSugestao = "somente_minhas"


class IngredienteOut(BaseModel):
    """Uma linha da formulação."""

    tipo: str
    nome: str
    essencia_id: int | None
    peso: int | None
    rotulo_peso: str | None
    percentual_produto: float
    percentual_concentrado: float | None
    volume_ml: float
    massa_g: float | None


class FormulacaoOut(BaseModel):
    """Resultado: se `valido` é falso, `ingredientes` vem vazio e `erros` explica."""

    valido: bool
    produto: str
    erros: list[str]
    avisos: list[str]
    volume_ml: float | None = None
    concentracao_pct: float | None = None
    concentrado_ml: float | None = None
    criterio: str | None = None
    ingredientes: list[IngredienteOut] = []
    massa_total_g: float | None = None
    # O que ainda precisa de confirmação técnica antes de produzir (base de exemplo, estimativas...).
    pendencias: list[str] = []
    validacao: str


class PropostaOut(BaseModel):
    """Proposta: intenção entendida + acorde + (se houver fundamento) a fórmula."""

    sugestao: SugestaoOut
    formulacao: FormulacaoOut | None = None
    # Por que não há fórmula (só aparece quando falta fundamento).
    sem_formulacao: str | None = None
    # Salvar como criação exige fórmula válida e pelo menos 2 essências (um acorde tem 2 ou mais).
    pode_salvar: bool = False
    motivo_nao_salvar: str | None = None


class FaixaOut(BaseModel):
    min: float
    max: float
    padrao: float | None = None


class ComponenteBaseOut(BaseModel):
    nome: str
    percentual: float


class ProdutoOut(BaseModel):
    """Produto disponível e seus limites (para montar o formulário)."""

    chave: str
    nome: str
    concentracoes: list[float]
    volume_ml: FaixaOut
    base: list[ComponenteBaseOut]
    # Composição da base e concentrações são de partida, ainda não confirmadas pela SÉRENÉ.
    exemplo: bool
