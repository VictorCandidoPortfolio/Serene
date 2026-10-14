"""Cadastro, verificação de email por código e login.

Fluxo:
1. `registrar`: cria a conta com `email_verificado=False` e envia um código
   de 4 dígitos para o email.
2. `verificar_email`: a usuária digita o código E a senha; se os dois
   conferem, a conta é marcada como verificada e já recebe um token.
3. `autenticar` (login): recusa contas não verificadas com 403
   `email_nao_verificado`, para o frontend levar à tela do código.
4. `reenviar_codigo`: gera um código novo (o anterior deixa de valer).
5. `esqueci_senha` + `redefinir_senha`: "esqueci minha senha". Reaproveita o
   mesmo código de 4 dígitos, a mesma tabela e os mesmos limites; só vale
   para contas JÁ verificadas (conta pendente se recadastra). Quem prova
   controlar o email (código certo) define a nova senha; o login continua
   sendo um passo separado.

Por que a confirmação exige a SENHA (correção de sequestro de conta): sem
isso, um atacante cadastrava o email da vítima com a senha DELE; a vítima
confirmava o código achando que criava a própria conta, e o atacante
entrava. Agora: recadastrar uma conta ainda pendente troca a senha pela da
pessoa nova, e o código só confirma a conta junto com a senha atual. Como o
código só chega a quem controla o email, a senha que fica valendo é sempre
a de quem é dona do email.

Proteções contra força bruta, todas no banco (funcionam entre instâncias):
- o código expira (EMAIL_CODE_EXPIRE_MINUTES);
- poucas tentativas erradas por código (EMAIL_CODE_MAX_ATTEMPTS);
- intervalo mínimo e máximo por hora de envios (EMAIL_CODE_RESEND_SECONDS,
  EMAIL_CODE_MAX_SENDS_PER_HOUR);
- máximo de palpites por conta por hora, somando todos os códigos
  (`rate_limit.VERIFICAR_POR_EMAIL`);
- `SELECT ... FOR UPDATE` nas linhas da conta: requisições simultâneas são
  atendidas uma de cada vez, então os contadores não podem ser burlados em
  paralelo.
"""

import logging
import math
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import email as email_core
from app.core import rate_limit
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    EmailIndisponivelError,
    EmailNaoVerificadoError,
    TooManyRequestsError,
)
from app.core.security import (
    codigo_confere,
    create_access_token,
    gerar_codigo_verificacao,
    hash_codigo,
    hash_password,
    verify_password,
)
from app.core.tempo import agora
from app.models.conta import VerificacaoEmail
from app.models.repertorio import User
from app.repositories.conta import VerificacaoEmailRepository
from app.repositories.repertorio import UserRepository
from app.schemas.auth import RegistroIn

logger = logging.getLogger("serene.auth")

# Hash fixo usado quando o email não existe: faz o login levar o mesmo tempo
# (bcrypt é lento) com ou sem conta, dificultando descobrir emails cadastrados
# pelo tempo de resposta.
_HASH_FICTICIO = hash_password("senha-ficticia-para-tempo-constante")

JANELA_ENVIOS = timedelta(hours=1)
# Contas nunca confirmadas são apagadas depois deste prazo sem novo código.
PENDENTE_EXPIRA = timedelta(days=7)
MENSAGEM_REENVIO = (
    "Se houver uma conta aguardando confirmação com este email, enviamos um novo código."
)
MENSAGEM_ESQUECI_SENHA = (
    "Se houver uma conta com este email, enviamos um código para redefinir a senha."
)
MENSAGEM_SENHA_REDEFINIDA = "Senha redefinida. Entre com a nova senha."
_CODIGO_INVALIDO = "Código inválido. Confira o email e a senha, ou peça um novo código."
_CODIGO_INVALIDO_REDEFINICAO = "Código inválido. Confira o email ou peça um novo código."


def mascarar_email(email: str) -> str:
    """"ana.silva@exemplo.com" → "a***@exemplo.com" (para logs, sem expor o email)."""
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:1]}***@{dominio}" if dominio else "***"


def _mensagem_redefinicao(user: User, codigo: str, minutos: int) -> email_core.Mensagem:
    """Email do código de redefinição de senha."""
    texto = (
        f"Olá, {user.nome}!\n\n"
        f"Seu código para redefinir a senha do Sérené é: {codigo}\n\n"
        f"Ele vale por {minutos} minutos. Se não foi você quem pediu, ignore este "
        "email: sua senha continua a mesma.\n"
    )
    html = (
        f"<p>Olá, {_escapar(user.nome)}!</p>"
        "<p>Seu código para redefinir a senha do Sérené é:</p>"
        f'<p style="font-size:32px;font-weight:700;letter-spacing:8px">{codigo}</p>'
        f"<p>Ele vale por {minutos} minutos. Se não foi você quem pediu, ignore este "
        "email: sua senha continua a mesma.</p>"
    )
    return email_core.Mensagem(
        para=user.email, assunto=f"Código para redefinir sua senha: {codigo}", texto=texto, html=html
    )


def _mensagem_codigo(user: User, codigo: str, minutos: int) -> email_core.Mensagem:
    """Monta o email com o código (texto puro + HTML simples)."""
    texto = (
        f"Olá, {user.nome}!\n\n"
        f"Seu código de verificação do Sérené é: {codigo}\n\n"
        f"Ele vale por {minutos} minutos. Se você não criou uma conta no Sérené, "
        "ignore este email.\n"
    )
    html = (
        f"<p>Olá, {_escapar(user.nome)}!</p>"
        "<p>Seu código de verificação do Sérené é:</p>"
        f'<p style="font-size:32px;font-weight:700;letter-spacing:8px">{codigo}</p>'
        f"<p>Ele vale por {minutos} minutos. Se você não criou uma conta no Sérené, "
        "ignore este email.</p>"
    )
    return email_core.Mensagem(
        para=user.email, assunto=f"Seu código Sérené: {codigo}", texto=texto, html=html
    )


def _escapar(texto: str) -> str:
    """Escapa HTML no nome digitado pela usuária (ele vai dentro do email)."""
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _segundos_ate(momento, referencia) -> int:
    """Segundos inteiros (arredondados para cima) de `referencia` até `momento`."""
    return max(1, math.ceil((momento - referencia).total_seconds()))


def _preparar_codigo(db: Session, user: User) -> str:
    """Gera um código novo para a usuária, aplicando os limites de envio.

    Sobrescreve o código anterior (que deixa de valer) e zera as tentativas.
    A linha da verificação é travada (`FOR UPDATE`): dois pedidos simultâneos
    não conseguem, juntos, passar do limite de envios. Não faz commit: quem
    chama só confirma a transação depois que o email foi realmente enviado.

    Raises:
        TooManyRequestsError: intervalo mínimo ou limite por hora não respeitado.
    """
    cfg = get_settings()
    repo = VerificacaoEmailRepository(db)
    momento = agora()
    codigo = gerar_codigo_verificacao()
    verificacao = repo.get(user.id, travar=True)

    if verificacao is None:
        repo.add(
            VerificacaoEmail(
                user_id=user.id,
                codigo_hash=hash_codigo(user.id, codigo),
                expira_em=momento + timedelta(minutes=cfg.email_code_expire_minutes),
                tentativas=0,
                enviado_em=momento,
                janela_inicio=momento,
                envios_na_janela=1,
            )
        )
        return codigo

    liberado_em = verificacao.enviado_em + timedelta(seconds=cfg.email_code_resend_seconds)
    if momento < liberado_em:
        espera = _segundos_ate(liberado_em, momento)
        db.rollback()  # solta a trava
        raise TooManyRequestsError(
            f"Aguarde {espera} segundos para pedir um novo código.", retry_after=espera
        )

    if momento - verificacao.janela_inicio >= JANELA_ENVIOS:
        verificacao.janela_inicio, verificacao.envios_na_janela = momento, 0
    if verificacao.envios_na_janela >= cfg.email_code_max_sends_per_hour:
        espera = _segundos_ate(verificacao.janela_inicio + JANELA_ENVIOS, momento)
        db.rollback()
        raise TooManyRequestsError(
            f"Limite de códigos atingido. Tente novamente em {math.ceil(espera / 60)} minuto(s).",
            retry_after=espera,
        )

    verificacao.codigo_hash = hash_codigo(user.id, codigo)
    verificacao.expira_em = momento + timedelta(minutes=cfg.email_code_expire_minutes)
    verificacao.tentativas = 0
    verificacao.enviado_em = momento
    verificacao.envios_na_janela += 1
    db.flush()
    return codigo


def _enviar_e_confirmar(
    db: Session, user: User, codigo: str, montar=_mensagem_codigo
) -> None:
    """Envia o email e só então faz commit.

    Se o envio falhar, a transação inteira é desfeita: no cadastro, a conta
    nem chega a ser criada (a usuária pode simplesmente tentar de novo, em
    vez de ficar com uma conta presa sem código). O erro técnico vai para o
    log; a usuária recebe só uma mensagem genérica.

    Raises:
        EmailIndisponivelError: o servidor de email recusou ou não respondeu.
    """
    minutos = get_settings().email_code_expire_minutes
    try:
        email_core.enviar(montar(user, codigo, minutos))
    except email_core.EmailEnvioError:
        db.rollback()
        logger.exception("Falha ao enviar código de verificação para %s", mascarar_email(user.email))
        raise EmailIndisponivelError(
            "Não foi possível enviar o email de verificação agora. Tente novamente em instantes."
        ) from None
    db.commit()


def _checar_validade(db: Session, verificacao: VerificacaoEmail) -> None:
    """Recusa o código se as tentativas acabaram ou se ele expirou.

    Tentativas antes da validade: esgotadas, nem um código certo é aceito.
    """
    cfg = get_settings()
    if verificacao.tentativas >= cfg.email_code_max_attempts:
        db.rollback()
        raise TooManyRequestsError(
            "Muitas tentativas erradas. Peça um novo código.", codigo="tentativas_esgotadas"
        )
    if agora() > verificacao.expira_em:
        db.rollback()
        raise BusinessRuleError("Este código expirou. Peça um novo.", codigo="codigo_expirado")


def registrar(db: Session, dados: RegistroIn) -> User:
    """Cria uma usuária nova — com repertório 100% vazio e email NÃO verificado.

    Se já existe uma conta PENDENTE com o email, ela é retomada por quem está
    se cadastrando agora: a senha e o nome são substituídos e um código novo
    é enviado (o anterior deixa de valer). Quem cadastrou antes e não
    confirmou nunca provou ser dona do email, então não tem direito à conta.

    Raises:
        ConflictError: email já cadastrado E confirmado.
        TooManyRequestsError: recadastro antes do intervalo de reenvio.
        EmailIndisponivelError: falha ao enviar o código (nada é gravado).
    """
    repo = UserRepository(db)
    repo.apagar_pendentes_antigos(agora() - PENDENTE_EXPIRA)
    email = dados.email.lower()
    user = repo.get_by_email(email, travar=True)

    if user is not None and user.email_verificado:
        db.rollback()
        raise ConflictError("Já existe uma conta com este email.")

    if user is None:
        user = User(
            email=email,
            senha_hash=hash_password(dados.senha),
            nome=dados.nome,
            email_verificado=False,
        )
        try:
            repo.add(user)
        except IntegrityError:
            # Corrida entre dois cadastros simultâneos: a unique do banco decide.
            db.rollback()
            raise ConflictError("Já existe uma conta com este email.") from None
    else:
        user.senha_hash = hash_password(dados.senha)
        user.nome = dados.nome
        logger.info("Cadastro pendente retomado para %s", mascarar_email(email))

    codigo = _preparar_codigo(db, user)
    _enviar_e_confirmar(db, user, codigo)
    logger.info("Código de verificação enviado para %s (cadastro)", mascarar_email(email))
    return user


def reenviar_codigo(db: Session, email: str) -> None:
    """Envia um novo código, se houver conta pendente com este email.

    Para email inexistente ou já verificado, não faz nada e o router devolve
    a MESMA resposta — assim o endpoint não serve para descobrir quais
    emails têm conta.

    Raises:
        TooManyRequestsError: pedido cedo demais ou acima do limite por hora.
        EmailIndisponivelError: falha ao enviar.
    """
    user = UserRepository(db).get_by_email(email, travar=True)
    if user is None or user.email_verificado:
        db.rollback()
        return
    codigo = _preparar_codigo(db, user)
    _enviar_e_confirmar(db, user, codigo)
    logger.info("Código de verificação reenviado para %s", mascarar_email(email))


def verificar_email(db: Session, email: str, codigo: str, senha: str) -> str:
    """Confere código + senha e, se certos, marca o email como verificado.

    Returns:
        str: um JWT de acesso — confirmar o email já deixa a usuária logada.

    Raises:
        BusinessRuleError: código ou senha errados (com quantas tentativas
            restam), código expirado, ou nada pendente para este email.
        TooManyRequestsError: tentativas esgotadas (por código ou por hora).
    """
    rate_limit.consumir(db, rate_limit.VERIFICAR_POR_EMAIL, email)
    cfg = get_settings()
    user = UserRepository(db).get_by_email(email, travar=True)
    if user is None:
        verify_password(senha, _HASH_FICTICIO)  # mesmo tempo de resposta
        db.rollback()
        raise BusinessRuleError(_CODIGO_INVALIDO)
    if user.email_verificado:
        # Só quem sabe a senha descobre que a conta já está confirmada.
        senha_ok = verify_password(senha, user.senha_hash)
        db.rollback()
        if senha_ok:
            raise BusinessRuleError(
                "Este email já foi confirmado. Faça login.", codigo="email_ja_verificado"
            )
        raise BusinessRuleError(_CODIGO_INVALIDO)

    repo = VerificacaoEmailRepository(db)
    verificacao = repo.get(user.id, travar=True)
    if verificacao is None:
        db.rollback()
        raise BusinessRuleError(_CODIGO_INVALIDO)

    _checar_validade(db, verificacao)

    codigo_ok = codigo_confere(user.id, codigo, verificacao.codigo_hash)
    senha_ok = codigo_ok and verify_password(senha, user.senha_hash)
    if not senha_ok:
        verificacao.tentativas += 1
        restantes = cfg.email_code_max_attempts - verificacao.tentativas
        db.commit()  # grava a tentativa e solta a trava
        logger.warning("Verificação recusada para %s (%s)", mascarar_email(email),
                       "senha" if codigo_ok else "código")
        if restantes <= 0:
            raise TooManyRequestsError(
                "As tentativas acabaram; peça um novo código.", codigo="tentativas_esgotadas"
            )
        if not codigo_ok:
            raise BusinessRuleError(
                f"Código incorreto. Você ainda tem {restantes} tentativa(s).",
                codigo="codigo_incorreto",
            )
        raise BusinessRuleError(
            "A senha não confere com a do cadastro. Se você se cadastrou de novo, use a "
            f"senha mais recente. Restam {restantes} tentativa(s).",
            codigo="senha_incorreta",
        )

    user.email_verificado = True
    user.email_verificado_em = agora()
    repo.delete(verificacao)
    db.commit()
    logger.info("Email confirmado: %s", mascarar_email(email))
    return create_access_token(user.id, versao=user.token_version)


def esqueci_senha(db: Session, email: str) -> None:
    """Envia um código de redefinição, se houver conta VERIFICADA com este email.

    Para email inexistente ou conta pendente não faz nada, e o router devolve
    a MESMA resposta: o endpoint não serve para descobrir quais emails têm
    conta. (Conta pendente não precisa disto: ela se recadastra.)

    Raises:
        TooManyRequestsError: pedido cedo demais ou acima do limite por hora.
        EmailIndisponivelError: falha ao enviar.
    """
    user = UserRepository(db).get_by_email(email, travar=True)
    if user is None or not user.email_verificado:
        db.rollback()
        return
    codigo = _preparar_codigo(db, user)
    _enviar_e_confirmar(db, user, codigo, _mensagem_redefinicao)
    logger.info("Código de redefinição de senha enviado para %s", mascarar_email(email))


def redefinir_senha(db: Session, email: str, codigo: str, nova_senha: str) -> None:
    """Confere o código e, se certo, troca a senha.

    Não devolve token: a usuária entra depois, com a senha nova. Todos os
    tokens emitidos antes (`token_version`) deixam de valer. O código é
    apagado ao ser usado (não vale duas vezes).

    Raises:
        BusinessRuleError: código errado (com quantas tentativas restam),
            expirado, ou nenhum código pendente para este email.
        TooManyRequestsError: tentativas esgotadas (por código ou por hora).
    """
    rate_limit.consumir(db, rate_limit.REDEFINIR_POR_EMAIL, email)
    cfg = get_settings()
    user = UserRepository(db).get_by_email(email, travar=True)
    if user is None or not user.email_verificado:
        db.rollback()
        raise BusinessRuleError(_CODIGO_INVALIDO_REDEFINICAO)

    repo = VerificacaoEmailRepository(db)
    verificacao = repo.get(user.id, travar=True)
    if verificacao is None:
        db.rollback()
        raise BusinessRuleError(_CODIGO_INVALIDO_REDEFINICAO)
    _checar_validade(db, verificacao)

    if not codigo_confere(user.id, codigo, verificacao.codigo_hash):
        verificacao.tentativas += 1
        restantes = cfg.email_code_max_attempts - verificacao.tentativas
        db.commit()  # grava a tentativa e solta a trava
        logger.warning("Redefinição de senha recusada para %s (código)", mascarar_email(email))
        if restantes <= 0:
            raise TooManyRequestsError(
                "As tentativas acabaram; peça um novo código.", codigo="tentativas_esgotadas"
            )
        raise BusinessRuleError(
            f"Código incorreto. Você ainda tem {restantes} tentativa(s).",
            codigo="codigo_incorreto",
        )

    user.senha_hash = hash_password(nova_senha)
    user.token_version += 1  # derruba as sessões abertas em outros dispositivos
    repo.delete(verificacao)
    db.commit()
    logger.info("Senha redefinida: %s", mascarar_email(email))


def autenticar(db: Session, email: str, senha: str) -> str:
    """Valida credenciais e devolve um JWT de acesso.

    Raises:
        TooManyRequestsError: muitas tentativas para este email.
        AuthenticationError: email ou senha inválidos (mensagem única para os
            dois casos, para não revelar quais emails existem).
        EmailNaoVerificadoError: senha certa, mas email ainda não confirmado.
            Checado só depois da senha: quem não sabe a senha não descobre
            que a conta está pendente.
    """
    rate_limit.consumir(db, rate_limit.LOGIN_POR_EMAIL, email)
    user = UserRepository(db).get_by_email(email)
    if user is None:
        verify_password(senha, _HASH_FICTICIO)
        logger.warning("Login recusado (email desconhecido): %s", mascarar_email(email))
        raise AuthenticationError("Email ou senha inválidos.")
    if not verify_password(senha, user.senha_hash):
        logger.warning("Login recusado (senha errada): %s", mascarar_email(email))
        raise AuthenticationError("Email ou senha inválidos.")
    if not user.email_verificado:
        raise EmailNaoVerificadoError(
            "Confirme seu email antes de entrar: digite o código que enviamos para "
            f"{user.email}."
        )
    return create_access_token(user.id, versao=user.token_version)
