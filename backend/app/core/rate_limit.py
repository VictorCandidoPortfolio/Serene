"""Limite de requisições (rate limiting) para as rotas públicas de conta.

Sem isto, qualquer pessoa poderia testar senhas sem parar no login, ou
disparar milhares de cadastros e emails. Os contadores ficam no banco
(`limites_requisicao`) porque no Vercel não há memória compartilhada entre
instâncias da função.

Dois tipos de chave:
- por IP: freia um atacante que tenta muitas contas a partir da mesma máquina;
- por email: freia um ataque distribuído (vários IPs) contra UMA conta.

Desligável com `RATE_LIMIT_ENABLED=false` (só para depurar localmente).
"""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import DbSession
from app.core.exceptions import TooManyRequestsError
from app.core.tempo import agora
from app.repositories.conta import LimiteRequisicaoRepository

# Contadores mais velhos que isto são apagados de vez em quando.
RETENCAO_CONTADORES = timedelta(days=1)
# Probabilidade de rodar a limpeza numa requisição (evita um job agendado).
CHANCE_LIMPEZA = 0.01


@dataclass(frozen=True)
class Limite:
    """No máximo `maximo` requisições a cada `janela_segundos`."""

    nome: str
    maximo: int
    janela_segundos: int


# Valores pensados para uma pessoa real nunca esbarrar neles, e um robô sim.
LOGIN_POR_IP = Limite("login-ip", 20, 5 * 60)
LOGIN_POR_EMAIL = Limite("login-email", 10, 15 * 60)
CADASTRO_POR_IP = Limite("cadastro-ip", 10, 60 * 60)
VERIFICAR_POR_IP = Limite("verificar-ip", 30, 10 * 60)
# Somado ao limite de tentativas POR CÓDIGO: mesmo pedindo códigos novos, uma
# conta aceita no máximo 15 palpites por hora (força bruta inviável).
VERIFICAR_POR_EMAIL = Limite("verificar-email", 15, 60 * 60)
REENVIO_POR_IP = Limite("reenvio-ip", 10, 60 * 60)
# Redefinição de senha: mesmo raciocínio da verificação (código de 4 dígitos).
ESQUECI_SENHA_POR_IP = Limite("esqueci-senha-ip", 10, 60 * 60)
REDEFINIR_POR_IP = Limite("redefinir-ip", 30, 10 * 60)
REDEFINIR_POR_EMAIL = Limite("redefinir-email", 15, 60 * 60)
# Troca de senha logada: quem roubou um token não pode usá-lo para testar a
# senha atual sem parar (e descobri-la para usar em outros sites).
TROCAR_SENHA_POR_CONTA = Limite("trocar-senha-conta", 10, 15 * 60)
# Cada foto enviada é um upload no Cloudinary (que tem cota): freia scripts.
FOTO_POR_CONTA = Limite("foto-conta", 20, 60 * 60)


def _hash(valor: str) -> str:
    """SHA-256 do IP/email: a tabela não guarda dados pessoais em claro."""
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()[:64]


def consumir(db: Session, limite: Limite, identificador: str) -> None:
    """Conta uma requisição e recusa se o limite da janela foi passado.

    Faz commit na hora, de propósito: o contador precisa ficar gravado mesmo
    que a operação seguinte falhe (é justamente a tentativa que falha — senha
    errada, código errado — que precisa ser contada).

    Raises:
        TooManyRequestsError: limite excedido (HTTP 429 com Retry-After).
    """
    if not get_settings().rate_limit_enabled:
        return
    repo = LimiteRequisicaoRepository(db)
    momento = agora()
    janela = timedelta(seconds=limite.janela_segundos)
    linha = repo.incrementar(f"{limite.nome}:{_hash(identificador)}", janela, momento)
    if secrets.randbelow(int(1 / CHANCE_LIMPEZA)) == 0:
        repo.limpar_expirados(momento - RETENCAO_CONTADORES)
    db.commit()

    if linha.contador > limite.maximo:
        espera = max(1, int((linha.janela_inicio + janela - momento).total_seconds()))
        minutos = -(-espera // 60)
        raise TooManyRequestsError(
            f"Muitas tentativas em pouco tempo. Tente novamente em {minutos} minuto(s).",
            retry_after=espera,
            codigo="limite_requisicoes",
        )


def ip_da_requisicao(request: Request) -> str:
    """IP de quem fez a requisição.

    Atrás do Vercel, o IP real vem nos headers que o próprio Vercel
    preenche (e sobrescreve, então a cliente não consegue falsificar). Fora
    de um proxy confiável esses headers são ignorados: senão bastaria mandar
    um `X-Forwarded-For` diferente a cada tentativa para nunca ser limitado.
    """
    if get_settings().trust_proxy_headers:
        for header in ("x-vercel-forwarded-for", "x-forwarded-for", "x-real-ip"):
            valor = request.headers.get(header)
            if valor:
                return valor.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def limitar_por_ip(limite: Limite) -> Callable:
    """Dependency do FastAPI que aplica `limite` ao IP da requisição.

    Já devolve o `Depends(...)`. Uso:
    `@router.post(..., dependencies=[limitar_por_ip(LOGIN_POR_IP)])`.
    """

    def _dependency(request: Request, db: DbSession) -> None:
        consumir(db, limite, ip_da_requisicao(request))

    return Depends(_dependency)
