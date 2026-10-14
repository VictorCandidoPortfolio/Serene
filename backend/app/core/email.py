"""Envio de email, com três "backends" escolhidos por `EMAIL_BACKEND`.

- `smtp`: envio real (Gmail, Outlook, SendGrid, Mailtrap...), configurado
  pelas variáveis `SMTP_*` do `.env`. Usa só a biblioteca padrão (`smtplib`).
- `console`: só imprime o email no terminal do uvicorn. Para desenvolver
  sem ter um email configurado. NUNCA use em produção: o código de
  verificação ficaria no log em vez de chegar à usuária.
- `memory`: guarda os emails numa lista em memória (`caixa_de_saida()`).
  Usado pelos testes para ler o código enviado sem depender de rede.

Quem chama não sabe qual backend está ativo: chama `enviar()` e trata
`EmailEnvioError`.
"""

import smtplib
import ssl
import sys
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings

# Evita que uma requisição fique presa indefinidamente num servidor SMTP lento.
TIMEOUT_SMTP_SEGUNDOS = 15

_caixa_memoria: list["Mensagem"] = []


class EmailEnvioError(Exception):
    """O email não pôde ser enviado (servidor fora, credencial errada...).

    A mensagem é técnica e vai só para o log; a usuária recebe um texto
    genérico (ver `auth_service`).
    """


@dataclass(frozen=True)
class Mensagem:
    """Um email a enviar: texto puro sempre, HTML opcional."""

    para: str
    assunto: str
    texto: str
    html: str | None = None


def caixa_de_saida() -> list[Mensagem]:
    """Emails "enviados" pelo backend `memory` (só faz sentido em testes)."""
    return _caixa_memoria


def enviar(mensagem: Mensagem) -> None:
    """Envia um email pelo backend configurado.

    Raises:
        EmailEnvioError: se o envio falhar.
    """
    backend = get_settings().email_backend
    if backend == "memory":
        _caixa_memoria.append(mensagem)
    elif backend == "console":
        print(
            f"\n[EMAIL_BACKEND=console] Para: {mensagem.para}\n"
            f"Assunto: {mensagem.assunto}\n\n{mensagem.texto}\n",
            file=sys.stderr,
            flush=True,
        )
    else:
        _enviar_smtp(mensagem)


def _enviar_smtp(mensagem: Mensagem) -> None:
    """Envio real via SMTP, com STARTTLS (porta 587), SSL (465) ou sem cifra."""
    cfg = get_settings()
    msg = EmailMessage()
    msg["Subject"] = mensagem.assunto
    msg["From"] = formataddr(("Sérené", cfg.smtp_from))
    msg["To"] = mensagem.para
    msg.set_content(mensagem.texto)
    if mensagem.html:
        msg.add_alternative(mensagem.html, subtype="html")

    # Contexto padrão = valida o certificado do servidor (sem isso, a senha do
    # SMTP poderia ser interceptada por um servidor falso no meio do caminho).
    contexto = ssl.create_default_context()
    try:
        if cfg.smtp_security == "ssl":
            servidor = smtplib.SMTP_SSL(
                cfg.smtp_host, cfg.smtp_port, timeout=TIMEOUT_SMTP_SEGUNDOS, context=contexto
            )
        else:
            servidor = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=TIMEOUT_SMTP_SEGUNDOS)
        with servidor:
            if cfg.smtp_security == "starttls":
                servidor.starttls(context=contexto)
            if cfg.smtp_user:
                servidor.login(cfg.smtp_user, cfg.smtp_password)
            servidor.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        # OSError cobre DNS errado, conexão recusada e timeout.
        raise EmailEnvioError(f"Falha no envio SMTP para {cfg.smtp_host}: {exc}") from exc
