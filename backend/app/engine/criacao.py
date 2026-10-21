"""Motor de CRIAÇÃO: do pedido da aluna ao acorde sugerido (funções PURAS).

    perfil da pessoa -> vetor-alvo -> territórios -> ranking das essências DELA
    -> montagem do acorde -> pesos relativos -> explicação

Garantias deste módulo (cada uma tem teste):
- DETERMINISMO: sem `random`, sem relógio. Todo desempate é fixo (id crescente).
- SÓ O REPERTÓRIO: o motor só enxerga as essências que o service entrega. Não
  há como ele "descobrir" uma nota de conhecimento ou de outra usuária.
- NADA INVENTADO: eixo sem valor (`None`) nunca vira número; a essência entra
  com proximidade neutra e aviso de baixa confiança.
- PESOS RELATIVOS: 1/2/3 = Pouco/Médio/Bastante, nunca porcentagem de produto.
- NENHUM NÚMERO DE DOMÍNIO AQUI: deslocamentos, limiares e pesos chegam por
  parâmetro, vindos de `knowledge_engine_rules` (ver `app/seed/data_criacao.py`).
  O que é estrutural (quais eixos existem, a escala 0–10) vive em `axes.py`.

Eixos usados (escala 0–10): v1 temperatura, v2 peso/persistência, v3 doçura,
v4 presença/intensidade, v5 complexidade estrutural. (O v6 da essência não
participa deste motor.) `v5` do ACORDE é calculado (diversidade), não lido.

Os textos explicativos saem de TEMPLATES preenchidos com dados. Nenhum modelo
de linguagem é chamado em lugar nenhum.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from app.core.text import chave
from app.engine.axes import (
    CAMADAS,
    ESCALA_MAX,
    ROTULOS_EIXOS,
    ROTULOS_PESO,
    EssenciaMotor,
    clamp,
    descrever_direcao,
    exigir_chaves,
)
from app.engine.compatibility import RelacaoFamilias, relacao_entre

# Eixos que o alvo carrega e que se comparam com a essência (v5 só existe no alvo
# e no acorde calculado: a essência não é "complexa", o conjunto é).
EIXOS_ALVO = ("v1", "v2", "v3", "v4", "v5")
EIXOS_COMPARADOS = ("v1", "v2", "v3", "v4")
EIXOS_DOCURA_TEMP = ("v1", "v2", "v3")

CHAVES_SCORE = (
    "ponto_neutro", "segundo_territorio_fracao", "bonus_territorio_alvo",
    "fator_territorio_fora", "multiplicador_bonus", "proximidade_neutra",
    "min_eixos_proximidade", "proximidade_muito", "proximidade_razoavel", "score_fraco",
    "max_itens_padrao", "peso_proximidade", "peso_compat", "compat_neutra",
    "bonus_presenca_por_item", "v5_por_territorio", "v5_por_distancia",
    "familia_segunda_fracao", "coerencia_ideal", "coerencia_sigma", "peso_coerencia",
    "peso_complementaridade", "peso_risco", "risco_atencao", "margem_isolada",
    "lacuna_eixo_minima", "cobertura_minima", "tolerancia_eixo", "intensidade_padrao",
    "pontos_familia_desejada",
)


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Territorio:
    """Território olfativo (família de gosto) e seu vocabulário curto."""

    chave: str
    nome: str
    familias: tuple[str, ...]
    adjetivo: str
    atributo: str
    ordem: int
    # Perfil típico do grupo (v2, v3, v4 e papel em %), usado pelo cadastro simples de essência.
    perfil: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Pedido:
    """O que a aluna pediu, já normalizado pelo service."""

    genero: str = "nao_definir"
    faixa_idade: str | None = None
    emocoes: tuple[str, ...] = ()
    preferencias: tuple[str, ...] = ()
    intensidade: float = 5.0
    # Famílias olfativas desejadas, já resolvidas para a chave do grupo de cheiro (ex.: "fresco").
    familias_desejadas: tuple[str, ...] = ()
    ocasiao: str | None = None


@dataclass(frozen=True)
class ResultadoAlvo:
    """Vetor-alvo, placar de territórios e o que veio da idade.

    Attributes:
        vetor: {v1..v5: 0–10}.
        territorios: {chave do território: pontos}.
        nao_reconhecidos: respostas sem regra no banco (nunca inventadas).
        max_itens: tamanho máximo do acorde (regra de idade).
        emocoes / preferencias: regras reconhecidas, na ordem pedida.
    """

    vetor: dict[str, float]
    territorios: dict[str, float]
    nao_reconhecidos: list[str]
    max_itens: int
    emocoes: list[str] = field(default_factory=list)
    preferencias: list[str] = field(default_factory=list)
    # Alguma emoção/preferência reconhecida deslocou um eixo (que não o v4) ou
    # pontuou um território. Sem isso o alvo é só o ponto neutro de partida, e
    # descrevê-lo como "direção" seria inventar.
    tem_direcao: bool = False


@dataclass(frozen=True)
class EssenciaPontuada:
    """Uma essência da aluna pontuada contra o alvo (uso interno do motor)."""

    essencia: EssenciaMotor
    territorio: str | None
    score: float
    proximidade: float
    no_territorio_alvo: bool
    nivel_proximidade: str  # "muito" | "razoavel" | "distante" | "sem_dado"


@dataclass(frozen=True)
class ItemAcorde:
    """Essência escolhida + peso relativo (1 pouco, 2 médio, 3 bastante)."""

    pontuada: EssenciaPontuada
    peso: int

    @property
    def rotulo_peso(self) -> str:
        return ROTULOS_PESO[self.peso]


@dataclass(frozen=True)
class VetorAcorde:
    """Resultado de `vetor_do_acorde`."""

    vetor: dict[str, float | None]
    papel: dict[str, int] | None
    familia_resultante: str | None


@dataclass(frozen=True)
class ResultadoMontagem:
    """Acorde montado, antes da atribuição de pesos."""

    escolhidas: list[EssenciaPontuada]
    fraco: bool


@dataclass(frozen=True)
class Compat:
    """Compatibilidade de um grupo (0–10) + essências isoladas."""

    score: float
    isoladas: list[str]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _media_abs(a: Mapping[str, float | None], b: Mapping[str, float | None],
               eixos: Sequence[str]) -> float | None:
    """Média das diferenças absolutas nos eixos em que AMBOS têm valor (None se nenhum)."""
    difs = [abs(a[e] - b[e]) for e in eixos if a.get(e) is not None and b.get(e) is not None]
    return sum(difs) / len(difs) if difs else None


def _faixa_de_texto(valor: float, faixas: Sequence[Mapping[str, Any]]) -> str:
    """Texto da primeira faixa cujo `ate` cobre o valor (a última pega o resto)."""
    for f in faixas:
        if valor <= float(f["ate"]):
            return str(f["texto"])
    return str(faixas[-1]["texto"])


def _lista_natural(itens: Sequence[str]) -> str:
    """["a","b","c"] -> "a, b e c"."""
    itens = list(itens)
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def faixa_da_idade(idade: int, regras_idade: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Converte idade em anos na chave da faixa (conversão vem de DADOS).

    Cada regra de idade traz `anos_de`/`anos_ate`. Se duas regras cobrirem a
    mesma idade (calibração mal feita) vale a de menor `anos_de`, depois a
    chave: determinístico. Idade fora de todas as faixas -> None (sem ajuste).
    """
    cobrem = sorted(
        (float(r.get("anos_de", 0)), k) for k, r in regras_idade.items()
        if float(r.get("anos_de", -1)) <= idade <= float(r.get("anos_ate", -2))
    )
    return cobrem[0][1] if cobrem else None


def territorio_da_familia(
    familia_chave: str | None,
    territorios: Mapping[str, Territorio],
    hierarquia: Mapping[str, str] | None = None,
) -> str | None:
    """Território de uma família cadastrada (sobe para a família-mãe se preciso).

    Família desconhecida (texto livre da aluna) -> None: a essência continua
    elegível, só não ganha bônus de território.
    """
    if not familia_chave:
        return None
    candidatas = [familia_chave]
    if hierarquia and familia_chave in hierarquia:
        candidatas.append(hierarquia[familia_chave])
    for slug in candidatas:
        for t in sorted(territorios.values(), key=lambda t: (t.ordem, t.chave)):
            if slug in t.familias:
                return t.chave
    return None


def carregar_territorios(regras: Mapping[str, Mapping[str, Any]]) -> dict[str, Territorio]:
    """Regras `criacao_territorio` -> {chave: Territorio}."""
    out = {}
    for k, v in regras.items():
        out[k] = Territorio(
            chave=k, nome=v["nome"], familias=tuple(v.get("familias", [])),
            adjetivo=v.get("adjetivo", v["nome"].lower()),
            atributo=v.get("atributo", ""), ordem=int(v.get("ordem", 99)), perfil=v.get("perfil") or {},
        )
    return out


# ---------------------------------------------------------------------------
# 5.1 Vetor-alvo e placar de territórios
# ---------------------------------------------------------------------------
def calcular_vetor_alvo(
    pedido: Pedido,
    regras_emocao: Mapping[str, Mapping[str, Any]],
    regras_preferencia: Mapping[str, Mapping[str, Any]],
    regras_idade: Mapping[str, Mapping[str, Any]],
    params: Mapping[str, Any],
    regras_ocasiao: Mapping[str, Mapping[str, Any]] | None = None,
) -> ResultadoAlvo:
    """Traduz o pedido num vetor-alvo e num placar de territórios.

    Além de emoções e preferências, o briefing alimenta o alvo com: famílias
    olfativas desejadas (`pontos_familia_desejada` por família, no placar de
    territórios) e ocasião de uso (regra com `target`/`terr`, como as demais).

    Parte do ponto neutro (`params["ponto_neutro"]`; v4 = intensidade pedida) e
    soma os deslocamentos de cada emoção/preferência reconhecida, com `clamp`
    em 0–10 a cada soma.

    `v4` (presença) vem EXCLUSIVAMENTE da intensidade da aluna e dos tetos de
    idade: deslocamentos `v4` das regras de emoção/preferência são ignorados
    aqui (senão "paz" anularia o controle de intensidade). Eles continuam nas
    regras porque o motor de ajuste (`movement`) usa valores desse tipo.

    Emoções contraditórias (Frescor + Conforto) não bloqueiam: os
    deslocamentos se somam e se equilibram.

    Returns:
        ResultadoAlvo. Chaves sem regra vão para `nao_reconhecidos`.
    """
    exigir_chaves(dict(params), CHAVES_SCORE, "peso_score/criacao_score")
    v: dict[str, float] = {e: float(x) for e, x in params["ponto_neutro"].items()}
    v["v4"] = clamp(float(pedido.intensidade))
    territorios: dict[str, float] = {}
    nao_reconhecidos: list[str] = []
    emocoes_ok: list[str] = []
    preferencias_ok: list[str] = []

    direcao = [False]

    def aplicar(regra: Mapping[str, Any]) -> None:
        for eixo, delta in (regra.get("target") or {}).items():
            if eixo == "v4" or eixo not in v:
                continue  # v4 vem da intensidade pedida
            v[eixo] = clamp(v[eixo] + float(delta))
            direcao[0] = direcao[0] or bool(delta)
        for nome_t, pontos in (regra.get("terr") or {}).items():
            k = chave(nome_t)
            territorios[k] = territorios.get(k, 0.0) + float(pontos)
            direcao[0] = direcao[0] or bool(pontos)

    for bruto, regras, tipo, ok in (
        *((e, regras_emocao, "emocao", emocoes_ok) for e in pedido.emocoes),
        *((p, regras_preferencia, "preferencia", preferencias_ok) for p in pedido.preferencias),
    ):
        k = chave(bruto)
        if k in ok:
            continue  # chip repetido não conta duas vezes
        if k in regras:
            aplicar(regras[k])
            ok.append(k)
        else:
            nao_reconhecidos.append(f"{tipo}:{bruto}")

    for k in pedido.familias_desejadas:
        territorios[k] = territorios.get(k, 0.0) + float(params["pontos_familia_desejada"])
        direcao[0] = True
    if pedido.ocasiao:
        regra_ocasiao = (regras_ocasiao or {}).get(pedido.ocasiao)
        if regra_ocasiao is None:
            nao_reconhecidos.append(f"ocasiao:{pedido.ocasiao}")
        else:
            aplicar(regra_ocasiao)

    max_itens = int(params["max_itens_padrao"])
    if pedido.faixa_idade:
        regra_idade = regras_idade.get(pedido.faixa_idade)
        if regra_idade is None:
            nao_reconhecidos.append(f"idade:{pedido.faixa_idade}")
        else:
            for eixo, delta in (regra_idade.get("delta") or {}).items():
                if eixo in v:
                    v[eixo] = clamp(v[eixo] + float(delta))
            if regra_idade.get("v4_max") is not None:
                v["v4"] = min(v["v4"], float(regra_idade["v4_max"]))
            max_itens = int(regra_idade.get("max_itens", max_itens))

    return ResultadoAlvo(
        vetor={e: round(v[e], 4) for e in EIXOS_ALVO}, territorios=territorios,
        nao_reconhecidos=nao_reconhecidos, max_itens=max_itens,
        emocoes=emocoes_ok, preferencias=preferencias_ok, tem_direcao=direcao[0],
    )


# ---------------------------------------------------------------------------
# 5.2 Territórios dominantes
# ---------------------------------------------------------------------------
def pick_territorios(
    territorios: Mapping[str, float],
    ordem: Mapping[str, int],
    params: Mapping[str, Any],
    perfis_referencia: Mapping[str, Mapping[str, float] | None] | None = None,
    vetor: Mapping[str, float] | None = None,
) -> list[str]:
    """Escolhe 1 ou 2 territórios dominantes.

    O segundo só entra se tiver pelo menos `segundo_territorio_fracao` (0,5) dos
    pontos do primeiro. Empate de pontos: menor `ordem` do território, depois
    a chave (determinístico).

    Sem nenhum ponto (nenhuma emoção/preferência apontou território): escolhe
    o território cujo perfil médio de referência (v1–v3 das notas daquela
    família em `knowledge_notes`) fica mais perto do vetor-alvo. Se nem isso
    houver, o de menor `ordem`. Nunca devolve lista vazia se `ordem` não for vazio.
    """
    ranking = sorted(
        ((k, p) for k, p in territorios.items() if p > 0),
        key=lambda kp: (-kp[1], ordem.get(kp[0], 99), kp[0]),
    )
    if ranking:
        top = [ranking[0][0]]
        if len(ranking) > 1 and ranking[1][1] >= float(params["segundo_territorio_fracao"]) * ranking[0][1]:
            top.append(ranking[1][0])
        return top

    if not ordem:
        return []
    perfis = perfis_referencia or {}
    alvo = vetor or {}
    candidatos = []
    for k in ordem:
        perfil = perfis.get(k) or {}
        # Soma das diferenças absolutas nos eixos em que ambos têm valor;
        # território sem perfil de referência fica por último (não é chute).
        difs = [abs(perfil[e] - alvo[e]) for e in EIXOS_DOCURA_TEMP
                if perfil.get(e) is not None and alvo.get(e) is not None]
        candidatos.append((not difs, sum(difs), ordem[k], k))
    candidatos.sort()
    return [candidatos[0][3]]


# ---------------------------------------------------------------------------
# 5.4 Pontuação das essências da aluna
# ---------------------------------------------------------------------------
def pontuar_essencias(
    repertorio: Sequence[EssenciaMotor],
    territorio_de: Mapping[int, str | None],
    alvo: Mapping[str, float],
    territorios: Mapping[str, float],
    top: Sequence[str],
    params: Mapping[str, Any],
) -> list[EssenciaPontuada]:
    """Ranking das essências DO REPERTÓRIO (maior score primeiro; empate: id menor).

        bonus = bonus_territorio_alvo            se a essência está num território dominante
                territorios[t] * fator_fora      caso contrário (0 se o território não pontuou)
        score = bonus * multiplicador + proximidade
        proximidade = 10 - média(|essência - alvo|) em v1..v4

    Eixo sem valor é ignorado; com menos de `min_eixos_proximidade` eixos a
    essência recebe a proximidade NEUTRA e fica marcada `sem_dado` — o motor
    não inventa v1–v4.
    """
    neutra = float(params["proximidade_neutra"])
    out: list[EssenciaPontuada] = []
    for e in repertorio:
        t = territorio_de.get(e.id)
        no_alvo = t is not None and t in top
        if no_alvo:
            bonus = float(params["bonus_territorio_alvo"])
        else:
            bonus = float(territorios.get(t, 0.0)) * float(params["fator_territorio_fora"]) if t else 0.0
        comuns = [x for x in EIXOS_COMPARADOS if e.vetor.get(x) is not None]
        if len(comuns) >= int(params["min_eixos_proximidade"]):
            media = _media_abs(e.vetor, alvo, EIXOS_COMPARADOS)
            prox = ESCALA_MAX - media
            nivel = ("muito" if prox > float(params["proximidade_muito"])
                     else "razoavel" if prox > float(params["proximidade_razoavel"]) else "distante")
            sem_dado = False
        else:
            prox, nivel, sem_dado = neutra, "sem_dado", True
        score = bonus * float(params["multiplicador_bonus"]) + prox
        out.append(EssenciaPontuada(
            essencia=e, territorio=t, score=score, proximidade=prox, no_territorio_alvo=no_alvo,
            nivel_proximidade=nivel,
        ))
    out.sort(key=lambda p: (-round(p.score, 9), p.essencia.id))
    return out


# ---------------------------------------------------------------------------
# 5.7 Vetor, pirâmide e família resultante do acorde
# ---------------------------------------------------------------------------
def vetor_do_acorde(
    itens: Sequence[tuple[EssenciaPontuada, int]],
    territorios: Mapping[str, Territorio],
    params: Mapping[str, Any],
) -> VetorAcorde:
    """Vetor v1–v5, papel na pirâmide (%) e família resultante de um acorde.

    - v1, v2, v3: média ponderada pelos pesos, ignorando essência sem o eixo.
    - v4: média ponderada + (n_itens - 1) * bonus_presenca_por_item, com clamp
      (mais essências, mais presença).
    - v5: (n_territórios_distintos - 1) * v5_por_territorio
           + distância_média_entre_pares * v5_por_distancia, com clamp.
    - papel: soma ponderada de saída/coração/fundo, normalizada para 100 %
      (saída e coração arredondados; fundo = 100 - saída - coração, para fechar).
    - família resultante: território de maior peso total; se o segundo tem mais
      de `familia_segunda_fracao` do primeiro, "Primeiro / Segundo".
    """
    vetor: dict[str, float | None] = {}
    for eixo in ("v1", "v2", "v3", "v4"):
        com = [(i.essencia.vetor[eixo], p) for i, p in itens if i.essencia.vetor.get(eixo) is not None]
        pw = sum(p for _, p in com)
        total = sum(p for _, p in itens)
        # Eixo com pouca cobertura não descreve o acorde: fica sem valor.
        ok = pw and pw / total >= float(params["cobertura_minima"])
        vetor[eixo] = sum(x * p for x, p in com) / pw if ok else None
    if vetor["v4"] is not None:
        vetor["v4"] = clamp(vetor["v4"] + (len(itens) - 1) * float(params["bonus_presenca_por_item"]))

    n_terr = len({i.territorio for i, _ in itens if i.territorio})
    pares = [d for a, b in combinations([i.essencia for i, _ in itens], 2)
             if (d := _media_abs(a.vetor, b.vetor, EIXOS_COMPARADOS)) is not None]
    dist_media = sum(pares) / len(pares) if pares else 0.0
    vetor["v5"] = clamp(max(n_terr - 1, 0) * float(params["v5_por_territorio"])
                        + dist_media * float(params["v5_por_distancia"]))

    # Pirâmide: só entram essências com papel informado.
    com_papel = [(i.essencia.papel, p) for i, p in itens if i.essencia.papel]
    papel = None
    cobre = sum(p for _, p in com_papel) / sum(p for _, p in itens)
    if com_papel and cobre >= float(params["cobertura_minima"]):
        bruto = {c: sum(float(pp.get(c) or 0) * p for pp, p in com_papel) for c in CAMADAS}
        soma = sum(bruto.values())
        if soma > 0:
            saida = round(100 * bruto["saida"] / soma)
            coracao = round(100 * bruto["coracao"] / soma)
            papel = {"saida": saida, "coracao": coracao, "fundo": 100 - saida - coracao}

    # Família resultante pelos territórios (peso total; empate: menor ordem).
    pesos_t: dict[str, int] = {}
    for i, p in itens:
        if i.territorio:
            pesos_t[i.territorio] = pesos_t.get(i.territorio, 0) + p
    ranking = sorted(pesos_t.items(), key=lambda kv: (-kv[1], territorios[kv[0]].ordem if kv[0] in territorios else 99, kv[0]))
    familia = None
    if ranking:
        nome = lambda k: territorios[k].nome if k in territorios else k  # noqa: E731
        familia = nome(ranking[0][0])
        if len(ranking) > 1 and ranking[1][1] > float(params["familia_segunda_fracao"]) * ranking[0][1]:
            familia += " / " + nome(ranking[1][0])
    return VetorAcorde(vetor=vetor, papel=papel, familia_resultante=familia)


# ---------------------------------------------------------------------------
# 5.8 Compatibilidade (par e grupo)
# ---------------------------------------------------------------------------
def compatibilidade_par(
    a: EssenciaMotor,
    b: EssenciaMotor,
    relacoes: Sequence[RelacaoFamilias],
    hierarquia: Mapping[str, str],
    params: Mapping[str, Any],
) -> float:
    """Score 0–10 do par: 0,4*coerência + 0,35*complementaridade + 0,25*(10 - risco).

    - coerência: curva em sino sobre a distância média em v1–v3 (ideal ~3,5):
      iguais demais ou opostas demais pontuam menos.
    - complementaridade: quão DIFERENTES são os papéis na pirâmide (uma abre,
      outra sustenta). Sem papel nas duas, vale o neutro.
    - risco: `risco_atencao` quando as famílias têm relação do tipo "atencao"
      em `knowledge_family_relations` (dado, não código).
    Sem dado para um componente, ele vale o neutro `compat_neutra`.
    """
    neutro = float(params["compat_neutra"])
    d3 = _media_abs(a.vetor, b.vetor, EIXOS_DOCURA_TEMP)
    if d3 is None:
        coerencia = neutro
    else:
        coerencia = 10 * math.exp(-((d3 - float(params["coerencia_ideal"])) ** 2)
                                  / (2 * float(params["coerencia_sigma"]) ** 2))
    if a.papel and b.papel:
        # papéis chegam em 0..1; a fórmula trabalha em pontos percentuais.
        dif = sum(abs(float(a.papel.get(c) or 0) - float(b.papel.get(c) or 0)) * 100 for c in CAMADAS) / 2
        compl = min(10.0, dif / 10)
    else:
        compl = neutro
    risco = 0.0
    if a.familia_chave and b.familia_chave and a.familia_chave != b.familia_chave:
        rel = relacao_entre(a.familia_chave, b.familia_chave, relacoes, dict(hierarquia))
        if rel is not None and rel.tipo == "atencao":
            risco = float(params["risco_atencao"])
    return (float(params["peso_coerencia"]) * coerencia
            + float(params["peso_complementaridade"]) * compl
            + float(params["peso_risco"]) * (10 - risco))


def compatibilidade_de_grupo(
    essencias: Sequence[EssenciaMotor],
    relacoes: Sequence[RelacaoFamilias],
    hierarquia: Mapping[str, str],
    params: Mapping[str, Any],
) -> Compat:
    """Média dos scores de todos os pares + essências "isoladas".

    Isolada = a média dela com as demais fica mais de `margem_isolada` pontos
    abaixo da média geral. Com menos de 2 essências não há par: devolve o neutro.
    """
    if len(essencias) < 2:
        return Compat(float(params["compat_neutra"]), [])
    scores: dict[tuple[int, int], float] = {
        (a.id, b.id): compatibilidade_par(a, b, relacoes, hierarquia, params)
        for a, b in combinations(essencias, 2)
    }
    geral = sum(scores.values()) / len(scores)
    isoladas = []
    if len(essencias) >= 3:  # com 2, as duas teriam a mesma média
        for e in essencias:
            meus = [s for (x, y), s in scores.items() if e.id in (x, y)]
            if sum(meus) / len(meus) < geral - float(params["margem_isolada"]):
                isoladas.append(e.nome)
    return Compat(geral, isoladas)


# ---------------------------------------------------------------------------
# 5.5 Montagem gulosa do acorde
# ---------------------------------------------------------------------------
def _proximidade_acorde(vetor: Mapping[str, float | None], alvo: Mapping[str, float],
                        neutra: float) -> float:
    media = _media_abs(vetor, alvo, EIXOS_COMPARADOS)
    return neutra if media is None else ESCALA_MAX - media


def montar_acorde(
    ranking: Sequence[EssenciaPontuada],
    alvo: Mapping[str, float],
    max_itens: int,
    territorios: Mapping[str, Territorio],
    relacoes: Sequence[RelacaoFamilias],
    hierarquia: Mapping[str, str],
    params: Mapping[str, Any],
) -> ResultadoMontagem:
    """Montagem GULOSA e enxuta: nunca passa de `max_itens`.

    Parte da essência de maior score e só acrescenta a candidata que (a)
    aproxima o vetor do acorde do alvo e (b) combina com as já escolhidas:

        valor = 0,6 * proximidade_do_acorde + 0,4 * compatibilidade_do_grupo

    Para quando, com 2+ escolhidas, a melhor candidata não supera o acorde
    atual (compatibilidade neutra no baseline): "adicionar mais não ajuda,
    não force". Desempate: maior score individual, depois menor id.

    `fraco` = nem a melhor essência chega ao `score_fraco`. O acorde é
    entregue assim mesmo; o service avisa e nomeia a lacuna.

    Guloso não garante o melhor acorde possível: é previsível e explicável.
    """
    if not ranking:
        return ResultadoMontagem([], True)
    p_prox, p_comp = float(params["peso_proximidade"]), float(params["peso_compat"])
    neutra = float(params["proximidade_neutra"])
    escolhidas = [ranking[0]]
    # Só se afirma "fraco" com dado: score baixo por falta de característica
    # (proximidade neutra) seria dizer que não combina sem saber.
    fraco = (ranking[0].score < float(params["score_fraco"])
             and ranking[0].nivel_proximidade != "sem_dado")

    def com_peso_2(grupo: Sequence[EssenciaPontuada]) -> list[tuple[EssenciaPontuada, int]]:
        return [(g, 2) for g in grupo]

    while len(escolhidas) < max_itens:
        ids = {e.essencia.id for e in escolhidas}
        restantes = [r for r in ranking if r.essencia.id not in ids]
        if not restantes:
            break
        atual = vetor_do_acorde(com_peso_2(escolhidas), territorios, params).vetor
        prox_atual = _proximidade_acorde(atual, alvo, neutra)
        avaliadas = []
        for r in restantes:
            tentativa = [*escolhidas, r]
            vet = vetor_do_acorde(com_peso_2(tentativa), territorios, params).vetor
            prox = _proximidade_acorde(vet, alvo, neutra)
            compat = compatibilidade_de_grupo([t.essencia for t in tentativa], relacoes, hierarquia, params).score
            valor = p_prox * prox + p_comp * compat
            # round: desempate estável apesar de ruído de ponto flutuante.
            avaliadas.append((-round(valor, 9), -round(r.score, 9), r.essencia.id, valor, r))
        avaliadas.sort(key=lambda t: t[:3])
        melhor_valor, melhor = avaliadas[0][3], avaliadas[0][4]
        if len(escolhidas) >= 2 and melhor_valor <= prox_atual * p_prox + float(params["compat_neutra"]) * p_comp:
            break
        escolhidas.append(melhor)
    return ResultadoMontagem(escolhidas, fraco)


# ---------------------------------------------------------------------------
# 5.6 Pesos relativos
# ---------------------------------------------------------------------------
def atribuir_pesos(
    escolhidas: Sequence[EssenciaPontuada], padrao_pesos: Mapping[str, Sequence[int]]
) -> list[ItemAcorde]:
    """Aplica o padrão fixo de pesos (`2 -> [2,2]`, `3 -> [3,2,1]`, `4 -> [3,2,2,1]`).

    Ordena por score individual (desempate: id) e entrega o maior peso à mais
    alinhada. É uma simplificação pedagógica: a proporção real depende da
    intensidade e da persistência de cada essência e deve ser validada em bancada.
    """
    n = len(escolhidas)
    padrao = padrao_pesos.get(str(n))
    if padrao is None or len(padrao) != n:
        raise ValueError(f"Sem padrão de pesos para acorde de {n} item(ns).")
    ordenadas = sorted(escolhidas, key=lambda p: (-round(p.score, 9), p.essencia.id))
    return [ItemAcorde(p, int(w)) for p, w in zip(ordenadas, padrao)]


# ---------------------------------------------------------------------------
# 5.3 / 5.9 Textos (templates preenchidos com dados)
# ---------------------------------------------------------------------------
def direcao_em_texto(
    vetor: Mapping[str, float],
    top: Sequence[str],
    territorios: Mapping[str, Territorio],
    vocab: Mapping[str, Any],
) -> str:
    """"{Território1} {território2?}, {doçura}, {temperatura} e {presença}."

    Ex.: "Floral frutada, delicadamente doce, fresca e com presença suave."
    Um adjetivo de temperatura já dito pelo território ("fresca") não se repete.
    """
    adjs = [territorios[k].adjetivo for k in top if k in territorios]
    temp = _faixa_de_texto(vetor["v1"], vocab["temperatura"])
    docura = _faixa_de_texto(vetor["v3"], vocab["docura"])
    presenca = _faixa_de_texto(vetor["v4"], vocab["presenca"])
    cabeca = " ".join(adjs).strip()
    cabeca = cabeca[:1].upper() + cabeca[1:]
    meio = ", ".join([docura] + ([] if temp in adjs else [temp]))
    corpo = f"{cabeca}, {meio} e {presenca}" if cabeca else f"{meio} e {presenca}"
    return corpo[:1].upper() + corpo[1:] + "."


def identidade(
    pedido: Pedido,
    alvo: ResultadoAlvo,
    top: Sequence[str],
    territorios: Mapping[str, Territorio],
    regras_emocao: Mapping[str, Mapping[str, Any]],
    regras_preferencia: Mapping[str, Mapping[str, Any]],
    vocab: Mapping[str, Any],
) -> dict[str, Any]:
    """Identidade olfativa: nome sugerido, personalidade, direção e "por quê".

    Tudo por template. Linguagem de tendência ("tende a"), nunca promessa.
    """
    direcao = direcao_em_texto(alvo.vetor, top, territorios, vocab)

    # Personalidade: atributos das emoções (na ordem pedida), depois dos
    # territórios dominantes; sem repetir; no máximo 4.
    atributos: list[str] = []
    for k in alvo.emocoes:
        a = regras_emocao[k].get("atributo")
        if a and a not in atributos:
            atributos.append(a)
    for k in top:
        a = territorios[k].atributo if k in territorios else None
        if a and a not in atributos:
            atributos.append(a)
    personalidade = atributos[:4]

    # Nome sugerido: substantivo da 1ª emoção + adjetivo da 2ª (ou o do território).
    nome = None
    if alvo.emocoes:
        r1 = regras_emocao[alvo.emocoes[0]]
        base = r1.get("substantivo")
        adj = (regras_emocao[alvo.emocoes[1]].get("adjetivo") if len(alvo.emocoes) > 1
               else (territorios[top[0]].atributo if top and top[0] in territorios else None))
        if base:
            nome = f"{base} {adj}".strip() if adj else base

    pediu = [regras_emocao[k].get("rotulo", k) for k in alvo.emocoes]
    gosta = [regras_preferencia[k].get("rotulo", k) for k in alvo.preferencias]
    frases = []
    if pediu:
        frases.append(f"Você pediu {_lista_natural(pediu)}")
        if gosta:
            frases[-1] += f", com preferência por algo {_lista_natural(gosta)}"
        frases[-1] += "."
    elif gosta:
        frases.append(f"Você indicou preferência por algo {_lista_natural(gosta)}.")
    # (sem emoções nem preferências o service nem chega aqui: ver `tem_direcao`)
    frases.append(f"A direção calculada a partir disso é: {direcao[:1].lower() + direcao[1:]}")
    return {"nome_sugerido": nome, "personalidade": personalidade, "direcao": direcao,
            "por_que": " ".join(frases)}


def _eixos_proximos(vetor: Mapping[str, float | None], alvo: Mapping[str, float],
                    tolerancia: float) -> list[str]:
    """Rótulos dos eixos (v1–v4) em que `vetor` está a até `tolerancia` do alvo.

    Só eixos COM valor entram: nada de afirmar proximidade onde falta dado.
    """
    return [ROTULOS_EIXOS[e][0] for e in EIXOS_COMPARADOS
            if vetor.get(e) is not None and abs(vetor[e] - alvo[e]) <= tolerancia]


def explicar_essencia(
    pontuada: EssenciaPontuada,
    papel_essencia: Mapping[str, float] | None,
    territorios: Mapping[str, Territorio],
    top: Sequence[str],
    alvo: Mapping[str, float],
    params: Mapping[str, Any],
    vocab: Mapping[str, Any],
) -> str | None:
    """Por que esta essência está no acorde — SÓ com fatos calculados.

    Cada frase só existe se houver dado que a sustente:
    - território: a família cadastrada pela aluna cai num território conhecido;
    - proximidade: eixos (com valor) a até `tolerancia_eixo` do que foi pedido;
    - papel: um papel da pirâmide que a aluna informou e que passa de 50 %.
    Sem nenhum desses fatos devolve `None` (a interface não mostra nada), em
    vez de uma frase genérica. Sem texto por "personalidade" da família.
    """
    frases: list[str] = []
    t = territorios.get(pontuada.territorio) if pontuada.territorio else None
    if t is not None:
        pedido = " (o que você pediu)" if pontuada.territorio in top else ""
        frases.append(f"É do território {t.nome}{pedido}.")
    perto = _eixos_proximos(pontuada.essencia.vetor, alvo, float(params["tolerancia_eixo"]))
    if perto:
        frases.append(f"Está próxima do que você pediu em {_lista_natural(perto)}.")
    if papel_essencia:
        limiar = float(vocab.get("papel_dominante_acima_de", 0.5))
        dominante = max(CAMADAS, key=lambda c: (float(papel_essencia.get(c) or 0), -CAMADAS.index(c)))
        if float(papel_essencia.get(dominante) or 0) > limiar:
            frases.append(vocab["frase_papel"][dominante])
    return " ".join(frases) or None


def explicacao_do_acorde(nomes: Sequence[str], alvo: ResultadoAlvo,
                         regras_emocao: Mapping[str, Mapping[str, Any]],
                         vetor_acorde: Mapping[str, float | None],
                         params: Mapping[str, Any]) -> str:
    """"Escolhi X porque você pediu Y" + onde o conjunto de fato chega perto.

    A segunda frase só aparece se o vetor do acorde, calculado, estiver dentro
    da tolerância do alvo em algum eixo. Nenhuma promessa sobre a pele.
    """
    pediu = [regras_emocao[k].get("rotulo", k) for k in alvo.emocoes]
    texto = f"Escolhi {_lista_natural(list(nomes))}"
    texto += f" porque você pediu {_lista_natural(pediu)}." if pediu else "."
    perto = _eixos_proximos(vetor_acorde, alvo.vetor, float(params["tolerancia_eixo"]))
    if perto:
        texto += f" Em conjunto, ficam próximas do que você pediu em {_lista_natural(perto)}."
    return texto


# ---------------------------------------------------------------------------
# Lacunas
# ---------------------------------------------------------------------------
def lacunas_de_territorio(
    top: Sequence[str],
    territorio_das_escolhidas: Sequence[str | None],
    repertorio_territorios: set[str],
    territorios: Mapping[str, Territorio],
    nomes_familias: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Territórios dominantes SEM nenhuma essência no repertório disponível.

    Nomeia a CATEGORIA (território + famílias), nunca uma essência ou marca.
    """
    out = []
    for k in top:
        if k in repertorio_territorios or k not in territorios:
            continue
        t = territorios[k]
        fams = [nomes_familias.get(f, f) for f in t.familias]
        out.append({
            "tipo": "territorio",
            "categoria": t.nome,
            "mensagem": f"Falta uma essência do território {t.nome} ({_lista_natural(fams[:3])}) "
                        "para chegar mais perto dessa direção.",
        })
    return out


def delta_de_lacuna(vetor_acorde: Mapping[str, float | None], alvo: Mapping[str, float],
                    params: Mapping[str, Any]) -> dict[str, float]:
    """Eixos em que o acorde ficou longe do alvo, como {eixo: variação desejada}.

    Só entram diferenças de pelo menos `lacuna_eixo_minima`, as duas maiores.
    O service entrega esse delta a `engine.gaps.lacuna_para_movimento`, que
    NOMEIA a família que falta (sem indicar essência, marca ou fornecedor).
    """
    minimo = float(params["lacuna_eixo_minima"])
    achados = []
    for eixo in EIXOS_COMPARADOS:
        atual = vetor_acorde.get(eixo)
        if atual is None:
            continue
        delta = alvo[eixo] - atual
        if abs(delta) >= minimo:
            achados.append((-abs(delta), eixo, delta))
    achados.sort()
    return {eixo: delta for _, eixo, delta in achados[:2]}


def descrever_delta(delta: Mapping[str, float]) -> str:
    """{"v1": -2.0, "v3": 1.6} -> "mais fresco e mais doce"."""
    return _lista_natural([descrever_direcao(e, d) for e, d in delta.items()])


def dados_suficientes(fraco: bool, escolhidas: Sequence[EssenciaPontuada]) -> bool:
    """True quando o acorde se apoia em dados: há essências e a melhor combina.

    Substitui o antigo selo "confiança alta/média/baixa", cujos limiares eram
    inventados. Aqui só há um fato verificável. Os motivos de uma limitação
    aparecem nos avisos e nas lacunas, não em um selo.
    """
    return bool(escolhidas) and not fraco
