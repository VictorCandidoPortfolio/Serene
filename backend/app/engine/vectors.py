"""Cálculo da "personalidade" de um acorde (funcionalidade 2.6).

Dado um conjunto de (essência, peso relativo), calcula o vetor v1–v5, o papel
na pirâmide (saída/coração/fundo) e a família dominante.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.engine.axes import CAMADAS, EIXOS, EssenciaMotor


@dataclass(frozen=True)
class ResultadoAcorde:
    """Resultado do cálculo de um acorde.

    Attributes:
        vetor: {eixo: média ponderada, ou None se nenhuma essência tem dado}.
        cobertura: {eixo: fração (0..1) do peso total que tinha dado}. Um eixo
            com cobertura 0.3 foi calculado só com 30% do acorde — o front
            deve mostrar isso como incerteza.
        eixos_sem_dado: eixos em que NENHUMA essência tinha valor.
        papel: {camada: 0..1} normalizado, ou None se nenhuma tinha papel.
        familia_resultante: família com maior peso somado (None se nenhuma).
        avisos: mensagens de incerteza para exibir à aluna.
    """

    vetor: dict[str, float | None]
    cobertura: dict[str, float]
    eixos_sem_dado: list[str]
    papel: dict[str, float] | None
    familia_resultante: str | None
    avisos: list[str] = field(default_factory=list)


def calcular_acorde(itens: Sequence[tuple[EssenciaMotor, int]]) -> ResultadoAcorde:
    """Calcula vetor, papel e família resultante de um acorde.

    Média ponderada pelo peso relativo, eixo a eixo, IGNORANDO essências sem
    valor naquele eixo. Ignorar (em vez de tratar como 0 ou como 5) é
    deliberado: 0 afirmaria "é frio", 5 afirmaria "é neutro" — ambos seriam
    dado inventado (regra de negócio 2). A incerteza aparece em `cobertura`.

    Args:
        itens: pares (essência da usuária, peso relativo 1..3).

    Returns:
        ResultadoAcorde.

    Raises:
        ValueError: se `itens` estiver vazio.
    """
    if not itens:
        raise ValueError("Um acorde precisa de pelo menos uma essência.")

    peso_total = sum(peso for _, peso in itens)
    vetor: dict[str, float | None] = {}
    cobertura: dict[str, float] = {}
    for eixo in EIXOS:
        com_dado = [(e.vetor[eixo], p) for e, p in itens if e.vetor.get(eixo) is not None]
        peso_com_dado = sum(p for _, p in com_dado)
        cobertura[eixo] = round(peso_com_dado / peso_total, 3)
        vetor[eixo] = (
            round(sum(v * p for v, p in com_dado) / peso_com_dado, 2) if peso_com_dado else None
        )

    eixos_sem_dado = [e for e in EIXOS if vetor[e] is None]
    avisos = [
        f"Nenhuma essência deste acorde tem valor em {eixo}; o eixo ficou sem cálculo."
        for eixo in eixos_sem_dado
    ]

    # Papel: soma ponderada por camada, depois normaliza para somar 1.
    com_papel = [(e.papel, p) for e, p in itens if e.papel]
    papel: dict[str, float] | None = None
    if com_papel:
        bruto = {c: sum(float(pp.get(c) or 0) * p for pp, p in com_papel) for c in CAMADAS}
        soma = sum(bruto.values())
        if soma > 0:
            papel = {c: round(v / soma, 3) for c, v in bruto.items()}
    if len(com_papel) < len(itens):
        avisos.append("Algumas essências não têm papel na pirâmide informado.")

    # Família dominante: soma de pesos por família. Empate: a primeira que
    # aparece no acorde, para o resultado ser determinístico.
    pesos_familia: dict[str, int] = {}
    for essencia, peso in itens:
        if essencia.familia:
            pesos_familia[essencia.familia] = pesos_familia.get(essencia.familia, 0) + peso
    familia = max(pesos_familia, key=pesos_familia.__getitem__) if pesos_familia else None

    return ResultadoAcorde(
        vetor=vetor,
        cobertura=cobertura,
        eixos_sem_dado=eixos_sem_dado,
        papel=papel,
        familia_resultante=familia,
        avisos=avisos,
    )


def media_vetores(vetores: Sequence[dict[str, float | None]]) -> dict[str, float | None]:
    """Média simples, eixo a eixo, ignorando `None` (nunca o trata como 0).

    Usada na identidade geral de uma coleção (média dos acordes das criações).
    Eixo sem nenhum valor fica `None`.
    """
    out: dict[str, float | None] = {}
    for eixo in EIXOS:
        valores = [v[eixo] for v in vetores if v and v.get(eixo) is not None]
        out[eixo] = round(sum(valores) / len(valores), 2) if valores else None
    return out
