"""Ponto de entrada da API: instancia o FastAPI, CORS, middlewares, routers e erros.

Rodar local: `uvicorn app.main:app --reload` → documentação em /docs.
No Vercel, o `app` deste arquivo é detectado automaticamente (app/main.py).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from app.core.config import get_settings
from app.core.dependencies import DbSession
from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    DomainError,
    EmailIndisponivelError,
    EmailNaoVerificadoError,
    FotoIndisponivelError,
    KnowledgeUnavailableError,
    NotFoundError,
    TooManyRequestsError,
)
from app.core.logging_config import configurar_logs
from app.core.middlewares import CabecalhosSegurancaMiddleware, LimiteCorpoMiddleware
from app.routers import (
    acordes,
    auth,
    colecoes,
    conhecimento,
    criacoes,
    essencias,
    mapa,
    perfil,
    referencias,
    testes,
)

_settings = get_settings()
configurar_logs(_settings.log_level)
logger = logging.getLogger("serene.api")

# Em produção a documentação interativa fica desligada (ENABLE_DOCS=true
# religa): ela entrega o mapa completo da API a qualquer visitante.
_docs = _settings.docs_enabled
app = FastAPI(
    title="SÉRENÉ — Mapa Olfativo Inteligente",
    description=(
        "Backend do SÉRENÉ. Autentique em /auth/login (botão Authorize) para usar "
        "os recursos do repertório pessoal."
    ),
    version="1.0.0",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

# Ordem: o último adicionado é o mais externo. O CORS fica por fora para que
# até as respostas 413 levem os headers de CORS (senão o navegador esconderia
# do frontend o motivo real do erro).
app.add_middleware(LimiteCorpoMiddleware)
app.add_middleware(CabecalhosSegurancaMiddleware, hsts=_settings.producao)
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_settings.cors_origins),
        # O token vai no header Authorization, não em cookie: sem credenciais
        # de navegador, outro site nunca consegue "pegar carona" na sessão.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],
        max_age=600,
    )

# Tradução centralizada de erros de domínio → HTTP. Os services não conhecem
# HTTP, e os routers não precisam de try/except.
_STATUS_POR_ERRO: dict[type[DomainError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    AuthenticationError: 401,
    EmailNaoVerificadoError: 403,
    BusinessRuleError: 400,
    TooManyRequestsError: 429,
    EmailIndisponivelError: 503,
    FotoIndisponivelError: 503,
    KnowledgeUnavailableError: 503,
}


@app.exception_handler(DomainError)
async def _erro_de_dominio(request: Request, exc: DomainError) -> JSONResponse:
    """Converte qualquer `DomainError` na resposta HTTP correspondente."""
    status_code = next(
        (code for cls, code in _STATUS_POR_ERRO.items() if isinstance(exc, cls)), 400
    )
    corpo: dict = {"detail": exc.message}
    headers: dict[str, str] = {}
    if exc.codigo:
        corpo["codigo"] = exc.codigo
    if status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        corpo["retry_after"] = retry_after
        headers["Retry-After"] = str(retry_after)
    if status_code == 429:
        logger.warning("Limite atingido em %s: %s", request.url.path, exc.message)
    return JSONResponse(corpo, status_code=status_code, headers=headers or None)


# Redes de segurança para erros de banco que escapem da validação. Antes,
# qualquer um deles virava um 500 sem explicação nem registro.
@app.exception_handler(IntegrityError)
async def _erro_integridade(request: Request, exc: IntegrityError) -> JSONResponse:
    """Violação de unique/FK que a regra de negócio não previu → 409."""
    logger.warning("IntegrityError em %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse({"detail": "Os dados conflitam com um registro existente."}, status_code=409)


@app.exception_handler(DataError)
async def _erro_dados(request: Request, exc: DataError) -> JSONResponse:
    """Valor que o banco recusou (grande demais, formato inválido) → 422."""
    logger.warning("DataError em %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse({"detail": "Algum valor é inválido ou grande demais."}, status_code=422)


@app.exception_handler(OperationalError)
async def _banco_indisponivel(request: Request, exc: OperationalError) -> JSONResponse:
    """Banco fora do ar ou inacessível → 503 (não é culpa da usuária)."""
    logger.error("Banco indisponível em %s %s: %s", request.method, request.url.path, exc.orig)
    return JSONResponse({"detail": "Serviço temporariamente indisponível."}, status_code=503)


@app.exception_handler(Exception)
async def _erro_inesperado(request: Request, exc: Exception) -> JSONResponse:
    """Qualquer outro erro: registra o traceback e responde sem detalhes internos."""
    logger.exception("Erro inesperado em %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Erro interno. Tente novamente em instantes."}, status_code=500)


for _router in (
    auth.router,
    essencias.router,
    criacoes.router,
    acordes.router,
    testes.router,
    referencias.router,
    perfil.router,
    colecoes.router,
    conhecimento.router,
    mapa.router,
):
    app.include_router(_router)


@app.get("/health", tags=["infra"])
def health() -> dict[str, str]:
    """A API está de pé (não toca no banco: serve para checagens rápidas)."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["infra"])
def health_ready(db: DbSession) -> JSONResponse:
    """A API consegue falar com o banco? 503 se não.

    Use este para monitorar o deploy: `/health` responde 200 mesmo com o
    banco fora do ar.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # qualquer falha de conexão = não está pronta
        logger.exception("Health check do banco falhou")
        return JSONResponse({"status": "indisponivel", "banco": "erro"}, status_code=503)
    return JSONResponse({"status": "ok", "banco": "ok"})
