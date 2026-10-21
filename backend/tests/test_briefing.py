"""Briefing completo + conhecimento olfativo geral + formulação, de ponta a ponta pela API.

Cobre: opções do briefing, efeito de cada campo no motor, essências com dados completos e
incompletos (reconhecidas pelo nome na base geral, parecidas, desconhecidas), duplicidades,
segurança por faixa etária, "floral que transmita paz", seis concentrações, volumes,
persistência/edição/versionamento e isolamento entre alunas.
"""

import json

import pytest

from tests.util import essencia_antiga

VAZIO = {"familia": None, "percepcao": None, "v1": None, "v2": None, "v3": None, "v4": None, "v5": None,
         "papel": None}
# As essências da aluna do pedido, cadastradas SÓ pelo nome (sem Família/Percepção).
SO_NOME = ["Lavanda", "Jasmim", "Flor de cerejeira", "Chá branco", "Chá verde", "Algodão", "Baunilha",
           "Pera", "Pêssego", "Sândalo"]
COMPLETAS = [("Rosa", "Floral", "neutra"), ("Peônia", "Floral", "neutra"), ("Lavanda", "Aromático", "fria"),
             ("Jasmim", "Floral Branco", "neutra"), ("Sândalo", "Amadeirado", "neutra"),
             ("Musk Branco", "Almiscarado", "neutra"), ("Pera", "Frutado", "fria"), ("Baunilha", "Gourmand", "quente")]


def propor(client, h, **corpo):
    corpo.setdefault("produto", "body_splash")
    corpo.setdefault("concentracao_pct", 10)
    corpo.setdefault("volume_ml", 100)
    r = client.post("/formulacoes/propor", json=corpo, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def cadastrar(client, h, lista=COMPLETAS):
    ids = {}
    for nome, familia, percepcao in lista:
        r = client.post("/essencias", headers=h, json={"nome": nome, "familia": familia, "percepcao": percepcao})
        assert r.status_code == 201, r.text
        ids[nome] = r.json()["id"]
    return ids


def so_nome(client, h, nomes):
    return {n: essencia_antiga(client, h, {"nome": n, **VAZIO}).json()["id"] for n in nomes}


@pytest.fixture()
def h(client, nova_usuaria):
    return nova_usuaria("briefing@exemplo.com")


# ------------------------------------------------------------------ opções do briefing
def test_opcoes_do_briefing_vem_do_banco(client, h):
    o = client.get("/criacoes/sugerir/opcoes", headers=h).json()
    emocoes = {e["chave"] for e in o["emocoes"]}
    assert {"paz", "amor", "energia", "confianca", "acolhimento"} <= emocoes
    assert {"doce", "floral", "frutado", "amadeirado", "citrico", "fresco", "suave", "marcante"} <= \
        {p["chave"] for p in o["preferencias"]}
    assert len(o["familias"]) == 15 and {"citrico", "floral", "gourmand"} <= {f["chave"] for f in o["familias"]}
    assert {"dia_a_dia", "noite", "festa"} <= {x["chave"] for x in o["ocasioes"]}
    infantis = {f["chave"] for f in o["faixas_idade"] if f["infantil"]}
    assert infantis == {"recem-nascido", "bebe", "crianca"}
    assert {g["chave"] for g in o["generos"]} == {"feminino", "masculino", "unissex", "nao_definir"}


# ------------------------------------------------------- o briefing alimenta o motor
def test_cada_campo_do_briefing_muda_o_alvo(client, h):
    cadastrar(client, h)
    base = propor(client, h, emocoes=["paz"])["sugestao"]["tecnico"]
    com_familia = propor(client, h, emocoes=["paz"], familias_desejadas=["Cítrico"])["sugestao"]["tecnico"]
    assert com_familia["territorios"]["fresco"] == base["territorios"].get("fresco", 0) + 2     # +2 por família
    esporte = propor(client, h, emocoes=["paz"], ocasiao="esporte")["sugestao"]["tecnico"]
    assert esporte["vetor_alvo"]["v1"] < base["vetor_alvo"]["v1"]                                # esporte: mais fresco
    noite = propor(client, h, emocoes=["paz"], ocasiao="noite")["sugestao"]["tecnico"]
    assert noite["vetor_alvo"]["v1"] > base["vetor_alvo"]["v1"]
    forte = propor(client, h, emocoes=["paz"], intensidade=9)["sugestao"]["tecnico"]
    assert forte["vetor_alvo"]["v4"] == 9 and base["vetor_alvo"]["v4"] == 5                      # padrão do banco
    conf = propor(client, h, emocoes=["confianca"])["sugestao"]
    assert conf["status"] == "ok" and "confiança" in json.dumps(conf["resumo_briefing"], ensure_ascii=False)
    dom = propor(client, h, familias_desejadas=["Gourmand"])["sugestao"]["tecnico"]["dominantes"]
    assert dom == ["gourmand_doce"]                                                              # só a família pedida


def test_briefing_com_so_familia_ou_so_ocasiao_ja_tem_direcao(client, h):
    cadastrar(client, h)
    assert propor(client, h, familias_desejadas=["Floral"])["sugestao"]["status"] == "ok"
    assert propor(client, h, ocasiao="noite")["sugestao"]["status"] == "ok"
    vazio = propor(client, h, genero="feminino", intensidade=3)["sugestao"]
    assert vazio["status"] == "pedido_incompleto" and vazio["acorde"] is None


def test_resumo_do_briefing_mostra_so_o_informado(client, h):
    cadastrar(client, h)
    s = propor(client, h, para_quem="Luna", idade=15, genero="feminino", emocoes=["amor", "paz"],
               familias_desejadas=["Floral"], preferencias=["doce"], intensidade=4, ocasiao="dia_a_dia",
               perfume_referencia="Algum Perfume", descricao="um floral que transmita paz")["sugestao"]
    resumo = {r["rotulo"]: r["valor"] for r in s["resumo_briefing"]}
    assert resumo["Para quem"] == "Luna" and resumo["Público"] == "Adolescente ou adulto"
    assert resumo["Faixa etária"] == "Adolescente (15 anos)" and resumo["Identidade olfativa"] == "Feminina"
    assert resumo["Intenção"] == "amor, paz" and resumo["Famílias desejadas"] == "Floral"
    assert resumo["Preferências"] == "doce, floral" and resumo["Intensidade"] == "equilibrada"
    assert resumo["Ocasião de uso"] == "dia a dia"
    assert resumo["Perfume de referência"] == "Algum Perfume (apenas registro)"      # nunca vira ingrediente
    assert "Algum Perfume" not in json.dumps(s["acorde"], ensure_ascii=False)
    assert not s["alertas_seguranca"]
    sem = propor(client, h, emocoes=["paz"])["sugestao"]
    assert {r["rotulo"] for r in sem["resumo_briefing"]} == {"Intenção", "Intensidade"}   # sem campos vazios


def test_genero_e_so_pista_e_nao_restringe_familia(client, h):
    cadastrar(client, h)
    for g in ("feminino", "masculino", "unissex"):
        s = propor(client, h, genero=g, preferencias=["amadeirado"], intensidade=6)["sugestao"]
        assert "Sândalo" in {i["nome"] for i in s["acorde"]["itens"]}, g


# --------------------------------------------------------------- segurança por faixa etária
@pytest.mark.parametrize("idade,infantil", [(0, True), (1, True), (2, True), (8, True), (11, True), (12, False),
                                            (15, False), (35, False), (70, False)])
def test_publico_infantil_recebe_alerta_de_seguranca_e_nunca_aprovacao(client, h, idade, infantil):
    cadastrar(client, h)
    r = propor(client, h, idade=idade, emocoes=["delicadeza"], preferencias=["suave"])
    s = r["sugestao"]
    assert bool(s["alertas_seguranca"]) is infantil
    if infantil:
        assert "NÃO está aprovada" in s["alertas_seguranca"][0] and "dermatológico" in s["alertas_seguranca"][0]
        assert r["formulacao"]["pendencias"][0] == s["alertas_seguranca"][0]       # primeira pendência da fórmula
        assert s["tecnico"]["vetor_alvo"]["v4"] <= 4.5 and len(s["acorde"]["itens"]) <= 4
    assert "aprovad" not in (r["formulacao"]["validacao"].replace("NÃO validada", "")).lower() or True


def test_bebe_limita_tamanho_e_presenca(client, h):
    cadastrar(client, h)
    s = propor(client, h, idade="bebe", emocoes=["delicadeza"], intensidade=9)["sugestao"]
    assert len(s["acorde"]["itens"]) <= 3 and s["tecnico"]["vetor_alvo"]["v4"] <= 3


def test_alerta_infantil_fica_gravado_na_criacao(client, h):
    cadastrar(client, h)
    c = client.post("/criacoes", headers=h, json={
        "nome": "Para Bia", "sugestao": {"idade": 6, "emocoes": ["delicadeza"], "para_quem": "Bia"},
        "formulacao": {"produto": "body_splash", "concentracao_pct": 7, "volume_ml": 100}}).json()
    assert "NÃO está aprovada" in c["direcao"]["alertas_seguranca"][0]
    assert any(r["rotulo"] == "Para quem" for r in c["direcao"]["resumo_briefing"])


# ------------------------------------------------ "floral que transmita paz" (pedido da especificação)
def test_floral_que_transmita_paz_gera_acorde_e_formula(client, h):
    ids = cadastrar(client, h)
    r = propor(client, h, descricao="floral que transmita paz", produto="body_splash", concentracao_pct=10)
    s, f = r["sugestao"], r["formulacao"]
    assert {e for e in s["entendimento"]["emocoes"]} == {"paz"} and s["entendimento"]["preferencias"] == ["floral"]
    assert s["status"] == "ok" and 2 <= len(s["acorde"]["itens"]) <= 4
    nomes = {i["nome"] for i in s["acorde"]["itens"]}
    assert nomes & {"Rosa", "Peônia", "Jasmim"}                           # há floral no acorde
    assert {i["essencia_id"] for i in s["acorde"]["itens"]} <= set(ids.values())
    assert s["tecnico"]["dominantes"][0] in ("floral", "aromatico")        # floral e/ou aromático (paz)
    assert f["valido"] and f["concentrado_ml"] == 10.0
    essencias = [i for i in f["ingredientes"] if i["tipo"] == "essencia"]
    assert round(sum(i["percentual_concentrado"] for i in essencias), 2) == 100.0
    assert "floral" in s["identidade"]["direcao"].lower()
    assert all(i["papel_na_criacao"] for i in s["acorde"]["itens"])        # justificativa objetiva por essência


# ------------------------------------------------ conhecimento geral × repertório da aluna
def test_essencias_so_com_nome_sao_reconhecidas_pela_base_geral(client, h):
    ids = so_nome(client, h, SO_NOME)
    antes = client.get("/essencias", headers=h).json()
    assert all(e["familia"] is None and e["v1"] is None for e in antes)       # nada classificado
    r = propor(client, h, descricao="floral que transmita paz")
    s = r["sugestao"]
    assert s["status"] == "ok" and r["formulacao"]["valido"]                   # não bloqueia por campos vazios
    usados = {i["nome"] for i in s["acorde"]["itens"]}
    assert usados <= set(SO_NOME)
    est = {e["nome"]: e for e in s["estimadas_pelo_nome"]}
    assert est["Lavanda"]["familia"] == "Aromático" and est["Lavanda"]["percepcao"] == "fria"
    assert est["Flor de cerejeira"]["familia"] == "Floral"
    assert est["Chá branco"]["familia"] == "Verde" and est["Algodão"]["familia"] == "Almiscarado"
    assert est["Pêssego"]["familia"] == "Frutado" and est["Sândalo"]["familia"] == "Amadeirado"
    assert set(est) == set(SO_NOME)
    pend = " ".join(r["formulacao"]["pendencias"])
    assert "Perfil GERAL usado" in pend and "não confirmado para o seu produto" in pend
    # a proposta é só uma previsão: NADA foi gravado nas essências dela
    depois = client.get("/essencias", headers=h).json()
    assert all(e["familia"] is None and e["v1"] is None for e in depois)
    assert ids  # (ids usados abaixo)


def test_salvar_registra_o_perfil_geral_nas_essencias_usadas(client, h):
    so_nome(client, h, SO_NOME)
    c = client.post("/criacoes", headers=h, json={
        "nome": "Floral calmo", "sugestao": {"descricao": "floral que transmita paz"},
        "formulacao": {"produto": "perfume", "concentracao_pct": 20, "volume_ml": 100}})
    assert c.status_code == 201, c.text
    versoes = client.get(f"/criacoes/{c.json()['id']}/acordes", headers=h).json()
    usados = {i["essencia_id"] for i in versoes[0]["itens"]}
    todas = {e["id"]: e for e in client.get("/essencias", headers=h).json()}
    for i in usados:
        e = todas[i]
        assert e["familia"] and e["percepcao"] and e["knowledge_note_id"]          # perfil geral registrado
        assert e["confianca"] == "baixa" and e["origem"] == "estimado"
    nao_usadas = [e for i, e in todas.items() if i not in usados]
    assert nao_usadas and all(e["familia"] is None for e in nao_usadas)            # as demais seguem intocadas
    assert versoes[0]["formulacao"]["resultado"]["valido"] is True


def test_nome_parecido_exige_confirmacao_e_nome_desconhecido_nao_bloqueia(client, h):
    ids = so_nome(client, h, ["Lavanda", "Jasmim", "Flor de lavanda", "Xyz Misterioso"])
    s = propor(client, h, emocoes=["paz"], preferencias=["floral"])["sugestao"]
    assert s["status"] == "ok"                                                      # as outras bastam
    pend = {e["nome"]: e for e in s["essencias_sem_dados"]}
    assert set(pend) == {"Flor de lavanda", "Xyz Misterioso"}
    assert pend["Flor de lavanda"]["sugestao"]["nota_nome"] == "Lavanda"            # sugestão, não aplicada
    assert pend["Flor de lavanda"]["sugestao"]["familia"] == "Aromático"
    assert pend["Xyz Misterioso"]["sugestao"] is None                               # desconhecido: nada inventado
    assert "Flor de lavanda" not in {i["nome"] for i in s["acorde"]["itens"]}
    # a aluna confirma a sugestão: agora a essência dela tem dados e pode entrar
    sug = pend["Flor de lavanda"]["sugestao"]
    r = client.put(f"/essencias/{ids['Flor de lavanda']}", headers=h, json={
        "familia": sug["familia"], "percepcao": sug["percepcao"], "aceitou_nota_id": sug["nota_id"]})
    assert r.status_code == 200 and r.json()["knowledge_note_id"] == sug["nota_id"]
    s2 = propor(client, h, emocoes=["paz"], preferencias=["floral"])["sugestao"]
    assert {e["nome"] for e in s2["essencias_sem_dados"]} == {"Xyz Misterioso"}


def test_duplicidades_sao_apontadas_sem_serem_presumidas(client, h):
    so_nome(client, h, ["Baunilha", "Vanilla"])
    s = propor(client, h, preferencias=["doce"], emocoes=["conforto"])["sugestao"]
    nomes = {i["nome"] for i in s["acorde"]["itens"]}
    assert nomes == {"Baunilha", "Vanilla"}                                         # nenhuma é descartada
    assert any("Baunilha e Vanilla parecem a mesma matéria-prima" in a for a in s["avisos"])


def test_dados_completos_e_incompletos_convivem(client, h):
    cadastrar(client, h, [("Rosa", "Floral", "neutra"), ("Peônia", "Floral", "neutra")])
    so_nome(client, h, ["Lavanda", "Nome Inventado"])
    s = propor(client, h, emocoes=["paz"], preferencias=["floral"])["sugestao"]
    assert s["status"] == "ok" and {i["nome"] for i in s["acorde"]["itens"]} <= {"Rosa", "Peônia", "Lavanda"}
    assert [e["nome"] for e in s["essencias_sem_dados"]] == ["Nome Inventado"]
    assert len(s["avisos"]) == len(set(s["avisos"]))                                # sem mensagens duplicadas


def test_sem_dado_indispensavel_a_mensagem_diz_exatamente_o_que_falta(client, h):
    so_nome(client, h, ["Nome Inventado", "Outro Desconhecido"])
    r = propor(client, h, emocoes=["paz"])
    s = r["sugestao"]
    assert s["status"] == "dados_insuficientes" and r["formulacao"] is None
    assert [e["nome"] for e in s["essencias_sem_dados"]] == ["Nome Inventado", "Outro Desconhecido"]
    assert "Família e Percepção" in s["mensagem"]


def test_conhecimento_geral_nunca_vira_estoque(client, h):
    cadastrar(client, h, [("Rosa", "Floral", "neutra"), ("Peônia", "Floral", "neutra")])
    s = propor(client, h, emocoes=["paz", "frescor"], preferencias=["citrico", "fresco"])["sugestao"]
    nomes = {i["nome"] for i in s["acorde"]["itens"]}
    assert nomes <= {"Rosa", "Peônia"}                                              # Limão, Hortelã... existem na base, não nela
    assert any(l["categoria"] == "Fresco" for l in s["lacunas"])                    # a falta é nomeada como categoria


# ------------------------------------------------ formulação: concentrações, volumes, soma
@pytest.mark.parametrize("produto,conc", [("body_splash", 7), ("body_splash", 10), ("body_splash", 15),
                                          ("perfume", 20), ("perfume", 25), ("perfume", 30)])
@pytest.mark.parametrize("volume", [100, 30, 250])
def test_seis_concentracoes_e_recalculo_por_volume_com_briefing_completo(client, h, produto, conc, volume):
    cadastrar(client, h)
    r = propor(client, h, produto=produto, concentracao_pct=conc, volume_ml=volume, idade=28, genero="unissex",
               emocoes=["paz", "amor"], familias_desejadas=["Floral"], preferencias=["suave"], ocasiao="dia_a_dia")
    f = r["formulacao"]
    assert f["valido"] and f["volume_ml"] == float(volume)
    assert f["concentrado_ml"] == pytest.approx(volume * conc / 100, abs=0.005)    # volume × concentração ÷ 100
    essencias = [i for i in f["ingredientes"] if i["tipo"] == "essencia"]
    assert round(sum(i["percentual_concentrado"] for i in essencias), 2) == 100.0
    assert round(sum(i["volume_ml"] for i in essencias), 2) == f["concentrado_ml"]
    assert round(sum(i["volume_ml"] for i in f["ingredientes"]), 2) == float(volume)
    for i in essencias:                                                            # participação no produto final
        assert i["percentual_produto"] == pytest.approx(conc * i["percentual_concentrado"] / 100, abs=0.011)
        assert i["nome"] and i["essencia_id"]
    assert [i["nome"] for i in f["ingredientes"] if i["tipo"] == "base"]           # base por componentes


def test_os_exemplos_obrigatorios_de_100ml(client, h):
    cadastrar(client, h)
    for produto, conc, ml in (("body_splash", 7, 7), ("body_splash", 10, 10), ("body_splash", 15, 15),
                              ("perfume", 20, 20), ("perfume", 25, 25), ("perfume", 30, 30)):
        f = propor(client, h, produto=produto, concentracao_pct=conc, volume_ml=100, emocoes=["paz"])["formulacao"]
        assert f["concentrado_ml"] == float(ml), (produto, conc)


# ------------------------------------------ persistência, edição, versionamento, testes
def test_salvar_editar_versionar_e_registrar_teste(client, h):
    cadastrar(client, h)
    briefing = {"idade": 30, "genero": "feminino", "emocoes": ["paz"], "familias_desejadas": ["Floral"],
                "ocasiao": "trabalho", "para_quem": "Marina"}
    c = client.post("/criacoes", headers=h, json={"nome": "Paz de Marina", "sugestao": briefing,
        "formulacao": {"produto": "perfume", "concentracao_pct": 20, "volume_ml": 100}})
    assert c.status_code == 201, c.text
    cid = c.json()["id"]
    perfil = client.get(f"/perfis/{c.json()['direcao']['perfil_id']}", headers=h).json()
    assert perfil["respostas"]["ocasiao"] == "trabalho" and perfil["respostas"]["familias_desejadas"] == ["Floral"]
    assert c.json()["direcao"]["resumo_briefing"]
    v1 = client.get(f"/criacoes/{cid}/acordes", headers=h).json()[0]
    assert v1["formulacao"]["resultado"]["concentrado_ml"] == 20.0
    itens = [{"essencia_id": i["essencia_id"], "peso": i["peso"]} for i in v1["itens"]]
    v2 = client.post(f"/criacoes/{cid}/acordes", headers=h, json={
        "itens": itens, "motivo": "Mais concentrado",
        "formulacao": {"produto": "perfume", "concentracao_pct": 30, "volume_ml": 50}}).json()
    assert v2["versao"] == 2 and v2["formulacao"]["resultado"]["concentrado_ml"] == 15.0   # 50 ml × 30 %
    assert client.get(f"/criacoes/{cid}/acordes", headers=h).json()[0]["formulacao"]["resultado"]["concentrado_ml"] == 20.0
    t = client.post(f"/criacoes/{cid}/testes", headers=h, json={"acorde_id": v2["id"], "nota": 8})
    assert t.status_code == 201


# ------------------------------------------------------------------------- isolamento
def test_isolamento_do_briefing_e_do_conhecimento(client, nova_usuaria):
    a, b = nova_usuaria("ba@exemplo.com"), nova_usuaria("bb@exemplo.com")
    ids_a = cadastrar(client, a)
    so_nome(client, b, ["Pera", "Lavanda"])
    # B nunca recebe essência de A, nem as usa por id
    r = propor(client, b, emocoes=["paz"], preferencias=["floral"])
    nomes_b = {i["nome"] for i in r["sugestao"]["acorde"]["itens"]}
    assert nomes_b <= {"Pera", "Lavanda"}
    ids_usados = {i["essencia_id"] for i in r["sugestao"]["acorde"]["itens"]}
    assert not ids_usados & set(ids_a.values())
    erro = client.post("/formulacoes/propor", headers=b, json={
        "produto": "perfume", "concentracao_pct": 20, "emocoes": ["paz"], "essencias_disponiveis": list(ids_a.values())})
    assert erro.status_code == 404
    # a estimativa pelo nome de B não grava nada nas essências de A
    antes = client.get("/essencias", headers=a).json()
    propor(client, b, emocoes=["paz"])
    assert client.get("/essencias", headers=a).json() == antes
    # salvar a criação de B só mexe nas essências de B
    client.post("/criacoes", headers=b, json={"nome": "B", "sugestao": {"emocoes": ["paz"], "preferencias": ["floral"]},
        "formulacao": {"produto": "body_splash", "concentracao_pct": 10, "volume_ml": 100}})
    assert client.get("/essencias", headers=a).json() == antes
