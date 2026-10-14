"""Tipos Pydantic reutilizados por vários recursos.

Por que schemas separados dos models: a API nunca expõe o model SQLAlchemy
direto. Assim, adicionar uma coluna interna (ex.: um hash) não a vaza
automaticamente na resposta, e a entrada nunca aceita campos de posse
(`user_id`, `criacao_id`) — eles vêm do token e da URL.
"""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Escala dos eixos do motor (ver app/engine/axes.py).
Eixo = Annotated[float, Field(ge=0, le=10)]
Fracao = Annotated[float, Field(ge=0, le=1)]
Confianca = Literal["alta", "media", "baixa"]
TipoReferencia = Literal["simples", "composta", "desconhecida"]

# Limites de tamanho. Sem eles, um texto acima de 64 KB estourava a coluna TEXT
# do MySQL (erro 500) e listas sem fim enchiam o banco. Os valores sobram para
# uso real e cortam abuso.
TEXTO_LONGO_MAX = 5000
ETIQUETAS_MAX = 30
TextoLongo = Annotated[str, Field(max_length=TEXTO_LONGO_MAX)]
Etiqueta = Annotated[str, Field(min_length=1, max_length=60)]
ListaEtiquetas = Annotated[list[Etiqueta], Field(max_length=ETIQUETAS_MAX)]
ItemTexto = Annotated[str, Field(min_length=1, max_length=160)]
ListaItens = Annotated[list[ItemTexto], Field(max_length=50)]


class ORMModel(BaseModel):
    """Base de schemas de SAÍDA: permite construir a partir de objetos ORM."""

    model_config = ConfigDict(from_attributes=True)


class EntradaModel(BaseModel):
    """Base de schemas de ENTRADA: rejeita campos desconhecidos.

    `extra="forbid"` faz um `{"user_id": 2}` no corpo virar erro 422 em vez
    de ser ignorado em silêncio — deixa explícito que posse não se informa.
    """

    model_config = ConfigDict(extra="forbid")


class EdicaoModel(EntradaModel):
    """Base de schemas de EDIÇÃO PARCIAL (PUT que só altera o que foi enviado).

    Nesses schemas todo campo é opcional (`None` = "não enviado"). Mas mandar
    `null` explicitamente num campo obrigatório no banco (ex.: `"nome": null`)
    passava pela validação e derrubava a API com erro 500. Cada subclasse
    lista em `campos_nao_nulos` o que não pode ser apagado assim.
    """

    campos_nao_nulos: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _rejeitar_nulos(self):
        nulos = [
            c for c in self.campos_nao_nulos
            if c in self.model_fields_set and getattr(self, c) is None
        ]
        if nulos:
            raise ValueError(f"não aceita valor vazio (null) em: {', '.join(nulos)}")
        return self


class Papel(BaseModel):
    """Afinidade com cada camada da pirâmide, 0..1."""

    saida: Fracao = 0
    coracao: Fracao = 0
    fundo: Fracao = 0


class LacunaOut(BaseModel):
    """Lacuna identificada pelo motor (sempre uma categoria, nunca uma essência)."""

    tipo: str
    mensagem: str
    detalhe: dict = Field(default_factory=dict)
