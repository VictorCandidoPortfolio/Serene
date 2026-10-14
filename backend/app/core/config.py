"""Leitura centralizada das variáveis de ambiente.

Por que um módulo só para isso: todo segredo (string de conexão, chave do JWT,
senha do email) entra no sistema por aqui e por nenhum outro lugar. Isso
facilita auditar que nada sensível está hardcoded e permite que os testes
troquem a configuração definindo variáveis de ambiente *antes* de importar a
aplicação.

O `.env` é carregado com `override=False`: variáveis já definidas no ambiente
real (CI, container, testes) têm prioridade sobre o arquivo.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(override=False)

EMAIL_BACKENDS = ("smtp", "console", "memory")
SMTP_SEGURANCAS = ("starttls", "ssl", "nenhuma")
AMBIENTES = ("development", "production")
# Só algoritmos HMAC: a chave é simétrica (JWT_SECRET_KEY). Aceitar "none" ou
# RS256 aqui só quebraria o login — ou, pior, abriria brecha em outra lib.
ALGORITMOS_JWT = ("HS256", "HS384", "HS512")
# Valores de exemplo publicados no repositório. Subir com um deles permitiria
# a QUALQUER pessoa forjar tokens, então a API se recusa a iniciar.
SEGREDOS_DE_EXEMPLO = {
    "troque-esta-chave-por-uma-aleatoria-e-longa",
    "changeme",
    "secret",
}


class ConfigError(RuntimeError):
    """Configuração obrigatória ausente ou inválida."""


def _required(name: str) -> str:
    """Lê uma variável obrigatória, falhando cedo e com mensagem clara.

    Falhar na inicialização é preferível a subir uma API com, por exemplo,
    uma chave de JWT vazia — o que tornaria qualquer token forjável.
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(
            f"Variável de ambiente obrigatória '{name}' não definida. "
            "Copie .env.example para .env e preencha."
        )
    return value


def _int(name: str, default: int, minimo: int = 0) -> int:
    """Lê um inteiro opcional, com valor mínimo aceito."""
    bruto = os.getenv(name, "").strip()
    if not bruto:
        return default
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ConfigError(f"{name} deve ser um número inteiro.") from exc
    if valor < minimo:
        raise ConfigError(f"{name} deve ser no mínimo {minimo}.")
    return valor


def _bool(name: str, default: bool) -> bool:
    """Lê um booleano ("true"/"false", "1"/"0", "sim"/"nao")."""
    bruto = os.getenv(name, "").strip().lower()
    if not bruto:
        return default
    if bruto in ("1", "true", "sim", "yes", "on"):
        return True
    if bruto in ("0", "false", "nao", "não", "no", "off"):
        return False
    raise ConfigError(f"{name} deve ser true ou false (recebido: '{bruto}').")


def _opcao(name: str, default: str, opcoes: tuple[str, ...]) -> str:
    """Lê uma variável que só aceita valores de uma lista fixa."""
    valor = os.getenv(name, default).strip().lower() or default
    if valor not in opcoes:
        raise ConfigError(f"{name} deve ser um de: {', '.join(opcoes)} (recebido: '{valor}').")
    return valor


@dataclass(frozen=True)
class Settings:
    """Configuração imutável da aplicação (frozen: ninguém altera em runtime)."""

    app_env: str
    database_url: str
    database_ssl: bool
    database_ssl_ca: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    # --- operação (ver app/main.py)
    docs_enabled: bool
    log_level: str
    trust_proxy_headers: bool
    rate_limit_enabled: bool
    # --- envio de email (ver app/core/email.py)
    email_backend: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_security: str
    # --- código de verificação de email (ver app/services/auth_service.py)
    email_code_expire_minutes: int
    email_code_max_attempts: int
    email_code_resend_seconds: int
    email_code_max_sends_per_hour: int
    # --- foto de perfil no Cloudinary (ver app/core/cloudinary.py)
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    cloudinary_folder: str

    @property
    def producao(self) -> bool:
        """True quando a API está no ar para usuárias reais."""
        return self.app_env == "production"

    @property
    def fotos_habilitadas(self) -> bool:
        """True quando o Cloudinary está configurado (as três credenciais)."""
        return bool(self.cloudinary_cloud_name)


def _config_smtp(backend: str) -> dict:
    """Lê e valida as variáveis de SMTP.

    Só são obrigatórias com `EMAIL_BACKEND=smtp`: assim dá para desenvolver
    (modo `console`) antes de ter um email configurado, mas é impossível subir
    em modo SMTP com a configuração pela metade e só descobrir no primeiro
    cadastro.
    """
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    seguranca = _opcao("SMTP_SECURITY", "starttls", SMTP_SEGURANCAS)
    cfg = {
        "smtp_host": os.getenv("SMTP_HOST", "").strip(),
        "smtp_port": _int("SMTP_PORT", 465 if seguranca == "ssl" else 587, minimo=1),
        "smtp_user": user,
        "smtp_password": password,
        # Na maioria dos provedores (Gmail, Outlook) o remetente tem de ser a
        # própria conta autenticada; por isso SMTP_FROM cai para SMTP_USER.
        "smtp_from": os.getenv("SMTP_FROM", "").strip() or user,
        "smtp_security": seguranca,
    }
    if backend == "smtp":
        if not cfg["smtp_host"]:
            raise ConfigError("EMAIL_BACKEND=smtp exige SMTP_HOST (ex.: smtp.gmail.com).")
        if not cfg["smtp_from"]:
            raise ConfigError("EMAIL_BACKEND=smtp exige SMTP_FROM ou SMTP_USER.")
        if user and not password:
            raise ConfigError("SMTP_USER foi definido, mas SMTP_PASSWORD está vazio.")
    return cfg


def _config_cloudinary() -> dict:
    """Lê as credenciais do Cloudinary (foto de perfil).

    São opcionais: sem elas a API sobe normalmente e só o envio de foto
    responde 503. Mas preencher só parte delas é erro de digitação/cópia, e
    é melhor descobrir na inicialização do que na primeira foto enviada.
    """
    cfg = {
        "cloudinary_cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME", "").strip(),
        "cloudinary_api_key": os.getenv("CLOUDINARY_API_KEY", "").strip(),
        "cloudinary_api_secret": os.getenv("CLOUDINARY_API_SECRET", "").strip(),
        "cloudinary_folder": os.getenv("CLOUDINARY_FOLDER", "").strip().strip("/") or "serene/perfis",
    }
    credenciais = ("cloudinary_cloud_name", "cloudinary_api_key", "cloudinary_api_secret")
    preenchidas = [c for c in credenciais if cfg[c]]
    if preenchidas and len(preenchidas) != len(credenciais):
        faltando = ", ".join(c.upper() for c in credenciais if not cfg[c])
        raise ConfigError(f"Cloudinary configurado pela metade: falta {faltando}.")
    return cfg


def _validar_producao(cfg: dict) -> None:
    """Regras extras que só valem em produção.

    Cada uma impede um erro de configuração que passaria despercebido até
    alguém ser prejudicado: códigos de verificação impressos num log em vez
    de enviados, ou uma API que nenhum navegador consegue chamar.
    """
    if cfg["email_backend"] != "smtp":
        raise ConfigError(
            "Em produção EMAIL_BACKEND deve ser 'smtp' "
            f"('{cfg['email_backend']}' não envia o email de verdade)."
        )
    if not cfg["cors_origins"]:
        raise ConfigError("Em produção CORS_ORIGINS deve listar a URL do frontend.")
    if "*" in cfg["cors_origins"]:
        raise ConfigError("CORS_ORIGINS não pode ser '*' (a API usa credenciais).")


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuração, lida uma única vez por processo (cacheada).

    `APP_ENV` não definido vira "production" quando a API roda no Vercel (que
    sempre define a variável `VERCEL`) e "development" no computador local.
    Assim, esquecer a variável no deploy é seguro por padrão.

    Returns:
        Settings: valores validados vindos do ambiente / `.env`.

    Raises:
        ConfigError: se alguma variável obrigatória faltar ou for inválida.
    """
    no_vercel = bool(os.getenv("VERCEL"))
    app_env = _opcao("APP_ENV", "production" if no_vercel else "development", AMBIENTES)
    producao = app_env == "production"

    secret = _required("JWT_SECRET_KEY")
    if secret.lower() in SEGREDOS_DE_EXEMPLO or "troque" in secret.lower():
        raise ConfigError(
            "JWT_SECRET_KEY ainda é o valor de exemplo. Gere uma chave com: "
            'python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )
    if len(secret) < 32:
        # HS256 com chave curta é vulnerável a força bruta offline do token.
        raise ConfigError("JWT_SECRET_KEY deve ter pelo menos 32 caracteres.")

    algoritmo = os.getenv("JWT_ALGORITHM", "HS256").strip().upper() or "HS256"
    if algoritmo not in ALGORITMOS_JWT:
        raise ConfigError(f"JWT_ALGORITHM deve ser um de: {', '.join(ALGORITMOS_JWT)}.")

    origins = tuple(
        o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
    )
    # Padrão "smtp": em produção, esquecer a variável deve falhar alto, e não
    # cair silenciosamente num modo que só imprime o código no terminal.
    backend = _opcao("EMAIL_BACKEND", "smtp", EMAIL_BACKENDS)

    cfg = dict(
        app_env=app_env,
        database_url=_required("DATABASE_URL"),
        database_ssl=_bool("DATABASE_SSL", False),
        database_ssl_ca=os.getenv("DATABASE_SSL_CA", "").strip(),
        jwt_secret_key=secret,
        jwt_algorithm=algoritmo,
        jwt_expire_minutes=_int("JWT_EXPIRE_MINUTES", 60, minimo=1),
        cors_origins=origins,
        docs_enabled=_bool("ENABLE_DOCS", not producao),
        log_level=_opcao("LOG_LEVEL", "info", ("debug", "info", "warning", "error")).upper(),
        # No Vercel o IP real da cliente vem em x-forwarded-for, e o próprio
        # Vercel sobrescreve esse header (não dá para falsificar). Fora dele,
        # confiar no header permitiria burlar o limite de tentativas.
        trust_proxy_headers=_bool("TRUST_PROXY_HEADERS", no_vercel),
        rate_limit_enabled=_bool("RATE_LIMIT_ENABLED", True),
        email_backend=backend,
        **_config_smtp(backend),
        email_code_expire_minutes=_int("EMAIL_CODE_EXPIRE_MINUTES", 10, minimo=1),
        email_code_max_attempts=_int("EMAIL_CODE_MAX_ATTEMPTS", 5, minimo=1),
        email_code_resend_seconds=_int("EMAIL_CODE_RESEND_SECONDS", 60, minimo=0),
        email_code_max_sends_per_hour=_int("EMAIL_CODE_MAX_SENDS_PER_HOUR", 5, minimo=1),
        **_config_cloudinary(),
    )
    if producao:
        _validar_producao(cfg)
    return Settings(**cfg)
