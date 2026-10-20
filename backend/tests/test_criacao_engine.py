"""Testes unitários do motor de criação (funções puras, sem banco).

As regras vêm do próprio seed (`data_criacao.py`): assim os testes conferem a
conta feita à mão contra os mesmos valores que o banco recebe.
"""

import random

import pytest

from app.engine import criacao as c
from app.engine.axes import EssenciaMotor
from app.engine.compatibility import RelacaoFamilias
from app.seed.data_criacao import REGRAS_CRIACAO

# {tipo: {chave: valor}} como o repositório entrega.
REGRAS: dict[str, dict] = {}
for _tipo, _chave, _valor, _ in REGRAS_CRIACAO:
    REGRAS.setdefault(_tipo, {})[_chave] = _valor
PARAMS = REGRAS["peso_score"]["criacao_score"]
PADRAO = REGRAS["peso_score"]["criacao_padrao_pesos"]
TERRITORIOS = c.carregar_territorios(REGRAS["criacao_territorio"])
ORDEM = {k: t.ordem for k, t in TERRITORIOS.items()}


def alvo_de(**kw) -> c.ResultadoAlvo:
    return c.calcular_vetor_alvo(
        c.Pedido(**kw), REGRAS["criacao_emocao"], REGRAS["criacao_preferencia"],
        REGRAS["criacao_idade"], PARAMS)


def ess(i, nome, fam=None, v=(5, 5, 5, 5), papel=None, chave_fam=None):
    return EssenciaMotor(
        id=i, nome=nome, familia=fam, familia_chave=chave_fam or (fam or "").lower() or None,
        vetor=dict(zip(("v1", "v2", "v3", "v4"), v)), papel=papel)


def pont(e, terr=None, **kw):
    return c.EssenciaPontuada(e, terr, kw.get("score", 10.0), 5.0, kw.get("no_alvo", False),
                              "razoavel", False)


# ---------------------------------------------------------------- vetor-alvo
def test_vetor_alvo_luna_bate_com_a_conta_a_mao():
    """Neutro (5,5,5,4,4); amor v3+1; paz v1-1; serenidade v1-1; doce v3+1; intensidade 4."""
    a = alvo_de(emocoes=("amor", "paz", "serenidade"), preferencias=("doce", "floral"), intensidade=4)
    assert a.vetor == {"v1": 3, "v2": 5, "v3": 7, "v4": 4, "v5": 4}
    # Floral: amor 2 + floral 2; Aromático: paz 2 + serenidade 2; Gourmand/Doce: doce 2.
    assert a.territorios == {"floral": 4, "aromatico": 4, "gourmand_doce": 2}
    assert a.max_itens == 4 and a.nao_reconhecidos == []


def test_v4_vem_so_da_intensidade():
    """"paz" tem v4 -1 na regra, mas não pode anular o controle de intensidade."""
    assert alvo_de(emocoes=("paz",), intensidade=8).vetor["v4"] == 8
    assert alvo_de(preferencias=("marcante",), intensidade=2).vetor["v4"] == 2


def test_clamp_0_a_10():
    a = alvo_de(emocoes=("frescor",) * 1 + ("renovacao", "liberdade", "energia"), preferencias=("fresco", "citrico"))
    assert a.vetor["v1"] == 0


def test_chip_repetido_conta_uma_vez_e_desconhecido_vai_para_aviso():
    a = alvo_de(emocoes=("amor", "Amor", "inexistente"), preferencias=("nao_sei",))
    assert a.territorios == {"floral": 2}
    assert a.nao_reconhecidos == ["emocao:inexistente", "preferencia:nao_sei"]


def test_emocoes_contraditorias_nao_bloqueiam():
    a = alvo_de(emocoes=("frescor", "conforto"))
    assert a.vetor["v1"] == 4  # 5 - 2 + 1
    assert a.territorios["fresco"] == 2 and a.territorios["gourmand_doce"] == 2


@pytest.mark.parametrize("faixa,teto,max_itens", [
    ("recem-nascido", 3, 3), ("bebe", 3, 3), ("crianca", 4.5, 4),
])
def test_idade_protege(faixa, teto, max_itens):
    a = alvo_de(faixa_idade=faixa, intensidade=10, emocoes=("magnetismo",))
    assert a.vetor["v4"] == teto and a.max_itens == max_itens


def test_idade_ajusta_eixos():
    bebe = alvo_de(faixa_idade="bebe")
    assert bebe.vetor["v2"] == 3.5 and bebe.vetor["v5"] == 2.5
    assert alvo_de(faixa_idade="crianca").vetor["v2"] == 4.5
    idoso = alvo_de(faixa_idade="idoso")
    assert idoso.vetor["v2"] == 5.5 and idoso.vetor["v5"] == 4.5
    for f in ("adolescente", "jovem", "adulto"):
        assert alvo_de(faixa_idade=f).vetor == alvo_de().vetor
    # intensidade abaixo do teto não é alterada
    assert alvo_de(faixa_idade="bebe", intensidade=1).vetor["v4"] == 1


def test_conversao_de_idade_em_faixa_vem_de_dados():
    f = lambda n: c.faixa_da_idade(n, REGRAS["criacao_idade"])  # noqa: E731
    assert [f(0), f(1), f(2), f(3), f(11), f(12), f(17), f(18), f(30), f(60), f(120)] == [
        "recem-nascido", "bebe", "bebe", "crianca", "crianca", "adolescente", "adolescente",
        "jovem", "adulto", "idoso", "idoso"]
    assert f(121) is None


# ----------------------------------------------------------------- territórios
def test_pick_um_territorio():
    assert c.pick_territorios({"floral": 6, "fresco": 2}, ORDEM, PARAMS) == ["floral"]


def test_pick_dois_territorios_quando_segundo_tem_pelo_menos_metade():
    assert c.pick_territorios({"floral": 4, "aromatico": 2}, ORDEM, PARAMS) == ["floral", "aromatico"]
    assert c.pick_territorios({"floral": 4, "aromatico": 1.9}, ORDEM, PARAMS) == ["floral"]


def test_pick_empate_desempata_pela_ordem_e_nunca_passa_de_dois():
    top = c.pick_territorios({"aromatico": 4, "floral": 4, "fresco": 4}, ORDEM, PARAMS)
    assert top == ["floral", "fresco"]


def test_pick_fallback_pelo_perfil_de_referencia():
    perfis = {"floral": {"v1": 5, "v2": 5, "v3": 5}, "fresco": {"v1": 2, "v2": 2, "v3": 3}}
    alvo = {"v1": 2, "v2": 2, "v3": 3, "v4": 5, "v5": 4}
    assert c.pick_territorios({}, ORDEM, PARAMS, perfis, alvo) == ["fresco"]


def test_pick_fallback_sem_perfil_usa_a_ordem_fixa():
    assert c.pick_territorios({}, ORDEM, PARAMS, {}, {"v1": 5, "v2": 5, "v3": 5}) == ["floral"]
    assert c.pick_territorios({}, {}, PARAMS) == []


# ------------------------------------------------------------------ pontuação
def test_essencia_no_territorio_dominante_pontua_mais_a_igual_proximidade():
    a = ess(1, "A", "Floral", (5, 5, 5, 5))
    b = ess(2, "B", "Amadeirado", (5, 5, 5, 5))
    alvo = {"v1": 5, "v2": 5, "v3": 5, "v4": 5, "v5": 4}
    r = c.pontuar_essencias([b, a], {1: "floral", 2: "amadeirado"}, {}, alvo,
                            {"floral": 4}, ["floral"], PARAMS)
    assert [p.essencia.id for p in r] == [1, 2]
    assert r[0].score == 3 * 2 + 10 and r[1].score == 10


def test_bonus_fora_do_alvo_usa_pontos_do_territorio():
    e = ess(1, "A", "Fresco", (5, 5, 5, 5))
    alvo = {"v1": 5, "v2": 5, "v3": 5, "v4": 5, "v5": 4}
    [p] = c.pontuar_essencias([e], {1: "fresco"}, {}, alvo, {"fresco": 2, "floral": 6}, ["floral"], PARAMS)
    assert p.score == pytest.approx(2 * 0.4 * 2 + 10)


def test_essencia_sem_dado_recebe_proximidade_neutra_e_nao_inventa():
    e = EssenciaMotor(1, "X", None, None, {"v1": None, "v2": None, "v3": 5, "v4": None})
    alvo = {"v1": 0, "v2": 0, "v3": 0, "v4": 0, "v5": 0}
    [p] = c.pontuar_essencias([e], {}, {}, alvo, {}, [], PARAMS)
    assert p.proximidade == PARAMS["proximidade_neutra"] and p.nivel_proximidade == "sem_dado"
    assert p.baixa_confianca


def test_desempate_do_ranking_e_pelo_id():
    iguais = [ess(i, f"E{i}", "Floral") for i in (7, 3, 5)]
    alvo = {"v1": 5, "v2": 5, "v3": 5, "v4": 5, "v5": 4}
    r = c.pontuar_essencias(iguais, {}, {}, alvo, {}, [], PARAMS)
    assert [p.essencia.id for p in r] == [3, 5, 7]


# ---------------------------------------------------------------- compatibilidade
def test_coerencia_par_muito_igual_e_muito_oposto_valem_menos_que_moderado():
    base = ess(1, "A", v=(5, 5, 5, 5))
    igual = ess(2, "B", v=(5, 5, 5, 5))
    moderado = ess(3, "C", v=(8.5, 8.5, 8.5, 5))     # distância 3,5 = ideal
    oposto = ess(4, "D", v=(10, 10, 10, 5))
    args = ([], {}, PARAMS)
    s = lambda x: c.compatibilidade_par(base, x, *args)  # noqa: E731
    assert s(moderado) > s(igual) and s(moderado) > s(oposto)


def test_risco_de_atencao_reduz_o_score():
    a = ess(1, "A", "Aromático", chave_fam="aromatico")
    b = ess(2, "B", "Floral Branco", chave_fam="floral_branco")
    rel = [RelacaoFamilias("aromatico", "floral_branco", "atencao", 0.6)]
    sem = c.compatibilidade_par(a, b, [], {}, PARAMS)
    com = c.compatibilidade_par(a, b, rel, {}, PARAMS)
    assert sem - com == pytest.approx(PARAMS["peso_risco"] * PARAMS["risco_atencao"])


def test_complementaridade_de_papeis_aumenta_o_score():
    saida = {"saida": 1.0, "coracao": 0, "fundo": 0}
    fundo = {"saida": 0, "coracao": 0, "fundo": 1.0}
    a, b = ess(1, "A", papel=saida), ess(2, "B", papel=fundo)
    c2 = ess(3, "C", papel=saida)
    assert c.compatibilidade_par(a, b, [], {}, PARAMS) > c.compatibilidade_par(a, c2, [], {}, PARAMS)


def test_grupo_marca_essencia_isolada():
    grupo = [ess(1, "A", v=(10, 10, 10, 5)), ess(2, "B", v=(10, 10, 10, 5)),
             ess(3, "C", v=(10, 10, 10, 5)), ess(4, "Isolada", v=(0, 0, 0, 5))]
    params = {**PARAMS, "margem_isolada": 0.5}  # a escala do score é curta; margem menor no teste
    assert c.compatibilidade_de_grupo(grupo, [], {}, params).isoladas == ["Isolada"]
    assert c.compatibilidade_de_grupo(grupo[:1], [], {}, PARAMS).isoladas == []


# ----------------------------------------------------------------- montagem
def ranking_de(essencias, alvo, top=("floral",)):
    return c.pontuar_essencias(essencias, {e.id: "floral" for e in essencias}, {}, alvo,
                               {"floral": 4}, list(top), PARAMS)


ALVO = {"v1": 4, "v2": 4, "v3": 5, "v4": 5, "v5": 4}


def montar(ranking, max_itens=4):
    return c.montar_acorde(ranking, ALVO, max_itens, TERRITORIOS, [], {}, PARAMS)


def test_montagem_nunca_passa_do_maximo():
    rep = [ess(i, f"E{i}", "Floral", (3 + i % 4, 3 + i % 3, 4 + i % 3, 5)) for i in range(1, 12)]
    for maximo in (1, 2, 3, 4):
        assert len(montar(ranking_de(rep, ALVO), maximo).escolhidas) <= maximo


def test_montagem_so_usa_o_repertorio_recebido():
    rep = [ess(i, f"E{i}", "Floral") for i in (10, 20, 30)]
    ids = {p.essencia.id for p in montar(ranking_de(rep, ALVO)).escolhidas}
    assert ids <= {10, 20, 30}


def test_montagem_para_quando_adicionar_nao_melhora():
    boas = [ess(1, "A", "Floral", (4, 4, 5, 5)), ess(2, "B", "Floral", (4, 4, 5, 5))]
    longe = [ess(3, "C", "Floral", (10, 10, 0, 0)), ess(4, "D", "Floral", (0, 10, 10, 10))]
    r = montar(ranking_de(boas + longe, ALVO))
    assert {p.essencia.id for p in r.escolhidas} == {1, 2}


def test_montagem_vazia_e_fraca():
    r = montar([])
    assert r.escolhidas == [] and r.fraco


def test_fraco_quando_a_melhor_nao_chega_a_8():
    longe = [ess(1, "A", "Amadeirado", (10, 10, 0, 0))]
    r = c.montar_acorde(c.pontuar_essencias(longe, {1: "amadeirado"}, {}, ALVO, {}, ["floral"], PARAMS),
                        ALVO, 4, TERRITORIOS, [], {}, PARAMS)
    assert r.fraco


def test_montagem_deterministica_inclusive_com_empates():
    rep = [ess(i, f"E{i}", "Floral", (4, 4, 5, 5)) for i in range(1, 9)]  # todas idênticas
    esperado = [p.essencia.id for p in montar(ranking_de(rep, ALVO)).escolhidas]
    for semente in range(5):
        embaralhada = rep[:]
        random.Random(semente).shuffle(embaralhada)
        assert [p.essencia.id for p in montar(ranking_de(embaralhada, ALVO)).escolhidas] == esperado
    assert esperado == sorted(esperado)


# -------------------------------------------------------------------- pesos
@pytest.mark.parametrize("n,esperado", [(1, [2]), (2, [2, 2]), (3, [3, 2, 1]), (4, [3, 2, 2, 1])])
def test_pesos_seguem_o_ranking(n, esperado):
    escolhidas = [pont(ess(i, f"E{i}"), score=20 - i) for i in range(1, n + 1)]
    itens = c.atribuir_pesos(list(reversed(escolhidas)), PADRAO)
    assert [i.peso for i in itens] == esperado
    assert [i.pontuada.essencia.id for i in itens] == list(range(1, n + 1))  # melhor score primeiro
    assert itens[0].rotulo_peso in ("Bastante", "Médio")


def test_piramide_fecha_em_100_e_v4_cresce_com_o_numero_de_itens():
    papeis = [{"saida": .5, "coracao": .3, "fundo": .2}, {"saida": .1, "coracao": .6, "fundo": .3},
              {"saida": 0, "coracao": .3, "fundo": .7}]
    itens = [(pont(ess(i + 1, f"E{i}", "Floral", (5, 5, 5, 5), papeis[i]), "floral"), 3 - i) for i in range(3)]
    r = c.vetor_do_acorde(itens, TERRITORIOS, PARAMS)
    assert sum(r.papel.values()) == 100
    um = c.vetor_do_acorde(itens[:1], TERRITORIOS, PARAMS)
    assert r.vetor["v4"] == pytest.approx(5 + 2 * PARAMS["bonus_presenca_por_item"])
    assert um.vetor["v4"] == 5


def test_v5_do_acorde_cresce_com_territorios_distintos():
    a = pont(ess(1, "A", v=(2, 2, 2, 5)), "floral")
    b = pont(ess(2, "B", v=(8, 8, 8, 5)), "amadeirado")
    mesmo = c.vetor_do_acorde([(a, 2), (pont(ess(2, "B", v=(8, 8, 8, 5)), "floral"), 2)], TERRITORIOS, PARAMS)
    dif = c.vetor_do_acorde([(a, 2), (b, 2)], TERRITORIOS, PARAMS)
    assert dif.vetor["v5"] == mesmo.vetor["v5"] + PARAMS["v5_por_territorio"]


def test_familia_resultante_composta_quando_segundo_passa_de_metade():
    a, b = pont(ess(1, "A"), "floral"), pont(ess(2, "B"), "frutado")
    assert c.vetor_do_acorde([(a, 3), (b, 2)], TERRITORIOS, PARAMS).familia_resultante == "Floral / Frutado"
    assert c.vetor_do_acorde([(a, 3), (b, 1)], TERRITORIOS, PARAMS).familia_resultante == "Floral"


# ------------------------------------------------------------------- textos
def test_direcao_em_texto_segue_o_template():
    vocab = REGRAS["criacao_vocabulario"]["identidade"]
    v = {"v1": 3, "v2": 5, "v3": 5, "v4": 3}
    assert c.direcao_em_texto(v, ["floral", "frutado"], TERRITORIOS, vocab) == \
        "Floral frutada, delicadamente doce, fresca e com presença suave."
    # "fresca" já dito pelo território não se repete
    assert c.direcao_em_texto(v, ["fresco"], TERRITORIOS, vocab) == \
        "Fresca, delicadamente doce e com presença suave."


def test_genero_so_troca_a_frase_nunca_a_familia():
    vocab = REGRAS["criacao_vocabulario"]["identidade"]
    p = pont(ess(1, "Peônia", "Floral"), "floral")
    fem = c.explicar_essencia(p, None, TERRITORIOS, "feminino", vocab)
    masc = c.explicar_essencia(p, None, TERRITORIOS, "masculino", vocab)
    assert fem == "Traz delicadeza e feminilidade." and masc == "Traz delicadeza floral."


def test_frase_do_papel_so_quando_passa_de_50_por_cento():
    vocab = REGRAS["criacao_vocabulario"]["identidade"]
    p = pont(ess(1, "X", "Floral"), "floral")
    assert c.explicar_essencia(p, {"saida": .9, "coracao": .1, "fundo": 0}, TERRITORIOS, "unissex", vocab) \
        .endswith("Abre a criação com leveza.")
    assert c.explicar_essencia(p, {"saida": .4, "coracao": .4, "fundo": .2}, TERRITORIOS, "unissex", vocab) \
        == "Traz delicadeza floral."


def test_nada_de_random_no_motor():
    import inspect
    fonte = inspect.getsource(c)
    assert "import random" not in fonte and "random." not in fonte
