"""Perfil olfativo → vetor-alvo → recomendação (funcionalidades 2.5, 2.7, 2.15, 2.16).

Duas etapas:
1. `calcular_vetor_alvo`: traduz as respostas do questionário (emoções,
   territórios, preferências, intensidade, público) num vetor-alvo, usando
   SÓ regras vindas de `knowledge_engine_rules`. Respostas sem regra
   correspondente são devolvidas em `nao_reconhecidos` — nunca inventadas.
2. `pontuar_essencias`: compara essências DO REPERTÓRIO DA USUÁRIA com o alvo.

Formatos esperados de regra (tipo → valor):
- `emocao`, `preferencia`, `correlacao_territorio`:
      {"vetor": {"v1": 7, "v3": 6}, "peso": 1.0}
  (só os eixos que a regra afirma; os outros ficam de fora)
- `territorio`: registro do território — {"nome": "Acolhimento", ...}.
  Só territórios registrados são aceitos; a correlação vem da regra
  `correlacao_territorio` de mesma chave.
- `publico`: {"nome": "Teen", "vetor": {...}, "peso": 1.0,
              "limites": {"v4": {"max": 6}}, "vocabulario": [...]}
- `peso_score/recomendacao`: {"peso_intensidade": 2.0, "min_eixos_comparados": 2}

Gênero (regra de negócio 7): é um insumo FLEXÍVEL. Só influencia o alvo se
existir uma regra `preferencia` com chave `genero_<valor>`, e mesmo assim só
soma uma contribuição suave — nunca exclui famílias nem essências.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.text import chave as normalizar_chave
from app.engine.axes import (
    EIXOS,
    ESCALA_MAX,
    ROTULOS_EIXOS,
    EssenciaMotor,
    clamp,
    descrever_direcao,
    exigir_chaves,
)

CHAVES_PARAMS = ("peso_intensidade", "min_eixos_comparados")
Regras = dict[str, dict[str, Any]]  # {tipo: {chave: valor}}


@dataclass(frozen=True)
class ResultadoAlvo:
    """Vetor-alvo e a trilha de como ele foi construído.

    Attributes:
        vetor: {eixo: alvo 0–10, ou None se nenhuma resposta falou do eixo}.
        contribuicoes: [(origem, chave, vetor parcial, peso)] — a explicação.
        nao_reconhecidos: respostas sem regra na base (ex.: emoção nova).
        eixos_sem_direcao: eixos que ficaram None.
        publico / vocabulario / limites: dados do público, se informado.
    """

    vetor: dict[str, float | None]
    contribuicoes: list[dict[str, Any]] = field(default_factory=list)
    nao_reconhecidos: list[str] = field(default_factory=list)
    eixos_sem_direcao: list[str] = field(default_factory=list)
    territorios: list[str] = field(default_factory=list)
    publico: str | None = None
    vocabulario: list[str] = field(default_factory=list)
    limites: dict[str, dict[str, float]] = field(default_factory=dict)

    def como_dict(self) -> dict[str, Any]:
        """Formato persistido em `perfis_olfativos.vetor_alvo`."""
        return dict(self.__dict__)


def _como_lista(valor: Any) -> list[str]:
    """Aceita string única ou lista nas respostas do questionário."""
    if valor is None:
        return []
    if isinstance(valor, str):
        return [valor]
    return [str(v) for v in valor]


def calcular_vetor_alvo(
    respostas: dict[str, Any],
    regras: Regras,
    params: dict,
    extras: list[dict[str, Any]] | None = None,
) -> ResultadoAlvo:
    """Traduz respostas de perfil num vetor-alvo.

    Cada resposta reconhecida contribui com um vetor PARCIAL e um peso; o alvo
    de cada eixo é a média ponderada das contribuições que falam dele. Depois,
    os limites do público (ex.: Kids com presença máxima 5) são aplicados.

    Args:
        respostas: questionário bruto (`perfis_olfativos.respostas`).
        regras: {tipo: {chave: valor}} só com regras ATIVAS.
        params: regra `peso_score/recomendacao`.
        extras: contribuições calculadas fora das regras, no mesmo formato
            ({origem, chave, vetor, peso}) — ex.: a direção estimada de um
            perfume de referência da aluna.

    Returns:
        ResultadoAlvo.

    Raises:
        RegraInvalidaError: parâmetros ausentes.
    """
    exigir_chaves(params, CHAVES_PARAMS, "peso_score/recomendacao")
    contribuicoes: list[dict[str, Any]] = [c for c in (extras or []) if c.get("vetor")]
    nao_reconhecidos: list[str] = []

    def contribuir(origem: str, chave_regra: str, valor: Any) -> None:
        """Registra o vetor parcial de uma regra (ignora eixos fora de v1..v5)."""
        vetor = {e: float(v) for e, v in (valor or {}).get("vetor", {}).items() if e in EIXOS}
        if vetor:
            contribuicoes.append(
                {"origem": origem, "chave": chave_regra, "vetor": vetor,
                 "peso": float(valor.get("peso", 1.0))}
            )

    # Emoções e preferências: regra direta por chave.
    for origem, tipo in (("emocoes", "emocao"), ("preferencias", "preferencia")):
        for bruto in _como_lista(respostas.get(origem)):
            k = normalizar_chave(bruto)
            if k in regras.get(tipo, {}):
                contribuir(tipo, k, regras[tipo][k])
            else:
                nao_reconhecidos.append(f"{tipo}:{bruto}")

    # Territórios: precisam estar registrados (tipo `territorio`) e ter
    # correlação (tipo `correlacao_territorio`).
    territorios: list[str] = []
    for bruto in _como_lista(respostas.get("territorios")):
        k = normalizar_chave(bruto)
        if k not in regras.get("territorio", {}):
            nao_reconhecidos.append(f"territorio:{bruto}")
            continue
        territorios.append(k)
        if k in regras.get("correlacao_territorio", {}):
            contribuir("territorio", k, regras["correlacao_territorio"][k])

    # Intensidade informada pela aluna é dado DELA: entra direto em v4.
    intensidade = respostas.get("intensidade")
    if isinstance(intensidade, (int, float)) and not isinstance(intensidade, bool):
        contribuicoes.append(
            {"origem": "intensidade", "chave": "informada",
             "vetor": {"v4": clamp(float(intensidade))},
             "peso": float(params["peso_intensidade"])}
        )

    # Gênero: contribuição suave e opcional; nunca uma trava.
    genero = respostas.get("genero")
    if genero:
        k = f"genero_{normalizar_chave(str(genero))}"
        if k in regras.get("preferencia", {}):
            contribuir("preferencia", k, regras["preferencia"][k])

    # Público: vetor opcional + limites + vocabulário.
    publico_nome, vocabulario, limites = None, [], {}
    if respostas.get("publico"):
        k = normalizar_chave(str(respostas["publico"]))
        regra_publico = regras.get("publico", {}).get(k)
        if regra_publico is None:
            nao_reconhecidos.append(f"publico:{respostas['publico']}")
        else:
            publico_nome = k
            contribuir("publico", k, regra_publico)
            vocabulario = list(regra_publico.get("vocabulario", []))
            limites = dict(regra_publico.get("limites", {}))

    vetor: dict[str, float | None] = {}
    for eixo in EIXOS:
        partes = [(c["vetor"][eixo], c["peso"]) for c in contribuicoes if eixo in c["vetor"]]
        soma_pesos = sum(p for _, p in partes)
        vetor[eixo] = round(sum(v * p for v, p in partes) / soma_pesos, 2) if soma_pesos else None

    for eixo, lim in limites.items():
        if vetor.get(eixo) is None:
            continue
        if "max" in lim:
            vetor[eixo] = min(vetor[eixo], float(lim["max"]))
        if "min" in lim:
            vetor[eixo] = max(vetor[eixo], float(lim["min"]))

    return ResultadoAlvo(
        vetor=vetor,
        contribuicoes=contribuicoes,
        nao_reconhecidos=nao_reconhecidos,
        eixos_sem_direcao=[e for e in EIXOS if vetor[e] is None],
        territorios=territorios,
        publico=publico_nome,
        vocabulario=vocabulario,
        limites=limites,
    )


@dataclass(frozen=True)
class EssenciaPontuada:
    """Uma essência do repertório pontuada contra o alvo (0–100)."""

    essencia_id: int
    nome: str
    familia: str | None
    score: int
    eixos_comparados: list[str]
    explicacao: str


def pontuar_essencias(
    alvo: dict[str, float | None],
    repertorio: Sequence[EssenciaMotor],
    params: dict,
) -> tuple[list[EssenciaPontuada], list[str]]:
    """Ordena as essências DA USUÁRIA pela proximidade com o vetor-alvo.

    Distância = RMS nos eixos em que alvo e essência têm valor; score =
    100 × (1 − distância/10). Essências com poucos eixos em comum não são
    pontuadas (seria uma nota baseada em quase nada) e voltam listadas à parte.

    Args:
        alvo: vetor-alvo (`ResultadoAlvo.vetor`).
        repertorio: essências da usuária — a ÚNICA fonte de candidatas.
        params: regra `peso_score/recomendacao`.

    Returns:
        (pontuadas em ordem decrescente, nomes das não avaliadas).
    """
    exigir_chaves(params, CHAVES_PARAMS, "peso_score/recomendacao")
    minimo = int(params["min_eixos_comparados"])
    pontuadas: list[EssenciaPontuada] = []
    nao_avaliadas: list[str] = []
    for e in repertorio:
        eixos = [x for x in EIXOS if alvo.get(x) is not None and e.vetor.get(x) is not None]
        if len(eixos) < minimo:
            nao_avaliadas.append(e.nome)
            continue
        difs = {x: e.vetor[x] - alvo[x] for x in eixos}
        rms = math.sqrt(sum(d * d for d in difs.values()) / len(eixos))
        score = round(100 * max(0.0, 1 - rms / ESCALA_MAX))
        pior = max(difs, key=lambda x: abs(difs[x]))
        nome_eixo = ROTULOS_EIXOS[pior][0]
        if abs(difs[pior]) < 1:
            explicacao = "Próxima do alvo em todos os eixos comparados."
        else:
            explicacao = f"Maior diferença em {nome_eixo}: é {descrever_direcao(pior, difs[pior])} do que o alvo."
        pontuadas.append(EssenciaPontuada(e.id, e.nome, e.familia, score, eixos, explicacao))
    pontuadas.sort(key=lambda p: p.score, reverse=True)
    return pontuadas, nao_avaliadas


# ---------------------------------------------------------------------------
# Identidade: o caminho inverso do perfil (acorde → territórios)
# ---------------------------------------------------------------------------
CHAVES_IDENTIDADE = ("min_eixos_comparados", "proximidade_minima", "max_territorios")


@dataclass(frozen=True)
class TerritorioIdentificado:
    """Um território que o vetor de um acorde/criação transmite."""

    chave: str
    nome: str
    proximidade: int
    eixos_comparados: list[str]
    explicacao: str


def identificar_territorios(
    vetor: dict[str, float | None],
    correlacoes: dict[str, Any],
    nomes: dict[str, str],
    params: dict,
) -> list[TerritorioIdentificado]:
    """Quais territórios um vetor transmite, do mais próximo ao menos próximo.

    Compara o vetor com a correlação de cada território (regras
    `correlacao_territorio`), só nos eixos que o território afirma E que o
    vetor tem. Territórios com poucos eixos em comum não entram — afirmar
    "transmite Elegância" com base em um eixo só seria chute.

    Args:
        vetor: vetor de um acorde (`acordes.vetor.valores`) ou média.
        correlacoes: {chave_território: {"vetor": {...}, "peso": n}}.
        nomes: {chave_território: nome de exibição} (regras `territorio`).
        params: regra `peso_score/identidade`.

    Returns:
        Até `max_territorios` territórios com proximidade ≥ `proximidade_minima`.
    """
    exigir_chaves(params, CHAVES_IDENTIDADE, "peso_score/identidade")
    minimo = int(params["min_eixos_comparados"])
    achados: list[TerritorioIdentificado] = []
    for chave_t, valor in correlacoes.items():
        if chave_t not in nomes:
            continue  # só territórios registrados
        alvo = {e: float(v) for e, v in (valor or {}).get("vetor", {}).items() if e in EIXOS}
        eixos = [e for e in alvo if vetor.get(e) is not None]
        if len(eixos) < minimo:
            continue
        difs = {e: vetor[e] - alvo[e] for e in eixos}
        rms = math.sqrt(sum(d * d for d in difs.values()) / len(eixos))
        proximidade = round(100 * max(0.0, 1 - rms / ESCALA_MAX))
        if proximidade < int(params["proximidade_minima"]):
            continue
        perto = [ROTULOS_EIXOS[e][0] for e in eixos if abs(difs[e]) < 1.5]
        explicacao = (
            f"Combina em {', '.join(perto)}." if perto
            else "Próximo no conjunto, sem nenhum eixo idêntico."
        )
        achados.append(TerritorioIdentificado(chave_t, nomes[chave_t], proximidade, eixos, explicacao))
    achados.sort(key=lambda t: t.proximidade, reverse=True)
    return achados[: int(params["max_territorios"])]
