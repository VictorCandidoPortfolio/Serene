"""Fragrâncias de referência: entender caminhos SEM virar estoque (funcionalidade 2.11).

Uma referência (um perfume comercial que a aluna gosta) não tem fórmula
conhecida. O que dá para fazer com honestidade:
- reconhecer, entre as notas que a aluna SABE (ou supõe) que ela tem, quais
  existem na base de conhecimento;
- estimar para que lado dos eixos essas notas apontam (direção, não fórmula);
- comparar as famílias dessas notas com as famílias do repertório dela:
  o que ela já tem para ir nessa direção e o que falta (lacuna).

Nada aqui devolve essência candidata: as notas da referência servem só para
apontar direção e nomear famílias (regras de negócio 4 e 5).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.engine.axes import EIXOS
from app.engine.vectors import media_vetores


@dataclass(frozen=True)
class NotaDaReferencia:
    """Uma nota citada na referência e reconhecida na base de conhecimento."""

    citada_como: str
    nota: str
    familia_chave: str | None
    familia: str | None
    vetor: dict[str, float | None]


@dataclass(frozen=True)
class AnaliseReferencia:
    """Resultado: direção estimada + famílias que a aluna tem e não tem."""

    vetor_estimado: dict[str, float | None]
    notas_reconhecidas: list[NotaDaReferencia]
    notas_desconhecidas: list[str]
    familias_presentes: list[str]
    familias_ausentes: list[str]
    avisos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        """Serialização para a API."""
        return {
            "vetor_estimado": self.vetor_estimado,
            "notas_reconhecidas": [n.__dict__ for n in self.notas_reconhecidas],
            "notas_desconhecidas": self.notas_desconhecidas,
            "familias_presentes": self.familias_presentes,
            "familias_ausentes": self.familias_ausentes,
            "avisos": self.avisos,
        }


def analisar_referencia(
    notas: Sequence[NotaDaReferencia],
    desconhecidas: Sequence[str],
    familias_do_repertorio: set[str],
) -> AnaliseReferencia:
    """Estima a direção de uma referência e cruza com o repertório da aluna.

    Args:
        notas: notas da referência reconhecidas na base de conhecimento.
        desconhecidas: notas citadas que a base não conhece (só listadas).
        familias_do_repertorio: slugs das famílias que a aluna possui.

    Returns:
        AnaliseReferencia. Sem nenhuma nota reconhecida, o vetor fica todo
        `None` e um aviso diz isso — não há estimativa sem base.
    """
    vetor = media_vetores([n.vetor for n in notas])
    familias: dict[str, str] = {}
    for n in notas:
        if n.familia_chave:
            familias.setdefault(n.familia_chave, n.familia or n.familia_chave)
    presentes = [nome for chave, nome in familias.items() if chave in familias_do_repertorio]
    ausentes = [nome for chave, nome in familias.items() if chave not in familias_do_repertorio]

    avisos = [
        "A direção é uma ESTIMATIVA a partir das notas conhecidas da referência, "
        "não a composição real do perfume."
    ]
    if not notas:
        avisos.append("Nenhuma nota da referência existe na base de conhecimento; não há como estimar a direção.")
    elif all(vetor.get(e) is None for e in EIXOS):
        avisos.append("As notas reconhecidas não têm valores de referência nos eixos.")
    return AnaliseReferencia(vetor, list(notas), list(desconhecidas), presentes, ausentes, avisos)
