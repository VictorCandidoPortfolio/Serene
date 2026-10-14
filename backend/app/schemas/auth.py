"""Schemas de autenticação e verificação de email."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import DIGITOS_CODIGO, problemas_da_senha
from app.schemas.common import EdicaoModel, EntradaModel, ORMModel


def _exigir_senha_forte(senha: str) -> str:
    """Validador compartilhado por cadastro e redefinição de senha."""
    problemas = problemas_da_senha(senha)
    if problemas:
        raise ValueError(" e ".join(problemas))
    return senha


class RegistroIn(EntradaModel):
    """Cadastro de uma nova usuária.

    A força da senha é validada aqui (e não só no frontend), porque qualquer
    cliente pode chamar a API diretamente. A regra mora em
    `app.core.security.problemas_da_senha`.
    """

    email: EmailStr
    senha: str = Field(min_length=1, max_length=72)
    nome: str = Field(min_length=1, max_length=120)

    @field_validator("senha")
    @classmethod
    def _senha_forte(cls, senha: str) -> str:
        return _exigir_senha_forte(senha)


class VerificarEmailIn(EntradaModel):
    """Email + código de 4 dígitos recebido por email + senha do cadastro."""

    email: EmailStr
    # String (e não int) para preservar zeros à esquerda: "0427" ≠ 427.
    codigo: str = Field(pattern=rf"^\d{{{DIGITOS_CODIGO}}}$")
    # A senha confirma que quem digita o código é quem definiu a senha da
    # conta (ver auth_service: correção de sequestro de conta pendente).
    senha: str = Field(min_length=1, max_length=72)


class ReenviarCodigoIn(EntradaModel):
    """Pedido de um novo código de verificação."""

    email: EmailStr


class EsqueciSenhaIn(EntradaModel):
    """Pedido de código para redefinir a senha."""

    email: EmailStr


class RedefinirSenhaIn(EntradaModel):
    """Email + código de 4 dígitos recebido por email + nova senha (forte)."""

    email: EmailStr
    codigo: str = Field(pattern=rf"^\d{{{DIGITOS_CODIGO}}}$")
    nova_senha: str = Field(min_length=1, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def _senha_forte(cls, senha: str) -> str:
        return _exigir_senha_forte(senha)


class PerfilUpdateIn(EdicaoModel):
    """Edição dos dados da conta logada (só o que foi enviado muda).

    O email fica de fora de propósito: trocá-lo exige confirmar o endereço
    novo por código, senão bastaria um token roubado para tomar a conta.
    """

    campos_nao_nulos = ("nome",)

    nome: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("nome")
    @classmethod
    def _sem_espacos_nas_pontas(cls, nome: str | None) -> str | None:
        if nome is None:
            return None
        nome = nome.strip()
        if not nome:
            raise ValueError("não pode ficar vazio")
        return nome


class TrocarSenhaIn(EntradaModel):
    """Troca de senha COM a sessão aberta: exige a senha atual."""

    senha_atual: str = Field(min_length=1, max_length=72)
    nova_senha: str = Field(min_length=1, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def _senha_forte(cls, senha: str) -> str:
        return _exigir_senha_forte(senha)


class FotoIn(EntradaModel):
    """Foto de perfil como data URI: "data:image/webp;base64,....".

    O tamanho máximo aqui é só uma primeira barreira (2 MB de imagem viram
    ~2,8 milhões de caracteres em base64); tipo e conteúdo reais são
    conferidos em `conta_service.decodificar_foto`.
    """

    imagem: str = Field(min_length=1, max_length=2_900_000)


class MensagemOut(BaseModel):
    """Resposta simples com um texto para a usuária."""

    mensagem: str


class UserOut(ORMModel):
    """Dados públicos da conta (nunca inclui `senha_hash`)."""

    id: int
    email: str
    nome: str
    email_verificado: bool = False
    # Endereço público da foto no Cloudinary (o public_id fica só no banco).
    foto_url: str | None = None
    criado_em: datetime | None = None


class RegistroOut(UserOut):
    """Resposta do cadastro: a conta (ainda não verificada) + prazos do código.

    Os prazos vêm do servidor para o frontend não precisar adivinhar a
    configuração (eles mudam pelo `.env`).
    """

    codigo_expira_minutos: int
    reenvio_em_segundos: int


class CodigoEnviadoOut(BaseModel):
    """Resposta do reenvio. A mensagem é a mesma exista ou não a conta."""

    mensagem: str
    reenvio_em_segundos: int


class TokenOut(ORMModel):
    """Resposta do login, no formato esperado pelo OAuth2 do Swagger."""

    access_token: str
    token_type: str = "bearer"
