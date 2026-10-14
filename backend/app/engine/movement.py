"""Motor de ajuste de acordes: "deixar mais fresco / doce / marcante...".

Dado um acorde e um movimento desejado (regra `vetor_movimento`), explora
ajustes SÓ com o que a aluna possui:
- aumentar ou diminuir o peso de uma essência que já está no acorde;
- retirar uma essência (se sobrarem pelo menos 2);
- adicionar uma essência DO REPERTÓRIO DELA que ainda não está no acorde.

Se nenhum ajuste alcança o movimento, chama `gaps.lacuna_para_movimento`
para nomear a categoria que falta (regra de negócio 4). O motor não tem
acesso a `knowledge_notes` como candidatas — elas não estão em `repertorio`,
por construção.

Formatos esperados:
- regra `vetor_movimento/<chave>`: {"delta": {"v1": -2.0, ...}}
- regra `peso_score/movimento`:
    {"progresso_minimo": 0.15, "max_sugestoes": 3, "penalidade_colateral": 0.5}
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.engine.axes import (
    EIXOS,
    ROTULOS_PESO,
    EssenciaMotor,
    Lacuna,
    RegraInvalidaError,
    exigir_chaves,
)
from app.engine.gaps import FamiliaRef, lacuna_para_movimento
from app.engine.vectors import calcular_acorde

CHAVES_PARAMS = ("progresso_minimo", "max_sugestoes", "penalidade_colateral")
MIN_ITENS_ACORDE = 2


@dataclass(frozen=True)
class SugestaoAjuste:
    """Um ajuste concreto, sempre usando essências que a aluna possui.

    Attributes:
        acao: "aumentar" | "diminuir" | "retirar" | "adicionar".
        progresso: fração (0..1) do movimento pedido que o ajuste alcança.
        efeito_colateral: quanto os eixos NÃO pedidos mudaram (relativo ao
            tamanho do movimento) — ajuda a aluna a ver o custo do ajuste.
        itens_resultantes: [(essencia_id, peso)] prontos para criar a
            próxima versão do acorde.
    """

    acao: str
    essencia_id: int
    nome: str
    peso_de: int | None
    peso_para: int | None
    descricao: str
    progresso: float
    efeito_colateral: float
    vetor_resultante: dict[str, float | None]
    itens_resultantes: list[tuple[int, int]]


@dataclass(frozen=True)
class ResultadoMovimento:
    """Resultado do motor de ajuste."""

    vetor_atual: dict[str, float | None]
    alcancavel: bool
    sugestoes: list[SugestaoAjuste] = field(default_factory=list)
    lacuna: Lacuna | None = None

    def como_dict(self) -> dict[str, Any]:
        """Serialização para a resposta da API."""
        return {
            "vetor_atual": self.vetor_atual,
            "alcancavel": self.alcancavel,
            "sugestoes": [s.__dict__ for s in self.sugestoes],
            "lacuna": self.lacuna.__dict__ if self.lacuna else None,
        }


def _medir(
    atual: dict[str, float | None],
    novo: dict[str, float | None],
    delta: dict[str, float],
) -> tuple[float, float]:
    """Mede (progresso, efeito colateral) de um vetor novo contra o atual.

    Progresso: quanto andou na direção pedida, eixo a eixo, limitado ao
    tamanho pedido (passar do ponto não conta como "mais progresso").
    """
    magnitude = sum(abs(d) for e, d in delta.items() if atual.get(e) is not None)
    if magnitude == 0:
        return 0.0, 0.0
    andou = 0.0
    for eixo, d in delta.items():
        c, n = atual.get(eixo), novo.get(eixo)
        if c is None or n is None or not d:
            continue
        passo = (n - c) * (1 if d > 0 else -1)
        andou += min(passo, abs(d))
    colateral = sum(
        abs((novo.get(e) or 0) - (atual.get(e) or 0))
        for e in EIXOS
        if e not in delta and atual.get(e) is not None and novo.get(e) is not None
    )
    return andou / magnitude, colateral / magnitude


def _candidatos(
    itens: Sequence[tuple[EssenciaMotor, int]], repertorio: Sequence[EssenciaMotor]
) -> list[tuple[str, EssenciaMotor, int | None, int | None, list[tuple[EssenciaMotor, int]]]]:
    """Gera todas as variações de um passo a partir do acorde atual."""
    out = []
    ids_no_acorde = {e.id for e, _ in itens}
    for i, (essencia, peso) in enumerate(itens):
        if peso < max(ROTULOS_PESO):
            novo = list(itens)
            novo[i] = (essencia, peso + 1)
            out.append(("aumentar", essencia, peso, peso + 1, novo))
        if peso > min(ROTULOS_PESO):
            novo = list(itens)
            novo[i] = (essencia, peso - 1)
            out.append(("diminuir", essencia, peso, peso - 1, novo))
        if len(itens) > MIN_ITENS_ACORDE:
            novo = [it for j, it in enumerate(itens) if j != i]
            out.append(("retirar", essencia, peso, None, novo))
    # Só o repertório DELA. `repertorio` vem do service filtrado por user_id.
    for essencia in repertorio:
        if essencia.id in ids_no_acorde:
            continue
        for peso in (1, 2):
            out.append(("adicionar", essencia, None, peso, list(itens) + [(essencia, peso)]))
    return out


def _descrever(acao: str, nome: str, de: int | None, para: int | None) -> str:
    """Texto legível do ajuste, ex.: "Aumentar Bergamota de Pouco para Médio"."""
    if acao == "adicionar":
        return f"Adicionar {nome} ({ROTULOS_PESO[para]})"
    if acao == "retirar":
        return f"Retirar {nome} do acorde"
    verbo = "Aumentar" if acao == "aumentar" else "Diminuir"
    return f"{verbo} {nome} de {ROTULOS_PESO[de]} para {ROTULOS_PESO[para]}"


def sugerir_ajuste(
    itens: Sequence[tuple[EssenciaMotor, int]],
    repertorio: Sequence[EssenciaMotor],
    regra_movimento: dict[str, Any],
    params: dict[str, Any],
    familias: Sequence[FamiliaRef] = (),
    descricao_movimento: str = "na direção pedida",
) -> ResultadoMovimento:
    """Sugere ajustes de um passo para mover o acorde na direção pedida.

    Args:
        itens: acorde atual [(essência, peso 1..3)].
        repertorio: TODAS as essências da usuária (candidatas a adição).
        regra_movimento: valor da regra `vetor_movimento` ({"delta": {...}}).
        params: regra `peso_score/movimento`.
        familias: famílias da base (usadas só para NOMEAR a lacuna).
        descricao_movimento: rótulo do movimento para as mensagens.

    Returns:
        ResultadoMovimento com até `max_sugestoes` ajustes, ou com `lacuna`
        quando nenhum ajuste atinge `progresso_minimo`.

    Raises:
        RegraInvalidaError: regra de movimento ou parâmetros malformados.
    """
    exigir_chaves(params, CHAVES_PARAMS, "peso_score/movimento")
    delta = exigir_chaves(regra_movimento, ("delta",), "vetor_movimento")["delta"]
    if not isinstance(delta, dict) or not any(e in EIXOS and d for e, d in delta.items()):
        raise RegraInvalidaError("Regra de movimento sem delta válido em v1..v5.")
    delta = {e: float(d) for e, d in delta.items() if e in EIXOS and d}

    atual = calcular_acorde(itens).vetor
    if all(atual.get(e) is None for e in delta):
        return ResultadoMovimento(
            vetor_atual=atual,
            alcancavel=False,
            lacuna=Lacuna(
                "dados_incompletos",
                "As essências deste acorde não têm valores nos eixos que este movimento "
                "altera; classifique-as antes de pedir o ajuste.",
                {"eixos": list(delta)},
            ),
        )

    minimo = float(params["progresso_minimo"])
    penal = float(params["penalidade_colateral"])
    avaliadas: list[tuple[float, SugestaoAjuste]] = []
    for acao, essencia, de, para, novos in _candidatos(itens, repertorio):
        vetor_novo = calcular_acorde(novos).vetor
        progresso, colateral = _medir(atual, vetor_novo, delta)
        if progresso < minimo:
            continue
        sugestao = SugestaoAjuste(
            acao=acao,
            essencia_id=essencia.id,
            nome=essencia.nome,
            peso_de=de,
            peso_para=para,
            descricao=_descrever(acao, essencia.nome, de, para),
            progresso=round(progresso, 3),
            efeito_colateral=round(colateral, 3),
            vetor_resultante=vetor_novo,
            itens_resultantes=[(e.id, p) for e, p in novos],
        )
        avaliadas.append((progresso - penal * colateral, sugestao))

    avaliadas.sort(key=lambda t: t[0], reverse=True)
    sugestoes = [s for _, s in avaliadas[: int(params["max_sugestoes"])]]
    if sugestoes:
        return ResultadoMovimento(vetor_atual=atual, alcancavel=True, sugestoes=sugestoes)

    presentes = {e.familia_chave for e in repertorio if e.familia_chave}
    lacuna = lacuna_para_movimento(delta, atual, familias, presentes, descricao_movimento)
    return ResultadoMovimento(vetor_atual=atual, alcancavel=False, lacuna=lacuna)
