"""Engine e fábrica de sessões do SQLAlchemy.

A engine é criada uma vez por processo (ela mantém o pool de conexões).
Cada requisição HTTP recebe a sua própria `Session` via
`app.core.dependencies.get_db_session`.

No Vercel cada instância da função tem o seu próprio pool; por isso ele é
pequeno (muitas instâncias × pool grande esgotariam o limite de conexões do
MySQL hospedado).
"""

import certifi
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def connect_args() -> dict:
    """TLS na conexão com o MySQL, quando `DATABASE_SSL=true`.

    O certificado da autoridade é SEMPRE informado: sem ele, o PyMySQL
    cifra a conexão mas aceita qualquer servidor (não verifica o
    certificado), o que permitiria interceptar a senha do banco. Usa o
    certificado do provedor (`DATABASE_SSL_CA`) se houver; senão, o pacote de
    autoridades públicas do `certifi` (serve para TiDB Cloud, PlanetScale e
    outros que usam certificados públicos).
    """
    cfg = get_settings()
    if not cfg.database_ssl or not cfg.database_url.startswith("mysql"):
        return {}
    return {"ssl": {"ca": cfg.database_ssl_ca or certifi.where()}}


def _criar_engine():
    """Engine do banco. Parâmetros de pool só se aplicam ao MySQL."""
    url = get_settings().database_url
    if not url.startswith("mysql"):
        return create_engine(url)
    return create_engine(
        url,
        connect_args=connect_args(),
        # O MySQL derruba conexões ociosas (wait_timeout). pre_ping testa a
        # conexão antes de usar e evita o erro "MySQL server has gone away".
        pool_pre_ping=True,
        # Provedores hospedados costumam derrubar conexões ociosas em ~5 min.
        pool_recycle=280,
        pool_size=3,
        max_overflow=5,
    )


engine = _criar_engine()

# expire_on_commit=False: depois do commit, os objetos continuam legíveis
# para serem serializados na resposta sem um novo SELECT por atributo.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
