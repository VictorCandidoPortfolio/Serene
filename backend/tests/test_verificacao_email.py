"""Senha forte e verificação de email por código de 4 dígitos."""

import dataclasses
import re
from datetime import timedelta

import pytest

from app.core import email as email_core
from app.core.security import create_access_token, problemas_da_senha
from app.models.conta import VerificacaoEmail
from app.models.repertorio import User
from app.services import auth_service
from tests.util import SENHA_PADRAO, ultimo_codigo


def _registrar(client, email="ana@exemplo.com", senha=SENHA_PADRAO):
    return client.post("/auth/register", json={"email": email, "senha": senha, "nome": "Ana"})


def _verificar(client, codigo, email="ana@exemplo.com", senha=SENHA_PADRAO):
    return client.post(
        "/auth/verificar-email", json={"email": email, "codigo": codigo, "senha": senha}
    )


def _codigo_errado(certo: str) -> str:
    return f"{(int(certo) + 1) % 10000:04d}"


def _config(monkeypatch, **valores):
    """Troca parâmetros de verificação só neste teste (Settings é imutável)."""
    novo = dataclasses.replace(auth_service.get_settings(), **valores)
    monkeypatch.setattr(auth_service, "get_settings", lambda: novo)


def _verificacao(db, email="ana@exemplo.com") -> VerificacaoEmail:
    db.expire_all()
    user = db.query(User).filter_by(email=email).one()
    return db.query(VerificacaoEmail).filter_by(user_id=user.id).one()


# ---------------------------------------------------------------- senha forte
@pytest.mark.parametrize(
    "senha, trecho",
    [
        ("senhafraca1", "maiúscula"),
        ("SenhaSemNumero", "número ou caractere especial"),
        ("Senha com espaco", "número ou caractere especial"),  # espaço não conta
        ("Ab1!", "pelo menos 8 caracteres"),
        ("Á1" + "ã" * 40, "longa demais"),  # 42 caracteres, mas 84 bytes
    ],
)
def test_senha_fraca_e_recusada(client, senha, trecho):
    r = _registrar(client, senha=senha)
    assert r.status_code == 422
    assert trecho in r.json()["detail"][0]["msg"]
    assert email_core.caixa_de_saida() == []  # nada é enviado


@pytest.mark.parametrize("senha", ["Senhaforte!", "Senhaforte1", "MAIUSCULA#", "Çedilha2024"])
def test_senha_forte_e_aceita(client, senha):
    assert _registrar(client, senha=senha).status_code == 201


def test_problemas_da_senha_lista_tudo_que_falta():
    assert problemas_da_senha("abc") == [
        "precisa ter pelo menos 8 caracteres",
        "precisa ter pelo menos uma letra maiúscula",
        "precisa ter pelo menos um número ou caractere especial (ex.: ! @ # $ %)",
    ]
    assert problemas_da_senha(SENHA_PADRAO) == []


# -------------------------------------------------------------- envio do código
def test_cadastro_envia_codigo_de_4_digitos_guardado_so_como_hash(client, db):
    r = _registrar(client)
    assert r.status_code == 201
    assert r.json()["codigo_expira_minutos"] == 10

    [mensagem] = email_core.caixa_de_saida()
    assert mensagem.para == "ana@exemplo.com"
    codigo = ultimo_codigo("ana@exemplo.com")
    assert re.fullmatch(r"\d{4}", codigo)

    verificacao = _verificacao(db)
    assert verificacao.codigo_hash != codigo and len(verificacao.codigo_hash) == 64


def test_falha_no_envio_nao_cria_a_conta(client, monkeypatch):
    def quebrado(_mensagem):
        raise email_core.EmailEnvioError("SMTP fora do ar")

    monkeypatch.setattr(email_core, "enviar", quebrado)
    r = _registrar(client)
    assert r.status_code == 503
    assert "SMTP" not in r.json()["detail"]  # detalhe técnico não vaza

    monkeypatch.undo()
    assert _registrar(client).status_code == 201  # o mesmo email pode tentar de novo


def test_cadastro_repetido_de_conta_pendente_retoma_a_conta(client):
    """Quem se cadastra de novo num email pendente assume a conta (nova senha, novo código)."""
    _registrar(client, senha="Primeira-111")
    antigo = ultimo_codigo("ana@exemplo.com")
    r = _registrar(client, senha="Segunda-222")
    assert r.status_code == 201
    novo = ultimo_codigo("ana@exemplo.com")
    # a senha que vale é a do último cadastro
    assert _verificar(client, novo, senha="Primeira-111").json()["codigo"] == "senha_incorreta"
    if antigo != novo:
        assert _verificar(client, antigo, senha="Segunda-222").json()["codigo"] == "codigo_incorreto"
    assert _verificar(client, novo, senha="Segunda-222").status_code == 200


def test_cadastro_de_conta_ja_confirmada_continua_409(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")
    assert _registrar(client, senha="Outra-senha-1").status_code == 409


def test_sequestro_de_conta_pre_cadastrada_foi_bloqueado(client):
    """Regressão do ataque confirmado na auditoria.

    Antes: o atacante cadastrava o email da vítima com a senha DELE; a vítima
    confirmava o código e o atacante entrava na conta dela.
    """
    vitima = "vitima@exemplo.com"
    assert _registrar(client, email=vitima, senha="Atacante-123").status_code == 201
    # A vítima se cadastra (com a senha dela) e confirma o código que recebeu.
    assert _registrar(client, email=vitima, senha="Vitima-456").status_code == 201
    r = _verificar(client, ultimo_codigo(vitima), email=vitima, senha="Vitima-456")
    assert r.status_code == 200
    # O atacante não entra mais; a vítima entra com a senha dela.
    atacante = client.post("/auth/login", data={"username": vitima, "password": "Atacante-123"})
    assert atacante.status_code == 401
    dona = client.post("/auth/login", data={"username": vitima, "password": "Vitima-456"})
    assert dona.status_code == 200


def test_codigo_certo_com_senha_errada_nao_confirma(client):
    _registrar(client)
    r = _verificar(client, ultimo_codigo("ana@exemplo.com"), senha="Errada-999")
    assert r.status_code == 400 and r.json()["codigo"] == "senha_incorreta"
    assert "4 tentativa" in r.json()["detail"]


# ------------------------------------------------------------- confirmação
def test_login_bloqueado_ate_confirmar(client):
    _registrar(client)
    errada = client.post("/auth/login", data={"username": "ana@exemplo.com", "password": "Errada-123"})
    assert errada.status_code == 401  # sem a senha, não descobre que está pendente
    certa = client.post("/auth/login", data={"username": "ana@exemplo.com", "password": SENHA_PADRAO})
    assert certa.status_code == 403 and certa.json()["codigo"] == "email_nao_verificado"


def test_codigo_certo_confirma_e_ja_loga(client):
    _registrar(client)
    r = _verificar(client, ultimo_codigo("ana@exemplo.com"))
    assert r.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email_verificado"] is True
    # O código já usado não serve mais:
    r = _verificar(client, ultimo_codigo("ana@exemplo.com"))
    assert r.status_code == 400 and r.json()["codigo"] == "email_ja_verificado"


def test_tentativas_erradas_esgotam_o_codigo(client):
    _registrar(client)
    certo = ultimo_codigo("ana@exemplo.com")
    errado = _codigo_errado(certo)
    for restantes in (4, 3, 2, 1):
        r = _verificar(client, errado)
        assert r.status_code == 400
        assert f"{restantes} tentativa" in r.json()["detail"]
    r = _verificar(client, errado)
    assert r.status_code == 429 and r.json()["codigo"] == "tentativas_esgotadas"
    # Esgotado, nem o código certo é aceito...
    assert _verificar(client, certo).status_code == 429
    # ...até pedir um novo.
    assert client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"}).status_code == 202
    assert _verificar(client, ultimo_codigo("ana@exemplo.com")).status_code == 200


def test_codigo_expirado(client, db):
    _registrar(client)
    verificacao = _verificacao(db)
    verificacao.expira_em -= timedelta(minutes=11)
    db.commit()
    r = _verificar(client, ultimo_codigo("ana@exemplo.com"))
    assert r.status_code == 400 and r.json()["codigo"] == "codigo_expirado"


def test_codigo_mal_formado_e_email_sem_conta(client):
    _registrar(client)
    for codigo in ("12a4", "123", "12345"):
        assert _verificar(client, codigo).status_code == 422
    assert _verificar(client, "1234", email="ninguem@exemplo.com").status_code == 400


def test_token_de_conta_pendente_nao_acessa_nada(client, db):
    _registrar(client)
    user = db.query(User).filter_by(email="ana@exemplo.com").one()
    token = create_access_token(user.id)  # simula um token emitido indevidamente
    assert client.get("/essencias", headers={"Authorization": f"Bearer {token}"}).status_code == 403


# ------------------------------------------------------------------- reenvio
def test_reenvio_troca_o_codigo(client):
    _registrar(client)
    antigo = ultimo_codigo("ana@exemplo.com")
    novo = antigo
    while novo == antigo:  # 1 chance em 10.000 de sair igual: pede outro
        client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"})
        novo = ultimo_codigo("ana@exemplo.com")
    assert _verificar(client, antigo).status_code == 400  # o antigo deixou de valer
    assert _verificar(client, novo).status_code == 200


def test_reenvio_respeita_intervalo_minimo(client, monkeypatch):
    _config(monkeypatch, email_code_resend_seconds=60)
    _registrar(client)
    r = client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"})
    assert r.status_code == 429
    assert 0 < r.json()["retry_after"] <= 60
    assert r.headers["Retry-After"] == str(r.json()["retry_after"])
    assert len(email_core.caixa_de_saida()) == 1


def test_reenvio_respeita_limite_por_hora(client, db, monkeypatch):
    _config(monkeypatch, email_code_max_sends_per_hour=2)
    _registrar(client)  # envio 1
    assert client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"}).status_code == 202
    r = client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"})
    assert r.status_code == 429 and "Limite" in r.json()["detail"]
    # Passada a janela de 1 hora, volta a poder.
    verificacao = _verificacao(db)
    verificacao.janela_inicio -= timedelta(hours=1)
    db.commit()
    assert client.post("/auth/reenviar-codigo", json={"email": "ana@exemplo.com"}).status_code == 202


def test_reenvio_nao_revela_quais_emails_existem(client, nova_usuaria):
    nova_usuaria("verificada@exemplo.com")
    _registrar(client)
    email_core.caixa_de_saida().clear()
    respostas = [
        client.post("/auth/reenviar-codigo", json={"email": e})
        for e in ("ninguem@exemplo.com", "verificada@exemplo.com", "ana@exemplo.com")
    ]
    assert {r.status_code for r in respostas} == {202}
    assert len({r.json()["mensagem"] for r in respostas}) == 1
    # Só a conta pendente recebeu email.
    assert [m.para for m in email_core.caixa_de_saida()] == ["ana@exemplo.com"]
