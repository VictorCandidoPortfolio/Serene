"""Motor olfativo — testes das funções PURAS (sem banco, sem HTTP).

As regras usadas aqui são as mesmas do seed, para que o teste documente o
comportamento com a calibração ilustrativa atual.
"""

import pytest

from app.engine.axes import EssenciaMotor, RegraInvalidaError, peso_numerico
from app.engine.compatibility import RelacaoFamilias, compatibilidade_grupo
from app.engine.gaps import FamiliaRef, lacunas_repertorio
from app.engine.movement import sugerir_ajuste
from app.engine.reconhecimento import NotaRef, buscar_correspondencias
from app.engine.recommendation import calcular_vetor_alvo, pontuar_essencias
from app.engine.vectors import calcular_acorde
from app.seed.data import REGRAS

PARAMS = {chave: valor for tipo, chave, valor, _ in REGRAS if tipo == "peso_score"}
MOVIMENTOS = {chave: valor for tipo, chave, valor, _ in REGRAS if tipo == "vetor_movimento"}
REGRAS_PERFIL: dict[str, dict] = {}
for _tipo, _chave, _valor, _ in REGRAS:
    REGRAS_PERFIL.setdefault(_tipo, {})[_chave] = _valor


def ess(id_, nome, fam, v, papel=None):
    """Atalho para montar uma essência do motor. `v` = (v1..v5) com None."""
    return EssenciaMotor(
        id=id_, nome=nome, familia=fam.title() if fam else None, familia_chave=fam,
        vetor=dict(zip(("v1", "v2", "v3", "v4", "v5"), v)), papel=papel,
    )


BERGAMOTA = ess(1, "Bergamota", "citrico", (2, 1.5, 3, 6, None), {"saida": 0.9, "coracao": 0.1, "fundo": 0})
JASMIM = ess(2, "Jasmim", "floral", (6, 5, 6, 7, None), {"saida": 0.1, "coracao": 0.8, "fundo": 0.1})
CEDRO = ess(3, "Cedro", "amadeirado", (5, 8, 2, 5, None), {"saida": 0, "coracao": 0.2, "fundo": 0.8})
SEM_DADOS = ess(4, "Mistério", None, (None,) * 5)

RELACOES = [
    RelacaoFamilias("citrico", "floral", "classico", 1.0, "Clássico."),
    RelacaoFamilias("floral", "amadeirado", "classico", 0.8),
    RelacaoFamilias("aromatico", "floral_branco", "atencao", 0.6, "Cuidado."),
]
FAMILIAS = [
    FamiliaRef("citrico", "Cítrico", None, {"v1": 2.0, "v2": 1.5, "v3": 3.0, "v4": 6.0}),
    FamiliaRef("aromatico", "Aromático", None, {"v1": 3.0, "v2": 3.0}),
    FamiliaRef("floral", "Floral", None, None),
    FamiliaRef("floral_branco", "Floral Branco", "floral", {"v1": 6.0}),
    FamiliaRef("amadeirado", "Amadeirado", None, {"v1": 5.0, "v2": 8.0}),
    FamiliaRef("ambarado", "Ambarado", None, {"v1": 8.5, "v2": 9.0, "v3": 7.0}),
]


# ------------------------------------------------------------------ vetores
def test_media_ponderada_por_peso_relativo():
    r = calcular_acorde([(BERGAMOTA, 1), (JASMIM, 3)])
    assert r.vetor["v1"] == pytest.approx((2 * 1 + 6 * 3) / 4)
    assert r.familia_resultante == "Floral"
    assert r.papel["coracao"] > r.papel["saida"]


def test_eixo_sem_dado_fica_none_e_nao_e_inventado():
    r = calcular_acorde([(BERGAMOTA, 1), (SEM_DADOS, 3)])
    assert r.vetor["v5"] is None and "v5" in r.eixos_sem_dado
    # A essência sem dado não puxa o v1 para 0 nem para 5:
    assert r.vetor["v1"] == 2
    assert r.cobertura["v1"] == 0.25
    assert r.avisos


def test_peso_numerico():
    assert peso_numerico("bastante") == 3 and peso_numerico(2) == 2
    for invalido in ("muito", 0, 4, True, 50.0):
        with pytest.raises(ValueError):
            peso_numerico(invalido)


# --------------------------------------------------------- compatibilidade
def test_compatibilidade_usa_relacoes_e_pesos_da_base():
    r = compatibilidade_grupo([BERGAMOTA, JASMIM], RELACOES, PARAMS["compatibilidade"])
    assert r.score == 100  # base 0.5 + clássico 0.5 × peso 1.0
    assert r.pares[0].tipo_relacao == "classico"
    assert not r.alertas


def test_compatibilidade_atencao_gera_alerta_e_herda_da_familia_mae():
    lavanda = ess(5, "Lavanda", "aromatico", (3, 3, 3, 5, None))
    tuberosa = ess(6, "Tuberosa", "floral_branco", (6, 6, 6, 8, None))
    r = compatibilidade_grupo([lavanda, tuberosa], RELACOES, PARAMS["compatibilidade"])
    assert r.pares[0].tipo_relacao == "atencao"
    assert any("Atenção" in a for a in r.alertas)
    # floral_branco × citrico não tem relação própria → usa floral × citrico
    r2 = compatibilidade_grupo(
        [tuberosa, BERGAMOTA], RELACOES, PARAMS["compatibilidade"], {"floral_branco": "floral"}
    )
    assert r2.pares[0].tipo_relacao == "classico"


def test_compatibilidade_sem_familia_nao_e_chutada():
    r = compatibilidade_grupo([BERGAMOTA, SEM_DADOS], RELACOES, PARAMS["compatibilidade"])
    assert r.score is None
    assert "não avaliada" in r.alertas[0]


def test_compatibilidade_sem_regra_falha_alto():
    with pytest.raises(RegraInvalidaError):
        compatibilidade_grupo([BERGAMOTA, JASMIM], RELACOES, {"base": 0.5})


# ---------------------------------------------------------------- movimento
def test_movimento_alcancavel_so_com_repertorio():
    repertorio = [BERGAMOTA, JASMIM, CEDRO]
    r = sugerir_ajuste(
        [(JASMIM, 2), (CEDRO, 2)], repertorio, MOVIMENTOS["mais_fresco"], PARAMS["movimento"], FAMILIAS
    )
    assert r.alcancavel and r.sugestoes
    ids_repertorio = {e.id for e in repertorio}
    for s in r.sugestoes:
        assert s.essencia_id in ids_repertorio
        assert {i for i, _ in s.itens_resultantes} <= ids_repertorio
        assert s.vetor_resultante["v1"] < r.vetor_atual["v1"]
    # A melhor opção envolve a bergamota (a única essência fresca).
    assert r.sugestoes[0].nome == "Bergamota"


def test_movimento_inalcancavel_nomeia_lacuna_sem_inventar_essencia():
    repertorio = [JASMIM, CEDRO]  # nada fresco
    r = sugerir_ajuste(
        [(JASMIM, 1), (CEDRO, 1)], repertorio, MOVIMENTOS["mais_fresco"], PARAMS["movimento"],
        FAMILIAS, descricao_movimento="mais fresco",
    )
    assert not r.alcancavel and not r.sugestoes
    assert r.lacuna.tipo == "movimento"
    assert "Cítrico" in r.lacuna.detalhe["familias"]
    # Nomeia a família, nunca uma nota ("Bergamota") que ela não tem:
    assert "Bergamota" not in r.lacuna.mensagem


def test_movimento_sem_dados_nos_eixos():
    r = sugerir_ajuste(
        [(SEM_DADOS, 1), (ess(9, "X", None, (None,) * 5), 1)], [], MOVIMENTOS["mais_fresco"],
        PARAMS["movimento"],
    )
    assert not r.alcancavel and r.lacuna.tipo == "dados_incompletos"


# ------------------------------------------------------------------ lacunas
def test_lacunas_repertorio_vazio():
    assert [lac.tipo for lac in lacunas_repertorio([], FAMILIAS, PARAMS["lacunas"])] == ["repertorio_vazio"]


def test_lacunas_familias_camadas_e_amplitude():
    lacunas = lacunas_repertorio([JASMIM, CEDRO], FAMILIAS, PARAMS["lacunas"])
    por_tipo = {lac.tipo: lac for lac in lacunas}
    ausentes = por_tipo["familia_ausente"].detalhe["familias"]
    assert "Cítrico" in ausentes and "Floral" not in ausentes
    assert "Floral Branco" not in ausentes  # subfamílias não são cobradas
    assert por_tipo["estrutura"].detalhe["camada"] == "saida"
    assert any(lac.tipo == "amplitude" and lac.detalhe["eixo"] == "v1" for lac in lacunas)


# ------------------------------------------------------------ recomendação
def test_vetor_alvo_a_partir_de_regras():
    r = calcular_vetor_alvo(
        {"emocoes": ["Amor"], "territorios": ["Acolhimento"], "publico": "Kids", "intensidade": 9},
        REGRAS_PERFIL, PARAMS["recomendacao"],
    )
    assert r.vetor["v3"] is not None and r.vetor["v1"] > 5
    assert r.vetor["v4"] <= 4.5  # limite do público Kids vence a intensidade pedida
    assert r.territorios == ["acolhimento"] and r.publico == "kids"
    assert "fofinho" in r.vocabulario


def test_vetor_alvo_nao_inventa_o_que_nao_tem_regra():
    r = calcular_vetor_alvo(
        {"emocoes": ["Nostalgia"], "territorios": ["Inexistente"]}, REGRAS_PERFIL, PARAMS["recomendacao"]
    )
    assert set(r.nao_reconhecidos) == {"emocao:Nostalgia", "territorio:Inexistente"}
    assert all(v is None for v in r.vetor.values())


def test_genero_nao_trava_familia():
    base = {"emocoes": ["alegria"]}
    com_genero = calcular_vetor_alvo({**base, "genero": "masculino"}, REGRAS_PERFIL, PARAMS["recomendacao"])
    sem_genero = calcular_vetor_alvo(base, REGRAS_PERFIL, PARAMS["recomendacao"])
    # Sem regra de preferência para o gênero, ele não altera nada.
    assert com_genero.vetor == sem_genero.vetor
    pontuadas, _ = pontuar_essencias(com_genero.vetor, [JASMIM, BERGAMOTA], PARAMS["recomendacao"])
    assert {p.essencia_id for p in pontuadas} == {1, 2}  # nenhuma família excluída


def test_pontuacao_ordena_so_o_repertorio():
    alvo = {"v1": 2.0, "v2": 2.0, "v3": 3.0, "v4": 6.0, "v5": None}
    pontuadas, nao_avaliadas = pontuar_essencias(alvo, [JASMIM, BERGAMOTA, SEM_DADOS], PARAMS["recomendacao"])
    assert [p.nome for p in pontuadas] == ["Bergamota", "Jasmim"]
    assert nao_avaliadas == ["Mistério"]


# ---------------------------------------------------------- reconhecimento
def test_reconhecimento_por_nome_e_sinonimo():
    notas = [NotaRef(1, "Bergamota", ("Bergamot",)), NotaRef(2, "Rosa", ()), NotaRef(3, "Cedro", ())]
    assert buscar_correspondencias("  BERGAMOT ", notas)[0].tipo == "exata"
    parcial = buscar_correspondencias("Óleo de Bergamota Calabresa", notas)
    assert parcial[0].nota_id == 1 and parcial[0].tipo == "parcial"
    assert buscar_correspondencias("Rosalina", notas) == []  # palavra inteira
    assert buscar_correspondencias("Cedrol", notas) == []
