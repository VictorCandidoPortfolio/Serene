"""Identificação de lacunas do repertório (funcionalidade 2.9).

Duas perguntas diferentes:
1. `lacunas_repertorio`: "o que falta no meu repertório como um todo?"
   (famílias ausentes, camadas da pirâmide fracas, pouca amplitude num eixo).
2. `lacuna_para_movimento`: "por que não consigo deixar ESTE acorde mais X?"
   — chamada por `movement.py` quando nenhum ajuste com o repertório atual
   alcança o movimento pedido.

Regra de negócio 4, que este módulo existe para cumprir: a resposta sempre
nomeia uma CATEGORIA (família, camada, eixo), nunca uma essência específica
que a aluna não tem. A base de conhecimento é usada para dar NOME à lacuna,
nunca para oferecer uma nota de referência como se estivesse disponível.

Formato esperado da regra `peso_score/lacunas`:
    {
      "papel_minimo": 0.5,            # papel[camada] >= isso conta p/ camada
      "min_essencias_por_camada": 1,  # abaixo disso a camada é "fraca"
      "amplitude_minima": 4,          # max-min num eixo abaixo disso = pouca amplitude
      "eixos_amplitude": ["v1", "v3"] # eixos avaliados (frio↔quente, seco↔doce)
    }
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.engine.axes import (
    CAMADAS,
    EIXOS,
    ESCALA_MAX,
    ROTULOS_CAMADAS,
    ROTULOS_EIXOS,
    EssenciaMotor,
    Lacuna,
    descrever_direcao,
    exigir_chaves,
)

CHAVES_PARAMS = ("papel_minimo", "min_essencias_por_camada", "amplitude_minima", "eixos_amplitude")


@dataclass(frozen=True)
class FamiliaRef:
    """Família da base de conhecimento, como o motor precisa enxergá-la.

    Attributes:
        chave: slug estável.
        nome: nome de exibição (vai na mensagem da lacuna).
        parent_chave: slug da família-mãe (None = família de topo).
        vetor_medio: média dos vetores de referência das notas dessa família
            em `knowledge_notes` — serve só para saber para que LADO dos eixos
            a família costuma puxar. Pode ser vazio.
    """

    chave: str
    nome: str
    parent_chave: str | None = None
    vetor_medio: dict[str, float | None] | None = None


def lacunas_repertorio(
    repertorio: Sequence[EssenciaMotor],
    familias: Sequence[FamiliaRef],
    params: dict,
) -> list[Lacuna]:
    """Visão geral do que falta no repertório da usuária.

    Args:
        repertorio: TODAS as essências da usuária (e só dela).
        familias: famílias da base de conhecimento.
        params: regra `peso_score/lacunas`.

    Returns:
        Lista de lacunas (vazia se nada relevante falta).

    Raises:
        RegraInvalidaError: parâmetros ausentes.
    """
    exigir_chaves(params, CHAVES_PARAMS, "peso_score/lacunas")
    if not repertorio:
        return [
            Lacuna(
                "repertorio_vazio",
                "Seu repertório ainda está vazio. Cadastre as essências que você possui "
                "para o SÉRENÉ poder analisar e sugerir combinações.",
            )
        ]

    lacunas: list[Lacuna] = []
    lacunas += _familias_ausentes(repertorio, familias)
    lacunas += _camadas_fracas(repertorio, params)
    lacunas += _amplitude(repertorio, params)

    sem_vetor = [e.nome for e in repertorio if all(e.vetor.get(x) is None for x in EIXOS)]
    if sem_vetor:
        lacunas.append(
            Lacuna(
                "dados_incompletos",
                "Algumas essências ainda não têm características sensoriais informadas; "
                "elas não entram nos cálculos até serem classificadas.",
                {"essencias": sem_vetor},
            )
        )
    return lacunas


def _familias_ausentes(
    repertorio: Sequence[EssenciaMotor], familias: Sequence[FamiliaRef]
) -> list[Lacuna]:
    """Famílias de topo sem nenhuma essência (nem de subfamília) no repertório."""
    mae = {f.chave: f.parent_chave for f in familias}
    presentes: set[str] = set()
    for e in repertorio:
        if e.familia_chave:
            presentes.add(e.familia_chave)
            if mae.get(e.familia_chave):
                presentes.add(mae[e.familia_chave])
    ausentes = [f.nome for f in familias if f.parent_chave is None and f.chave not in presentes]
    if not ausentes:
        return []
    return [
        Lacuna(
            "familia_ausente",
            "Seu repertório não tem nenhuma essência destas famílias: "
            + ", ".join(ausentes) + ".",
            {"familias": ausentes},
        )
    ]


def _camadas_fracas(repertorio: Sequence[EssenciaMotor], params: dict) -> list[Lacuna]:
    """Camadas da pirâmide com poucas essências que as sustentam."""
    minimo = float(params["papel_minimo"])
    min_qtd = int(params["min_essencias_por_camada"])
    com_papel = [e for e in repertorio if e.papel]
    if not com_papel:
        # Sem papel informado não dá para avaliar a estrutura — dizer isso,
        # em vez de afirmar que "falta fundo".
        return [
            Lacuna(
                "estrutura_desconhecida",
                "Nenhuma essência tem papel na pirâmide (saída/coração/fundo) informado; "
                "não é possível avaliar a estrutura do repertório.",
            )
        ]
    lacunas = []
    for camada in CAMADAS:
        qtd = sum(1 for e in com_papel if float(e.papel.get(camada) or 0) >= minimo)
        if qtd < min_qtd:
            rotulo = ROTULOS_CAMADAS[camada]
            lacunas.append(
                Lacuna(
                    "estrutura",
                    f"Estrutura fraca em notas de {rotulo}: {qtd} essência(s) com papel "
                    f"predominante de {rotulo}.",
                    {"camada": camada, "quantidade": qtd},
                )
            )
    return lacunas


def _amplitude(repertorio: Sequence[EssenciaMotor], params: dict) -> list[Lacuna]:
    """Eixos em que o repertório cobre só uma faixa estreita."""
    lacunas = []
    amp_min = float(params["amplitude_minima"])
    meio = ESCALA_MAX / 2
    for eixo in params["eixos_amplitude"]:
        if eixo not in ROTULOS_EIXOS:
            continue
        valores = [e.vetor[eixo] for e in repertorio if e.vetor.get(eixo) is not None]
        if not valores:
            continue
        lo, hi = min(valores), max(valores)
        if hi - lo >= amp_min:
            continue
        nome, baixo, alto = ROTULOS_EIXOS[eixo]
        if lo > meio:
            falta = f"mais {baixo}"
        elif hi < meio:
            falta = f"mais {alto}"
        else:
            falta = f"mais {baixo} e mais {alto}"
        lacunas.append(
            Lacuna(
                "amplitude",
                f"Pouca amplitude em {nome} ({baixo} ↔ {alto}): seu repertório vai de "
                f"{lo:g} a {hi:g}. Faltam essências {falta}.",
                {"eixo": eixo, "min": lo, "max": hi},
            )
        )
    return lacunas


def lacuna_para_movimento(
    delta: dict[str, float],
    vetor_atual: dict[str, float | None],
    familias: Sequence[FamiliaRef],
    familias_presentes: set[str],
    descricao_movimento: str,
) -> Lacuna:
    """Nomeia o que falta quando um movimento não é alcançável.

    Procura, na base de conhecimento, famílias cujo vetor médio fica do lado
    certo de cada eixo do movimento em relação ao acorde atual. Prefere
    famílias AUSENTES do repertório (se a aluna já tivesse uma delas, o
    ajuste provavelmente teria sido encontrado).

    Args:
        delta: {eixo: variação desejada} da regra de movimento.
        vetor_atual: vetor do acorde.
        familias: famílias da base (com `vetor_medio`).
        familias_presentes: slugs de famílias que a aluna já possui.
        descricao_movimento: ex.: "mais fresco" (para a mensagem).

    Returns:
        Lacuna do tipo "movimento" — nomeia família(s) ou, na falta de dado
        de referência, só a direção no eixo.
    """
    direcoes = [descrever_direcao(e, d) for e, d in delta.items() if d and e in ROTULOS_EIXOS]
    candidatas: list[tuple[float, FamiliaRef]] = []
    for fam in familias:
        if not fam.vetor_medio:
            continue
        ganho, avaliou = 0.0, False
        for eixo, d in delta.items():
            f, c = fam.vetor_medio.get(eixo), vetor_atual.get(eixo)
            if not d or f is None or c is None:
                continue
            avaliou = True
            ganho += (f - c) * (1 if d > 0 else -1)
        if avaliou and ganho > 0:
            candidatas.append((ganho, fam))

    # Ausentes primeiro, depois maior ganho.
    candidatas.sort(key=lambda t: (t[1].chave in familias_presentes, -t[0]))
    nomes = [f.nome for _, f in candidatas[:2]]
    base = (
        f"Com o seu repertório atual não é possível deixar este acorde {descricao_movimento}."
    )
    if nomes:
        mensagem = (
            f"{base} O que falta é uma essência da família {' ou '.join(nomes)}. "
            "O SÉRENÉ não sugere uma essência específica porque ela não está no seu repertório."
        )
    else:
        mensagem = (
            f"{base} Falta uma essência {' e '.join(direcoes) or 'com outro perfil'} "
            "do que as que compõem o acorde."
        )
    return Lacuna("movimento", mensagem, {"familias": nomes, "direcoes": direcoes})
