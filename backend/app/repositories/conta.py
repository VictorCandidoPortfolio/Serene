"""Acesso às tabelas de infraestrutura da conta (usadas antes do login)."""

from datetime import datetime, timedelta

from sqlalchemy import case, delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.conta import LimiteRequisicao, VerificacaoEmail


class VerificacaoEmailRepository:
    """Código de verificação pendente de cada usuária (no máximo um).

    Sem escopo por dona porque a usuária ainda não tem token; o `user_id`
    vem sempre de uma busca por email feita pelo `auth_service`, nunca da
    requisição.
    """

    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int, travar: bool = False) -> VerificacaoEmail | None:
        """Verificação pendente da usuária, ou None.

        Args:
            travar: faz `SELECT ... FOR UPDATE`. Com isso, duas requisições
                simultâneas para a mesma conta são atendidas uma de cada vez
                (a segunda espera o commit da primeira). Sem a trava, palpites
                em paralelo liam o mesmo contador de tentativas e o limite era
                burlado — 12 conferências com limite 5, nos testes.
        """
        stmt = select(VerificacaoEmail).where(VerificacaoEmail.user_id == user_id)
        if travar:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def add(self, verificacao: VerificacaoEmail) -> VerificacaoEmail:
        """Insere a primeira verificação da usuária."""
        self.db.add(verificacao)
        self.db.flush()
        return verificacao

    def delete(self, verificacao: VerificacaoEmail) -> None:
        """Remove a verificação (depois que o email foi confirmado)."""
        self.db.delete(verificacao)
        self.db.flush()


class LimiteRequisicaoRepository:
    """Contadores de limite de requisições (ver `app.core.rate_limit`)."""

    def __init__(self, db: Session):
        self.db = db

    def incrementar(self, chave: str, janela: timedelta, momento: datetime) -> LimiteRequisicao:
        """Soma 1 ao contador da chave, numa ÚNICA instrução atômica.

        Se a janela anterior já acabou, recomeça do 1. Fazer isso no banco (e
        não ler-somar-gravar no Python) é o que impede requisições paralelas
        de "perderem" incrementos e passarem do limite.

        No MySQL, as atribuições do ON DUPLICATE KEY UPDATE são avaliadas da
        esquerda para a direita e cada uma já enxerga o valor novo das
        anteriores; por isso `contador` vem antes de `janela_inicio` (o teste
        de "janela expirada" precisa ver a janela antiga).

        Returns:
            A linha atualizada (contador e início da janela atuais).
        """
        tabela = LimiteRequisicao.__table__
        expirada = tabela.c.janela_inicio <= momento - janela
        novos = [
            ("contador", case((expirada, 1), else_=tabela.c.contador + 1)),
            ("janela_inicio", case((expirada, momento), else_=tabela.c.janela_inicio)),
        ]
        valores = {"chave": chave, "janela_inicio": momento, "contador": 1}
        if self.db.get_bind().dialect.name == "mysql":
            stmt = mysql_insert(tabela).values(**valores).on_duplicate_key_update(novos)
        else:
            # SQLite (testes): no ON CONFLICT todas as expressões enxergam a linha antiga.
            stmt = sqlite_insert(tabela).values(**valores).on_conflict_do_update(
                index_elements=["chave"], set_=dict(novos)
            )
        self.db.execute(stmt)
        # populate_existing: relê do banco mesmo que a linha já esteja na sessão.
        return self.db.get(LimiteRequisicao, chave, populate_existing=True)

    def limpar_expirados(self, antes_de: datetime) -> None:
        """Apaga contadores cuja janela começou antes de `antes_de`."""
        self.db.execute(delete(LimiteRequisicao).where(LimiteRequisicao.janela_inicio < antes_de))
