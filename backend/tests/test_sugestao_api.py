"""Integração (API) do motor de criação: POST /criacoes/sugerir e POST /criacoes.

Os nomes das essências abaixo existem SÓ para os testes: nenhum seed os grava
para usuária alguma (usuária nova começa com repertório 100 % vazio).
"""

import json

import pytest

from app.models.knowledge import KnowledgeNote
from tests.util import essencia_antiga

# nome: (família, v1, v2, v3, v4, (saída, coração, fundo))
LUNA = {
    "Pera": ("Frutado", 4, 3, 7, 4, (0.5, 0.4, 0.1)),
    "Bergamota": ("Cítrico", 2, 1.5, 3, 6, (0.9, 0.1, 0.0)),
    "Mandarina": ("Cítrico", 3, 2, 5, 5, (0.8, 0.2, 0.0)),
    "Peônia": ("Floral", 4, 3, 5, 3, (0.3, 0.7, 0.0)),
    "Rosa": ("Floral", 5, 4, 5, 5, (0.1, 0.8, 0.1)),
    "Jasmim": ("Floral Branco", 6, 5, 6, 7, (0.1, 0.8, 0.1)),
    "Lavanda": ("Aromático", 3, 3, 3, 5, (0.5, 0.5, 0.0)),
    "Musk Branco": ("Almiscarado", 5, 6, 4, 3, (0.0, 0.2, 0.8)),
    "Baunilha": ("Gourmand", 8, 7, 9, 6, (0.0, 0.1, 0.9)),
    "Sândalo": ("Amadeirado", 6, 7, 3, 4, (0.0, 0.2, 0.8)),
}
PEDIDO_LUNA = {
    "para_quem": "Luna", "genero": "feminino", "idade": 15,
    "emocoes": ["amor", "paz", "serenidade"], "preferencias": ["doce", "floral"],
    "intensidade": 4,
}


def cadastrar(client, headers, repertorio=LUNA) -> dict[str, int]:
    """Cadastra as essências e devolve {nome: id}."""
    ids = {}
    for nome, (fam, v1, v2, v3, v4, (s, c, f)) in repertorio.items():
        # Cadastro oficial (3 campos) + valores exatos gravados direto no banco (só testes).
        r = essencia_antiga(client, headers, {
            "nome": nome, "familia": fam, "v1": v1, "v2": v2, "v3": v3, "v4": v4,
            "papel": {"saida": s, "coracao": c, "fundo": f}, "confianca": "media",
        })
        assert r.status_code == 201, r.text
        ids[nome] = r.json()["id"]
    return ids


@pytest.fixture()
def luna(client, nova_usuaria):
    h = nova_usuaria("luna@exemplo.com")
    return h, cadastrar(client, h)


def sugerir(client, h, **pedido):
    r = client.post("/criacoes/sugerir", json=pedido, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_cenario_luna(client, luna):
    h, ids = luna
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert r["status"] == "ok"
    ident = r["identidade"]
    assert ident["direcao"] and ident["por_que"] and ident["personalidade"]
    assert "amor, paz e serenidade" in ident["por_que"]
    itens = r["acorde"]["itens"]
    assert 3 <= len(itens) <= 4
    assert {i["essencia_id"] for i in itens} <= set(ids.values())  # só o repertório dela
    assert sorted(i["peso"] for i in itens)[-1] == 3
    assert {i["rotulo_peso"] for i in itens} <= {"Pouco", "Médio", "Bastante"}
    assert all(i["papel_na_criacao"] is None or i["papel_na_criacao"].startswith("É do território") or "pediu" in i["papel_na_criacao"] or "criação" in i["papel_na_criacao"] for i in itens)
    assert r["dados_suficientes"] is True and "confianca" not in r
    assert sum(r["acorde"]["piramide"].values()) == 100
    # Linguagem de consultora: nada de vetor/score na parte exibida.
    exibido = json.dumps({k: v for k, v in r.items() if k != "tecnico"}, ensure_ascii=False).lower()
    for proibido in ("v1", "score", "coherence", "distance"):
        assert proibido not in exibido


def test_mesmo_pedido_duas_vezes_e_identico(client, luna):
    h, _ = luna
    assert sugerir(client, h, **PEDIDO_LUNA) == sugerir(client, h, **PEDIDO_LUNA)


def test_repertorio_vazio_e_insuficiente(client, nova_usuaria):
    h = nova_usuaria("vazia@exemplo.com")
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert r["status"] == "insuficiente" and r["acorde"] is None
    assert r["mensagem"] == "Cadastre pelo menos 2 essências para o laboratório criar com você."
    assert r["identidade"] is not None


def test_uma_essencia_so_devolve_acorde_de_um_item_com_aviso(client, nova_usuaria):
    h = nova_usuaria("uma@exemplo.com")
    cadastrar(client, h, {"Peônia": LUNA["Peônia"]})
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert len(r["acorde"]["itens"]) == 1
    assert any("pouca variedade" in a for a in r["avisos"])


def test_territorio_sem_essencia_nomeia_lacuna_sem_inventar(client, nova_usuaria):
    """Pede floral/aromático, mas só tem amadeirado e âmbar: acorde parcial + lacuna nomeada."""
    h = nova_usuaria("sem@exemplo.com")
    ids = cadastrar(client, h, {"Sândalo": LUNA["Sândalo"], "Cedro": ("Amadeirado", 5, 8, 2, 5, (0, .2, .8))})
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert {i["essencia_id"] for i in r["acorde"]["itens"]} <= set(ids.values())
    assert any("parcialmente" in a for a in r["avisos"])
    categorias = {l["categoria"] for l in r["lacunas"]}
    assert categorias & {"Floral", "Aromático"}
    texto = json.dumps(r["lacunas"], ensure_ascii=False)
    assert "Peônia" not in texto and "Lavanda" not in texto


def test_bebe_limita_presenca_e_tamanho(client, luna):
    h, _ = luna
    r = sugerir(client, h, genero="nao_definir", idade="bebe", emocoes=["delicadeza"],
                preferencias=["marcante"], intensidade=9)
    assert len(r["acorde"]["itens"]) <= 3
    assert r["tecnico"]["vetor_alvo"]["v4"] <= 3
    assert r["tecnico"]["max_itens"] == 3
    # idade em número converte em faixa por regra de dados
    r2 = sugerir(client, h, idade=1, emocoes=["delicadeza"], intensidade=9)
    assert r2["tecnico"]["faixa_idade"] == "bebe" and r2["tecnico"]["vetor_alvo"]["v4"] <= 3


def test_crianca_limita_presenca(client, luna):
    h, _ = luna
    r = sugerir(client, h, idade=8, emocoes=["alegria"], intensidade=10)
    assert r["tecnico"]["vetor_alvo"]["v4"] == 4.5


def test_faixa_desconhecida_e_recusada(client, luna):
    h, _ = luna
    r = client.post("/criacoes/sugerir", json={"idade": "marciano"}, headers=h)
    assert r.status_code in (400, 422)


def test_genero_nao_trava_familia(client, nova_usuaria):
    """Homem pedindo doce recebe acorde doce; mulher pedindo amadeirado recebe amadeirado."""
    h = nova_usuaria("g@exemplo.com")
    ids = cadastrar(client, h)
    homem = sugerir(client, h, genero="masculino", preferencias=["doce"], emocoes=["conforto"])
    assert "Baunilha" in {i["nome"] for i in homem["acorde"]["itens"]}
    mulher = sugerir(client, h, genero="feminino", preferencias=["amadeirado"], intensidade=6)
    assert "Sândalo" in {i["nome"] for i in mulher["acorde"]["itens"]}
    assert ids  # repertório compartilhado


def test_nao_sei_e_chaves_desconhecidas_nao_quebram(client, luna):
    h, _ = luna
    r = sugerir(client, h, emocoes=["amor", "inexistente"], preferencias=["nao_sei"])
    assert r["status"] == "ok"
    assert any("Não reconheci" in a for a in r["avisos"])


def test_essencias_disponiveis_restringe(client, luna):
    h, ids = luna
    escolha = [ids["Pera"], ids["Rosa"], ids["Sândalo"]]
    r = sugerir(client, h, **PEDIDO_LUNA, essencias_disponiveis=escolha)
    assert {i["essencia_id"] for i in r["acorde"]["itens"]} <= set(escolha)


def test_modo_mostrar_lacunas_lista_categorias(client, nova_usuaria):
    h = nova_usuaria("lac@exemplo.com")
    cadastrar(client, h, {"Peônia": LUNA["Peônia"], "Rosa": LUNA["Rosa"], "Pera": LUNA["Pera"]})
    base = sugerir(client, h, **PEDIDO_LUNA)
    mais = sugerir(client, h, **PEDIDO_LUNA, modo="mostrar_lacunas")
    assert len(mais["lacunas"]) >= len(base["lacunas"])


def test_nenhuma_nota_de_conhecimento_aparece(client, nova_usuaria, db):
    """Mesmo com notas na base, só entra o que a usuária cadastrou."""
    h = nova_usuaria("k@exemplo.com")
    cadastrar(client, h, {"Peônia": LUNA["Peônia"], "Rosa": LUNA["Rosa"]})
    nomes_base = {n.nome for n in db.query(KnowledgeNote)}
    assert nomes_base  # a base tem notas (Bergamota, Jasmim...)
    r = sugerir(client, h, **PEDIDO_LUNA)
    nomes = {i["nome"] for i in r["acorde"]["itens"]}
    assert nomes <= {"Peônia", "Rosa"} and not (nomes & nomes_base)
    assert "Bergamota" not in json.dumps(r, ensure_ascii=False)


def test_opcoes_vem_do_banco(client, nova_usuaria):
    h = nova_usuaria("o@exemplo.com")
    r = client.get("/criacoes/sugerir/opcoes", headers=h)
    assert r.status_code == 200
    o = r.json()
    assert len(o["emocoes"]) >= 16 and {"chave": "doce", "rotulo": "doce"} in o["preferencias"]
    assert [f["chave"] for f in o["faixas_idade"]][:2] == ["recem-nascido", "bebe"]


def test_criar_com_sugestao_recalcula_no_servidor_e_grava(client, luna):
    h, ids = luna
    r = client.post("/criacoes", headers=h, json={"nome": "Amor Sereno", "sugestao": PEDIDO_LUNA})
    assert r.status_code == 201, r.text
    criacao = r.json()
    assert criacao["direcao"]["identidade"]["direcao"]
    acordes = client.get(f"/criacoes/{criacao['id']}/acordes", headers=h).json()
    assert len(acordes) == 1 and acordes[0]["versao"] == 1
    previa = sugerir(client, h, **PEDIDO_LUNA)["acorde"]["itens"]
    assert [(i["essencia_id"], i["peso"]) for i in acordes[0]["itens"]] == \
           [(i["essencia_id"], {1: "pouco", 2: "medio", 3: "bastante"}[i["peso"]]) for i in previa]
    perfil = client.get(f"/perfis/{criacao['direcao']['perfil_id']}", headers=h).json()
    assert perfil["respostas"]["emocoes"] == ["amor", "paz", "serenidade"]


def test_cliente_nao_envia_numeros(client, luna):
    h, _ = luna
    r = client.post("/criacoes/sugerir", headers=h, json={**PEDIDO_LUNA, "vetor_alvo": {"v1": 0}})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Confiabilidade: nada de resultado ou justificativa sem dado que o sustente
# ---------------------------------------------------------------------------
def test_pedido_sem_direcao_nao_inventa_identidade_nem_acorde(client, luna):
    h, _ = luna
    for pedido in ({}, {"intensidade": 2}, {"preferencias": ["suave"], "intensidade": 2},
                   {"emocoes": ["inexistente"]}, {"idade": "bebe"}):
        r = sugerir(client, h, **pedido)
        assert r["status"] == "pedido_incompleto", pedido
        assert r["identidade"] is None and r["acorde"] is None
        assert "emoção ou preferência" in r["mensagem"]


def test_essencia_sem_caracteristicas_nao_entra_e_e_citada_uma_vez(client, nova_usuaria):
    h = nova_usuaria("sd@exemplo.com")
    cadastrar(client, h, {"Peônia": LUNA["Peônia"], "Rosa": LUNA["Rosa"], "Pera": LUNA["Pera"]})
    vazio = {"v1": None, "v2": None, "v3": None, "v4": None, "v5": None, "papel": None}
    r0 = essencia_antiga(client, h, {"nome": "Mistério", "familia": None, **vazio})
    r1 = essencia_antiga(client, h, {"nome": "Enigma", "familia": "Floral", **vazio})
    assert r0.status_code == r1.status_code == 201
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert {"Mistério", "Enigma"}.isdisjoint({i["nome"] for i in r["acorde"]["itens"]})
    ficaram = [a for a in r["avisos"] if "Ficaram de fora" in a]
    assert len(ficaram) == 1 and "Mistério" in ficaram[0] and "Enigma" in ficaram[0]


def test_repertorio_todo_sem_caracteristicas_nao_gera_acorde(client, nova_usuaria):
    h = nova_usuaria("sd2@exemplo.com")
    for nome in ("Um", "Dois"):
        essencia_antiga(client, h, {"nome": nome, "familia": "Floral", "v1": None, "v2": None, "v3": None,
                                    "v4": None, "v5": None, "papel": None})
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert r["status"] == "dados_insuficientes" and r["acorde"] is None
    assert r["dados_suficientes"] is False and "Família e Percepção" in r["mensagem"]
    assert sorted(e["nome"] for e in r["essencias_sem_dados"]) == ["Dois", "Um"]   # a aluna vê o que completar
    assert r["avisos"] == []  # a orientação está na mensagem; não se repete


def test_avisos_nao_se_repetem(client, luna):
    h, _ = luna
    for pedido in (PEDIDO_LUNA, {**PEDIDO_LUNA, "modo": "mostrar_lacunas"}):
        r = sugerir(client, h, **pedido)
        assert len(r["avisos"]) == len(set(r["avisos"]))
        msgs = [l["mensagem"] for l in r["lacunas"]]
        assert len(msgs) == len(set(msgs))


def test_piramide_so_com_papel_informado(client, nova_usuaria):
    h = nova_usuaria("pir@exemplo.com")
    sem_papel = {k: (v[0], v[1], v[2], v[3], v[4], (0, 0, 0)) for k, v in LUNA.items()}
    for nome, (fam, v1, v2, v3, v4, _) in sem_papel.items():
        essencia_antiga(client, h, {"nome": nome, "familia": fam, "v1": v1, "v2": v2, "v3": v3, "v4": v4,
                                    "v5": None, "papel": None})
    r = sugerir(client, h, **PEDIDO_LUNA)
    assert r["acorde"]["piramide"] is None
    assert all("Abre" not in (i["papel_na_criacao"] or "") for i in r["acorde"]["itens"])


def test_compatibilidade_avulsa_sem_relacao_nao_mostra_porcentagem(client, nova_usuaria):
    h = nova_usuaria("cp@exemplo.com")
    ids = cadastrar(client, h, {"Sândalo": LUNA["Sândalo"], "Baunilha": LUNA["Baunilha"]})
    r = client.post("/essencias/compatibilidade", headers=h, json={"essencia_ids": list(ids.values())})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["score"] is None and corpo["pares"] == []
    assert len(corpo["alertas"]) == 1 and "Sem relação cadastrada" in corpo["alertas"][0]


def test_compatibilidade_com_relacao_cadastrada_calcula_e_marca_base_de_exemplo(client, nova_usuaria):
    h = nova_usuaria("cp2@exemplo.com")
    ids = cadastrar(client, h, {"Bergamota": LUNA["Bergamota"], "Peônia": LUNA["Peônia"]})
    corpo = client.post("/essencias/compatibilidade", headers=h, json={"essencia_ids": list(ids.values())}).json()
    assert isinstance(corpo["score"], int) and corpo["pares_avaliados"] == 1
    assert corpo["base_exemplo"] is True  # relações do seed ainda são de exemplo
