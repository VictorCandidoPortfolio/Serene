"""Cadastro SIMPLES de essência: o que o sistema deduz de Nome + Família + Percepção.

A aluna não sabe (e não deve precisar saber) o que é persistência, papel ou
vetor. Ela informa o grupo de cheiro ("Família": Fresco, Floral...) e a
sensação ("Percepção": Fria, Neutra, Quente). Este módulo, PURO e determinístico,
completa o resto. Nenhum número está aqui: tudo vem de regras do banco
(`criacao_territorio.perfil` e `peso_score/percepcao`), valores iniciais a
calibrar com a professora.

Precedência dos valores (de cima para baixo):
1. Nota reconhecida pela base E a aluna manteve família+percepção sugeridas E a
   nota NÃO é de exemplo -> valores e confiança da própria nota.
2. Qualquer outro caso -> perfil típico do grupo + temperatura da percepção,
   com confiança baixa. (Nota de exemplo nunca tem os números copiados:
   é calibração de demonstração, não medida.)

Limitação conhecida: duas essências do mesmo grupo e da mesma percepção ficam
com perfis idênticos. É uma estimativa grosseira; reconhecer o nome na base
(notas com dados reais) é o que a torna mais precisa.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PERCEPCOES = ("fria", "neutra", "quente")


@dataclass(frozen=True)
class Derivado:
    """Campos técnicos deduzidos pelo servidor (a aluna nunca os vê nem os define).

    `papel` em 0..1 (formato do banco: {"saida", "coracao", "fundo"}), somando 1.
    """

    v1: float
    v2: float
    v3: float
    v4: float
    v5: float
    papel: dict[str, float]
    tipo: str
    confianca: str
    origem: str     # "estimado" (família+percepção) | "inferido" (valores de uma nota)


def percepcao_de_v1(v1: float | None, regra: Mapping[str, Any]) -> str | None:
    """Converte uma temperatura (v1) em percepção: <= 3.5 Fria, <= 6.5 Neutra, senão Quente.

    Os limiares vêm da regra `peso_score/percepcao`. `None` -> `None` (não se
    sabe, e não se chuta).
    """
    if v1 is None:
        return None
    if v1 <= float(regra["fria_ate"]):
        return "fria"
    if v1 <= float(regra["neutra_ate"]):
        return "neutra"
    return "quente"


def papel_em_fracao(papel_pct: Mapping[str, float]) -> dict[str, float]:
    """Papel em pontos percentuais (soma 100) -> fração 0..1 (soma 1), como o banco guarda.

    Raises:
        ValueError: se o papel da regra não somar 100 (regra malformada).
    """
    total = sum(float(v) for v in papel_pct.values())
    if round(total, 6) != 100:
        raise ValueError(f"O papel típico do grupo deve somar 100, soma {total}.")
    return {c: float(papel_pct[c]) / 100 for c in ("saida", "coracao", "fundo")}


def derivar(
    perfil_grupo: Mapping[str, Any],
    percepcao: str,
    regra_percepcao: Mapping[str, Any],
) -> Derivado:
    """Deduz os campos técnicos de uma essência a partir de grupo + percepção.

    - v1 (temperatura): pela percepção (Fria 3, Neutra 5, Quente 8).
    - v2 (peso), v3 (doçura), v4 (presença) e papel: pelo perfil típico do grupo.
    - v5 (complexidade): neutro; só é calculada de verdade no acorde.
    - confiança baixa, origem estimada, tipo desconhecido: é uma estimativa.

    Raises:
        KeyError: percepção fora de fria/neutra/quente.
    """
    return Derivado(
        v1=float(regra_percepcao["v1"][percepcao]),
        v2=float(perfil_grupo["v2"]),
        v3=float(perfil_grupo["v3"]),
        v4=float(perfil_grupo["v4"]),
        v5=float(regra_percepcao["v5_neutro"]),
        papel=papel_em_fracao(perfil_grupo["papel"]),
        tipo="desconhecida",
        confianca="baixa",
        origem="estimado",
    )


def valores_da_nota(
    v: Mapping[str, float | None],
    papel: Mapping[str, float] | None,
    tipo: str,
    confianca: str,
    v5_neutro: float,
) -> Derivado | None:
    """Valores de uma nota reconhecida (precedência 1), ou `None` se a nota é incompleta.

    Nota sem v1..v4 ou sem papel não serve para preencher a essência: devolve
    `None` e o chamador usa a derivação por grupo+percepção (sem inventar o que
    a nota não afirma).
    """
    if any(v.get(e) is None for e in ("v1", "v2", "v3", "v4")) or not papel:
        return None
    return Derivado(
        v1=float(v["v1"]), v2=float(v["v2"]), v3=float(v["v3"]), v4=float(v["v4"]), v5=float(v5_neutro),
        papel={c: float(papel.get(c) or 0) for c in ("saida", "coracao", "fundo")},
        tipo=tipo, confianca=confianca, origem="inferido",
    )
