"""Dependencies do FastAPI: sessão de banco e usuária autenticada.

`get_current_user` é a FONTE ÚNICA DE VERDADE sobre "quem está pedindo isto".
Todo o isolamento entre usuárias (seção 3 do spec) parte do `user.id`
devolvido aqui e passado aos repositórios. Nenhum endpoint deve aceitar um
`user_id` vindo do corpo, da query ou da URL — só daqui.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import EmailNaoVerificadoError
from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import SessionLocal
from app.models.repertorio import User

# tokenUrl aponta para o endpoint de login: é o que faz o botão "Authorize"
# do Swagger (/docs) funcionar sem configuração extra.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db_session() -> Iterator[Session]:
    """Abre uma sessão por requisição e garante o fechamento no final.

    Commits são responsabilidade explícita dos services: uma requisição que
    falha no meio não deixa escrita parcial, porque o `close()` sem commit
    descarta a transação.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db_session)]

_CREDENCIAIS_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticada: token ausente, inválido ou expirado.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """Decodifica o JWT e carrega a usuária correspondente.

    Recarregar do banco (em vez de confiar só no token) garante que uma conta
    apagada deixe de funcionar imediatamente, mesmo com token ainda válido.

    Raises:
        HTTPException 401: em qualquer falha — a mensagem é propositalmente
            genérica para não ajudar quem tenta forjar tokens.
    """
    try:
        user_id, versao = decode_access_token(token)
    except InvalidTokenError:
        raise _CREDENCIAIS_INVALIDAS from None
    # `users` é a única tabela pessoal onde um get por PK é seguro: o id vem
    # do token assinado, não de input da cliente.
    user = db.get(User, user_id)
    # Senha trocada depois da emissão do token: a sessão antiga não vale mais.
    if user is None or versao != user.token_version:
        raise _CREDENCIAIS_INVALIDAS
    # Defesa extra: tokens só são emitidos depois da verificação, mas se um
    # dia algum caminho emitir antes, a conta pendente continua sem acesso.
    if not user.email_verificado:
        raise EmailNaoVerificadoError("Confirme seu email antes de usar o Sérené.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
