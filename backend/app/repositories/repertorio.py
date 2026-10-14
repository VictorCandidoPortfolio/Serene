"""Repositórios concretos da camada de repertório pessoal.

Cada classe só declara `model` (e, quando precisa, consultas específicas que
SEMPRE partem de `self._select()`). O isolamento vem da classe-base.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.conta import VerificacaoEmail
from app.models.repertorio import (
    Acorde,
    Colecao,
    ColecaoCriacao,
    Criacao,
    Essencia,
    PerfilOlfativo,
    Referencia,
    Teste,
    User,
)
from app.repositories.base import CriacaoChildRepository, OwnedRepository, _validar_user_id


MAX_ITENS_COLECAO = 100


class UserRepository:
    """Acesso a `users`. Não é "pessoal" no sentido de posse: é a própria conta.

    Usado só por autenticação (cadastro/login), por isso não recebe user_id.
    """

    def __init__(self, db):
        self.db = db

    def get_by_email(self, email: str, travar: bool = False) -> User | None:
        """Busca por email (case-insensitive: normalizamos para minúsculas).

        Args:
            travar: `SELECT ... FOR UPDATE` — usado no cadastro e na
                verificação para serializar requisições simultâneas da mesma
                conta. Ordem de travas no projeto: sempre a usuária ANTES da
                verificação (ordem fixa evita deadlock).
        """
        stmt = select(User).where(User.email == email.strip().lower())
        if travar:
            stmt = stmt.with_for_update()
        return self.db.scalar(stmt)

    def apagar_pendentes_antigos(self, corte: datetime) -> int:
        """Apaga contas nunca confirmadas cujo último código saiu antes de `corte`.

        Conta pendente não tem nada além do cadastro (não consegue entrar),
        então não há dado da aluna a perder. Returns: quantas foram apagadas.
        """
        ultimo_envio = (
            select(VerificacaoEmail.enviado_em)
            .where(VerificacaoEmail.user_id == User.id)
            .scalar_subquery()
        )
        alvos = self.db.scalars(
            select(User).where(
                User.email_verificado.is_(False),
                User.criado_em < corte,
                (ultimo_envio.is_(None)) | (ultimo_envio < corte),
            )
        ).all()
        for user in alvos:
            self.db.delete(user)
        self.db.flush()
        return len(alvos)

    def add(self, user: User) -> User:
        """Insere a usuária e devolve com id preenchido."""
        self.db.add(user)
        self.db.flush()
        return user


class EssenciaRepository(OwnedRepository[Essencia]):
    """Essências da aluna — o repertório que alimenta todo o motor."""

    model = Essencia
    nome_recurso = "Essência"
    nome_plural = "essências"
    limite = 1000


class CriacaoRepository(OwnedRepository[Criacao]):
    """Criações da aluna (âncora de posse de acordes e testes)."""

    model = Criacao
    nome_recurso = "Criação"
    nome_plural = "criações"
    limite = 500


class AcordeRepository(CriacaoChildRepository[Acorde]):
    """Versões de acorde — posse via criacoes.user_id."""

    model = Acorde
    nome_recurso = "Acorde"
    nome_plural = "versões de acorde"
    limite = 200


class TesteRepository(CriacaoChildRepository[Teste]):
    """Testes/avaliações — posse via criacoes.user_id."""

    model = Teste
    nome_recurso = "Teste"
    nome_plural = "testes"
    limite = 200


class ReferenciaRepository(OwnedRepository[Referencia]):
    """Fragrâncias de referência (bússola, nunca estoque)."""

    model = Referencia
    nome_recurso = "Referência"
    nome_plural = "referências"
    limite = 500


class PerfilRepository(OwnedRepository[PerfilOlfativo]):
    """Perfis olfativos (questionário + vetor-alvo)."""

    model = PerfilOlfativo
    nome_recurso = "Perfil"
    nome_plural = "perfis"
    limite = 200


class ColecaoRepository(OwnedRepository[Colecao]):
    """Coleções da aluna."""

    model = Colecao
    nome_recurso = "Coleção"
    nome_plural = "coleções"
    limite = 100


class ColecaoItemRepository:
    """Itens de coleção (`colecao_criacoes`) — posse via colecoes.user_id.

    Não herda de `CriacaoChildRepository` porque o pai aqui é a coleção.
    Mesmo princípio: JOIN com o pai e filtro pela dona em toda consulta.
    """

    def __init__(self, db, user_id: int):
        self.db = db
        self.user_id = _validar_user_id(user_id)

    def _select(self):
        return (
            select(ColecaoCriacao)
            .join(Colecao, ColecaoCriacao.colecao_id == Colecao.id)
            .where(Colecao.user_id == self.user_id)
        )

    def list_by_colecao(self, colecao_id: int) -> Sequence[ColecaoCriacao]:
        """Itens da coleção, na ordem definida pela aluna."""
        stmt = (
            self._select()
            .where(ColecaoCriacao.colecao_id == colecao_id)
            .order_by(ColecaoCriacao.ordem, ColecaoCriacao.id)
        )
        return self.db.scalars(stmt).all()

    def get(self, colecao_id: int, criacao_id: int) -> ColecaoCriacao | None:
        """Item (coleção, criação) da dona, ou None."""
        stmt = self._select().where(
            ColecaoCriacao.colecao_id == colecao_id, ColecaoCriacao.criacao_id == criacao_id
        )
        return self.db.scalar(stmt)

    def proxima_ordem(self, colecao: Colecao) -> int:
        """Posição para um item novo (vai para o fim)."""
        self._exigir_dona(colecao)
        atual = self.db.scalar(
            select(func.max(ColecaoCriacao.ordem)).where(ColecaoCriacao.colecao_id == colecao.id)
        )
        return 0 if atual is None else atual + 1

    def add(self, colecao: Colecao, criacao: Criacao, ordem: int) -> ColecaoCriacao:
        """Liga criação à coleção. AMBAS precisam ser da dona.

        Checar só a coleção não basta: sem checar a criação, a usuária A
        poderia colocar a criação da B na coleção dela e passar a lê-la.
        """
        self._exigir_dona(colecao)
        if criacao.user_id != self.user_id:
            raise NotFoundError(f"Criação {criacao.id} não encontrada.")
        total = self.db.scalar(
            select(func.count()).select_from(ColecaoCriacao)
            .where(ColecaoCriacao.colecao_id == colecao.id)
        )
        if total >= MAX_ITENS_COLECAO:
            raise BusinessRuleError(
                f"Limite de {MAX_ITENS_COLECAO} criações por coleção atingido.",
                codigo="limite_atingido",
            )
        item = ColecaoCriacao(colecao_id=colecao.id, criacao_id=criacao.id, ordem=ordem)
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item: ColecaoCriacao) -> None:
        """Remove o vínculo (a criação em si continua existindo)."""
        self.db.delete(item)
        self.db.flush()

    def _exigir_dona(self, colecao: Colecao) -> None:
        if colecao.user_id != self.user_id:
            raise NotFoundError(f"Coleção {colecao.id} não encontrada.")
