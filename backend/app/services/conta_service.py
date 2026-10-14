"""Conta LOGADA: editar o nome, trocar a senha e a foto de perfil.

Diferente de `auth_service` (que atende quem ainda não tem token), aqui a
usuária já vem autenticada por `get_current_user`; nada é buscado por email.

Foto de perfil: o frontend manda a imagem como data URI base64, este módulo
confere tipo e conteúdo, `app.core.cloudinary` faz o upload e o banco guarda
só o endereço público (`foto_url`) e o id do arquivo (`foto_public_id`).
"""

import base64
import binascii
import logging
import re
import secrets

from sqlalchemy.orm import Session

from app.core import cloudinary, rate_limit
from app.core.exceptions import BusinessRuleError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.repertorio import User
from app.schemas.auth import PerfilUpdateIn

logger = logging.getLogger("serene.conta")

FOTO_MAX_BYTES = 2 * 1024 * 1024
_DATA_URI = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,")
# Os primeiros bytes de cada formato. Conferir o conteúdo (e não só o tipo
# declarado) impede mandar, por exemplo, um SVG com script dizendo ser PNG.
_ASSINATURAS = {
    "image/jpeg": lambda b: b[:3] == b"\xff\xd8\xff",
    "image/png": lambda b: b[:8] == b"\x89PNG\r\n\x1a\n",
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}
_FOTO_INVALIDA = "O arquivo enviado não é uma imagem válida. Use JPEG, PNG ou WebP."


def decodificar_foto(data_uri: str) -> bytes:
    """Confere uma foto enviada como data URI e devolve os bytes da imagem.

    Raises:
        BusinessRuleError: formato não aceito, base64 corrompido, imagem
            maior que FOTO_MAX_BYTES, ou conteúdo que não bate com o tipo.
    """
    encontrado = _DATA_URI.match(data_uri)
    if not encontrado:
        raise BusinessRuleError(
            "Envie a foto como imagem JPEG, PNG ou WebP.", codigo="foto_formato"
        )
    try:
        conteudo = base64.b64decode(data_uri[encontrado.end():], validate=True)
    except (binascii.Error, ValueError):
        raise BusinessRuleError(_FOTO_INVALIDA, codigo="foto_invalida") from None
    if len(conteudo) > FOTO_MAX_BYTES:
        raise BusinessRuleError("A foto pode ter no máximo 2 MB.", codigo="foto_grande")
    if not _ASSINATURAS[encontrado.group(1)](conteudo):
        raise BusinessRuleError(_FOTO_INVALIDA, codigo="foto_invalida")
    return conteudo


def atualizar_perfil(db: Session, user: User, dados: PerfilUpdateIn) -> User:
    """Altera só os campos enviados (hoje, o nome)."""
    if dados.nome is not None:
        user.nome = dados.nome
    db.commit()
    return user


def trocar_senha(db: Session, user: User, senha_atual: str, nova_senha: str) -> str:
    """Troca a senha de quem está logada e devolve um token NOVO.

    A versão do token sobe: as sessões abertas em outros aparelhos caem
    (quem roubou um token perde o acesso), e a sessão atual continua com o
    token devolvido aqui, sem precisar entrar de novo.

    Erros de senha atual são 400, e não 401, de propósito: um 401 faria o
    frontend achar que a sessão expirou e deslogar a usuária.

    Raises:
        TooManyRequestsError: tentativas demais para esta conta.
        BusinessRuleError: senha atual errada, ou nova igual à atual.
    """
    rate_limit.consumir(db, rate_limit.TROCAR_SENHA_POR_CONTA, str(user.id))
    if not verify_password(senha_atual, user.senha_hash):
        logger.warning("Troca de senha recusada (senha atual errada) para a conta %s", user.id)
        raise BusinessRuleError("A senha atual não confere.", codigo="senha_atual_incorreta")
    if verify_password(nova_senha, user.senha_hash):
        raise BusinessRuleError(
            "A nova senha precisa ser diferente da atual.", codigo="senha_repetida"
        )
    user.senha_hash = hash_password(nova_senha)
    user.token_version += 1
    db.commit()
    logger.info("Senha trocada pela própria usuária (conta %s)", user.id)
    return create_access_token(user.id, versao=user.token_version)


def salvar_foto(db: Session, user: User, data_uri: str) -> User:
    """Envia a foto nova para o Cloudinary e troca a da conta.

    Ordem pensada para nunca deixar a conta sem foto por causa de uma falha:
    1. confere a imagem (antes de gastar upload);
    2. faz o upload com um nome aleatório (a URL não é adivinhável a partir
       do id da conta);
    3. grava no banco; se o banco falhar, apaga o upload recém-feito;
    4. só então apaga a foto antiga.

    Raises:
        BusinessRuleError: imagem inválida.
        TooManyRequestsError: envios demais nesta hora.
        FotoIndisponivelError: Cloudinary não configurado ou fora do ar.
    """
    decodificar_foto(data_uri)
    rate_limit.consumir(db, rate_limit.FOTO_POR_CONTA, str(user.id))
    nova = cloudinary.enviar_imagem(data_uri, public_id=f"u{user.id}-{secrets.token_urlsafe(12)}")

    antiga = user.foto_public_id
    user.foto_url, user.foto_public_id = nova.url, nova.public_id
    try:
        db.commit()
    except Exception:
        db.rollback()
        cloudinary.apagar_imagem(nova.public_id)
        raise
    if antiga:
        cloudinary.apagar_imagem(antiga)
    return user


def remover_foto(db: Session, user: User) -> User:
    """Tira a foto da conta e apaga o arquivo no Cloudinary (melhor esforço)."""
    antiga = user.foto_public_id
    user.foto_url = user.foto_public_id = None
    db.commit()
    if antiga:
        cloudinary.apagar_imagem(antiga)
    return user
