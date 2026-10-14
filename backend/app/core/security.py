"""Primitivas de segurança: hash de senha e emissão/validação de JWT.

Este módulo não conhece banco nem FastAPI — só transforma dados. Quem decide
"quem é a usuária desta requisição" é `app.core.dependencies.get_current_user`,
que usa as funções daqui.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt só considera os primeiros 72 BYTES da senha (não caracteres: "ç" ou
# "ã" ocupam 2 bytes em UTF-8). Senha maior daria falsa sensação de segurança.
SENHA_MIN_CARACTERES = 8
SENHA_MAX_BYTES = 72
DIGITOS_CODIGO = 4

# Custo do bcrypt (2^12 iterações, ~250 ms): lento de propósito, para que
# testar senhas em massa seja caro. Subir o número deixa hashes novos mais
# fortes; os antigos continuam valendo, porque o custo fica gravado no hash.
BCRYPT_ROUNDS = 12


class InvalidTokenError(Exception):
    """Token ausente, malformado, com assinatura inválida ou expirado."""


def hash_password(plain_password: str) -> str:
    """Gera o hash bcrypt de uma senha.

    Usa a biblioteca `bcrypt` diretamente (o `passlib` não recebe mais
    manutenção). Os hashes `$2b$...` são os mesmos de antes: contas antigas
    continuam entrando normalmente.

    Args:
        plain_password: senha em texto puro. Nunca deve ser logada nem
            persistida — só o retorno desta função vai para o banco.

    Returns:
        str: hash no formato `$2b$...`, que já inclui salt e custo.
    """
    senha = plain_password.encode("utf-8")
    return bcrypt.hashpw(senha, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Compara uma senha com o hash salvo (comparação em tempo constante).

    Senha acima de 72 bytes nunca confere: o cadastro não permite criá-la, e
    o bcrypt 5 recusaria a comparação com erro.

    Returns:
        bool: True se a senha confere.
    """
    senha = plain_password.encode("utf-8")
    if len(senha) > SENHA_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(senha, password_hash.encode("ascii"))
    except ValueError:
        # Hash malformado no banco: trata como senha errada, sem derrubar o login.
        return False


def create_access_token(
    user_id: int, expires_minutes: int | None = None, versao: int = 0
) -> str:
    """Emite um JWT de acesso para a usuária.

    O payload carrega só o mínimo: `sub` (id da usuária) e `exp`. Nada de
    email/nome no token — o token é legível por quem o possui (JWT é assinado,
    não criptografado) e dados de perfil podem mudar depois da emissão.

    Args:
        user_id: id da usuária autenticada.
        expires_minutes: sobrescreve a validade padrão (útil em testes).
        versao: `users.token_version` atual; trocar a senha a incrementa e
            invalida os tokens antigos.

    Returns:
        str: token codificado.
    """
    settings = get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        # O padrão JWT exige `sub` como string; o PyJWT valida isso.
        "sub": str(user_id),
        "tv": versao,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> tuple[int, int]:
    """Valida assinatura e expiração de um JWT e devolve (id da usuária, versão).

    Token sem a claim `tv` (emitido antes dela existir) conta como versão 0.

    `algorithms=[...]` é passado explicitamente para impedir o ataque clássico
    de trocar o algoritmo no header do token (ex.: `alg: none`).

    Raises:
        InvalidTokenError: em qualquer falha — o chamador não precisa (e não
            deve) distinguir o motivo para o cliente.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        return int(payload["sub"]), int(payload.get("tv", 0))
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise InvalidTokenError(str(exc)) from exc


# --------------------------------------------------------------- senha forte
def problemas_da_senha(senha: str) -> list[str]:
    """Lista o que falta para a senha ser considerada forte (vazia = ok).

    Regra do produto: pelo menos 8 caracteres, pelo menos uma letra
    MAIÚSCULA e pelo menos um NÚMERO ou CARACTERE ESPECIAL. Espaço não conta
    como caractere especial (senão "Abcdefg " passaria).

    Os textos são escritos para vir depois de "Senha ..." — é assim que o
    frontend monta a mensagem de erro de validação.

    Args:
        senha: senha em texto puro (nunca logar).

    Returns:
        list[str]: problemas encontrados, em linguagem da usuária.
    """
    problemas = []
    if len(senha) < SENHA_MIN_CARACTERES:
        problemas.append(f"precisa ter pelo menos {SENHA_MIN_CARACTERES} caracteres")
    if len(senha.encode("utf-8")) > SENHA_MAX_BYTES:
        problemas.append("é longa demais (acentos ocupam mais espaço; use até 72 caracteres simples)")
    if not any(c.isupper() for c in senha):
        problemas.append("precisa ter pelo menos uma letra maiúscula")
    if not any(c.isdigit() or not (c.isalnum() or c.isspace()) for c in senha):
        problemas.append("precisa ter pelo menos um número ou caractere especial (ex.: ! @ # $ %)")
    return problemas


# ----------------------------------------------------- código de verificação
def gerar_codigo_verificacao() -> str:
    """Gera um código numérico aleatório de 4 dígitos (ex.: "0427").

    `secrets` usa o gerador criptográfico do sistema operacional: diferente
    do módulo `random`, o próximo código não pode ser previsto a partir dos
    anteriores. Zeros à esquerda são mantidos (são 10.000 códigos possíveis).
    """
    return f"{secrets.randbelow(10**DIGITOS_CODIGO):0{DIGITOS_CODIGO}d}"


def _chave_codigos() -> bytes:
    """Chave própria para o HMAC dos códigos, derivada da JWT_SECRET_KEY.

    Separação de uso: a mesma chave não deve assinar tokens e proteger
    códigos. Derivar (em vez de pedir outra variável de ambiente) mantém a
    configuração simples e ainda garante que vazar uma das chaves derivadas
    não revela a outra.
    """
    mestra = get_settings().jwt_secret_key.encode("utf-8")
    return hmac.new(mestra, b"serene:codigo-verificacao-email", hashlib.sha256).digest()


def hash_codigo(user_id: int, codigo: str) -> str:
    """HMAC-SHA256 do código, amarrado à usuária e a uma chave secreta.

    Por que HMAC e não um hash simples: com só 10.000 códigos possíveis, quem
    obtivesse uma cópia do banco testaria todos em milissegundos. Com a chave
    secreta (que não fica no banco) isso deixa de ser possível. O `user_id`
    na mensagem impede reaproveitar o hash de uma conta em outra.
    """
    return hmac.new(_chave_codigos(), f"{user_id}:{codigo}".encode("utf-8"), hashlib.sha256).hexdigest()


def codigo_confere(user_id: int, codigo: str, codigo_hash: str) -> bool:
    """Compara o código digitado com o hash salvo, em tempo constante."""
    return hmac.compare_digest(hash_codigo(user_id, codigo), codigo_hash)
