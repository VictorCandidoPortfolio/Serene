"""Funcionalidades da descrição do produto que ganharam suporte (out/2026).

Cobre: classificação com floralidade, territórios, Mapa Olfativo,
compatibilidade avulsa, criador de fragrâncias (intenção, referência e
recomendações), identidade de acorde, caminhos de referência, motivo das
versões e identidade geral de coleções — sempre conferindo o isolamento.
"""

import re

import pytest

from app.main import app
from tests.util import VALORES_DA_ALUNA, essencia_antiga

TERRITORIOS = {"acolhimento", "delicadeza", "alegria", "amor", "encanto", "renovacao",
               "frescor", "elegancia", "magnetismo", "sensualidade"}


def _post(client, url, json, h, esperado=201):
    r = client.post(url, json=json, headers=h)
    assert r.status_code == esperado, r.text
    return r.json()


@pytest.fixture()
def repertorio(client, nova_usuaria):
    """Usuária com 3 essências (Jasmim, Cedro, Bergamota): família pela nota de exemplo, números dela."""
    h = nova_usuaria("ana@exemplo.com")
    ids = {
        nome: essencia_antiga(client, h, {"nome": nome, **VALORES_DA_ALUNA[nome]}, grupo).json()["id"]
        for nome, grupo in (("Bergamota", "Cítrico"), ("Jasmim", "Floral"), ("Cedro", "Amadeirado"))
    }
    return h, ids


def test_floralidade_entra_no_acorde_e_no_movimento(client, repertorio):
    h, ids = repertorio
    c = _post(client, "/criacoes", {"nome": "C"}, h)
    a = _post(client, f"/criacoes/{c['id']}/acordes", {"itens": [
        {"essencia_id": ids["Cedro"], "peso": "bastante"}, {"essencia_id": ids["Bergamota"], "peso": "medio"}]}, h)
    assert a["vetor"]["valores"]["v6"] is not None
    ajuste = _post(client, f"/criacoes/{c['id']}/acordes/{a['id']}/ajuste", {"movimento": "mais_floral"}, h, 200)
    assert ajuste["alcancavel"] and ajuste["sugestoes"][0]["essencia_id"] == ids["Jasmim"]


def test_territorios_da_descricao(client, nova_usuaria):
    """Os territórios vêm do banco e incluem os da descrição do produto."""
    h = nova_usuaria("t@exemplo.com")
    chaves = {t["chave"] for t in client.get("/conhecimento/territorios", headers=h).json()}
    assert TERRITORIOS <= chaves


# ------------------------------------------------------------- Mapa Olfativo
def test_mapa_traz_pontos_da_aluna_e_estrutura_da_base(client, repertorio, nova_usuaria):
    h, ids = repertorio
    c = _post(client, "/criacoes", {"nome": "Primavera"}, h)
    _post(client, f"/criacoes/{c['id']}/acordes", {"itens": [
        {"essencia_id": ids["Jasmim"], "peso": 2}, {"essencia_id": ids["Cedro"], "peso": 1}]}, h)
    _post(client, f"/criacoes/{c['id']}/acordes", {"itens": [
        {"essencia_id": ids["Jasmim"], "peso": 3}, {"essencia_id": ids["Cedro"], "peso": 1}]}, h)

    m = client.get("/mapa", headers=h).json()
    assert {e["nome"] for e in m["essencias"]} == {"Bergamota", "Jasmim", "Cedro"}
    assert all(e["vetor"]["v1"] is not None for e in m["essencias"])
    assert [(cr["nome"], cr["versao"]) for cr in m["criacoes"]] == [("Primavera", 2)]
    assert TERRITORIOS <= {t["chave"] for t in m["territorios"]}
    assert m["relacoes"] and m["familias"] and m["mapas"]
    assert [e["chave"] for e in m["eixos"]] == ["v1", "v2", "v3", "v4", "v5", "v6"]

    # Isolamento: outra usuária vê a base, mas nenhum ponto da primeira.
    b = nova_usuaria("b@exemplo.com")
    mb = client.get("/mapa", headers=b).json()
    assert mb["essencias"] == [] and mb["criacoes"] == [] and mb["territorios"]


# --------------------------------------------------- compatibilidade avulsa
def test_compatibilidade_avulsa_nao_grava_nada(client, repertorio, nova_usuaria):
    h, ids = repertorio
    r = _post(client, "/essencias/compatibilidade",
              {"essencia_ids": [ids["Bergamota"], ids["Jasmim"], ids["Cedro"]]}, h, 200)
    assert r["score"] is not None and len(r["pares"]) == 3
    assert client.get("/criacoes", headers=h).json() == []  # nada criado

    b = nova_usuaria("b@exemplo.com")
    eb = essencia_antiga(client, b, {"nome": "Minha"}).json()
    r = client.post("/essencias/compatibilidade", headers=b,
                    json={"essencia_ids": [eb["id"], ids["Jasmim"]]})
    assert r.status_code == 404  # essência de outra usuária
    r = client.post("/essencias/compatibilidade", headers=h,
                    json={"essencia_ids": [ids["Jasmim"], ids["Jasmim"]]})
    assert r.status_code == 422


# ------------------------------------------------------ criador de fragrâncias
def test_criacao_a_partir_de_intencao_sem_perfil(client, repertorio):
    h, ids = repertorio
    c = _post(client, "/criacoes", {"nome": "Abraço", "intencao": {
        "territorios": ["acolhimento"], "publico": "adulta"}}, h)
    assert c["direcao"]["territorios"] == ["acolhimento"]
    assert c["direcao"]["vetor_alvo"]["v1"] is not None
    assert client.get("/perfis", headers=h).json() == []  # nenhum perfil foi preciso

    rec = client.get(f"/criacoes/{c['id']}/recomendacoes", headers=h).json()
    assert {r["essencia_id"] for r in rec["recomendacoes"]} <= set(ids.values())
    scores = [r["score"] for r in rec["recomendacoes"]]
    assert scores == sorted(scores, reverse=True)


def test_criacao_sem_direcao_nao_tem_recomendacao(client, repertorio):
    h, _ = repertorio
    c = _post(client, "/criacoes", {"nome": "Livre"}, h)
    r = client.get(f"/criacoes/{c['id']}/recomendacoes", headers=h)
    assert r.status_code == 400 and r.json()["codigo"] == "sem_direcao"


def test_criacao_aceita_uma_origem_de_direcao_so(client, repertorio):
    h, _ = repertorio
    p = _post(client, "/perfis", {"respostas": {"emocoes": ["amor"]}}, h)
    r = client.post("/criacoes", headers=h, json={
        "nome": "X", "perfil_id": p["id"], "intencao": {"territorios": ["amor"]}})
    assert r.status_code == 422


def test_criacao_inspirada_em_referencia(client, repertorio, nova_usuaria):
    h, _ = repertorio
    ref = _post(client, "/referencias", {"nome": "Perfume Y", "notas_conhecidas": ["jasmim", "cedro"]}, h)
    c = _post(client, "/criacoes", {"nome": "Inspirada", "referencia_id": ref["id"]}, h)
    assert c["direcao"]["referencia_id"] == ref["id"]
    assert c["direcao"]["texto"].startswith("Inspirada em “Perfume Y”")
    assert c["direcao"]["vetor_alvo"]["v6"] is not None

    b = nova_usuaria("b@exemplo.com")
    assert client.post("/criacoes", headers=b, json={"nome": "X", "referencia_id": ref["id"]}).status_code == 404


# ------------------------------------------------------- identidade do acorde
def test_identidade_do_acorde_aponta_territorios(client, repertorio, nova_usuaria):
    h, ids = repertorio
    c = _post(client, "/criacoes", {"nome": "C"}, h)
    a = _post(client, f"/criacoes/{c['id']}/acordes", {"itens": [
        {"essencia_id": ids["Jasmim"], "peso": 3}, {"essencia_id": ids["Cedro"], "peso": 1}]}, h)
    ident = client.get(f"/criacoes/{c['id']}/acordes/{a['id']}/identidade", headers=h).json()
    assert ident["territorios"], ident
    assert all(t["chave"] in TERRITORIOS and 0 <= t["proximidade"] <= 100 for t in ident["territorios"])
    proximidades = [t["proximidade"] for t in ident["territorios"]]
    assert proximidades == sorted(proximidades, reverse=True)

    b = nova_usuaria("b@exemplo.com")
    assert client.get(f"/criacoes/{c['id']}/acordes/{a['id']}/identidade", headers=b).status_code == 404


# ------------------------------------------------------ caminhos da referência
def test_caminhos_da_referencia(client, repertorio, nova_usuaria):
    h, ids = repertorio
    ref = _post(client, "/referencias", {"nome": "Perfume Z", "familia_percebida": "Ambarado",
                                         "notas_conhecidas": ["Bergamot", "Âmbar", "xarope de unicórnio"]}, h)
    r = client.get(f"/referencias/{ref['id']}/caminhos", headers=h).json()
    assert {n["nota"] for n in r["notas_reconhecidas"]} == {"Bergamota", "Âmbar"}
    assert r["notas_desconhecidas"] == ["xarope de unicórnio"]
    assert "Cítrico" in r["familias_presentes"] and "Ambarado" in r["familias_ausentes"]
    assert r["vetor_estimado"]["v1"] is not None
    assert any("ESTIMATIVA" in a for a in r["avisos"])
    assert {x["essencia_id"] for x in r["recomendacoes"]["recomendacoes"]} <= set(ids.values())

    b = nova_usuaria("b@exemplo.com")
    assert client.get(f"/referencias/{ref['id']}/caminhos", headers=b).status_code == 404


def test_perfil_usa_a_direcao_da_referencia(client, repertorio, nova_usuaria):
    h, _ = repertorio
    ref = _post(client, "/referencias", {"nome": "R", "notas_conhecidas": ["jasmim"]}, h)
    p = _post(client, "/perfis", {"respostas": {"referencia_id": ref["id"]}}, h)
    origens = [c["origem"] for c in p["vetor_alvo"]["contribuicoes"]]
    assert origens == ["referencia"] and p["vetor_alvo"]["vetor"]["v6"] == 9

    b = nova_usuaria("b@exemplo.com")
    r = client.post("/perfis", headers=b, json={"respostas": {"referencia_id": ref["id"]}})
    assert r.status_code == 404


# ------------------------------------------------------------ evolução
def test_versao_guarda_o_motivo(client, repertorio):
    h, ids = repertorio
    c = _post(client, "/criacoes", {"nome": "C"}, h)
    itens = [{"essencia_id": ids["Jasmim"], "peso": 2}, {"essencia_id": ids["Cedro"], "peso": 2}]
    v1 = _post(client, f"/criacoes/{c['id']}/acordes", {"itens": itens}, h)
    v2 = _post(client, f"/criacoes/{c['id']}/acordes",
               {"itens": itens, "motivo": "Ajuste mais fresco: adicionar Bergamota"}, h)
    assert v1["motivo"] is None and v2["motivo"] == "Ajuste mais fresco: adicionar Bergamota"
    r = client.post(f"/criacoes/{c['id']}/acordes", headers=h, json={"itens": itens, "motivo": "x" * 301})
    assert r.status_code == 422


# -------------------------------------------------------------- coleções
def test_identidade_geral_da_colecao(client, repertorio):
    h, ids = repertorio
    col = _post(client, "/colecoes", {"nome": "Linha"}, h)
    for itens in ([("Jasmim", 3), ("Cedro", 1)], [("Bergamota", 2), ("Jasmim", 1)]):
        c = _post(client, "/criacoes", {"nome": "C", "status": "aprovada"}, h)
        _post(client, f"/criacoes/{c['id']}/acordes",
              {"itens": [{"essencia_id": ids[n], "peso": p} for n, p in itens]}, h)
        col = _post(client, f"/colecoes/{col['id']}/criacoes", {"criacao_id": c["id"]}, h)
    sem_acorde = _post(client, "/criacoes", {"nome": "Sem acorde", "status": "aprovada"}, h)
    col = _post(client, f"/colecoes/{col['id']}/criacoes", {"criacao_id": sem_acorde["id"]}, h)

    ident = col["identidade_geral"]
    assert ident["criacoes"] == 3 and ident["criacoes_com_acorde"] == 2
    assert ident["vetor_medio"]["v1"] is not None and ident["familias"]
    assert isinstance(ident["territorios"], list)


# --------------------------------------- toda rota nova também exige login
PUBLICAS = {("POST", "/auth/register"), ("POST", "/auth/login"), ("POST", "/auth/verificar-email"),
            ("POST", "/auth/reenviar-codigo"), ("POST", "/auth/esqueci-senha"),
            ("POST", "/auth/redefinir-senha"), ("GET", "/health"), ("GET", "/health/ready")}


def test_toda_rota_exige_token(client):
    """Varredura do OpenAPI: uma rota nova esquecida sem proteção quebra este teste."""
    desprotegidas = []
    for path, metodos in app.openapi()["paths"].items():
        for metodo in metodos:
            if (metodo.upper(), path) in PUBLICAS:
                continue
            url = re.sub(r"\{\w+\}", "1", path)
            r = client.request(metodo.upper(), url, json={})
            if r.status_code != 401:
                desprotegidas.append((metodo.upper(), path, r.status_code))
    assert not desprotegidas
