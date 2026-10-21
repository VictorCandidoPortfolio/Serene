"""Pedido de formulação reutilizado por acordes (versão com fórmula) e criações.

Fica num módulo próprio para `schemas/criacoes.py` e `schemas/formulacao.py`
poderem importá-lo sem import circular.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.schemas.common import EntradaModel

Positivo = Annotated[Decimal, Field(gt=0, le=100000)]
Percentual = Annotated[Decimal, Field(ge=0, le=100)]
Densidade = Annotated[Decimal, Field(gt=0, le=3)]


class FormulacaoPedidoIn(EntradaModel):
    """Produto, concentração e volume de uma formulação.

    `concentracao_pct` é obrigatória e precisa ser uma das concentrações do
    produto (7/10/15 body splash; 20/25/30 perfume). `proporcoes_pct` é
    opcional: {essencia_id: % no concentrado}, somando 100 (critério manual).
    """

    produto: str = Field(min_length=1, max_length=60)
    volume_ml: Positivo = Decimal(100)
    concentracao_pct: Percentual
    proporcoes_pct: dict[int, Annotated[Decimal, Field(gt=0, le=100)]] | None = None
