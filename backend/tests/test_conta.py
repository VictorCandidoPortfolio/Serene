"""Conta logada: editar nome, trocar senha sem deslogar e foto de perfil.

O Cloudinary nunca é chamado de verdade: `_post` (a única função que usa a
rede) é trocada por um dublê que registra as chamadas.
"""

import base64
import dataclasses

import pytest

from app.core import cloudinary
from app.core.config import ConfigError, _config_cloudinary
from app.core.exceptions import FotoIndisponivelError
from tests.util import SENHA_PADRAO

NOVA_SENHA = "Outra-senha-456"
# Cabeçalho PNG válido seguido de bytes quaisquer: basta para a checagem de
# conteúdo (o dublê do Cloudinary não decodifica a imagem).
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _data_uri(conteudo: bytes = PNG, tipo: str = "image/png") -> str:
    return f"data:{tipo};base64,{base64.b64encode(conteudo).decode()}"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ dados
def test_editar_nome(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com", nome="Ana")
    r = client.put("/auth/me", json={"nome": "  Ana Maria  "}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["nome"] == "Ana Maria"
    assert client.get("/auth/me", headers=h).json()["nome"] == "Ana Maria"


@pytest.mark.parametrize(
    "corpo",
    [{"nome": "   "}, {"nome": None}, {"nome": ""}, {"email": "outro@exemplo.com"}],
)
def test_edicao_invalida_e_422(client, nova_usuaria, corpo):
    h = nova_usuaria("ana@exemplo.com", nome="Ana")
    assert client.put("/auth/me", json=corpo, headers=h).status_code == 422
    assert client.get("/auth/me", headers=h).json()["nome"] == "Ana"


def test_editar_exige_login(client):
    assert client.put("/auth/me", json={"nome": "X"}).status_code == 401


# ------------------------------------------------------------------ senha
def test_trocar_senha_mantem_esta_sessao_e_derruba_as_outras(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    outro_aparelho = client.post(
        "/auth/login", data={"username": "ana@exemplo.com", "password": SENHA_PADRAO}
    ).json()["access_token"]

    r = client.post(
        "/auth/me/senha", json={"senha_atual": SENHA_PADRAO, "nova_senha": NOVA_SENHA}, headers=h
    )
    assert r.status_code == 200, r.text
    novo = _bearer(r.json()["access_token"])

    assert client.get("/auth/me", headers=novo).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401
    assert client.get("/auth/me", headers=_bearer(outro_aparelho)).status_code == 401

    def login(senha):
        return client.post("/auth/login", data={"username": "ana@exemplo.com", "password": senha})

    assert login(SENHA_PADRAO).status_code == 401
    assert login(NOVA_SENHA).status_code == 200


def test_senha_atual_errada_e_400_e_nao_derruba_a_sessao(client, nova_usuaria):
    """400 (e não 401): um 401 faria o frontend deslogar a usuária."""
    h = nova_usuaria("ana@exemplo.com")
    r = client.post(
        "/auth/me/senha", json={"senha_atual": "Errada-123", "nova_senha": NOVA_SENHA}, headers=h
    )
    assert r.status_code == 400
    assert r.json()["codigo"] == "senha_atual_incorreta"
    assert client.get("/auth/me", headers=h).status_code == 200


def test_nova_senha_fraca_e_422(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    r = client.post(
        "/auth/me/senha", json={"senha_atual": SENHA_PADRAO, "nova_senha": "fraca"}, headers=h
    )
    assert r.status_code == 422


def test_nova_senha_igual_a_atual_e_400(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    r = client.post(
        "/auth/me/senha", json={"senha_atual": SENHA_PADRAO, "nova_senha": SENHA_PADRAO}, headers=h
    )
    assert r.status_code == 400
    assert r.json()["codigo"] == "senha_repetida"


def test_troca_de_senha_tem_limite_por_conta(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    status = [
        client.post(
            "/auth/me/senha", json={"senha_atual": f"Chute-{i}", "nova_senha": NOVA_SENHA}, headers=h
        ).status_code
        for i in range(11)
    ]
    assert status[:10] == [400] * 10
    assert status[10] == 429


# ------------------------------------------------------------------- foto
@pytest.fixture()
def cloudinary_falso(monkeypatch):
    """Liga o Cloudinary com credenciais de teste e grava as chamadas de rede."""
    cfg = dataclasses.replace(
        cloudinary.get_settings(),
        cloudinary_cloud_name="demo",
        cloudinary_api_key="123456",
        cloudinary_api_secret="segredo-de-teste",
        cloudinary_folder="serene/perfis",
    )
    monkeypatch.setattr(cloudinary, "get_settings", lambda: cfg)
    chamadas = []

    def _post(url, campos):
        chamadas.append((url, dict(campos)))
        if url.endswith("/upload"):
            pid = f"{campos['folder']}/{campos['public_id']}"
            return {"secure_url": f"https://res.cloudinary.com/demo/image/upload/v1/{pid}.png", "public_id": pid}
        return {"result": "ok"}

    monkeypatch.setattr(cloudinary, "_post", _post)
    return chamadas


def test_assinatura_igual_ao_exemplo_da_documentacao_do_cloudinary():
    params = {
        "eager": "w_400,h_300,c_pad|w_260,h_200,c_crop",
        "public_id": "sample_image",
        "timestamp": "1315060510",
        "file": "nao-entra-na-assinatura",
        "api_key": "nem-isto",
    }
    assert cloudinary.assinar(params, "abcd") == "bfd09f95f331f558cbd1320e67aa8d488770583e"


def test_enviar_foto_salva_a_url(client, nova_usuaria, cloudinary_falso):
    h = nova_usuaria("ana@exemplo.com")
    r = client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    assert r.status_code == 200, r.text
    url = r.json()["foto_url"]
    assert url.startswith("https://res.cloudinary.com/demo/image/upload/")
    assert client.get("/auth/me", headers=h).json()["foto_url"] == url

    endereco, campos = cloudinary_falso[0]
    assert endereco == "https://api.cloudinary.com/v1_1/demo/image/upload"
    assert campos["file"] == _data_uri()
    assert campos["folder"] == "serene/perfis"
    assert campos["api_key"] == "123456"
    assert "segredo-de-teste" not in str(campos)  # o segredo só entra na assinatura
    assert campos["signature"] == cloudinary.assinar(campos, "segredo-de-teste")


def test_trocar_foto_apaga_a_antiga(client, nova_usuaria, cloudinary_falso):
    h = nova_usuaria("ana@exemplo.com")
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    primeira = cloudinary_falso[0][1]
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)

    acoes = [url.rsplit("/", 1)[1] for url, _ in cloudinary_falso]
    assert acoes == ["upload", "upload", "destroy"]
    assert cloudinary_falso[2][1]["public_id"] == f"{primeira['folder']}/{primeira['public_id']}"


def test_nome_do_arquivo_nao_e_adivinhavel(client, nova_usuaria, cloudinary_falso):
    h = nova_usuaria("ana@exemplo.com")
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    ids = [c["public_id"] for url, c in cloudinary_falso if url.endswith("/upload")]
    assert ids[0] != ids[1] and len(ids[0]) > 12


def test_remover_foto(client, nova_usuaria, cloudinary_falso):
    h = nova_usuaria("ana@exemplo.com")
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    r = client.delete("/auth/me/foto", headers=h)
    assert r.status_code == 200
    assert r.json()["foto_url"] is None
    assert cloudinary_falso[-1][0].endswith("/destroy")


@pytest.mark.parametrize(
    ("imagem", "codigo"),
    [
        (_data_uri(b"<svg onload='alert(1)'/>", "image/svg+xml"), "foto_formato"),
        ("iVBORw0KGgo=", "foto_formato"),  # base64 sem o prefixo data:
        (_data_uri(b"GIF89a" + b"\x00" * 10, "image/gif"), "foto_formato"),
        (_data_uri(b"isto nao e uma imagem"), "foto_invalida"),  # diz PNG, nao e
        ("data:image/png;base64,@@@nao-e-base64@@@", "foto_invalida"),
        (_data_uri(PNG + b"\x00" * (2 * 1024 * 1024)), "foto_grande"),
    ],
    # Nomes curtos: o pytest põe o id do caso numa variável de ambiente, e a
    # imagem de 2 MB passaria do limite do Windows.
    ids=["svg", "sem-prefixo", "gif", "conteudo-nao-e-png", "base64-corrompido", "maior-que-2mb"],
)
def test_foto_invalida_e_recusada_sem_chamar_o_cloudinary(
    client, nova_usuaria, cloudinary_falso, imagem, codigo
):
    h = nova_usuaria("ana@exemplo.com")
    r = client.put("/auth/me/foto", json={"imagem": imagem}, headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["codigo"] == codigo
    assert cloudinary_falso == []


def test_formatos_aceitos(client, nova_usuaria, cloudinary_falso):
    h = nova_usuaria("ana@exemplo.com")
    jpeg = _data_uri(b"\xff\xd8\xff\xe0" + b"\x00" * 32, "image/jpeg")
    webp = _data_uri(b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32, "image/webp")
    for imagem in (jpeg, webp):
        assert client.put("/auth/me/foto", json={"imagem": imagem}, headers=h).status_code == 200


def test_corpo_grande_demais_e_413(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    r = client.put("/auth/me/foto", json={"imagem": "A" * 3_100_000}, headers=h)
    assert r.status_code == 413


def test_sem_cloudinary_configurado_e_503(client, nova_usuaria):
    h = nova_usuaria("ana@exemplo.com")
    r = client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    assert r.status_code == 503
    assert "configurado" in r.json()["detail"]


def test_falha_no_cloudinary_e_503_e_nada_muda(client, nova_usuaria, cloudinary_falso, monkeypatch):
    h = nova_usuaria("ana@exemplo.com")
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)
    antes = client.get("/auth/me", headers=h).json()["foto_url"]

    def _fora_do_ar(url, campos):
        raise FotoIndisponivelError("Não foi possível salvar a foto agora.")

    monkeypatch.setattr(cloudinary, "_post", _fora_do_ar)
    assert client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h).status_code == 503
    assert client.get("/auth/me", headers=h).json()["foto_url"] == antes


def test_remover_foto_funciona_mesmo_com_cloudinary_fora(client, nova_usuaria, cloudinary_falso, monkeypatch):
    h = nova_usuaria("ana@exemplo.com")
    client.put("/auth/me/foto", json={"imagem": _data_uri()}, headers=h)

    def _fora_do_ar(url, campos):
        raise FotoIndisponivelError("fora")

    monkeypatch.setattr(cloudinary, "_post", _fora_do_ar)
    r = client.delete("/auth/me/foto", headers=h)
    assert r.status_code == 200
    assert r.json()["foto_url"] is None


def test_foto_exige_login(client):
    assert client.put("/auth/me/foto", json={"imagem": _data_uri()}).status_code == 401
    assert client.delete("/auth/me/foto").status_code == 401


def test_cloudinary_configurado_pela_metade_impede_a_api_de_subir(monkeypatch):
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "demo")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "")
    with pytest.raises(ConfigError, match="CLOUDINARY_API_KEY"):
        _config_cloudinary()
