"""Fluxo ponta a ponta pela API: cadastro → reconhecimento → acorde → ajuste → teste → coleção."""

from tests.util import VALORES_DA_ALUNA


def _post(client, url, json, h, esperado=201):
    r = client.post(url, json=json, headers=h)
    assert r.status_code == esperado, r.text
    return r.json()


def test_reconhecimento_sugere_mas_nao_aplica_sozinho(client, nova_usuaria):
    h = nova_usuaria("r@exemplo.com")
    e = _post(client, "/essencias", {"nome": "bergamot"}, h)
    # Nada aplicado automaticamente...
    assert e["knowledge_note_id"] is None and e["familia"] is None and e["v1"] is None
    assert e["confianca"] == "baixa"
    # ...mas a sugestão veio.
    sug = e["sugestoes_referencia"][0]
    assert sug["nome"] == "Bergamota" and sug["correspondencia"] == "exata"

    # A nota da base é de EXEMPLO: a sugestão traz a marca, o aviso e só a classificação.
    assert sug["ilustrativa"] is True and sug["v1"] is None and sug["papel"] is None
    assert any("EXEMPLO" in a for a in sug["avisos"])

    # A aluna confirma, informando o v4 dela. Só a classificação vem da nota;
    # o exemplo nunca vira "ficha técnica" nem copia número para a essência.
    e2 = _post(
        client, "/essencias",
        {"nome": "Bergamota Fornecedor X", "knowledge_note_id": sug["nota_id"],
         "aplicar_referencia": True, "v4": 4},
        h,
    )
    assert e2["familia"] == "Cítrico" and e2["v1"] is None and e2["v4"] == 4
    assert e2["origem"] == "estimado" and e2["confianca"] == "baixa"
    assert e2["editado_da_referencia"] is False and e2["sugestoes_referencia"] == []

    # Referência composta/baixa confiança vem com aviso.
    avisos = client.get("/essencias/sugestao-classificacao", params={"nome": "ambar"}, headers=h).json()
    assert avisos and len(avisos[0]["avisos"]) >= 2


def test_nota_validada_copia_numeros_e_marca_edicao(client, nova_usuaria, nota_validada):
    """Quando a base oficial entrar (ilustrativo=False), aplicar a referência copia os números."""
    h = nova_usuaria("v@exemplo.com")
    e = _post(client, "/essencias", {"nome": "Cedro", "knowledge_note_id": nota_validada,
                                     "aplicar_referencia": True}, h)
    assert e["v2"] == 8 and e["origem"] == "tecnico" and e["confianca"] == "alta"
    assert e["editado_da_referencia"] is False
    # Editar um valor vindo da referência marca a essência como editada.
    r = client.put(f"/essencias/{e['id']}", json={"v2": 9}, headers=h).json()
    assert r["editado_da_referencia"] is True


def test_fluxo_criacao_acorde_ajuste_teste_colecao(client, nova_usuaria):
    h = nova_usuaria("fluxo@exemplo.com")
    jasmim = _post(client, "/essencias", {"nome": "Jasmim", "knowledge_note_id": 3,
                                          "aplicar_referencia": True, **VALORES_DA_ALUNA["Jasmim"]}, h)
    cedro = _post(client, "/essencias", {"nome": "Cedro", "knowledge_note_id": 4,
                                         "aplicar_referencia": True, **VALORES_DA_ALUNA["Cedro"]}, h)

    perfil = _post(client, "/perfis", {"respostas": {
        "emocoes": ["amor", "serenidade"], "territorios": ["acolhimento"], "publico": "teen",
        "genero": "feminino", "idade": 15}}, h)
    assert perfil["vetor_alvo"]["publico"] == "teen"

    criacao = _post(client, "/criacoes", {"nome": "Menina de 15", "perfil_id": perfil["id"]}, h)
    assert criacao["direcao"]["texto"].startswith("Territórios: Acolhimento")

    url = f"/criacoes/{criacao['id']}/acordes"
    itens = [{"essencia_id": jasmim["id"], "peso": "bastante"}, {"essencia_id": cedro["id"], "peso": "médio"}]
    v1 = _post(client, url, {"itens": itens}, h)
    assert v1["versao"] == 1
    assert v1["vetor"]["valores"]["v1"] is not None
    assert v1["compatibilidade"]["score"] is not None
    assert v1["familia_resultante"] == "Floral"
    assert client.get(f"/criacoes/{criacao['id']}", headers=h).json()["status"] == "em_ajuste"

    # Sem nada fresco no repertório: o motor nomeia a lacuna (família), não uma essência.
    ajuste = _post(client, f"{url}/{v1['id']}/ajuste", {"movimento": "mais fresco"}, h, 200)
    assert ajuste["alcancavel"] is False
    assert "Cítrico" in ajuste["lacuna"]["mensagem"]
    assert "Bergamota" not in ajuste["lacuna"]["mensagem"]

    # Com uma bergamota no repertório, o ajuste passa a ser possível.
    berg = _post(client, "/essencias", {"nome": "Bergamota", "knowledge_note_id": 1,
                                        "aplicar_referencia": True, **VALORES_DA_ALUNA["Bergamota"]}, h)
    ajuste = _post(client, f"{url}/{v1['id']}/ajuste", {"movimento": "mais_fresco"}, h, 200)
    assert ajuste["alcancavel"] is True
    assert ajuste["sugestoes"][0]["essencia_id"] == berg["id"]

    # Aplicar a sugestão = criar a v2 (a v1 fica intacta no histórico).
    novos = [{"essencia_id": i, "peso": p} for i, p in ajuste["sugestoes"][0]["itens_resultantes"]]
    v2 = _post(client, url, {"itens": novos}, h)
    assert v2["versao"] == 2
    historico = client.get(url, headers=h).json()
    assert [a["versao"] for a in historico] == [1, 2]
    assert historico[0]["itens"] == v1["itens"]

    # Movimento desconhecido é erro de negócio claro.
    r = client.post(f"{url}/{v1['id']}/ajuste", json={"movimento": "mais_roxo"}, headers=h)
    assert r.status_code == 400 and "mais_fresco" in r.json()["detail"]

    # Testes versionados; acorde precisa ser da mesma criação.
    t1 = _post(client, f"/criacoes/{criacao['id']}/testes", {"acorde_id": v2["id"], "nota": 9}, h)
    t2 = _post(client, f"/criacoes/{criacao['id']}/testes", {"nota": 7}, h)
    assert (t1["versao"], t2["versao"]) == (1, 2)
    r = client.post(f"/criacoes/{criacao['id']}/testes", json={"nota": 11}, headers=h)
    assert r.status_code == 422

    # Coleção só aceita criação aprovada.
    col = _post(client, "/colecoes", {"nome": "Linha Teen"}, h)
    _post(client, f"/colecoes/{col['id']}/criacoes", {"criacao_id": criacao["id"]}, h, 400)
    client.put(f"/criacoes/{criacao['id']}", json={"status": "aprovada"}, headers=h)
    outra = _post(client, "/criacoes", {"nome": "Outra", "status": "aprovada"}, h)
    _post(client, f"/colecoes/{col['id']}/criacoes", {"criacao_id": criacao["id"]}, h)
    col = _post(client, f"/colecoes/{col['id']}/criacoes", {"criacao_id": outra["id"]}, h)
    assert [i["criacao_id"] for i in col["itens"]] == [criacao["id"], outra["id"]]
    col = client.put(f"/colecoes/{col['id']}/ordem",
                     json={"criacao_ids": [outra["id"], criacao["id"]]}, headers=h).json()
    assert [i["criacao_id"] for i in col["itens"]] == [outra["id"], criacao["id"]]
    assert client.delete(f"/colecoes/{col['id']}/criacoes/{outra['id']}", headers=h).status_code == 204

    # Recomendações vêm do repertório dela, ordenadas.
    rec = client.get(f"/perfis/{perfil['id']}/recomendacoes", headers=h).json()
    assert {r["essencia_id"] for r in rec["recomendacoes"]} <= {jasmim["id"], cedro["id"], berg["id"]}
    scores = [r["score"] for r in rec["recomendacoes"]]
    assert scores == sorted(scores, reverse=True)

    # Lacunas gerais do repertório.
    tipos = {lac["tipo"] for lac in client.get("/essencias/lacunas", headers=h).json()}
    assert "familia_ausente" in tipos


def test_criacao_arquivada_nao_recebe_versoes(client, nova_usuaria):
    h = nova_usuaria("arq@exemplo.com")
    a = _post(client, "/essencias", {"nome": "A", "familia": "Floral"}, h)
    b = _post(client, "/essencias", {"nome": "B", "familia": "Cítrico"}, h)
    c = _post(client, "/criacoes", {"nome": "Velha", "status": "arquivada"}, h)
    r = client.post(f"/criacoes/{c['id']}/acordes", headers=h,
                    json={"itens": [{"essencia_id": a["id"], "peso": 1}, {"essencia_id": b["id"], "peso": 1}]})
    assert r.status_code == 400


def test_acorde_valida_entrada(client, nova_usuaria):
    h = nova_usuaria("val@exemplo.com")
    a = _post(client, "/essencias", {"nome": "A"}, h)
    c = _post(client, "/criacoes", {"nome": "C"}, h)
    url = f"/criacoes/{c['id']}/acordes"
    um_item = {"itens": [{"essencia_id": a["id"], "peso": 1}]}
    repetido = {"itens": [{"essencia_id": a["id"], "peso": 1}, {"essencia_id": a["id"], "peso": 2}]}
    porcentagem = {"itens": [{"essencia_id": a["id"], "peso": 30}, {"essencia_id": 999, "peso": 70}]}
    for corpo in (um_item, repetido, porcentagem):
        assert client.post(url, json=corpo, headers=h).status_code == 422
