"""Models de infraestrutura da CONTA (não são repertório nem conhecimento).

`VerificacaoEmail` guarda o código de 4 dígitos pendente de cada usuária.
Não passa pelos repositórios escopados por dona porque é usado ANTES do
login (a usuária ainda não tem token); quem o acessa é só `auth_service`,
sempre a partir do email informado.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VerificacaoEmail(Base):
    """Código de verificação pendente — no máximo um por usuária (`user_id` único).

    Pedir um código novo SOBRESCREVE o anterior, que deixa de valer. A linha é
    apagada quando o email é confirmado.

    Datas em UTC "ingênuo" (sem fuso), calculadas no Python: comparar com o
    `NOW()` do MySQL dependeria do fuso configurado no servidor do banco.
    """

    __tablename__ = "verificacoes_email"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # HMAC-SHA256 do código (nunca o código em texto puro).
    codigo_hash: Mapped[str] = mapped_column(String(64))
    expira_em: Mapped[datetime] = mapped_column(DateTime)
    # Tentativas erradas com o código ATUAL; zera a cada código novo.
    tentativas: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    enviado_em: Mapped[datetime] = mapped_column(DateTime)
    # Janela de 1 hora para limitar quantos códigos podem ser enviados
    # (protege a caixa de entrada contra spam e limita a força bruta).
    janela_inicio: Mapped[datetime] = mapped_column(DateTime)
    envios_na_janela: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class LimiteRequisicao(Base):
    """Contador de tentativas por janela de tempo (limite de requisições).

    Fica no banco, e não na memória do processo, porque no Vercel cada
    requisição pode cair numa instância diferente da função: um contador em
    memória seria zerado a cada instância nova e não limitaria nada.

    `chave` é "<tipo de limite>:<sha256 do IP ou email>" — o hash evita
    guardar IPs e emails em claro nesta tabela.
    """

    __tablename__ = "limites_requisicao"

    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    janela_inicio: Mapped[datetime] = mapped_column(DateTime)
    contador: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
