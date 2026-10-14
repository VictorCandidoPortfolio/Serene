"""Repositórios-base que IMPÕEM o isolamento entre usuárias.

Por que isto existe: o MySQL não tem Row Level Security. No Postgres/Supabase
original, esquecer um `WHERE user_id = ...` era barrado pelo banco; aqui,
esquecer é vazar dados. Então o filtro não pode depender de disciplina em
cada endpoint — ele está embutido no único caminho de acesso a dados pessoais:

- Um repositório pessoal SÓ pode ser construído com um `user_id` (vindo de
  `get_current_user`). Não existe construtor "sem dona".
- Toda leitura parte de `_select()`, que já traz o filtro de posse. Não há
  método público que aceite um `Select` arbitrário.
- `add()` sobrescreve `user_id` com o da dona do repositório: mesmo que um
  service distraído monte o objeto com outro dono, ele é corrigido.
- Registro de outra usuária é indistinguível de registro inexistente
  (`NotFoundError` → 404), para ninguém sondar ids alheios.

REGRA PARA QUEM FOR ESTENDER: nunca use `session.get(Model, id)` nem
`select(Model)` direto num model pessoal fora daqui. Se precisar de uma
consulta nova, crie um método no repositório que comece por `self._select()`.
"""

from collections.abc import Iterable, Sequence
from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.db.base import Base
from app.models.repertorio import Criacao

M = TypeVar("M", bound=Base)

# Campos que NUNCA podem ser alterados por `update()` — trocar a dona ou o pai
# de um registro seria uma forma de "transferir" dados entre usuárias.
CAMPOS_PROTEGIDOS = frozenset({"id", "user_id", "criacao_id", "colecao_id", "versao", "criado_em"})


def _validar_user_id(user_id: Any) -> int:
    """Recusa construir um repositório sem uma dona válida.

    `bool` é subclasse de `int` em Python; excluí-lo evita `user_id=True`
    virar a usuária 1 por acidente.
    """
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
        raise ValueError("Repositório pessoal exige o id da usuária autenticada.")
    return user_id


class _Escopado(Generic[M]):
    """Parte comum: sessão + dona + utilitários que só usam `_select()`."""

    model: ClassVar[type]
    nome_recurso: ClassVar[str] = "Registro"
    nome_plural: ClassVar[str] = "registros"
    # Cota: máximo de registros por dona (ou por criação, nos filhos). Sem
    # ela, uma conta podia criar registros sem fim e encher o banco — e o
    # motor, que percorre o repertório inteiro, ficaria cada vez mais lento.
    limite: ClassVar[int | None] = None

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = _validar_user_id(user_id)

    def _select(self) -> Select:
        """Consulta-base JÁ filtrada pela dona. Implementada nas subclasses."""
        raise NotImplementedError

    def _nao_encontrado(self, id_: int) -> NotFoundError:
        return NotFoundError(f"{self.nome_recurso} {id_} não encontrado(a).")

    def _exigir_cota(self, total_atual: int, onde: str) -> None:
        """Recusa a inserção se a cota do recurso já foi atingida."""
        if self.limite is not None and total_atual >= self.limite:
            raise BusinessRuleError(
                f"Limite de {self.limite} {self.nome_plural} {onde} atingido.",
                codigo="limite_atingido",
            )

    def update(self, obj: M, campos: dict[str, Any]) -> M:
        """Aplica alterações de campos, ignorando os protegidos.

        O objeto precisa ter sido obtido por este repositório (logo, já
        pertence à dona). Campos de posse/versão são silenciosamente ignorados
        como segunda linha de defesa — os schemas já não os expõem.
        """
        for nome, valor in campos.items():
            if nome in CAMPOS_PROTEGIDOS:
                continue
            setattr(obj, nome, valor)
        self.db.flush()
        return obj


class OwnedRepository(_Escopado[M]):
    """Repositório de tabelas com POSSE DIRETA (coluna `user_id`)."""

    def _select(self) -> Select:
        """`SELECT ... WHERE model.user_id = <dona>` — ponto de partida de tudo."""
        return select(self.model).where(self.model.user_id == self.user_id)

    def list(self, *order_by: Any) -> Sequence[M]:
        """Todos os registros da dona (ordenados por id se nada for passado)."""
        stmt = self._select().order_by(*(order_by or (self.model.id,)))
        return self.db.scalars(stmt).all()

    def get(self, id_: int) -> M | None:
        """Registro da dona com esse id, ou None (inclusive se for de outra)."""
        return self.db.scalar(self._select().where(self.model.id == id_))

    def get_or_404(self, id_: int) -> M:
        """Como `get`, mas levanta `NotFoundError` — nunca 403 (ver exceptions)."""
        obj = self.get(id_)
        if obj is None:
            raise self._nao_encontrado(id_)
        return obj

    def get_many(self, ids: Iterable[int]) -> dict[int, M]:
        """Busca vários ids de uma vez; ids de outra usuária simplesmente não voltam."""
        ids = list(set(ids))
        if not ids:
            return {}
        rows = self.db.scalars(self._select().where(self.model.id.in_(ids))).all()
        return {r.id: r for r in rows}

    def add(self, obj: M) -> M:
        """Insere o registro FORÇANDO a dona (ignora qualquer user_id prévio).

        Raises:
            BusinessRuleError: cota de registros da dona atingida.
        """
        total = self.db.scalar(
            select(func.count()).select_from(self.model).where(self.model.user_id == self.user_id)
        )
        self._exigir_cota(total, "por conta")
        obj.user_id = self.user_id
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: M) -> None:
        """Apaga um registro da dona. Recusa objeto de outra (defesa extra)."""
        if obj.user_id != self.user_id:
            raise self._nao_encontrado(obj.id)
        self.db.delete(obj)
        self.db.flush()


class CriacaoChildRepository(_Escopado[M]):
    """Repositório de tabelas com POSSE TRANSITIVA via `criacao_id`.

    Acordes e testes não têm `user_id`: a dona é `criacoes.user_id`. Toda
    consulta faz JOIN com `criacoes` e filtra pela dona — saber o id de um
    acorde alheio não basta para lê-lo.
    """

    def _select(self) -> Select:
        """`SELECT m.* FROM m JOIN criacoes ... WHERE criacoes.user_id = <dona>`."""
        return (
            select(self.model)
            .join(Criacao, self.model.criacao_id == Criacao.id)
            .where(Criacao.user_id == self.user_id)
        )

    def list_by_criacao(self, criacao_id: int) -> Sequence[M]:
        """Todas as versões de uma criação da dona, da mais antiga à mais nova."""
        stmt = (
            self._select()
            .where(self.model.criacao_id == criacao_id)
            .order_by(self.model.versao)
        )
        return self.db.scalars(stmt).all()

    def get(self, criacao_id: int, id_: int) -> M | None:
        """Registro `id_` DENTRO da criação `criacao_id` e da dona."""
        stmt = self._select().where(self.model.criacao_id == criacao_id, self.model.id == id_)
        return self.db.scalar(stmt)

    def get_or_404(self, criacao_id: int, id_: int) -> M:
        """Como `get`, mas levanta `NotFoundError`."""
        obj = self.get(criacao_id, id_)
        if obj is None:
            raise self._nao_encontrado(id_)
        return obj

    def proxima_versao(self, criacao: Criacao) -> int:
        """Próximo número de versão (max + 1) dentro da criação.

        Exige a `Criacao` já carregada por `CriacaoRepository` — ou seja, já
        validada como da dona. A unique `(criacao_id, versao)` no banco é a
        rede de segurança contra duas requisições simultâneas.
        """
        self._exigir_dona(criacao)
        atual = self.db.scalar(
            select(func.max(self.model.versao)).where(self.model.criacao_id == criacao.id)
        )
        return (atual or 0) + 1

    def add(self, criacao: Criacao, obj: M) -> M:
        """Insere um filho numa criação da dona (nunca por `criacao_id` solto).

        Raises:
            BusinessRuleError: cota de versões da criação atingida.
        """
        self._exigir_dona(criacao)
        total = self.db.scalar(
            select(func.count()).select_from(self.model).where(self.model.criacao_id == criacao.id)
        )
        self._exigir_cota(total, "por criação")
        obj.criacao_id = criacao.id
        self.db.add(obj)
        self.db.flush()
        return obj

    def _exigir_dona(self, criacao: Criacao) -> None:
        if criacao.user_id != self.user_id:
            raise NotFoundError(f"Criação {criacao.id} não encontrada.")
