"""Exceções de domínio, independentes de HTTP.

Services levantam estas exceções; `app.main` as traduz para respostas HTTP.
Assim a regra de negócio não importa FastAPI e os routers não precisam de
try/except repetido.
"""


class DomainError(Exception):
    """Base de todos os erros de domínio.

    Attributes:
        message: texto que vai para o cliente (campo `detail` da resposta).
        codigo: identificador estável e opcional (campo `codigo`), para o
            frontend reagir a um erro específico sem depender do texto — ex.:
            "email_nao_verificado" leva à tela de digitar o código.
    """

    codigo_padrao: str | None = None

    def __init__(self, message: str, codigo: str | None = None):
        super().__init__(message)
        self.message = message
        self.codigo = codigo or self.codigo_padrao


class NotFoundError(DomainError):
    """Registro inexistente OU pertencente a outra usuária.

    IMPORTANTE (isolamento): propositalmente não existe um "ForbiddenError"
    para registros de outra usuária. Responder 403 revelaria que o id existe;
    respondendo 404 nos dois casos, uma usuária não consegue nem sondar quais
    ids pertencem a outras.
    """


class ConflictError(DomainError):
    """Violação de unicidade de negócio (ex.: email já cadastrado)."""


class AuthenticationError(DomainError):
    """Credenciais inválidas."""


class EmailNaoVerificadoError(DomainError):
    """A conta existe e a senha confere, mas o email ainda não foi confirmado.

    Mapeado para 403 (e não 401): as credenciais estão certas, só falta um
    passo. Só é levantado DEPOIS de conferir a senha, para que apenas quem
    sabe a senha descubra que a conta está pendente.
    """

    codigo_padrao = "email_nao_verificado"


class BusinessRuleError(DomainError):
    """Entrada sintaticamente válida mas que viola uma regra de negócio."""


class TooManyRequestsError(DomainError):
    """Limite de tentativas/envios atingido (HTTP 429).

    `retry_after` (segundos) vira o header `Retry-After` e o campo
    `retry_after` do corpo — o corpo existe porque o navegador não deixa o
    JavaScript ler headers não padronizados de outra origem sem configuração
    extra de CORS.
    """

    def __init__(self, message: str, retry_after: int | None = None, codigo: str | None = None):
        super().__init__(message, codigo)
        self.retry_after = retry_after


class EmailIndisponivelError(DomainError):
    """O email de verificação não pôde ser enviado (HTTP 503).

    Não é erro da usuária: o servidor SMTP falhou ou está mal configurado.
    """


class FotoIndisponivelError(DomainError):
    """O envio da foto de perfil não está disponível agora (HTTP 503).

    Cloudinary sem configuração no `.env`, fora do ar ou recusando as
    credenciais. Também não é erro da usuária.
    """


class KnowledgeUnavailableError(DomainError):
    """A base de conhecimento não tem os dados que o motor precisa.

    Ex.: regras de `peso_score` ausentes porque o seed não foi executado.
    Mapeado para 503: não é erro da usuária, é configuração do sistema.
    """
