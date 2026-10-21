"""Formulação: motor (Decimal, sem banco) e API (fluxo, posse e isolamento)."""

from decimal import Decimal

import pytest

from app.engine.axes import RegraInvalidaError
from app.engine.formulacao import ItemFormulacao, calcular_formulacao, validar_regra
from app.seed.data_criacao import REGRAS_FORMULACAO
from tests.test_sugestao_api import LUNA, cadastrar
from tests.util import essencia_antiga

REGRAS = {chave: valor for _, chave, valor, _ in REGRAS_FORMULACAO}
BODY = REGRAS["formulacao_body_splash"]
PERFUME = REGRAS["formulacao_perfume"]
D = Decimal


def itens(*pesos):
    return [ItemFormulacao(i + 1, f"E{i + 1}", p) for i, p in enumerate(pesos)]


def ess(r):
    return [i for i in r.ingredientes if i.tipo == "essencia"]


def base(r):
    return [i for i in r.ingredientes if i.tipo == "base"]


# ------------------------------------------------- as seis concentrações (100 ml)
@pytest.mark.parametrize("regra,conc", [
    (BODY, 7), (BODY, 10), (BODY, 15), (PERFUME, 20), (PERFUME, 25), (PERFUME, 30),
])
def test_concentrado_de_100ml_e_igual_a_concentracao(regra, conc):
    """concentrado = volume × concentração ÷ 100: para 100 ml, 7→7 ml ... 30→30 ml."""
    r = calcular_formulacao(regra, itens(3, 2, 1), 100, conc)
    assert r.valido and r.erros == []
    assert r.concentrado_ml == D(conc)
    assert sum(i.volume_ml for i in ess(r)) == D(conc)
    assert sum(i.volume_ml for i in base(r)) == D(100 - conc)
    assert sum(i.volume_ml for i in r.ingredientes) == D(100)
    assert sum(i.percentual_concentrado for i in ess(r)) == D(100)   # soma exata de 100 %


@pytest.mark.parametrize("volume", [30, 50, 77.7, 100, 250, 1000])
@pytest.mark.parametrize("regra,conc", [(BODY, 7), (BODY, 15), (PERFUME, 20), (PERFUME, 30)])
def test_mudanca_de_volume_mantem_as_contas_fechadas(regra, conc, volume):
    r = calcular_formulacao(regra, itens(3, 2, 2, 1), volume, conc)
    assert r.valido
    assert sum(i.volume_ml for i in r.ingredientes) == D(str(volume)).quantize(D("0.01"))
    assert sum(i.percentual_concentrado for i in ess(r)) == D(100)
    esperado = (D(str(volume)) * D(conc) / 100).quantize(D("0.01"))
    assert sum(i.volume_ml for i in ess(r)) == esperado == r.concentrado_ml


def test_percentuais_individuais_pelos_pesos_3_2_1():
    r = calcular_formulacao(BODY, itens(3, 2, 1), 100, 10)
    por = {i.nome: i for i in ess(r)}
    assert por["E1"].percentual_concentrado == D("50.00") and por["E1"].volume_ml == D("5.00")
    assert por["E2"].percentual_concentrado == D("33.33") and por["E2"].volume_ml == D("3.33")
    assert por["E3"].percentual_concentrado == D("16.67") and por["E3"].volume_ml == D("1.67")
    # participação no produto final = % do concentrado × concentração
    assert por["E1"].percentual_produto == D("5.00")
    assert r.criterio == "pesos_relativos"


def test_base_segue_a_composicao_definida_e_nao_e_alcool_puro():
    r = calcular_formulacao(BODY, itens(2, 2), 100, 10)
    comp = {i.nome: i.volume_ml for i in base(r)}
    assert set(comp) == {"Álcool de cereais", "Água desmineralizada", "Glicerina vegetal", "Solubilizante"}
    assert comp["Álcool de cereais"] == D("49.50") and comp["Água desmineralizada"] == D("36.00")
    assert comp["Glicerina vegetal"] == D("1.80") and comp["Solubilizante"] == D("2.70")
    assert sum(comp.values()) == D("90.00")
    assert len(base(calcular_formulacao(PERFUME, itens(2, 2), 100, 20))) == 2


@pytest.mark.parametrize("regra,conc", [(BODY, 20), (BODY, 5), (BODY, 7.5), (PERFUME, 15), (PERFUME, 35), (PERFUME, 0)])
def test_concentracao_que_nao_existe_para_o_produto_e_recusada(regra, conc):
    r = calcular_formulacao(regra, itens(2, 2), 100, conc)
    assert not r.valido and r.ingredientes == []
    assert "não existe para" in r.erros[0] and "Escolha:" in r.erros[0]


def test_concentracoes_mostradas_sao_so_as_do_produto():
    assert "7 %, 10 %, 15 %" in calcular_formulacao(BODY, itens(2, 2), 100, 20).erros[0]
    assert "20 %, 25 %, 30 %" in calcular_formulacao(PERFUME, itens(2, 2), 100, 7).erros[0]


@pytest.mark.parametrize("vol", ["9.99", "5000.01", "0", "-5"])
def test_volume_fora_da_faixa(vol):
    r = calcular_formulacao(BODY, itens(2, 2), vol, 10)
    assert not r.valido and "volume" in r.erros[0]


def test_massa_so_com_densidade_informada():
    comdens = [ItemFormulacao(1, "A", 3, D("0.9")), ItemFormulacao(2, "B", 1)]
    r = calcular_formulacao(BODY, comdens, 100, 10)
    por = {i.nome: i for i in r.ingredientes}
    assert por["A"].massa_g == D("6.75")      # 7,50 ml × 0,9
    assert por["B"].massa_g is None            # sem densidade: não se inventa
    assert r.massa_total_g is None             # total só com TODAS as densidades


def test_massa_total_quando_todas_as_densidades_sao_conhecidas():
    regra = {**BODY, "base": {"componentes": [{"chave": "x", "nome": "Base", "percentual": 100, "densidade_g_ml": 0.9}]}}
    r = calcular_formulacao(regra, [ItemFormulacao(1, "A", 2, D("0.9"))], 100, 10)
    assert r.massa_total_g == D("90.00")       # (10 + 90) ml × 0,9


def test_quantidade_abaixo_da_precisao_gera_um_aviso():
    r = calcular_formulacao(BODY, itens(3, 1, 1, 1, 1, 1), 10, 7)   # 0,7 ml / 8 = 0,09; 0,7/8 ≈ 0,0875
    assert r.valido
    r2 = calcular_formulacao(BODY, [ItemFormulacao(i, f"E{i}", 1) for i in range(1, 21)], 10, 7)
    avisos = [a for a in r2.avisos if "Abaixo da precisão" in a]
    assert len(avisos) == 1 and "volume final para pelo menos" in avisos[0]


# ------------------------------------------------- proporções: critérios explícitos
def test_proporcoes_manuais_somam_100_e_substituem_os_pesos():
    r = calcular_formulacao(BODY, itens(1, 1), 100, 10, {1: 70, 2: 30})
    assert r.criterio == "manual" and r.valido
    por = {i.nome: i for i in ess(r)}
    assert por["E1"].volume_ml == D("7.00") and por["E2"].volume_ml == D("3.00")


@pytest.mark.parametrize("manuais", [{1: 70, 2: 20}, {1: 70}, {1: 100, 2: 0}, {1: 60, 2: 30, 3: 10}])
def test_proporcoes_manuais_invalidas(manuais):
    r = calcular_formulacao(BODY, itens(1, 1), 100, 10, manuais)
    assert not r.valido and r.ingredientes == []


def lim(i, nome, peso, limite, fonte="Ficha do fornecedor"):
    return ItemFormulacao(i, nome, peso, limite_pct_produto=D(str(limite)), limite_fonte=fonte)


def test_limite_documentado_fixa_a_essencia_e_redistribui_o_excedente():
    # A (peso 3) seria 50 % do concentrado = 5 % do produto; limite 3 % do produto = 30 % do concentrado.
    r = calcular_formulacao(BODY, [lim(1, "A", 3, 3), ItemFormulacao(2, "B", 2), ItemFormulacao(3, "C", 1)], 100, 10)
    por = {i.nome: i for i in ess(r)}
    assert por["A"].percentual_concentrado == D("30.00")
    assert por["B"].percentual_concentrado == D("46.67") and por["C"].percentual_concentrado == D("23.33")
    assert sum(i.percentual_concentrado for i in ess(r)) == D("100")
    assert any("A foi limitada" in a and "Ficha do fornecedor" in a for a in r.avisos)
    assert por["A"].percentual_produto <= D("3.00")


def test_limites_que_impedem_fechar_o_concentrado_recusam_a_formulacao():
    r = calcular_formulacao(BODY, [lim(1, "A", 2, 2), lim(2, "B", 2, 2)], 100, 15)   # só cabem 4 % de 15 %
    assert not r.valido and "limites de uso documentados" in r.erros[0]


def test_manual_acima_do_limite_documentado_e_erro_e_nao_e_corrigido_em_silencio():
    r = calcular_formulacao(BODY, [lim(1, "A", 1, 3), ItemFormulacao(2, "B", 1)], 100, 10, {1: 50, 2: 50})
    assert not r.valido and "acima do limite documentado de 3" in r.erros[0]


def test_restricao_documentada_para_a_categoria_bloqueia():
    bloqueada = ItemFormulacao(1, "A", 2, bloqueada_na_categoria=True)
    r = calcular_formulacao(BODY, [bloqueada, ItemFormulacao(2, "B", 2)], 100, 10)
    assert not r.valido and "restrição documentada para Body splash" in r.erros[0]


def test_sem_limite_documentado_aparece_um_aviso_unico_com_os_nomes():
    r = calcular_formulacao(BODY, itens(2, 2, 1), 100, 10)
    avisos = [a for a in r.avisos if "Sem limite de uso documentado" in a]
    assert len(avisos) == 1 and all(n in avisos[0] for n in ("E1", "E2", "E3"))
    com = calcular_formulacao(BODY, [lim(1, "A", 2, 9), lim(2, "B", 2, 9)], 100, 10)
    assert not [a for a in com.avisos if "Sem limite" in a]


def test_validacao_nunca_diz_que_a_formula_e_segura():
    r = calcular_formulacao(BODY, itens(2, 2), 100, 10)
    assert "NÃO validada" in r.validacao


def test_itens_invalidos():
    assert not calcular_formulacao(BODY, [], 100, 10).valido
    assert not calcular_formulacao(BODY, itens(2, 5), 100, 10).valido
    assert not calcular_formulacao(BODY, [ItemFormulacao(1, "A", 2), ItemFormulacao(1, "A", 2)], 100, 10).valido


def test_determinismo():
    a = calcular_formulacao(BODY, itens(3, 2, 2, 1), 77.7, 15)
    b = calcular_formulacao(BODY, list(reversed(itens(3, 2, 2, 1))), 77.7, 15)
    assert a == b


def test_regra_malformada_falha_alto():
    with pytest.raises(RegraInvalidaError):
        validar_regra({"nome": "X"}, "formulacao_x")
    with pytest.raises(RegraInvalidaError):
        validar_regra({**BODY, "base": {"componentes": [{"chave": "a", "nome": "A", "percentual": 90}]}}, "x")
    with pytest.raises(RegraInvalidaError):
        validar_regra({**BODY, "concentracoes": []}, "x")


# --------------------------------------------------------------------- API
@pytest.fixture()
def ambiente(client, nova_usuaria):
    a = nova_usuaria("fa@exemplo.com")
    b = nova_usuaria("fb@exemplo.com")
    return a, b, cadastrar(client, a)


def post(client, h, rota, **corpo):
    return client.post(rota, json=corpo, headers=h)


DESCRICAO = "Quero algo doce, floral e bem suave, que passe calma e amor."


def test_produtos_vem_do_banco_com_as_seis_concentracoes_e_a_base(client, ambiente):
    a, _, _ = ambiente
    r = client.get("/formulacoes/produtos", headers=a)
    por = {p["chave"]: p for p in r.json()}
    assert set(por) == {"body_splash", "perfume"}      # os produtos antigos foram desativados
    assert por["body_splash"]["concentracoes"] == [7.0, 10.0, 15.0]
    assert por["perfume"]["concentracoes"] == [20.0, 25.0, 30.0]
    assert por["body_splash"]["volume_ml"]["padrao"] == 100.0
    assert sum(c["percentual"] for c in por["perfume"]["base"]) == 100
    assert por["body_splash"]["exemplo"] is True


@pytest.mark.parametrize("produto,conc", [("body_splash", 7), ("body_splash", 10), ("body_splash", 15),
                                          ("perfume", 20), ("perfume", 25), ("perfume", 30)])
def test_fluxo_completo_para_as_seis_concentracoes(client, ambiente, produto, conc):
    a, _, ids = ambiente
    r = post(client, a, "/formulacoes/propor", produto=produto, concentracao_pct=conc, volume_ml=100,
             descricao=DESCRICAO)
    assert r.status_code == 200, r.text
    corpo = r.json()
    f = corpo["formulacao"]
    assert corpo["sugestao"]["status"] == "ok" and f["valido"] and corpo["sem_formulacao"] is None
    assert f["concentrado_ml"] == float(conc)
    essencias = [i for i in f["ingredientes"] if i["tipo"] == "essencia"]
    assert set(i["essencia_id"] for i in essencias) <= set(ids.values())     # só o repertório dela
    assert round(sum(i["volume_ml"] for i in essencias), 2) == conc
    assert round(sum(i["percentual_concentrado"] for i in essencias), 2) == 100.0
    assert round(sum(i["volume_ml"] for i in f["ingredientes"]), 2) == 100.0
    assert "NÃO validada" in f["validacao"]


def test_a_descricao_e_interpretada_e_mostrada_para_conferir(client, ambiente):
    a, _, _ = ambiente
    e = post(client, a, "/formulacoes/propor", produto="body_splash", concentracao_pct=10, volume_ml=100,
             descricao=DESCRICAO).json()["sugestao"]["entendimento"]
    assert set(e["emocoes"]) == {"paz", "amor"} and set(e["preferencias"]) == {"doce", "floral", "suave"}
    assert e["intensidade"] == 2.0 and e["negados"] == []


def test_negacao_e_palavras_desconhecidas(client, ambiente):
    a, _, _ = ambiente
    r = post(client, a, "/formulacoes/propor", produto="perfume", concentracao_pct=20, volume_ml=100,
             descricao="quero floral, sem doce, com cheiro de nuvem azul").json()
    e = r["sugestao"]["entendimento"]
    assert e["preferencias"] == ["floral"] and e["negados"] == ["doce"]
    assert r["formulacao"] is not None


def test_descricao_que_nao_diz_nada_conhecido_nao_gera_formula(client, ambiente):
    a, _, _ = ambiente
    r = post(client, a, "/formulacoes/propor", produto="perfume", concentracao_pct=20, volume_ml=100,
             descricao="xyzzy plugh qwerty").json()
    assert r["sugestao"]["status"] == "pedido_incompleto" and r["formulacao"] is None
    assert "Não identifiquei" in r["sugestao"]["mensagem"]


def test_repertorio_vazio_ou_sem_caracteristicas_nao_gera_formula(client, nova_usuaria):
    h = nova_usuaria("vz@exemplo.com")
    r = post(client, h, "/formulacoes/propor", produto="perfume", concentracao_pct=20, volume_ml=100,
             descricao=DESCRICAO).json()
    assert r["sugestao"]["status"] == "insuficiente" and r["formulacao"] is None
    essencia_antiga(client, h, {"nome": "Sem dados", "familia": "Floral", "v1": None, "v2": None, "v3": None,
                                "v4": None, "v5": None, "papel": None})
    r = post(client, h, "/formulacoes/propor", produto="perfume", concentracao_pct=20, volume_ml=100,
             descricao=DESCRICAO).json()
    assert r["sugestao"]["status"] == "dados_insuficientes" and r["formulacao"] is None


def test_proposta_com_acorde_fraco_nao_inventa_proporcoes(client, nova_usuaria):
    h = nova_usuaria("fraco@exemplo.com")
    cadastrar(client, h, {"Sândalo": LUNA["Sândalo"], "Baunilha": LUNA["Baunilha"]})
    r = post(client, h, "/formulacoes/propor", produto="body_splash", concentracao_pct=10, volume_ml=100,
             descricao="quero algo fresco, citrico e leve").json()
    assert r["sugestao"]["status"] == "ok" and r["sugestao"]["dados_suficientes"] is False
    assert r["formulacao"] is None and "fundamento" in r["sem_formulacao"]


def test_concentracao_invalida_na_proposta_e_recusada(client, ambiente):
    a, _, _ = ambiente
    r = post(client, a, "/formulacoes/propor", produto="body_splash", concentracao_pct=20, volume_ml=100,
             descricao=DESCRICAO).json()
    assert r["formulacao"]["valido"] is False and "não existe para" in r["formulacao"]["erros"][0]
    assert r["formulacao"]["ingredientes"] == []


def test_outro_volume(client, ambiente):
    a, _, _ = ambiente
    f = post(client, a, "/formulacoes/propor", produto="perfume", concentracao_pct=25, volume_ml=50,
             descricao=DESCRICAO).json()["formulacao"]
    assert f["concentrado_ml"] == 12.5 and round(sum(i["volume_ml"] for i in f["ingredientes"]), 2) == 50.0


def test_ficha_limita_e_bloqueia_pelo_repertorio_da_aluna(client, ambiente):
    a, _, ids = ambiente
    cat = "body_splash"
    r = client.put(f"/essencias/{ids['Peônia']}/ficha", headers=a, json={
        "documentacao": {"tipo": "ifra", "referencia": "Ficha IFRA da Peônia"},
        "limites_uso": {cat: {"max_pct_produto": 1.0, "fonte": "IFRA 49 cat. 4"}}})
    assert r.status_code == 200, r.text
    f = post(client, a, "/formulacoes/calcular", produto=cat, concentracao_pct=10, volume_ml=100,
             itens=[{"essencia_id": ids["Peônia"], "peso": 3}, {"essencia_id": ids["Pera"], "peso": 2}]).json()
    por = {i["nome"]: i for i in f["ingredientes"] if i["tipo"] == "essencia"}
    assert f["valido"] and por["Peônia"]["percentual_produto"] <= 1.0
    assert any("Peônia foi limitada" in x for x in f["avisos"])
    client.put(f"/essencias/{ids['Pera']}/ficha", headers=a, json={
        "restricoes": {"categorias_nao_indicadas": [cat], "observacoes": "Não indicada para pele"}})
    f = post(client, a, "/formulacoes/calcular", produto=cat, concentracao_pct=10, volume_ml=100,
             itens=[{"essencia_id": ids["Pera"], "peso": 2}, {"essencia_id": ids["Rosa"], "peso": 2}]).json()
    assert f["valido"] is False and "restrição documentada" in f["erros"][0]
    # a mesma essência pode ser usada em outra categoria
    f2 = post(client, a, "/formulacoes/calcular", produto="perfume", concentracao_pct=20, volume_ml=100,
              itens=[{"essencia_id": ids["Pera"], "peso": 2}, {"essencia_id": ids["Rosa"], "peso": 2}]).json()
    assert f2["valido"] is True


def test_ficha_exige_fonte_para_limite_e_rejeita_campos_estranhos(client, ambiente):
    a, _, ids = ambiente
    sem_fonte = client.put(f"/essencias/{ids['Rosa']}/ficha", headers=a,
                           json={"limites_uso": {"perfume": {"max_pct_produto": 2}}})
    assert sem_fonte.status_code == 422
    estranho = client.put(f"/essencias/{ids['Rosa']}/ficha", headers=a, json={"inventado": 1})
    assert estranho.status_code == 422
    vazia = client.put(f"/essencias/{ids['Rosa']}/ficha", headers=a, json={"notas": {"saida": []}})
    assert vazia.status_code == 200 and vazia.json()["ficha"] is None   # nada informado = nada gravado


def test_ficha_completa_e_devolvida_como_documentada(client, ambiente):
    a, _, ids = ambiente
    ficha = {"identificacao": {"nome_comercial": "Rosa Damascena", "codigo": "RS-01", "densidade_g_ml": 0.95},
             "notas": {"saida": ["pétalas"], "coracao": ["rosa"], "fundo": ["âmbar"]},
             "documentacao": {"tipo": "ficha_tecnica", "referencia": "Fornecedor X, rev. 2"}}
    r = client.put(f"/essencias/{ids['Rosa']}/ficha", headers=a, json=ficha)
    assert r.status_code == 200 and r.json()["ficha"] == ficha
    f = post(client, a, "/formulacoes/calcular", produto="perfume", concentracao_pct=20, volume_ml=100,
             itens=[{"essencia_id": ids["Rosa"], "peso": 2}, {"essencia_id": ids["Pera"], "peso": 2}]).json()
    rosa = next(i for i in f["ingredientes"] if i["nome"] == "Rosa")
    assert rosa["massa_g"] == 9.5       # 10 ml × 0,95 g/ml da ficha
    assert next(i for i in f["ingredientes"] if i["nome"] == "Pera")["massa_g"] is None


def test_versao_com_formulacao_edicao_e_novas_versoes(client, ambiente):
    a, _, ids = ambiente
    c = client.post("/criacoes", headers=a, json={
        "nome": "Luna", "sugestao": {"descricao": DESCRICAO},
        "formulacao": {"produto": "body_splash", "concentracao_pct": 10, "volume_ml": 100}})
    assert c.status_code == 201, c.text
    cid = c.json()["id"]
    v1 = client.get(f"/criacoes/{cid}/acordes", headers=a).json()[0]
    assert v1["formulacao"]["pedido"]["concentracao_pct"] == 10.0
    assert v1["formulacao"]["resultado"]["valido"] is True
    itens = [{"essencia_id": i["essencia_id"], "peso": i["peso"]} for i in v1["itens"]]
    # editar a fórmula: outra concentração e proporções manuais -> nova versão
    ids_ord = [i["essencia_id"] for i in v1["itens"]]
    manual = {str(ids_ord[0]): 60, str(ids_ord[1]): 40, **{str(i): 0.0001 for i in ids_ord[2:]}}
    if len(ids_ord) == 2:
        manual = {str(ids_ord[0]): 60, str(ids_ord[1]): 40}
    else:
        resto = 40 / (len(ids_ord) - 1)
        manual = {str(ids_ord[0]): 60, **{str(i): resto for i in ids_ord[1:]}}
    r = client.post(f"/criacoes/{cid}/acordes", headers=a, json={
        "itens": itens, "motivo": "Mais concentrada",
        "formulacao": {"produto": "body_splash", "concentracao_pct": 15, "volume_ml": 100, "proporcoes_pct": manual}})
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["versao"] == 2 and v2["formulacao"]["resultado"]["criterio"] == "manual"
    assert v2["formulacao"]["resultado"]["concentrado_ml"] == 15.0
    # versão sem pedido herda o da anterior (editar só os pesos não perde a fórmula)
    trocado = [{**itens[0], "peso": 1}, *itens[1:]]
    v3 = client.post(f"/criacoes/{cid}/acordes", headers=a, json={"itens": trocado, "motivo": "Menos do 1º"}).json()
    assert v3["formulacao"]["pedido"]["concentracao_pct"] == 15.0
    assert v3["formulacao"]["pedido"]["proporcoes_pct"] is not None   # mesmas essências: divisão manual mantida
    # fórmula inválida na edição: a versão NÃO é criada
    ruim = client.post(f"/criacoes/{cid}/acordes", headers=a, json={
        "itens": itens, "formulacao": {"produto": "body_splash", "concentracao_pct": 30, "volume_ml": 100}})
    assert ruim.status_code in (400, 422) and "Fórmula inválida" in ruim.text
    assert len(client.get(f"/criacoes/{cid}/acordes", headers=a).json()) == 3
    # registrar teste da versão com fórmula
    t = client.post(f"/criacoes/{cid}/testes", headers=a, json={"acorde_id": v2["id"], "nota": 8})
    assert t.status_code == 201


def test_formulacao_na_criacao_invalida_nao_grava_nada(client, ambiente):
    a, _, _ = ambiente
    r = client.post("/criacoes", headers=a, json={
        "nome": "X", "sugestao": {"descricao": DESCRICAO},
        "formulacao": {"produto": "perfume", "concentracao_pct": 7, "volume_ml": 100}})
    assert r.status_code in (400, 422)
    assert client.get("/criacoes", headers=a).json() == [] and client.get("/perfis", headers=a).json() == []
    assert client.post("/criacoes", headers=a, json={"nome": "Y", "formulacao": {
        "produto": "perfume", "concentracao_pct": 20}}).status_code == 422


def test_calcular_a_partir_do_acorde_da_criacao(client, ambiente):
    a, _, _ = ambiente
    c = client.post("/criacoes", headers=a, json={"nome": "Luna", "sugestao": {"descricao": DESCRICAO}}).json()
    versoes = client.get(f"/criacoes/{c['id']}/acordes", headers=a).json()
    r = post(client, a, "/formulacoes/calcular", produto="perfume", volume_ml=50, concentracao_pct=30,
             criacao_id=c["id"]).json()
    assert r["valido"] and r["concentrado_ml"] == 15.0
    assert {i["essencia_id"] for i in r["ingredientes"] if i["tipo"] == "essencia"} == \
           {i["essencia_id"] for i in versoes[0]["itens"]}


def test_entradas_malformadas_sao_422(client, ambiente):
    a, _, ids = ambiente
    item = [{"essencia_id": ids["Rosa"], "peso": 2}]
    base_ = {"produto": "body_splash", "concentracao_pct": 10}
    for ruim in ({**base_, "volume_ml": -1, "itens": item}, {**base_, "volume_ml": 0, "itens": item},
                 {"produto": "body_splash", "volume_ml": 100, "itens": item},          # sem concentração
                 {**base_, "concentracao_pct": 101, "itens": item}, {**base_},
                 {**base_, "itens": item, "criacao_id": 1}, {**base_, "itens": item, "user_id": 9},
                 {**base_, "itens": [{"essencia_id": ids["Rosa"], "peso": 7}]}, {**base_, "itens": item + item}):
        assert post(client, a, "/formulacoes/calcular", **ruim).status_code == 422, ruim


def test_produto_desconhecido(client, ambiente):
    a, _, ids = ambiente
    r = post(client, a, "/formulacoes/calcular", produto="shampoo", concentracao_pct=10, volume_ml=100,
             itens=[{"essencia_id": ids["Rosa"], "peso": 2}])
    assert r.status_code in (400, 422) and "desconhecido" in r.text
    assert post(client, a, "/formulacoes/propor", produto="shampoo", concentracao_pct=10, volume_ml=100,
                descricao=DESCRICAO).status_code in (400, 422)


# ------------------------------------------------------------- isolamento
def test_isolamento_b_nao_formula_nem_propoe_com_essencias_de_a(client, ambiente):
    a, b, ids = ambiente
    r = post(client, b, "/formulacoes/calcular", produto="body_splash", concentracao_pct=10, volume_ml=100,
             itens=[{"essencia_id": ids["Rosa"], "peso": 2}])
    assert r.status_code == 404
    p = post(client, b, "/formulacoes/propor", produto="body_splash", concentracao_pct=10, volume_ml=100,
             descricao=DESCRICAO, essencias_disponiveis=list(ids.values()))
    assert p.status_code == 404
    p = post(client, b, "/formulacoes/propor", produto="body_splash", concentracao_pct=10, volume_ml=100,
             descricao=DESCRICAO).json()
    assert p["sugestao"]["status"] == "insuficiente" and p["formulacao"] is None   # B não enxerga as de A
    c = client.post("/criacoes", headers=a, json={"nome": "X", "sugestao": {"descricao": DESCRICAO}}).json()
    assert post(client, b, "/formulacoes/calcular", produto="body_splash", concentracao_pct=10, volume_ml=100,
                criacao_id=c["id"]).status_code == 404
    # B não consegue formular uma versão de A criando acorde na criação de A
    assert client.post(f"/criacoes/{c['id']}/acordes", headers=b, json={"itens": [
        {"essencia_id": ids["Rosa"], "peso": 2}, {"essencia_id": ids["Pera"], "peso": 2}],
        "formulacao": {"produto": "perfume", "concentracao_pct": 20}}).status_code == 404


def test_ficha_de_a_nao_afeta_nem_vaza_para_b(client, ambiente, nova_usuaria):
    a, b, ids = ambiente
    client.put(f"/essencias/{ids['Rosa']}/ficha", headers=a,
               json={"restricoes": {"categorias_nao_indicadas": ["perfume"]}})
    assert client.get(f"/essencias/{ids['Rosa']}", headers=b).status_code == 404
    assert client.get("/essencias", headers=b).json() == []


def test_exige_login(client):
    assert client.post("/formulacoes/calcular", json={}).status_code in (401, 403)
    assert client.post("/formulacoes/propor", json={}).status_code in (401, 403)
    assert client.get("/formulacoes/produtos").status_code in (401, 403)
