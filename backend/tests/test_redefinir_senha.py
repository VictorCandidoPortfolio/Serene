"""Redefinição de senha ("esqueci minha senha") por código enviado ao email."""

import dataclasses

from app.core import email as email_core
from app.models.conta import VerificacaoEmail
from app.models.repertorio import User
from app.services import auth_service
from tests.util import SENHA_PADRAO, ultimo_codigo

NOVA = "Nova-senha-456"


def _esqueci(client, email="ana@exemplo.com"):
    return client.post("/auth/esqueci-senha", json={"email": email})


def _redefinir(client, codigo, nova=NOVA, email="ana@exemplo.com"):
    return client.post(
        "/auth/redefinir-senha", json={"email": email, "codigo": codigo, "nova_senha": nova}
    )


def _login(client, senha, email="ana@exemplo.com"):
    return client.post("/auth/login", data={"username": email, "password": senha})


def _errado(certo: str) -> str:
    return f"{(int(certo) + 1) % 10000:04d}"


def test_fluxo_completo_troca_a_senha(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")

    r = _esqueci(client)
    assert r.status_code == 202
    codigo = ultimo_codigo("ana@exemplo.com")

    r = _redefinir(client, codigo)
    assert r.status_code == 200, r.text
    assert _login(client, SENHA_PADRAO).status_code == 401  # a antiga não vale mais
    assert _login(client, NOVA).status_code == 200


def test_resposta_igual_para_email_inexistente_e_sem_envio(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")
    existente = _esqueci(client)
    antes = len(email_core.caixa_de_saida())
    inexistente = _esqueci(client, "ninguem@exemplo.com")
    assert existente.status_code == inexistente.status_code == 202
    assert existente.json() == inexistente.json()
    assert len(email_core.caixa_de_saida()) == antes  # nada enviado


def test_conta_pendente_nao_recebe_codigo_de_redefinicao(client):
    client.post(
        "/auth/register", json={"email": "p@exemplo.com", "senha": SENHA_PADRAO, "nome": "P"}
    )
    antes = len(email_core.caixa_de_saida())
    assert _esqueci(client, "p@exemplo.com").status_code == 202
    assert len(email_core.caixa_de_saida()) == antes


def test_codigo_errado_conta_tentativa_e_nao_troca_a_senha(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    codigo = ultimo_codigo("ana@exemplo.com")
    r = _redefinir(client, _errado(codigo))
    assert r.status_code == 400 and r.json()["codigo"] == "codigo_incorreto"
    assert _login(client, SENHA_PADRAO).status_code == 200


def test_tentativas_esgotadas_bloqueiam_ate_o_codigo_certo(client, nova_usuaria, monkeypatch):
    nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    codigo = ultimo_codigo("ana@exemplo.com")
    for _ in range(auth_service.get_settings().email_code_max_attempts):
        _redefinir(client, _errado(codigo))
    r = _redefinir(client, codigo)
    assert r.status_code == 429 and r.json()["codigo"] == "tentativas_esgotadas"
    assert _login(client, SENHA_PADRAO).status_code == 200


def test_codigo_expirado(client, nova_usuaria, db):
    nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    codigo = ultimo_codigo("ana@exemplo.com")
    user = db.query(User).filter_by(email="ana@exemplo.com").one()
    v = db.query(VerificacaoEmail).filter_by(user_id=user.id).one()
    v.expira_em = v.expira_em.replace(year=2000)
    db.commit()
    r = _redefinir(client, codigo)
    assert r.status_code == 400 and r.json()["codigo"] == "codigo_expirado"


def test_codigo_nao_vale_duas_vezes(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    codigo = ultimo_codigo("ana@exemplo.com")
    assert _redefinir(client, codigo).status_code == 200
    assert _redefinir(client, codigo, nova="Outra-senha-789").status_code == 400
    assert _login(client, NOVA).status_code == 200


def test_nova_senha_fraca_e_recusada_sem_gastar_o_codigo(client, nova_usuaria):
    nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    codigo = ultimo_codigo("ana@exemplo.com")
    assert _redefinir(client, codigo, nova="fraca").status_code == 422
    assert _redefinir(client, codigo).status_code == 200  # o código continua valendo


def test_email_sem_conta_recebe_erro_generico(client):
    r = _redefinir(client, "1234", email="ninguem@exemplo.com")
    assert r.status_code == 400 and "inválido" in r.json()["detail"]


def test_reenvio_antes_do_intervalo_e_barrado(client, nova_usuaria, monkeypatch):
    novo = dataclasses.replace(auth_service.get_settings(), email_code_resend_seconds=60)
    monkeypatch.setattr(auth_service, "get_settings", lambda: novo)
    nova_usuaria("ana@exemplo.com")
    assert _esqueci(client).status_code == 202
    assert _esqueci(client).status_code == 429


def test_redefinir_derruba_o_token_de_outro_dispositivo(client, nova_usuaria):
    headers = nova_usuaria("ana@exemplo.com")
    assert client.get("/auth/me", headers=headers).status_code == 200

    _esqueci(client)
    assert _redefinir(client, ultimo_codigo("ana@exemplo.com")).status_code == 200

    # O token antigo (outro dispositivo) não vale mais...
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/essencias", headers=headers).status_code == 401
    # ...e só a senha nova gera um token que funciona.
    token = _login(client, NOVA).json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_redefinicao_que_falha_nao_derruba_a_sessao(client, nova_usuaria):
    headers = nova_usuaria("ana@exemplo.com")
    _esqueci(client)
    _redefinir(client, _errado(ultimo_codigo("ana@exemplo.com")))
    assert client.get("/auth/me", headers=headers).status_code == 200
