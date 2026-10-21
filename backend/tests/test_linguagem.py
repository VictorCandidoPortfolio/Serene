"""Interpretação em linguagem natural (sem IA) e compatibilidade sem "mesma família basta"."""

from app.engine.axes import EssenciaMotor
from app.engine.compatibility import RelacaoFamilias, compatibilidade_grupo
from app.engine.linguagem import interpretar
from app.seed.data_criacao import REGRAS_CRIACAO

REGRAS: dict[str, dict] = {}
for _t, _c, _v, _ in REGRAS_CRIACAO:
    REGRAS.setdefault(_t, {})[_c] = _v
EMO, PREF = REGRAS["criacao_emocao"], REGRAS["criacao_preferencia"]
VOCAB = REGRAS["criacao_vocabulario"]["linguagem"]


def ler(texto):
    return interpretar(texto, EMO, PREF, VOCAB)


def test_reconhece_palavras_cadastradas_sem_acento_e_em_qualquer_caixa():
    i = ler("Quero algo DOCE, Floral e CÍTRICO que passe CALMA e Serenidade")
    assert i.emocoes == ["paz", "serenidade"] and i.preferencias == ["doce", "floral", "citrico"]


def test_ordem_do_texto_e_sem_repeticao():
    assert ler("floral, doce, floral, flores").preferencias == ["floral", "doce"]


def test_palavra_inteira_nao_parte_de_palavra():
    assert not ler("docemente florescendo").entendeu_algo   # 'doce' e 'flor' dentro de outras palavras


def test_negacao_anula_o_termo_e_nao_vira_o_oposto():
    i = ler("quero floral, sem doce e não quero cítrico")
    assert i.preferencias == ["floral"] and i.negados == ["doce", "citrico"]
    assert not ler("nem floral").entendeu_algo


def test_frase_composta():
    assert ler("cheiro de roupa limpa").preferencias == ["limpo"]


def test_intensidade_pela_primeira_palavra_reconhecida():
    assert ler("bem suave e discreto").intensidade == 2.0
    assert ler("algo forte").intensidade == 8.0
    assert ler("sem forte").intensidade is None
    assert ler("doce").intensidade is None


def test_texto_sem_nada_conhecido_nao_entende_nada():
    for t in (None, "", "   ", "xyzzy plugh", "quero um perfume"):
        i = ler(t)
        assert not i.entendeu_algo and i.emocoes == [] and i.preferencias == []


def test_deterministico():
    t = "doce, floral, calma, amor, sem fresco"
    assert ler(t) == ler(t)


# ------------------------------------------- compatibilidade: família igual não basta
def e(i, nome, fam):
    return EssenciaMotor(i, nome, fam.title(), fam, {"v1": 5, "v2": 5, "v3": 5, "v4": 5})


PESOS = {"base": 0.5, "classico": 0.5, "complementar": 0.3, "contraste": 0.1, "atencao": -0.3, "limiar_alerta": 0.4}


def test_mesma_familia_nao_gera_compatibilidade():
    r = compatibilidade_grupo([e(1, "Rosa", "floral"), e(2, "Peônia", "floral")], [], PESOS)
    assert r.score is None and r.como_dict()["pares"] == []
    assert r.alertas == ["Essências da mesma família não têm compatibilidade calculada só por isso."]


def test_mesma_familia_fora_da_media_do_grupo():
    rel = [RelacaoFamilias("floral", "citrico", "classico", 1.0)]
    grupo = [e(1, "Rosa", "floral"), e(2, "Peônia", "floral"), e(3, "Bergamota", "citrico")]
    r = compatibilidade_grupo(grupo, rel, PESOS)
    # pares avaliados: Rosa+Bergamota e Peônia+Bergamota (clássico = 100); Rosa+Peônia não conta
    assert r.score == 100 and r.como_dict()["pares_avaliados"] == 2 and r.como_dict()["pares_total"] == 3
