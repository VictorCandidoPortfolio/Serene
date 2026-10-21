"""Calculadora de FORMULAÇÃO: do acorde (pesos relativos) às quantidades finais.

Aqui aparecem quantidades reais (ml, g, %): por isso a aritmética usa `Decimal`
(sem erro de ponto flutuante) e tudo o que é limite técnico vem de DADOS.

Regra matemática do concentrado (a única fonte da quantidade de essência):

    concentrado (ml) = volume final × concentração selecionada ÷ 100

    100 ml: 7 % -> 7 ml; 10 % -> 10 ml; 15 % -> 15 ml (body splash);
            20 % -> 20 ml; 25 % -> 25 ml; 30 % -> 30 ml (perfume).

Divisão do concentrado entre as essências, por critério EXPLÍCITO:
1. `pesos_relativos` (padrão): parte da essência = seu peso (Pouco 1, Médio 2,
   Bastante 3) ÷ soma dos pesos do acorde.
2. Limites de uso documentados: se a participação da essência no PRODUTO
   passaria do `max_pct_produto` da ficha dela, a essência é fixada no limite e
   o excedente é redistribuído às demais, proporcionalmente aos pesos (e dito
   no aviso). Se nem assim fecha, a formulação é recusada.
3. `manual`: a aluna informa a % de cada essência no concentrado (soma 100 %);
   limites documentados NÃO são "corrigidos" em silêncio: ultrapassar é erro.

A soma das essências dentro do concentrado é sempre exatamente 100,00 %.

A BASE segue uma composição definida na regra do produto (componentes e % da
base, que somam 100). O resto do produto NUNCA é presumido como álcool puro.

O que a função NÃO faz: não valida segurança, estabilidade, solubilidade nem
conformidade regulatória (a fórmula sai sempre como NÃO VALIDADA) e não estima
densidade (massa só existe com densidade informada).

Formato da regra de produto (`peso_score/formulacao_<produto>`):
    {
      "nome": "Body splash",
      "concentracoes": [7, 10, 15],                     # únicas permitidas (% do produto)
      "volume_ml": {"min": 10, "max": 5000, "padrao": 100},
      "precisao_ml": 0.05, "min_essencias": 1,
      "base": {"componentes": [{"chave": "...", "nome": "...", "percentual": 55,
                                "densidade_g_ml": null}, ...]}     # percentuais somam 100
    }
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.engine.axes import ROTULOS_PESO, RegraInvalidaError, exigir_chaves

CHAVES_REGRA = ("nome", "concentracoes", "volume_ml", "precisao_ml", "min_essencias", "base")
CASA = Decimal("0.01")
CEM = Decimal(100)

VALIDACAO = (
    "Fórmula calculada, NÃO validada: o sistema não verifica segurança, estabilidade, solubilidade "
    "nem conformidade regulatória. Teste em pequena escala e confirme as especificações da base e "
    "dos fornecedores antes de produzir."
)


def _d(valor: Any) -> Decimal:
    """Converte para Decimal via texto (evita herdar o erro binário de um float)."""
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def q(valor: Decimal) -> Decimal:
    """Arredonda a 2 casas (meio para cima, como numa conta feita à mão)."""
    return valor.quantize(CASA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ItemFormulacao:
    """Uma essência do acorde com tudo o que a calculadora precisa saber dela.

    `limite_pct_produto` só vale se documentado (o service só preenche quando a
    ficha traz a fonte). `bloqueada_na_categoria` = a ficha lista este produto
    em `categorias_nao_indicadas`.
    """

    essencia_id: int
    nome: str
    peso: int
    densidade_g_ml: Decimal | None = None
    limite_pct_produto: Decimal | None = None
    limite_fonte: str | None = None
    bloqueada_na_categoria: bool = False
    restricao_texto: str | None = None


@dataclass(frozen=True)
class Ingrediente:
    """Uma linha da formulação."""

    tipo: str                      # "essencia" | "base"
    nome: str
    essencia_id: int | None
    peso: int | None
    rotulo_peso: str | None
    percentual_produto: Decimal    # participação no produto final
    percentual_concentrado: Decimal | None   # % dentro do concentrado (só essências)
    volume_ml: Decimal
    massa_g: Decimal | None        # só com densidade informada


@dataclass(frozen=True)
class ResultadoFormulacao:
    """Resultado. Sem `valido`, não há ingredientes: nada se calcula."""

    valido: bool
    erros: list[str]
    avisos: list[str]
    produto: str
    volume_ml: Decimal | None = None
    concentracao_pct: Decimal | None = None
    concentrado_ml: Decimal | None = None
    criterio: str | None = None    # "pesos_relativos" | "manual"
    ingredientes: list[Ingrediente] = field(default_factory=list)
    massa_total_g: Decimal | None = None   # só se TODAS as densidades são conhecidas
    validacao: str = VALIDACAO


def validar_regra(regra: Mapping[str, Any], chave: str) -> Mapping[str, Any]:
    """Falha alto se a regra do produto estiver malformada (nada de default no código)."""
    exigir_chaves(dict(regra), CHAVES_REGRA, f"peso_score/{chave}")
    if not isinstance(regra["concentracoes"], list) or not regra["concentracoes"]:
        raise RegraInvalidaError(f"Regra '{chave}': 'concentracoes' precisa de uma lista não vazia.")
    vol = regra["volume_ml"]
    if not isinstance(vol, Mapping) or not {"min", "max", "padrao"} <= set(vol):
        raise RegraInvalidaError(f"Regra '{chave}': 'volume_ml' precisa de min, max e padrao.")
    if not _d(vol["min"]) <= _d(vol["padrao"]) <= _d(vol["max"]):
        raise RegraInvalidaError(f"Regra '{chave}': 'volume_ml' com padrao fora de [min, max].")
    comps = (regra["base"] or {}).get("componentes") if isinstance(regra["base"], Mapping) else None
    if not comps:
        raise RegraInvalidaError(f"Regra '{chave}': a base precisa de uma composição definida.")
    if sum(_d(c["percentual"]) for c in comps) != CEM:
        raise RegraInvalidaError(f"Regra '{chave}': os componentes da base precisam somar 100 %.")
    return regra


def _proporcoes_por_peso(
    itens: Sequence[ItemFormulacao], conc: Decimal
) -> tuple[dict[int, Decimal], list[str], str | None]:
    """Proporção de cada essência no concentrado (fração 0..1) pelo critério de pesos.

    Aplica os limites documentados (fixa no limite e redistribui o excedente
    proporcionalmente aos pesos das demais). Devolve (frações, avisos, erro).
    """
    fixas: dict[int, Decimal] = {}
    avisos: list[str] = []
    while True:
        livres = [i for i in itens if i.essencia_id not in fixas]
        restante = Decimal(1) - sum(fixas.values(), Decimal(0))
        soma = sum(Decimal(i.peso) for i in livres)
        tentativa = {i.essencia_id: restante * Decimal(i.peso) / soma for i in livres} if livres else {}
        estourou = [
            i for i in livres
            if i.limite_pct_produto is not None and conc * tentativa[i.essencia_id] > i.limite_pct_produto
        ]
        if not estourou:
            if not livres and restante > Decimal("0.000001"):
                return {}, avisos, ("Os limites de uso documentados impedem fechar o concentrado nesta "
                                    "concentração. Reduza a concentração ou revise os limites das essências.")
            return {**fixas, **tentativa}, avisos, None
        for i in estourou:
            fixas[i.essencia_id] = i.limite_pct_produto / conc
            avisos.append(
                f"{i.nome} foi limitada a {q(i.limite_pct_produto / conc * CEM)} % do concentrado "
                f"(limite documentado de {i.limite_pct_produto} % do produto"
                + (f"; fonte: {i.limite_fonte}" if i.limite_fonte else "") + ")."
            )


def _fechar_em(partes: dict[Any, Decimal], total: Decimal, chave_maior: Any) -> dict[Any, Decimal]:
    """Quantiza cada parte (2 casas) e joga a sobra de arredondamento na maior, para fechar em `total`."""
    qs = {k: q(v) for k, v in partes.items()}
    qs[chave_maior] += total - sum(qs.values())
    return qs


def calcular_formulacao(
    regra: Mapping[str, Any],
    itens: Sequence[ItemFormulacao],
    volume_ml: Decimal | float | int | str,
    concentracao_pct: Decimal | float | int | str,
    proporcoes_manuais: Mapping[int, Decimal | float | int | str] | None = None,
) -> ResultadoFormulacao:
    """Calcula a formulação, ou diz por que não dá.

    Args:
        regra: regra do produto (ver docstring do módulo), já validada.
        itens: essências do acorde com peso relativo (1..3) e, se houver, a
            documentação de limites/restrições.
        volume_ml: volume final.
        concentracao_pct: uma das concentrações permitidas do produto.
        proporcoes_manuais: {essencia_id: % no concentrado}; soma 100.

    Returns:
        ResultadoFormulacao. Qualquer erro => `valido=False`, sem ingredientes.
    """
    produto = str(regra["nome"])
    erros: list[str] = []
    avisos: list[str] = []

    volume = _d(volume_ml)
    vmin, vmax = _d(regra["volume_ml"]["min"]), _d(regra["volume_ml"]["max"])
    if volume < vmin or volume > vmax:
        erros.append(f"O volume de {q(volume)} ml está fora da faixa de {produto}: {vmin} a {vmax} ml.")

    permitidas = [_d(c) for c in regra["concentracoes"]]
    conc = _d(concentracao_pct)
    if conc not in permitidas:
        opcoes = ", ".join(f"{c.normalize():f} %" for c in permitidas)
        erros.append(f"A concentração de {conc.normalize():f} % não existe para {produto}. Escolha: {opcoes}.")

    if len(itens) < int(regra["min_essencias"]):
        erros.append(f"{produto} precisa de pelo menos {int(regra['min_essencias'])} essência(s).")
    ids = [i.essencia_id for i in itens]
    if len(ids) != len(set(ids)):
        erros.append("Cada essência só pode aparecer uma vez na formulação.")
    for i in itens:
        if i.peso not in ROTULOS_PESO:
            erros.append(f"Peso inválido para {i.nome}: use 1 (Pouco), 2 (Médio) ou 3 (Bastante).")
        if i.densidade_g_ml is not None and i.densidade_g_ml <= 0:
            erros.append(f"A densidade de {i.nome} precisa ser maior que zero.")
        if i.bloqueada_na_categoria:
            erros.append(f"{i.nome} tem restrição documentada para {produto}: não use nesta categoria.")
    if erros:
        return ResultadoFormulacao(False, erros, avisos, produto)

    # ---- proporções das essências dentro do concentrado ----------------------
    if proporcoes_manuais is not None:
        criterio = "manual"
        manuais = {k: _d(v) for k, v in proporcoes_manuais.items()}
        if set(manuais) != set(ids):
            erros.append("As proporções manuais precisam cobrir exatamente as essências da fórmula.")
        elif any(v <= 0 for v in manuais.values()):
            erros.append("Cada proporção manual precisa ser maior que zero.")
        elif abs(sum(manuais.values()) - CEM) > CASA:
            erros.append(f"As proporções manuais somam {q(sum(manuais.values()))} %; precisam somar 100 %.")
        else:
            for i in itens:
                if i.limite_pct_produto is not None and conc * manuais[i.essencia_id] / CEM > i.limite_pct_produto:
                    erros.append(
                        f"{i.nome} ficaria com {q(conc * manuais[i.essencia_id] / CEM)} % do produto, acima do "
                        f"limite documentado de {i.limite_pct_produto} %."
                    )
        if erros:
            return ResultadoFormulacao(False, erros, avisos, produto)
        fracoes = {k: v / CEM for k, v in manuais.items()}
    else:
        criterio = "pesos_relativos"
        fracoes, ajustes, erro = _proporcoes_por_peso(itens, conc)
        if erro:
            return ResultadoFormulacao(False, [erro], avisos, produto)
        avisos += ajustes

    # ---- quantidades ---------------------------------------------------------
    volume_q = q(volume)
    concentrado = q(volume * conc / CEM)
    base_ml = volume_q - concentrado
    if base_ml <= 0:
        return ResultadoFormulacao(False, ["Não sobra volume para a base."], avisos, produto)

    maior = max(itens, key=lambda i: (fracoes[i.essencia_id], -i.essencia_id)).essencia_id
    pct_conc = _fechar_em({k: v * CEM for k, v in fracoes.items()}, CEM, maior)   # soma = 100,00
    ml_ess = _fechar_em({k: concentrado * fracoes[k] for k in fracoes}, concentrado, maior)

    ingredientes: list[Ingrediente] = []
    for i in sorted(itens, key=lambda x: (-ml_ess[x.essencia_id], x.essencia_id)):
        ml = ml_ess[i.essencia_id]
        ingredientes.append(Ingrediente(
            "essencia", i.nome, i.essencia_id, i.peso, ROTULOS_PESO[i.peso],
            # Participação no produto = concentração × % no concentrado (exata, não depende do
            # arredondamento do ml); assim as essências somam exatamente a concentração escolhida.
            q(conc * pct_conc[i.essencia_id] / CEM), pct_conc[i.essencia_id], ml,
            q(ml * i.densidade_g_ml) if i.densidade_g_ml is not None else None,
        ))

    comps = regra["base"]["componentes"]
    maior_base = max(comps, key=lambda c: _d(c["percentual"]))["chave"]
    ml_base = _fechar_em({c["chave"]: base_ml * _d(c["percentual"]) / CEM for c in comps}, base_ml, maior_base)
    for c in comps:
        dens = _d(c["densidade_g_ml"]) if c.get("densidade_g_ml") else None
        ml = ml_base[c["chave"]]
        ingredientes.append(Ingrediente(
            "base", str(c["nome"]), None, None, None, q(ml / volume_q * CEM), None, ml,
            q(ml * dens) if dens is not None else None,
        ))

    # ---- validação técnica do resultado --------------------------------------
    if sum(i.volume_ml for i in ingredientes) != volume_q:
        raise RegraInvalidaError("Falha interna: as partes não fecham no volume final.")
    if sum(i.percentual_concentrado for i in ingredientes if i.tipo == "essencia") != CEM:
        raise RegraInvalidaError("Falha interna: as essências não somam 100 % do concentrado.")

    precisao = _d(regra["precisao_ml"])
    abaixo = [i for i in ingredientes if i.tipo == "essencia" and i.volume_ml < precisao]
    if abaixo:
        menor = min(i.percentual_concentrado for i in ingredientes if i.tipo == "essencia") / CEM
        necessario = precisao / (conc / CEM * menor)
        avisos.append(
            f"Abaixo da precisão de medida ({precisao} ml): " + ", ".join(i.nome for i in abaixo)
            + f". Aumente o volume final para pelo menos {q(necessario)} ml."
        )
    sem_limite = sorted(i.nome for i in itens if i.limite_pct_produto is None)
    if sem_limite:
        avisos.append(
            "Sem limite de uso documentado na ficha de: " + ", ".join(sem_limite)
            + ". Confira a documentação do fornecedor antes de produzir."
        )
    restricoes = [f"{i.nome}: {i.restricao_texto}" for i in itens if i.restricao_texto]
    if restricoes:
        avisos.append("Restrições documentadas: " + "; ".join(restricoes))

    massas = [i.massa_g for i in ingredientes]
    massa_total = sum(massas, Decimal(0)) if all(m is not None for m in massas) else None
    return ResultadoFormulacao(
        True, [], avisos, produto, volume_ml=volume_q, concentracao_pct=conc, concentrado_ml=concentrado,
        criterio=criterio, ingredientes=ingredientes, massa_total_g=massa_total,
    )
