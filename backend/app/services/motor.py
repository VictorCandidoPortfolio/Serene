"""Ponte entre a base de conhecimento (banco) e o motor (funções puras).

O motor não conhece SQLAlchemy. Este módulo carrega regras, relações e
famílias via `KnowledgeRepository`, converte para os tipos do motor e traduz
erros de regra para erros de domínio.

Importante: este contexto NÃO carrega essências. Essências entram no motor
só pelos services pessoais, a partir de repositórios filtrados por dona —
assim nunca há como uma nota de conhecimento virar candidata de sugestão.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import cached_property
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import KnowledgeUnavailableError
from app.core.text import chave
from app.engine.axes import EIXOS, EssenciaMotor, RegraInvalidaError
from app.engine.compatibility import RelacaoFamilias
from app.engine.gaps import FamiliaRef
from app.models.knowledge import KnowledgeFamily
from app.models.repertorio import Essencia
from app.repositories.knowledge import KnowledgeRepository

# Eixos que as notas de referência informam (v5, complexidade, não tem
# referência: depende da essência concreta da aluna).
EIXOS_DE_REFERENCIA = ("v1", "v2", "v3", "v4", "v6")


@contextmanager
def regras_obrigatorias() -> Iterator[None]:
    """Converte `RegraInvalidaError` do motor em `KnowledgeUnavailableError` (503)."""
    try:
        yield
    except RegraInvalidaError as exc:
        raise KnowledgeUnavailableError(
            f"{exc} Execute o seed da base de conhecimento (python -m app.seed)."
        ) from exc


class ContextoMotor:
    """Dados de conhecimento prontos para o motor, carregados sob demanda.

    Um contexto por requisição: `cached_property` evita reconsultar a mesma
    tabela várias vezes dentro de uma operação, sem cache global que ficaria
    desatualizado depois de um novo seed.
    """

    def __init__(self, db: Session):
        self.repo = KnowledgeRepository(db)

    @cached_property
    def _familias(self) -> list[KnowledgeFamily]:
        return list(self.repo.familias())

    @cached_property
    def _indice_familias(self) -> dict[str, KnowledgeFamily]:
        """Aceita tanto o slug quanto o nome ("Cítrico" → citrico)."""
        idx: dict[str, KnowledgeFamily] = {}
        for f in self._familias:
            idx[chave(f.nome)] = f
            # "Aquático/Marinho" também é reconhecida como "Aquático" ou "Marinho".
            for parte in f.nome.split("/"):
                idx.setdefault(chave(parte), f)
            idx[f.slug] = f  # slug tem prioridade sobre nome em caso de colisão
        return idx

    def familia_por_texto(self, texto: str | None) -> KnowledgeFamily | None:
        """Família da base que corresponde ao texto livre da aluna, se houver."""
        return self._indice_familias.get(chave(texto)) if texto else None

    @cached_property
    def hierarquia(self) -> dict[str, str]:
        """{slug_subfamilia: slug_mae}."""
        por_id = {f.id: f for f in self._familias}
        return {f.slug: por_id[f.parent_id].slug for f in self._familias if f.parent_id in por_id}

    @cached_property
    def relacoes(self) -> list[RelacaoFamilias]:
        """Relações entre famílias, em slugs."""
        por_id = {f.id: f.slug for f in self._familias}
        return [
            RelacaoFamilias(
                por_id[r.family_a_id], por_id[r.family_b_id], r.tipo_relacao, r.peso, r.descricao
            )
            for r in self.repo.relacoes()
            if r.family_a_id in por_id and r.family_b_id in por_id
        ]

    @cached_property
    def familias_ref(self) -> list[FamiliaRef]:
        """Famílias com o vetor médio das notas de referência de cada uma.

        O vetor médio só serve para NOMEAR lacunas ("falta algo cítrico"),
        nunca como candidato de sugestão.
        """
        por_id = {f.id: f for f in self._familias}
        acumulado: dict[int, dict[str, list[float]]] = {}
        for nota in self.repo.notas():
            if nota.family_id is None:
                continue
            for eixo in EIXOS_DE_REFERENCIA:
                valor = getattr(nota, f"{eixo}_ref")
                if valor is not None:
                    acumulado.setdefault(nota.family_id, {}).setdefault(eixo, []).append(valor)
        out = []
        for f in self._familias:
            medias = {e: sum(v) / len(v) for e, v in acumulado.get(f.id, {}).items()}
            parent = por_id.get(f.parent_id)
            out.append(FamiliaRef(f.slug, f.nome, parent.slug if parent else None, medias or None))
        return out

    def parametros(self, chave_regra: str) -> dict[str, Any]:
        """Regra `peso_score/<chave>` (parâmetros numéricos do motor).

        Raises:
            KnowledgeUnavailableError: regra ausente (seed não executado).
        """
        regra = self.repo.regra("peso_score", chave_regra)
        if regra is None or not isinstance(regra.valor, dict):
            raise KnowledgeUnavailableError(
                f"Regra 'peso_score/{chave_regra}' ausente na base de conhecimento. "
                "Execute o seed (python -m app.seed)."
            )
        return regra.valor

    def essencia_motor(self, e: Essencia) -> EssenciaMotor:
        """Converte uma essência DA USUÁRIA para o formato do motor.

        A subfamília (mais específica) tem prioridade no reconhecimento; se a
        aluna escreveu uma família que não existe na base, `familia_chave`
        fica None e o motor trata como "família desconhecida".
        """
        fam = self.familia_por_texto(e.subfamilia) or self.familia_por_texto(e.familia)
        return EssenciaMotor(
            id=e.id,
            nome=e.nome,
            familia=e.familia,
            familia_chave=fam.slug if fam else None,
            vetor={eixo: getattr(e, eixo) for eixo in EIXOS},
            papel=e.papel or None,
        )
