"""Middlewares ASGI de proteção: tamanho do corpo e cabeçalhos de segurança.

Escritos como ASGI puro (e não `BaseHTTPMiddleware`) para não carregar o
corpo inteiro na memória nem atrapalhar respostas em streaming.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Nenhuma requisição legítima da API passa de alguns KB. Sem limite, a API
# lia um corpo de 20 MB inteiro na memória antes de recusá-lo.
CORPO_MAX_BYTES = 1_000_000
# Exceções por rota. A foto de perfil vem em base64 dentro do JSON: 2 MB de
# imagem viram ~2,8 MB de texto. Fica abaixo dos 4,5 MB que o Vercel aceita
# por requisição. (O frontend reduz a foto antes; isto é só o teto.)
CORPO_MAX_POR_ROTA = {"/auth/me/foto": 3_000_000}

# Caminhos da documentação interativa: precisam carregar scripts e estilos do
# Swagger/ReDoc, então não recebem a CSP restritiva da API.
_CAMINHOS_DOCS = ("/docs", "/redoc", "/openapi.json")


class _CorpoGrandeDemais(Exception):
    """Sinal interno: o corpo passou do limite enquanto era lido."""


async def _responder_413(send: Send) -> None:
    corpo = json.dumps({"detail": "Requisição grande demais."}).encode()
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(corpo)).encode())],
    })
    await send({"type": "http.response.body", "body": corpo})


class LimiteCorpoMiddleware:
    """Recusa (413) requisições cujo corpo passe de `maximo` bytes.

    Confere o `Content-Length` declarado e também conta os bytes realmente
    recebidos (um cliente pode mentir no header ou mandar sem ele).
    """

    def __init__(
        self,
        app: ASGIApp,
        maximo: int = CORPO_MAX_BYTES,
        por_rota: dict[str, int] | None = None,
    ):
        self.app = app
        self.maximo = maximo
        self.por_rota = CORPO_MAX_POR_ROTA if por_rota is None else por_rota

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        maximo = self.por_rota.get(scope.get("path", "").rstrip("/"), self.maximo)
        declarado = dict(scope["headers"]).get(b"content-length")
        if declarado is not None and declarado.isdigit() and int(declarado) > maximo:
            await _responder_413(send)
            return

        recebido = 0
        resposta_iniciada = False

        async def receive_limitado() -> Message:
            """Repassa o corpo contando os bytes; interrompe ao passar do limite."""
            nonlocal recebido
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebido += len(mensagem.get("body", b""))
                if recebido > maximo:
                    raise _CorpoGrandeDemais
            return mensagem

        async def send_rastreado(mensagem: Message) -> None:
            """Repassa a resposta anotando se ela já começou a ser enviada."""
            nonlocal resposta_iniciada
            if mensagem["type"] == "http.response.start":
                resposta_iniciada = True
            await send(mensagem)

        try:
            await self.app(scope, receive_limitado, send_rastreado)
        except _CorpoGrandeDemais:
            if not resposta_iniciada:
                await _responder_413(send)


class CabecalhosSegurancaMiddleware:
    """Acrescenta cabeçalhos de segurança a todas as respostas da API.

    - `X-Content-Type-Options: nosniff`: o navegador não "adivinha" que um
      JSON é HTML/script.
    - `X-Frame-Options` + `frame-ancestors`: a API não pode ser embutida em
      iframe (clickjacking).
    - `Content-Security-Policy: default-src 'none'`: uma resposta da API
      nunca deve executar nada se for aberta no navegador.
    - `Cache-Control: no-store`: respostas com dados pessoais não ficam em
      cache de navegador ou proxy.
    - `Strict-Transport-Security` (só em produção): força HTTPS.
    """

    def __init__(self, app: ASGIApp, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = scope["path"].startswith(_CAMINHOS_DOCS)

        async def send_com_cabecalhos(mensagem: Message) -> None:
            """Acrescenta os cabeçalhos de segurança no início da resposta."""
            if mensagem["type"] == "http.response.start":
                headers = list(mensagem.get("headers", []))
                existentes = {k.lower() for k, _ in headers}
                extras = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                ]
                if not docs:
                    extras.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"))
                if b"cache-control" not in existentes:
                    extras.append((b"cache-control", b"no-store"))
                if self.hsts:
                    extras.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
                headers.extend(h for h in extras if h[0] not in existentes)
                mensagem = {**mensagem, "headers": headers}
            await send(mensagem)

        await self.app(scope, receive, send_com_cabecalhos)
