"""Regressões da auditoria de segurança (out/2026).

Cada teste reproduz um ataque ou falha encontrada na auditoria e prova que
ela continua corrigida. Se um destes quebrar, a falha voltou.
"""

import dataclasses
import threading
from collections import Counter
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core import rate_limit
from app.core.config import ConfigError, get_settings
from app.core.exceptions import DomainError
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.conta import LimiteRequisicao
from app.models.repertorio import User
from app.repositories.repertorio import EssenciaRepository
from app.services import auth_service
from tests.util import SENHA_PADRAO, ultimo_codigo


@pytest.fixture()
def c500(client):
    """Cliente que devolve o 500 em vez de levantar (como em produção)."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _config(monkeypatch, modulo, **valores):
    """Troca valores da configuração (imutável) só neste teste."""
    novo = dataclasses.replace(get_settings(), **valores)
    monkeypatch.setattr(modulo, "get_settings", lambda: novo)


# ------------------------------------------------------- limite de tentativas
def test_login_bloqueia_forca_bruta_por_email(client, nova_usuaria):
    nova_usuaria("alvo@exemplo.com")
    status = [
        client.post("/auth/login", data={"username": "alvo@exemplo.com", "password": f"Errada-{i}"})
        .status_code for i in range(rate_limit.LOGIN_POR_EMAIL.maximo + 1)
    ]
    assert status[:-1] == [401] * rate_limit.LOGIN_POR_EMAIL.maximo
    assert status[-1] == 429
    # Bloqueado, nem a senha certa entra até a janela acabar.
    r = client.post("/auth/login", data={"username": "alvo@exemplo.com", "password": SENHA_PADRAO})
    assert r.status_code == 429 and r.json()["codigo"] == "limite_requisicoes"
    assert int(r.headers["Retry-After"]) > 0


def test_login_bloqueia_varredura_por_ip(client):
    maximo = rate_limit.LOGIN_POR_IP.maximo
    status = [
        client.post("/auth/login", data={"username": f"u{i}@exemplo.com", "password": "Errada-1"}).status_code
        for i in range(maximo + 1)
    ]
    assert status[-1] == 429 and set(status[:-1]) == {401}


def test_janela_do_limite_recomeca(client, db, nova_usuaria):
    nova_usuaria("j@exemplo.com")
    for i in range(rate_limit.LOGIN_POR_EMAIL.maximo + 1):
        client.post("/auth/login", data={"username": "j@exemplo.com", "password": f"Errada-{i}"})
    # Simula a janela de 15 min passando.
    for linha in db.query(LimiteRequisicao).all():
        linha.janela_inicio -= timedelta(hours=1)
    db.commit()
    r = client.post("/auth/login", data={"username": "j@exemplo.com", "password": SENHA_PADRAO})
    assert r.status_code == 200


def test_x_forwarded_for_falso_nao_burla_o_limite(client):
    """Fora de um proxy confiável, trocar o header a cada tentativa não zera o contador."""
    maximo = rate_limit.LOGIN_POR_IP.maximo
    status = [
        client.post(
            "/auth/login",
            data={"username": f"x{i}@exemplo.com", "password": "Errada-1"},
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        ).status_code
        for i in range(maximo + 1)
    ]
    assert status[-1] == 429


def test_ip_vem_do_header_quando_atras_do_vercel(monkeypatch):
    _config(monkeypatch, rate_limit, trust_proxy_headers=True)

    class Req:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        client = None

    assert rate_limit.ip_da_requisicao(Req()) == "203.0.113.7"


def test_verificacao_limitada_por_conta_mesmo_pedindo_codigos_novos(client):
    """Somando todos os códigos, uma conta aceita no máximo N palpites por hora."""
    client.post("/auth/register", json={"email": "bf@exemplo.com", "senha": SENHA_PADRAO, "nome": "B"})
    status = []
    for rodada in range(4):
        certo = ultimo_codigo("bf@exemplo.com")
        errado = f"{(int(certo) + 1) % 10000:04d}"
        for _ in range(5):
            status.append(client.post("/auth/verificar-email", json={
                "email": "bf@exemplo.com", "codigo": errado, "senha": SENHA_PADRAO}).status_code)
        client.post("/auth/reenviar-codigo", json={"email": "bf@exemplo.com"})
    conferidos = sum(1 for s in status if s in (400,))
    assert conferidos <= rate_limit.VERIFICAR_POR_EMAIL.maximo
    assert status[-1] == 429


def test_limite_pode_ser_desligado(client, monkeypatch, nova_usuaria):
    nova_usuaria("d@exemplo.com")
    _config(monkeypatch, rate_limit, rate_limit_enabled=False)
    for i in range(rate_limit.LOGIN_POR_EMAIL.maximo + 3):
        r = client.post("/auth/login", data={"username": "d@exemplo.com", "password": f"Errada-{i}"})
    assert r.status_code == 401


# ------------------------------------------- corrida (só faz sentido no MySQL)
def test_palpites_em_paralelo_respeitam_o_limite(client, db):
    """Antes: 60 palpites simultâneos fizeram o servidor conferir 12 (limite 5)."""
    if db.get_bind().dialect.name != "mysql":
        pytest.skip("SQLite em memória serializa tudo; rode com TEST_DATABASE_URL de MySQL")
    client.post("/auth/register", json={"email": "par@exemplo.com", "senha": SENHA_PADRAO, "nome": "P"})
    errado = f"{(int(ultimo_codigo('par@exemplo.com')) + 1) % 10000:04d}"
    fabrica = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    resultados: list[str] = []

    def palpite():
        with fabrica() as s:
            try:
                auth_service.verificar_email(s, "par@exemplo.com", errado, SENHA_PADRAO)
            except DomainError as exc:
                resultados.append(exc.codigo or "")

    threads = [threading.Thread(target=palpite) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    contagem = Counter(resultados)
    assert contagem["codigo_incorreto"] + (contagem["tentativas_esgotadas"] > 0) <= get_settings().email_code_max_attempts


def test_reenvios_em_paralelo_respeitam_o_limite(client, db, monkeypatch):
    """Antes: 30 reenvios simultâneos dispararam 28 emails (limite 5/hora)."""
    if db.get_bind().dialect.name != "mysql":
        pytest.skip("SQLite em memória serializa tudo; rode com TEST_DATABASE_URL de MySQL")
    from app.core import email as email_core

    client.post("/auth/register", json={"email": "spam@exemplo.com", "senha": SENHA_PADRAO, "nome": "S"})
    fabrica = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)

    def reenvio():
        with fabrica() as s:
            try:
                auth_service.reenviar_codigo(s, "spam@exemplo.com")
            except DomainError:
                pass

    threads = [threading.Thread(target=reenvio) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    enviados = [m for m in email_core.caixa_de_saida() if m.para == "spam@exemplo.com"]
    assert len(enviados) <= get_settings().email_code_max_sends_per_hour


# --------------------------------------------------- entradas que davam 500
@pytest.mark.parametrize("rota_criar, corpo_criar, rota_editar, campo", [
    ("/essencias", {"nome": "X"}, "/essencias/{id}", "nome"),
    ("/essencias", {"nome": "X"}, "/essencias/{id}", "confianca"),
    ("/essencias", {"nome": "X"}, "/essencias/{id}", "tipo"),
    ("/essencias", {"nome": "X"}, "/essencias/{id}", "origem"),
    ("/essencias", {"nome": "X"}, "/essencias/{id}", "favorito"),
    ("/criacoes", {"nome": "C"}, "/criacoes/{id}", "nome"),
    ("/criacoes", {"nome": "C"}, "/criacoes/{id}", "status"),
    ("/referencias", {"nome": "R"}, "/referencias/{id}", "nome"),
    ("/referencias", {"nome": "R"}, "/referencias/{id}", "notas_conhecidas"),
    ("/colecoes", {"nome": "Col"}, "/colecoes/{id}", "nome"),
])
def test_null_em_campo_obrigatorio_e_422(c500, nova_usuaria, rota_criar, corpo_criar, rota_editar, campo):
    h = nova_usuaria("n@exemplo.com")
    criado = c500.post(rota_criar, json=corpo_criar, headers=h).json()
    r = c500.put(rota_editar.format(id=criado["id"]), json={campo: None}, headers=h)
    assert r.status_code == 422, r.text
    assert campo in r.text


def test_null_em_listas_continua_limpando(client, nova_usuaria):
    h = nova_usuaria("l@exemplo.com")
    e = client.post("/essencias", json={"nome": "X", "tags": ["a"]}, headers=h).json()
    r = client.put(f"/essencias/{e['id']}", json={"tags": None}, headers=h)
    assert r.status_code == 200 and r.json()["tags"] == []


@pytest.mark.parametrize("rota, corpo", [
    ("/essencias", {"nome": "x", "observacoes": "a" * 5001}),
    ("/essencias", {"nome": "x", "tags": [f"t{i}" for i in range(31)]}),
    ("/essencias", {"nome": "x", "descritores": ["a" * 61]}),
    ("/criacoes", {"nome": "x", "objetivo": "a" * 5001}),
    ("/referencias", {"nome": "x", "notas_conhecidas": ["n"] * 51}),
    ("/perfis", {"respostas": {"emocoes": ["amor"], "lixo": "y" * 20_000}}),
    ("/perfis", {"respostas": {"emocoes": ["e"] * 31}}),
])
def test_entradas_grandes_demais_sao_422(c500, nova_usuaria, rota, corpo):
    h = nova_usuaria("g@exemplo.com")
    assert c500.post(rota, json=corpo, headers=h).status_code == 422


def test_acorde_com_mais_de_20_essencias_e_422(client, nova_usuaria):
    h = nova_usuaria("a@exemplo.com")
    c = client.post("/criacoes", json={"nome": "C"}, headers=h).json()
    itens = [{"essencia_id": i, "peso": 1} for i in range(1, 22)]
    assert client.post(f"/criacoes/{c['id']}/acordes", json={"itens": itens}, headers=h).status_code == 422


def test_corpo_maior_que_1mb_e_413(client):
    r = client.post("/auth/register", content=b'{"x":"' + b"a" * 1_100_000 + b'"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_cota_por_conta(client, nova_usuaria, monkeypatch):
    monkeypatch.setattr(EssenciaRepository, "limite", 2)
    h = nova_usuaria("q@exemplo.com")
    assert client.post("/essencias", json={"nome": "A"}, headers=h).status_code == 201
    assert client.post("/essencias", json={"nome": "B"}, headers=h).status_code == 201
    r = client.post("/essencias", json={"nome": "C"}, headers=h)
    assert r.status_code == 400 and r.json()["codigo"] == "limite_atingido"


# ------------------------------------------------- cabeçalhos e infraestrutura
def test_cabecalhos_de_seguranca(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_health_ready_consulta_o_banco(client):
    assert client.get("/health/ready").json() == {"status": "ok", "banco": "ok"}


def test_conta_pendente_com_token_recebe_codigo_estavel(client, db):
    from app.core.security import create_access_token

    client.post("/auth/register", json={"email": "p@exemplo.com", "senha": SENHA_PADRAO, "nome": "P"})
    user = db.query(User).filter_by(email="p@exemplo.com").one()
    r = client.get("/essencias", headers={"Authorization": f"Bearer {create_access_token(user.id)}"})
    assert r.status_code == 403 and r.json()["codigo"] == "email_nao_verificado"


# ------------------------------------------------------------ configuração
def _carregar_config(monkeypatch, **env):
    from app.core import config

    for chave, valor in env.items():
        monkeypatch.setenv(chave, valor)
    config.get_settings.cache_clear()
    try:
        return config.get_settings()
    finally:
        config.get_settings.cache_clear()


@pytest.mark.parametrize("env, trecho", [
    ({"JWT_SECRET_KEY": "troque-esta-chave-por-uma-aleatoria-e-longa"}, "exemplo"),
    ({"JWT_ALGORITHM": "none"}, "JWT_ALGORITHM"),
    ({"JWT_ALGORITHM": "RS256"}, "JWT_ALGORITHM"),
    ({"APP_ENV": "production", "EMAIL_BACKEND": "console"}, "smtp"),
    ({"APP_ENV": "production", "EMAIL_BACKEND": "smtp", "SMTP_HOST": "h", "SMTP_FROM": "a@b.c",
      "CORS_ORIGINS": ""}, "CORS_ORIGINS"),
    ({"APP_ENV": "production", "EMAIL_BACKEND": "smtp", "SMTP_HOST": "h", "SMTP_FROM": "a@b.c",
      "CORS_ORIGINS": "*"}, "CORS_ORIGINS"),
])
def test_configuracao_insegura_impede_a_api_de_subir(monkeypatch, env, trecho):
    with pytest.raises(ConfigError, match=trecho):
        _carregar_config(monkeypatch, **env)


def test_producao_desliga_docs_e_liga_proxy_no_vercel(monkeypatch):
    cfg = _carregar_config(
        monkeypatch, VERCEL="1", EMAIL_BACKEND="smtp", SMTP_HOST="smtp.exemplo.com",
        SMTP_FROM="nao-responda@exemplo.com", CORS_ORIGINS="https://serene.vercel.app",
    )
    assert cfg.producao and not cfg.docs_enabled and cfg.trust_proxy_headers


# ------------------------------------------------------------------ senhas
def test_hash_antigo_do_passlib_continua_valendo():
    """Hash real gerado pelo passlib 1.7.4 antes da troca pelo bcrypt direto."""
    antigo = "$2b$12$MCHkVrP4qp/yRxV.9VupseqYoItNJ3ug85nGygNa8xJDFq2NUUGOO"
    assert verify_password("senha-forte-123", antigo)
    assert not verify_password("senha-errada", antigo)


def test_senha_gigante_nao_derruba_o_login():
    assert verify_password("a" * 200, hash_password("Senha-forte-1")) is False
    assert verify_password("x", "hash-malformado") is False


# --------------------------------------------- bugs de referência (essências)
def test_aplicar_referencia_na_edicao_nao_apaga_correcao_da_aluna(client, nova_usuaria, nota_validada):
    h = nova_usuaria("r@exemplo.com")
    e = client.post("/essencias", json={"nome": "Cedro", "knowledge_note_id": nota_validada,
                                        "aplicar_referencia": True}, headers=h).json()
    client.put(f"/essencias/{e['id']}", json={"v2": 9}, headers=h)  # correção da aluna
    r = client.put(f"/essencias/{e['id']}", json={"aplicar_referencia": True}, headers=h).json()
    assert r["v2"] == 9 and r["editado_da_referencia"] is True


def test_mesmo_valor_da_referencia_nao_marca_editado(client, nova_usuaria, nota_validada):
    h = nova_usuaria("s@exemplo.com")
    e = client.post("/essencias", json={"nome": "Cedro", "knowledge_note_id": nota_validada,
                                        "aplicar_referencia": True}, headers=h).json()
    r = client.put(f"/essencias/{e['id']}", json={"v2": e["v2"]}, headers=h).json()
    assert r["editado_da_referencia"] is False
