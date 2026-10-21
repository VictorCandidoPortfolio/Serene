"""Schemas de essências (repertório pessoal)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

# ------------------------------------------------------------------- ficha
# Três tipos de informação, nunca misturados:
# - DOCUMENTADA: está na ficha (com `documentacao.referencia`; limites exigem `fonte`);
# - AVALIAÇÃO SENSORIAL: eixos v1–v6 e descritores, que são percepção da aluna;
# - DESCONHECIDA: campo ausente. O sistema nunca preenche por conta própria.
Texto120 = Annotated[str, Field(min_length=1, max_length=120)]
Texto300 = Annotated[str, Field(min_length=1, max_length=300)]
Nota = Annotated[str, Field(min_length=1, max_length=60)]
CategoriaProduto = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,40}$")]


class FichaIdentificacao(EntradaModel):
    """Identificação do produto do fornecedor."""

    nome_comercial: Texto120 | None = None
    codigo: Texto120 | None = None
    cas: Texto120 | None = None
    lote: Texto120 | None = None
    # Densidade da ficha técnica (g/ml); só com ela a quantidade em gramas é calculada.
    densidade_g_ml: Annotated[float, Field(gt=0, le=3)] | None = None


class FichaNotas(EntradaModel):
    """Notas olfativas por camada, como descritas na documentação."""

    saida: Annotated[list[Nota], Field(max_length=20)] | None = None
    coracao: Annotated[list[Nota], Field(max_length=20)] | None = None
    fundo: Annotated[list[Nota], Field(max_length=20)] | None = None


class FichaDocumentacao(EntradaModel):
    """De onde vem a informação documentada."""

    tipo: Literal["ficha_tecnica", "ifra", "sds", "outro"] | None = None
    referencia: Texto300 | None = None


class FichaLimite(EntradaModel):
    """Limite de uso DOCUMENTADO para uma categoria (exige a fonte)."""

    max_pct_produto: float = Field(gt=0, le=100)
    fonte: Texto300


class FichaRestricoes(EntradaModel):
    """Restrições documentadas. As categorias listadas BLOQUEIAM o uso no cálculo."""

    categorias_nao_indicadas: Annotated[list[CategoriaProduto], Field(max_length=10)] | None = None
    observacoes: Texto300 | None = None


class Ficha(EntradaModel):
    """Ficha técnica da essência (tudo opcional)."""

    identificacao: FichaIdentificacao | None = None
    notas: FichaNotas | None = None
    documentacao: FichaDocumentacao | None = None
    limites_uso: Annotated[dict[CategoriaProduto, FichaLimite], Field(max_length=10)] | None = None
    restricoes: FichaRestricoes | None = None


class _CadastroSimples(BaseModel):
    """Cadastro de essência em 3 campos: o que a aluna informa.

    O servidor é a ÚNICA fonte de v1–v5, papel, tipo, confiança e origem: se o
    cliente enviar qualquer um deles (ou qualquer campo desconhecido), é
    IGNORADO, sem erro. Só posse (`user_id`, `id`) é rejeitada de propósito.
    Os textos são validados no service, com mensagens em português simples.
    """

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _sem_posse(cls, dados):
        if isinstance(dados, dict) and {"user_id", "id"} & set(dados):
            raise ValueError("posse do registro não se informa")
        return dados


class EssenciaCreate(_CadastroSimples):
    """Nome, Família (um dos grupos de cheiro) e Percepção (fria/neutra/quente)."""

    nome: str = Field(default="", max_length=200)
    familia: str = Field(default="", max_length=120)
    percepcao: str = Field(default="", max_length=20)
    # Id da nota que a aluna TOCOU para confirmar o reconhecimento pelo nome.
    aceitou_nota_id: int | None = Field(default=None, ge=1)


class EssenciaUpdate(_CadastroSimples):
    """Edição: os mesmos 3 campos (os omitidos ficam como estão). Os derivados são recalculados."""

    nome: str | None = Field(default=None, max_length=200)
    familia: str | None = Field(default=None, max_length=120)
    percepcao: str | None = Field(default=None, max_length=20)
    aceitou_nota_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _sem_nulos(self) -> "EssenciaUpdate":
        nulos = [c for c in ("nome", "familia", "percepcao") if c in self.model_fields_set and getattr(self, c) is None]
        if nulos:
            raise ValueError(f"não aceita valor vazio (null) em: {', '.join(nulos)}")
        return self


class FichaIn(Ficha):
    """Ficha técnica documentada (fora do cadastro simples; ver PUT /essencias/{id}/ficha)."""


class SugestaoNomeOut(BaseModel):
    """Reconhecimento pelo nome: só SUGESTÃO, nada é gravado nem aplicado às escuras."""

    encontrada: bool
    nivel: Literal["exata", "parecida"] | None = None
    nota_id: int | None = None
    nota_nome: str | None = None
    familia: str | None = None
    percepcao: str | None = None
    aviso_educativo: str | None = None


class OpcaoCadastroOut(BaseModel):
    chave: str
    nome: str


class OpcoesCadastroOut(BaseModel):
    """Opções dos chips do cadastro (vêm do banco)."""

    familias: list[OpcaoCadastroOut]
    percepcoes: list[OpcaoCadastroOut]


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
    percepcao: str | None = None
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
    ficha: dict | None = None
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
    # True = nota de exemplo (não validada): vem sem números, só classificação.
    ilustrativa: bool = False
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
    pares_avaliados: int = 0
    pares_total: int = 0
    # A nota usa relações/regras de exemplo (ainda não validadas pela SÉRENÉ).
    base_exemplo: bool = False
