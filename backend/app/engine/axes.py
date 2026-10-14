"""Definições do sistema de eixos e tipos de dados compartilhados pelo motor.

As constantes daqui NÃO são heurísticas calibráveis (essas vivem em
`knowledge_engine_rules`): são a própria definição do vocabulário do motor —
quais eixos existem, a escala deles e o que significa "pouco/médio/bastante".
Mudar isso é mudar o contrato de dados, não calibrar o motor.
"""

from dataclasses import dataclass, field
from typing import Any

# v1 temperatura (frescor ↔ calor), v2 peso/persistência (profundidade),
# v3 doçura, v4 presença/intensidade, v5 complexidade estrutural,
# v6 floralidade. Escala 0–10 em todos.
EIXOS: tuple[str, ...] = ("v1", "v2", "v3", "v4", "v5", "v6")
ESCALA_MIN = 0.0
ESCALA_MAX = 10.0

# (nome, rótulo do lado baixo, rótulo do lado alto) — usado nas explicações.
# Mesmos nomes da interface (frontend/src/lib/format.js), para a aluna ler
# "profundidade" no texto e no gráfico, e não dois nomes para a mesma coisa.
ROTULOS_EIXOS: dict[str, tuple[str, str, str]] = {
    "v1": ("temperatura", "fresco", "quente"),
    "v2": ("profundidade", "leve", "profundo"),
    "v3": ("doçura", "seco", "doce"),
    "v4": ("intensidade", "discreto", "marcante"),
    "v5": ("complexidade", "simples", "complexo"),
    "v6": ("floralidade", "não floral", "floral"),
}

CAMADAS: tuple[str, ...] = ("saida", "coracao", "fundo")
ROTULOS_CAMADAS: dict[str, str] = {"saida": "saída", "coracao": "coração", "fundo": "fundo"}

# Peso RELATIVO dentro do acorde. Não é porcentagem de produto (regra de
# negócio 1): "bastante" é 3x "pouco" DENTRO da mistura, e só isso.
PESOS_RELATIVOS: dict[str, int] = {"pouco": 1, "medio": 2, "bastante": 3}
ROTULOS_PESO: dict[int, str] = {1: "Pouco", 2: "Médio", 3: "Bastante"}
NOMES_PESO: dict[int, str] = {v: k for k, v in PESOS_RELATIVOS.items()}


class RegraInvalidaError(ValueError):
    """Uma regra necessária ao motor está ausente ou malformada.

    O service traduz para `KnowledgeUnavailableError` (HTTP 503): é problema
    de configuração da base de conhecimento, não da aluna.
    """


@dataclass(frozen=True)
class EssenciaMotor:
    """Visão mínima de uma essência DA USUÁRIA, como o motor a enxerga.

    Attributes:
        id: id da essência no repertório.
        nome: nome de exibição.
        familia: família como a aluna cadastrou (exibição).
        familia_chave: família canônica (slug de `knowledge_families`) quando
            reconhecida; None quando a família é livre/desconhecida.
        vetor: {eixo: valor 0–10 ou None}.
        papel: {"saida", "coracao", "fundo"} 0..1, ou None se desconhecido.
    """

    id: int
    nome: str
    familia: str | None
    familia_chave: str | None
    vetor: dict[str, float | None]
    papel: dict[str, float] | None = None


@dataclass(frozen=True)
class Lacuna:
    """Algo que falta no repertório para chegar a um objetivo.

    Sempre nomeia uma CATEGORIA (família, camada, eixo) — nunca uma essência
    específica que a aluna não tem (regra de negócio 4).
    """

    tipo: str
    mensagem: str
    detalhe: dict[str, Any] = field(default_factory=dict)


def peso_numerico(peso: str | int) -> int:
    """Converte "pouco"/"medio"/"bastante" (ou 1/2/3) no inteiro relativo.

    Raises:
        ValueError: peso fora da escala.
    """
    if isinstance(peso, int) and not isinstance(peso, bool):
        if peso in ROTULOS_PESO:
            return peso
    elif isinstance(peso, str) and peso in PESOS_RELATIVOS:
        return PESOS_RELATIVOS[peso]
    raise ValueError(f"Peso relativo inválido: {peso!r}. Use pouco/medio/bastante ou 1/2/3.")


def clamp(valor: float) -> float:
    """Limita um valor à escala 0–10 dos eixos."""
    return max(ESCALA_MIN, min(ESCALA_MAX, valor))


def descrever_direcao(eixo: str, delta: float) -> str:
    """Texto curto como "mais fresco" para um delta (sinal) num eixo.

    Quando o lado baixo é uma negação ("não floral"), usa "menos floral" —
    "mais não floral" não é português.
    """
    _, baixo, alto = ROTULOS_EIXOS[eixo]
    if delta > 0:
        return f"mais {alto}"
    return f"menos {alto}" if baixo.startswith("não ") else f"mais {baixo}"


def exigir_chaves(regra: dict[str, Any] | None, chaves: tuple[str, ...], nome: str) -> dict:
    """Valida que uma regra de parâmetros contém as chaves esperadas.

    Falhar alto aqui é melhor do que usar um default silencioso: um default
    no código seria exatamente o "número mágico hardcoded" que a arquitetura
    proíbe.

    Raises:
        RegraInvalidaError: regra ausente ou sem alguma chave.
    """
    if not isinstance(regra, dict):
        raise RegraInvalidaError(f"Regra '{nome}' ausente na base de conhecimento.")
    faltando = [c for c in chaves if c not in regra]
    if faltando:
        raise RegraInvalidaError(f"Regra '{nome}' sem os parâmetros: {', '.join(faltando)}.")
    return regra
