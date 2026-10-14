"""Autenticação: registro, login, JWT e proteção de rotas."""

from app.core.security import create_access_token
from tests.util import SENHA_PADRAO, ultimo_codigo

LISTAS_PESSOAIS = ["/essencias", "/criacoes", "/referencias", "/perfis", "/colecoes"]


def test_registro_verificacao_login_me(client):
    r = client.post(
        "/auth/register",
        json={"email": "Ana@Exemplo.com", "senha": SENHA_PADRAO, "nome": "Ana"},
    )
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["email"] == "ana@exemplo.com"  # normalizado
    assert corpo["email_verificado"] is False
    assert "senha" not in corpo and "senha_hash" not in corpo

    # Antes de confirmar o email, o login é recusado com um código estável.
    r = client.post("/auth/login", data={"username": "ana@exemplo.com", "password": SENHA_PADRAO})
    assert r.status_code == 403
    assert r.json()["codigo"] == "email_nao_verificado"

    r = client.post(
        "/auth/verificar-email",
        json={"email": "ana@exemplo.com", "codigo": ultimo_codigo("ana@exemplo.com"),
              "senha": SENHA_PADRAO},
    )
    assert r.status_code == 200
    assert client.get(
        "/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()["email_verificado"] is True

    r = client.post("/auth/login", data={"username": "ana@exemplo.com", "password": SENHA_PADRAO})
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["token_type"] == "bearer"

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["nome"] == "Ana"


def test_email_duplicado(client, nova_usuaria):
    nova_usuaria("dup@exemplo.com")
    r = client.post(
        "/auth/register", json={"email": "DUP@exemplo.com", "senha": "Outra-senha-1", "nome": "X"}
    )
    assert r.status_code == 409


def test_senha_errada_e_email_inexistente_mesma_resposta(client, nova_usuaria):
    nova_usuaria("bia@exemplo.com")
    errada = client.post("/auth/login", data={"username": "bia@exemplo.com", "password": "Errada-123"})
    inexistente = client.post("/auth/login", data={"username": "nao@existe.com", "password": "x" * 8})
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json()


def test_senha_curta_rejeitada(client):
    r = client.post("/auth/register", json={"email": "c@e.com", "senha": "123", "nome": "C"})
    assert r.status_code == 422


def test_rotas_protegidas_sem_token(client):
    for rota in ["/auth/me", *LISTAS_PESSOAIS, "/conhecimento/familias"]:
        assert client.get(rota).status_code == 401, rota


def test_token_invalido_e_expirado(client, nova_usuaria):
    nova_usuaria("exp@exemplo.com")
    assert client.get("/auth/me", headers={"Authorization": "Bearer lixo"}).status_code == 401
    expirado = create_access_token(1, expires_minutes=-1)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expirado}"}).status_code == 401


def test_token_de_usuaria_inexistente(client):
    token = create_access_token(9999)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_usuaria_nova_tem_repertorio_vazio(client, nova_usuaria):
    """Diferencial do produto: nada da base de conhecimento vira repertório."""
    h = nova_usuaria("nova@exemplo.com")
    for rota in LISTAS_PESSOAIS:
        r = client.get(rota, headers=h)
        assert r.status_code == 200, rota
        assert r.json() == [], rota
    # ...mesmo com a base de conhecimento populada pelo seed:
    assert len(client.get("/conhecimento/notas", headers=h).json()) > 0
