"""Análise de compatibilidade entre essências (funcionalidade 2.8).

Compatibilidade par-a-par e de grupo, calculada a partir das relações entre
famílias (`knowledge_family_relations`) e dos pesos de score
(`knowledge_engine_rules`, tipo `peso_score`, chave `compatibilidade`).
Nenhum peso está no código: se a regra não existir, o motor recusa calcular.

Formato esperado da regra `peso_score/compatibilidade`:
    {
      "base": 0.5,            # ponto de partida de qualquer par avaliado
      "mesma_familia": 0.3,   # bônus quando as duas são da mesma família
      "sem_relacao": 0.0,     # ajuste quando não há relação cadastrada
      "classico": 0.5, "complementar": 0.3, "contraste": 0.1, "atencao": -0.3,
      "limiar_alerta": 0.4    # pares abaixo disso geram alerta
    }
O ajuste de um tipo é multiplicado por `relacao.peso` (0..1).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from app.engine.axes import EssenciaMotor, exigir_chaves

CHAVES_PESOS = (
    "base",
    "mesma_familia",
    "sem_relacao",
    "classico",
    "complementar",
    "contraste",
    "atencao",
    "limiar_alerta",
)


@dataclass(frozen=True)
class RelacaoFamilias:
    """Relação entre duas famílias, já traduzida para slugs."""

    familia_a: str
    familia_b: str
    tipo: str
    peso: float
    descricao: str | None = None


@dataclass(frozen=True)
class ResultadoPar:
    """Compatibilidade entre duas essências. `score` None = não avaliável."""

    essencia_a: int
    essencia_b: int
    score: float | None
    tipo_relacao: str | None
    explicacao: str


@dataclass(frozen=True)
class ResultadoCompatibilidade:
    """Compatibilidade de um grupo: score 0–100 (ou None) + pares + alertas."""

    score: int | None
    pares: list[ResultadoPar]
    alertas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        """Formato persistido em `acordes.compatibilidade` e devolvido na API."""
        return {
            "score": self.score,
            "alertas": self.alertas,
            "pares": [p.__dict__ for p in self.pares],
        }


def _indexar(relacoes: Sequence[RelacaoFamilias]) -> dict[frozenset[str], RelacaoFamilias]:
    """Indexa relações por par NÃO ordenado (A–B == B–A)."""
    return {frozenset((r.familia_a, r.familia_b)): r for r in relacoes}


def _buscar_relacao(
    a: str, b: str, indice: dict[frozenset[str], RelacaoFamilias], hierarquia: dict[str, str]
) -> RelacaoFamilias | None:
    """Procura a relação do par; se não houver, sobe para a família-mãe.

    Ex.: "floral_branco" × "citrico" sem relação própria herda a relação
    "floral" × "citrico". Isso evita ter que cadastrar N×M relações para cada
    subfamília, sem inventar nada — é a relação cadastrada da família-mãe.
    """
    candidatos_a = [a] + ([hierarquia[a]] if a in hierarquia else [])
    candidatos_b = [b] + ([hierarquia[b]] if b in hierarquia else [])
    for x in candidatos_a:
        for y in candidatos_b:
            rel = indice.get(frozenset((x, y)))
            if rel is not None:
                return rel
    return None


def relacao_entre(
    familia_a: str,
    familia_b: str,
    relacoes: Sequence[RelacaoFamilias],
    hierarquia: dict[str, str] | None = None,
) -> RelacaoFamilias | None:
    """Relação cadastrada entre duas famílias (com herança da família-mãe), ou None.

    Versão pública de `_buscar_relacao`, para o motor de criação consultar
    relações de "atenção" sem recalcular o score de compatibilidade inteiro.
    """
    return _buscar_relacao(familia_a, familia_b, _indexar(relacoes), hierarquia or {})


def compatibilidade_par(
    a: EssenciaMotor,
    b: EssenciaMotor,
    relacoes: Sequence[RelacaoFamilias],
    pesos: dict[str, float],
    hierarquia: dict[str, str] | None = None,
) -> ResultadoPar:
    """Compatibilidade entre duas essências, em 0..1.

    Args:
        a, b: essências do repertório da usuária.
        relacoes: relações entre famílias (da base de conhecimento).
        pesos: regra `peso_score/compatibilidade` (ver docstring do módulo).
        hierarquia: {slug_subfamilia: slug_familia_mae}.

    Returns:
        ResultadoPar; `score` é None quando alguma das duas não tem família
        reconhecida — sem família não há base para avaliar, e o motor não
        chuta (regra de negócio 2).
    """
    exigir_chaves(pesos, CHAVES_PESOS, "peso_score/compatibilidade")
    return _par(a, b, _indexar(relacoes), pesos, hierarquia or {})


def _par(
    a: EssenciaMotor,
    b: EssenciaMotor,
    indice: dict[frozenset[str], RelacaoFamilias],
    pesos: dict[str, float],
    hierarquia: dict[str, str],
) -> ResultadoPar:
    """Implementação de `compatibilidade_par` com índice pré-calculado."""
    if not a.familia_chave or not b.familia_chave:
        sem = a.nome if not a.familia_chave else b.nome
        return ResultadoPar(
            a.id, b.id, None, None,
            f"'{sem}' não tem família reconhecida na base; compatibilidade não avaliada.",
        )

    base = float(pesos["base"])
    if a.familia_chave == b.familia_chave:
        score = base + float(pesos["mesma_familia"])
        return ResultadoPar(
            a.id, b.id, round(max(0.0, min(1.0, score)), 3), "mesma_familia",
            f"'{a.nome}' e '{b.nome}' são da mesma família ({a.familia}).",
        )

    rel = _buscar_relacao(a.familia_chave, b.familia_chave, indice, hierarquia)
    if rel is None:
        score = base + float(pesos["sem_relacao"])
        return ResultadoPar(
            a.id, b.id, round(max(0.0, min(1.0, score)), 3), None,
            f"Não há relação cadastrada entre {a.familia} e {b.familia}; "
            "score neutro, sem afirmação de que combinam ou não.",
        )

    ajuste = float(pesos.get(rel.tipo, 0.0)) * float(rel.peso)
    score = max(0.0, min(1.0, base + ajuste))
    texto = rel.descricao or f"Relação '{rel.tipo}' entre {a.familia} e {b.familia}."
    return ResultadoPar(a.id, b.id, round(score, 3), rel.tipo, texto)


def compatibilidade_grupo(
    essencias: Sequence[EssenciaMotor],
    relacoes: Sequence[RelacaoFamilias],
    pesos: dict[str, float],
    hierarquia: dict[str, str] | None = None,
) -> ResultadoCompatibilidade:
    """Compatibilidade de um grupo (todas as combinações 2 a 2).

    O score do grupo é a média dos pares AVALIÁVEIS, em 0–100. Pares com
    relação de "atenção" ou abaixo do limiar viram alerta — o alerta explica,
    não proíbe: quem decide é a aluna.

    Returns:
        ResultadoCompatibilidade; `score` None se nenhum par pôde ser avaliado.

    Raises:
        RegraInvalidaError: se `pesos` não tiver os parâmetros esperados.
    """
    exigir_chaves(pesos, CHAVES_PESOS, "peso_score/compatibilidade")
    indice = _indexar(relacoes)
    hier = hierarquia or {}
    limiar = float(pesos["limiar_alerta"])

    pares = [_par(a, b, indice, pesos, hier) for a, b in combinations(essencias, 2)]
    alertas: list[str] = []
    for par in pares:
        if par.score is None:
            alertas.append(par.explicacao)
        elif par.tipo_relacao == "atencao" or par.score < limiar:
            alertas.append(f"Atenção: {par.explicacao}")

    avaliados = [p.score for p in pares if p.score is not None]
    score = round(100 * sum(avaliados) / len(avaliados)) if avaliados else None
    # dict.fromkeys remove alertas duplicados preservando a ordem.
    return ResultadoCompatibilidade(score=score, pares=pares, alertas=list(dict.fromkeys(alertas)))
