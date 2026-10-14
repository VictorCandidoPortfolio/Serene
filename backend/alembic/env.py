"""Ambiente do Alembic.

- A URL vem de `app.core.config` (DATABASE_URL), a mesma usada pela API.
  Ela é passada direto ao `create_engine` em vez de `config.set_main_option`,
  porque o configparser do alembic.ini interpretaria `%` em senhas.
- `target_metadata` é o metadata dos models: permite `alembic revision
  --autogenerate` e `alembic check` (que confirma que models e migrations
  estão em sincronia).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 — registra todas as tabelas no metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import connect_args

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations conectando no banco."""
    engine = create_engine(
        get_settings().database_url, poolclass=pool.NullPool, connect_args=connect_args()
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
