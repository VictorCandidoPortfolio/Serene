"""Fixtures compartilhadas dos testes.

Banco de teste:
- Por padrão, SQLite em memória (rápido, sem dependência externa).
- Com `TEST_DATABASE_URL` definido, usa esse banco (ex.: um MySQL
  DESCARTÁVEL) — as tabelas são criadas e APAGADAS a cada teste.

Os testes criam o schema com `create_all` (o schema das migrations é
validado à parte por `alembic check`); em produção, só Alembic cria tabelas.

As variáveis de ambiente são definidas ANTES de importar a aplicação:
`app.core.config` lê o ambiente na primeira chamada, e `load_dotenv` não
sobrescreve o que já está definido — então o `.env` de desenvolvimento
nunca é usado pelos testes.
"""

import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = "chave-de-teste-" + "x" * 40
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "30"
os.environ["CORS_ORIGINS"] = ""
# Emails vão para uma lista em memória (app.core.email.caixa_de_saida), de
# onde os testes leem o código de verificação. Intervalo de reenvio zerado
# para os testes não precisarem esperar; o teste do intervalo o liga de volta.
os.environ["EMAIL_BACKEND"] = "memory"
os.environ["EMAIL_CODE_RESEND_SECONDS"] = "0"
# Cloudinary desligado: definir vazio impede o `.env` de desenvolvimento de
# ligá-lo (os testes nunca fazem upload de verdade; test_conta usa um dublê).
for _var in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"):
    os.environ[_var] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.dependencies import get_db_session  # noqa: E402
from app.core.email import caixa_de_saida  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import popular  # noqa: E402
from app.models.knowledge import KnowledgeFamily, KnowledgeNote  # noqa: E402
from tests.util import SENHA_PADRAO, ultimo_codigo  # noqa: E402


def _criar_engine():
    """Engine de teste. SQLite precisa de StaticPool (mesma conexão em memória
    para todas as sessões) e de `PRAGMA foreign_keys=ON` (desligado por padrão
    no SQLite — sem isso os ON DELETE CASCADE não seriam testados)."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(TEST_DATABASE_URL, pool_pre_ping=True)


_engine = _criar_engine()
_SessionTest = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    """Schema novo + base de conhecimento (seed) para cada teste."""
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    with _SessionTest() as sessao:
        popular(sessao)
    sessao = _SessionTest()
    try:
        yield sessao
    finally:
        sessao.close()
        Base.metadata.drop_all(_engine)


@pytest.fixture()
def nota_validada(db):
    """Id de uma nota de referência VALIDADA (ilustrativo=False), com números.

    O seed só traz notas de exemplo; esta fixture cobre o caminho que a base
    oficial vai usar: aplicar uma referência copia também os números.
    """
    familia = db.scalar(select(KnowledgeFamily).filter_by(slug="amadeirado"))
    nota = KnowledgeNote(
        nome="Cedro validado (teste)", sinonimos=[], family_id=familia.id,
        tipo_referencia="simples", papel_tipico={"saida": 0.0, "coracao": 0.2, "fundo": 0.8},
        v1_ref=5.0, v2_ref=8.0, v3_ref=2.0, v4_ref=5.0, v6_ref=0.0,
        confianca_referencia="alta", descritores=[], ilustrativo=False,
    )
    db.add(nota)
    db.commit()
    return nota.id


@pytest.fixture()
def client(db):
    """TestClient com a sessão de banco trocada pela de teste."""

    def _sessao_teste():
        s = _SessionTest()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _sessao_teste
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _caixa_limpa():
    """Cada teste começa com a caixa de saída de emails vazia."""
    caixa_de_saida().clear()
    yield
    caixa_de_saida().clear()


@pytest.fixture()
def nova_usuaria(client):
    """Fábrica: registra, confirma o email com o código e devolve os headers com o JWT."""

    def _criar(email: str, senha: str = SENHA_PADRAO, nome: str = "Aluna") -> dict:
        r = client.post("/auth/register", json={"email": email, "senha": senha, "nome": nome})
        assert r.status_code == 201, r.text
        r = client.post(
            "/auth/verificar-email",
            json={"email": email, "codigo": ultimo_codigo(email), "senha": senha},
        )
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _criar
