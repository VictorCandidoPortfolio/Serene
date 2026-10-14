"""Schemas de criações, acordes (versões) e testes."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.engine.axes import NOMES_PESO
from app.schemas.common import EdicaoModel, EntradaModel, LacunaOut, ORMModel, TextoLongo
from app.schemas.outros import RespostasPerfil

StatusCriacao = Literal["rascunho", "em_ajuste", "aprovada", "arquivada"]
PesoRelativo = Literal["pouco", "medio", "bastante"]
# Um acorde real tem poucas essências. O limite também protege o servidor: a
# compatibilidade compara todos os pares, e o custo cresce com o quadrado
# (150 essências geravam 11 mil pares e 1,6 MB de resposta).
MAX_ITENS_ACORDE = 20
Percepcao = Literal["baixa", "media", "alta"]


# ------------------------------------------------------------------ criações
class CriacaoCreate(EntradaModel):
    """Nova criação. A direção (opcional) vem de UMA destas origens:

    - `perfil_id`: um perfil olfativo já criado;
    - `intencao`: território(s), emoções e público escolhidos na hora;
    - `referencia_id`: um perfume de referência (direção estimada).
    """

    nome: str = Field(min_length=1, max_length=160)
    objetivo: TextoLongo | None = None
    status: StatusCriacao = "rascunho"
    perfil_id: int | None = None
    intencao: RespostasPerfil | None = None
    referencia_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _uma_origem(self) -> "CriacaoCreate":
        origens = [o for o in (self.perfil_id, self.intencao, self.referencia_id) if o is not None]
        if len(origens) > 1:
            raise ValueError("escolha só uma origem de direção: perfil, intenção ou referência")
        return self


class CriacaoUpdate(EdicaoModel):
    """Edição parcial da criação (nome, objetivo, status, perfil)."""

    campos_nao_nulos = ("nome", "status")

    nome: str | None = Field(default=None, min_length=1, max_length=160)
    objetivo: TextoLongo | None = None
    status: StatusCriacao | None = None
    perfil_id: int | None = None


class CriacaoOut(ORMModel):
    """Criação como devolvida pela API."""

    id: int
    nome: str
    objetivo: str | None
    direcao: dict[str, Any] | None
    status: str
    criado_em: datetime | None = None
    atualizado_em: datetime | None = None


# ------------------------------------------------------------------- acordes
class AcordeItemIn(EntradaModel):
    """Uma essência do repertório + peso RELATIVO no acorde.

    O peso aceita "pouco"/"medio"/"bastante" ou 1/2/3 e é normalizado para o
    nome. Nunca é porcentagem de produto (regra de negócio 1).
    """

    essencia_id: int
    peso: PesoRelativo

    @field_validator("peso", mode="before")
    @classmethod
    def _peso_numerico(cls, valor: Any) -> Any:
        if isinstance(valor, int) and not isinstance(valor, bool) and valor in NOMES_PESO:
            return NOMES_PESO[valor]
        if isinstance(valor, str):
            return valor.strip().lower().replace("é", "e")
        return valor


class AcordeCreate(EntradaModel):
    """Nova versão de acorde: 2 a N essências distintas do repertório."""

    itens: list[AcordeItemIn] = Field(min_length=2, max_length=MAX_ITENS_ACORDE)
    # Opcional: o que mudou nesta versão e por quê (aparece no histórico).
    motivo: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _sem_repetidas(self) -> "AcordeCreate":
        ids = [i.essencia_id for i in self.itens]
        if len(ids) != len(set(ids)):
            raise ValueError("Cada essência só pode aparecer uma vez no acorde.")
        return self


class AcordeOut(ORMModel):
    """Uma versão de acorde com o resultado do motor."""

    id: int
    criacao_id: int
    versao: int
    itens: list[dict[str, Any]]
    vetor: dict[str, Any] | None
    papel: dict[str, Any] | None
    familia_resultante: str | None
    compatibilidade: dict[str, Any] | None
    motivo: str | None = None
    criado_em: datetime | None = None


class AjusteIn(EntradaModel):
    """Pedido de ajuste: chave de uma regra `vetor_movimento` (ex.: "mais_fresco")."""

    movimento: str = Field(min_length=1, max_length=80)


class SugestaoAjusteOut(ORMModel):
    """Um ajuste possível usando só essências do repertório."""

    acao: str
    essencia_id: int
    nome: str
    peso_de: int | None
    peso_para: int | None
    descricao: str
    progresso: float
    efeito_colateral: float
    vetor_resultante: dict[str, float | None]
    itens_resultantes: list[tuple[int, int]]


class AjusteOut(ORMModel):
    """Resultado do motor de ajuste. Nada é gravado — a aluna decide."""

    movimento: str
    descricao: str | None
    vetor_atual: dict[str, float | None]
    alcancavel: bool
    sugestoes: list[SugestaoAjusteOut]
    lacuna: LacunaOut | None


# -------------------------------------------------------------------- testes
class TesteCreate(EntradaModel):
    """Registro de um teste (sempre uma nova versão)."""

    acorde_id: int | None = None
    resultado_percebido: TextoLongo | None = None
    persistencia_percebida: Percepcao | None = None
    intensidade_percebida: Percepcao | None = None
    o_que_ficou_bom: TextoLongo | None = None
    o_que_precisa_mudar: TextoLongo | None = None
    nota: int | None = Field(default=None, ge=0, le=10)
    proximo_ajuste: TextoLongo | None = None


class TesteOut(ORMModel):
    """Teste como devolvido pela API."""

    id: int
    criacao_id: int
    acorde_id: int | None
    versao: int
    resultado_percebido: str | None
    persistencia_percebida: str | None
    intensidade_percebida: str | None
    o_que_ficou_bom: str | None
    o_que_precisa_mudar: str | None
    nota: int | None
    proximo_ajuste: str | None
    criado_em: datetime | None = None


# ----------------------------------------------------------------- identidade
class TerritorioIdentificadoOut(ORMModel):
    """Um território que o acorde transmite."""

    chave: str
    nome: str
    proximidade: int
    eixos_comparados: list[str]
    explicacao: str


class IdentidadeOut(ORMModel):
    """Identidade de uma versão de acorde: família dominante + territórios."""

    acorde_id: int
    versao: int
    familia_resultante: str | None
    territorios: list[TerritorioIdentificadoOut]
    avisos: list[str]
