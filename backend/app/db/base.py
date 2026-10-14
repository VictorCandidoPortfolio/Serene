"""Base declarativa do SQLAlchemy 2.0.

A `naming_convention` dá nomes determinísticos a índices, uniques, FKs e
checks. Sem ela, o MySQL inventa nomes e o Alembic não consegue gerar
migrations de alteração/remoção de constraints de forma confiável.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe-mãe de todos os models. Não contém colunas."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
