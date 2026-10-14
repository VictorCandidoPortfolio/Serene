"""Cliente mínimo da API REST do Cloudinary: upload e remoção de imagens.

Por que não o SDK oficial: só precisamos de duas chamadas (upload e destroy),
e as duas são um POST assinado. Fazer à mão com a biblioteca padrão evita
uma dependência a mais no pacote da função (Vercel).

Upload ASSINADO: a assinatura é o SHA-1 dos parâmetros em ordem alfabética
seguidos do `CLOUDINARY_API_SECRET`. O segredo nunca sai do backend; o
frontend nem sabe que o Cloudinary existe — ele só manda a imagem para a API.

Credenciais em CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY /
CLOUDINARY_API_SECRET (ver `.env.example`).
"""

import hashlib
import json
import logging
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from app.core.config import get_settings
from app.core.exceptions import FotoIndisponivelError

logger = logging.getLogger("serene.cloudinary")

API_BASE = "https://api.cloudinary.com/v1_1"
TIMEOUT_SEGUNDOS = 20
# Parâmetros que o Cloudinary NÃO inclui na assinatura.
_FORA_DA_ASSINATURA = {"file", "api_key", "resource_type", "cloud_name", "signature"}
_SSL = ssl.create_default_context(cafile=certifi.where())


@dataclass(frozen=True)
class ImagemEnviada:
    """O que guardamos de um upload: endereço público e id do arquivo."""

    url: str
    public_id: str


def assinar(params: dict[str, str], segredo: str) -> str:
    """Assinatura de uma chamada à API do Cloudinary.

    Ex.: {"public_id": "x", "timestamp": "1"} → sha1("public_id=x&timestamp=1" + segredo).
    """
    texto = "&".join(
        f"{chave}={params[chave]}"
        for chave in sorted(params)
        if chave not in _FORA_DA_ASSINATURA and params[chave] not in ("", None)
    )
    return hashlib.sha1((texto + segredo).encode("utf-8")).hexdigest()


def _post(url: str, campos: dict[str, str]) -> dict:
    """POST de formulário para o Cloudinary; devolve o JSON da resposta.

    Isolado numa função para os testes trocarem a rede por um dublê.

    Raises:
        FotoIndisponivelError: rede fora, timeout ou resposta de erro.
    """
    corpo = urllib.parse.urlencode(campos).encode("ascii")
    pedido = urllib.request.Request(url, data=corpo, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS, context=_SSL) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # A mensagem do Cloudinary vai só para o log (pode citar a conta).
        detalhe = exc.read().decode("utf-8", "replace")[:500]
        logger.error("Cloudinary respondeu %s em %s: %s", exc.code, url, detalhe)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.error("Falha ao falar com o Cloudinary (%s): %s", url, exc)
    raise FotoIndisponivelError(
        "Não foi possível salvar a foto agora. Tente novamente em instantes."
    )


def _chamar(acao: str, params: dict[str, str]) -> dict:
    """Assina e envia uma chamada `image/<acao>` com as credenciais do `.env`."""
    cfg = get_settings()
    if not cfg.fotos_habilitadas:
        raise FotoIndisponivelError(
            "O envio de foto ainda não foi configurado neste servidor."
        )
    params = {**params, "timestamp": str(int(time.time()))}
    campos = {
        **params,
        "api_key": cfg.cloudinary_api_key,
        "signature": assinar(params, cfg.cloudinary_api_secret),
    }
    return _post(f"{API_BASE}/{cfg.cloudinary_cloud_name}/image/{acao}", campos)


def enviar_imagem(data_uri: str, public_id: str) -> ImagemEnviada:
    """Envia uma imagem (data URI base64) para a pasta CLOUDINARY_FOLDER.

    Args:
        data_uri: "data:image/webp;base64,...", já validada pelo service.
        public_id: nome do arquivo no Cloudinary (aleatório, ver conta_service).

    Raises:
        FotoIndisponivelError: Cloudinary não configurado, fora do ar ou
            recusando a imagem.
    """
    resposta = _chamar(
        "upload",
        {
            "file": data_uri,
            "folder": get_settings().cloudinary_folder,
            "public_id": public_id,
            "overwrite": "false",
        },
    )
    url, pid = resposta.get("secure_url"), resposta.get("public_id")
    if not url or not pid:
        logger.error("Resposta inesperada do upload no Cloudinary: %s", str(resposta)[:300])
        raise FotoIndisponivelError(
            "Não foi possível salvar a foto agora. Tente novamente em instantes."
        )
    return ImagemEnviada(url=url, public_id=pid)


def apagar_imagem(public_id: str) -> None:
    """Apaga uma imagem do Cloudinary. Melhor esforço: falhas só vão para o log.

    Uma foto antiga que sobrou no Cloudinary não atrapalha ninguém; já falhar
    a troca de foto da usuária por causa disso atrapalharia.
    """
    try:
        _chamar("destroy", {"public_id": public_id, "invalidate": "true"})
    except FotoIndisponivelError:
        logger.warning("Não foi possível apagar a imagem antiga %s do Cloudinary.", public_id)
