"""Essências cadastradas com o nome de um GRUPO de cheiro passam a usar a família real da base.

O cadastro simples (0012) gravou o nome do grupo escolhido ("Fresco", "Gourmand/Doce",
"Âmbar/Envolvente") em `essencias.familia`. O cadastro agora usa as famílias
cadastradas na base, então esses três nomes (que não existem lá) viram a família
correspondente: Fresco -> Cítrico, Gourmand/Doce -> Gourmand, Âmbar/Envolvente -> Ambarado.
Os outros cinco grupos (Frutado, Floral, Aromático, Amadeirado, Almiscarado) já são
nomes de família. Só ajusta o texto de `familia`; nenhum outro valor muda.

Downgrade: não desfaz (o mapeamento inverso é ambíguo: "Cítrico" pode ter sido digitado
em qualquer época); as essências continuam válidas.

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENOMEAR = {"Fresco": "Cítrico", "Gourmand/Doce": "Gourmand", "Âmbar/Envolvente": "Ambarado"}


def upgrade() -> None:
    """Troca o nome do grupo pela família real nas essências já cadastradas."""
    essencias = sa.table("essencias", sa.column("familia", sa.String))
    for antigo, novo in RENOMEAR.items():
        op.execute(essencias.update().where(essencias.c.familia == antigo).values(familia=novo))


def downgrade() -> None:
    """Sem desfazer: o mapeamento inverso é ambíguo e as essências continuam válidas."""
