"""Endpoints de autenticação (registro, verificação de email, login JWT) e da conta logada (/me)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DbSession
from app.core.rate_limit import (
    CADASTRO_POR_IP,
    ESQUECI_SENHA_POR_IP,
    LOGIN_POR_IP,
    REDEFINIR_POR_IP,
    REENVIO_POR_IP,
    VERIFICAR_POR_IP,
    limitar_por_ip,
)
from app.schemas.auth import (
    CodigoEnviadoOut,
    EsqueciSenhaIn,
    FotoIn,
    MensagemOut,
    PerfilUpdateIn,
    RedefinirSenhaIn,
    ReenviarCodigoIn,
    RegistroIn,
    RegistroOut,
    TokenOut,
    TrocarSenhaIn,
    UserOut,
    VerificarEmailIn,
)
from app.services import auth_service, conta_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegistroOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[limitar_por_ip(CADASTRO_POR_IP)],
)
def register(dados: RegistroIn, db: DbSession):
    """Cria uma conta e envia um código de 4 dígitos para o email.

    A conta só consegue entrar depois de `POST /auth/verificar-email`. Se o
    email já tem uma conta PENDENTE, ela é retomada (nova senha, novo código).
    """
    user = auth_service.registrar(db, dados)
    cfg = get_settings()
    return RegistroOut(
        **UserOut.model_validate(user).model_dump(),
        codigo_expira_minutos=cfg.email_code_expire_minutes,
        reenvio_em_segundos=cfg.email_code_resend_seconds,
    )


@router.post(
    "/verificar-email", response_model=TokenOut, dependencies=[limitar_por_ip(VERIFICAR_POR_IP)]
)
def verificar_email(dados: VerificarEmailIn, db: DbSession):
    """Confere código + senha. Se certos, já devolve o token de acesso."""
    return TokenOut(
        access_token=auth_service.verificar_email(db, dados.email, dados.codigo, dados.senha)
    )


@router.post(
    "/reenviar-codigo",
    response_model=CodigoEnviadoOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[limitar_por_ip(REENVIO_POR_IP)],
)
def reenviar_codigo(dados: ReenviarCodigoIn, db: DbSession):
    """Envia um novo código (o anterior deixa de valer).

    A resposta é a mesma exista ou não uma conta pendente com o email.
    """
    auth_service.reenviar_codigo(db, dados.email)
    return CodigoEnviadoOut(
        mensagem=auth_service.MENSAGEM_REENVIO,
        reenvio_em_segundos=get_settings().email_code_resend_seconds,
    )


@router.post(
    "/esqueci-senha",
    response_model=CodigoEnviadoOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[limitar_por_ip(ESQUECI_SENHA_POR_IP)],
)
def esqueci_senha(dados: EsqueciSenhaIn, db: DbSession):
    """Envia por email um código de 4 dígitos para redefinir a senha.

    A resposta é a mesma exista ou não uma conta com o email.
    """
    auth_service.esqueci_senha(db, dados.email)
    return CodigoEnviadoOut(
        mensagem=auth_service.MENSAGEM_ESQUECI_SENHA,
        reenvio_em_segundos=get_settings().email_code_resend_seconds,
    )


@router.post(
    "/redefinir-senha", response_model=MensagemOut, dependencies=[limitar_por_ip(REDEFINIR_POR_IP)]
)
def redefinir_senha(dados: RedefinirSenhaIn, db: DbSession):
    """Confere o código e troca a senha. Depois, entre em `/auth/login`."""
    auth_service.redefinir_senha(db, dados.email, dados.codigo, dados.nova_senha)
    return MensagemOut(mensagem=auth_service.MENSAGEM_SENHA_REDEFINIDA)


@router.post("/login", response_model=TokenOut, dependencies=[limitar_por_ip(LOGIN_POR_IP)])
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Troca email + senha por um JWT.

    Usa o formulário OAuth2 padrão (`username` = email, `password`), que é o
    que o botão "Authorize" do Swagger envia. Conta com email não confirmado
    recebe 403 com `codigo: "email_nao_verificado"`.
    """
    return TokenOut(access_token=auth_service.autenticar(db, form.username, form.password))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    """Dados da usuária autenticada."""
    return user


# ---------------------------------------------------------------- conta logada
@router.put("/me", response_model=UserOut)
def atualizar_me(dados: PerfilUpdateIn, user: CurrentUser, db: DbSession):
    """Edita os dados da conta (hoje, o nome). O email não muda por aqui."""
    return conta_service.atualizar_perfil(db, user, dados)


@router.post("/me/senha", response_model=TokenOut)
def trocar_senha(dados: TrocarSenhaIn, user: CurrentUser, db: DbSession):
    """Troca a senha conferindo a atual.

    Devolve um token novo: esta sessão continua aberta, e as de outros
    aparelhos (com o token antigo) passam a receber 401.
    """
    return TokenOut(
        access_token=conta_service.trocar_senha(db, user, dados.senha_atual, dados.nova_senha)
    )


@router.put("/me/foto", response_model=UserOut)
def enviar_foto(dados: FotoIn, user: CurrentUser, db: DbSession):
    """Recebe a foto (data URI base64), envia ao Cloudinary e guarda a URL.

    Aceita JPEG, PNG ou WebP de até 2 MB. 503 se o Cloudinary não estiver
    configurado no servidor.
    """
    return conta_service.salvar_foto(db, user, dados.imagem)


@router.delete("/me/foto", response_model=UserOut)
def remover_foto(user: CurrentUser, db: DbSession):
    """Remove a foto de perfil (e o arquivo no Cloudinary)."""
    return conta_service.remover_foto(db, user)
