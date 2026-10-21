"""ISOLAMENTO ENTRE USUÁRIAS — o teste mais importante do projeto.

O MySQL não tem Row Level Security: se algum caminho da aplicação esquecer o
filtro por dona, nada no banco impede o vazamento. Estes testes provam, pela
API, que a usuária B não consegue LER, EDITAR, APAGAR nem USAR (como insumo de
outra operação) nenhum registro da usuária A — mesmo sabendo o id exato.

Todo acesso negado responde 404 (e não 403): B não consegue nem descobrir se
o id existe.
"""

import pytest

from app.models.repertorio import Essencia
from app.repositories.repertorio import AcordeRepository, EssenciaRepository
from tests.util import essencia_antiga


@pytest.fixture()
def cenario(client, nova_usuaria):
    """A com um repertório completo; B recém-criada."""
    a = nova_usuaria("a@exemplo.com", nome="A")
    b = nova_usuaria("b@exemplo.com", nome="B")

    def post(url, json, h=a):
        r = client.post(url, json=json, headers=h)
        assert r.status_code == 201, r.text
        return r.json()

    e1 = essencia_antiga(client, a, {"nome": "Bergamota", "familia": "Cítrico", "v1": 2, "v2": 1, "v3": 3, "v4": 6},
                         "Cítrico", "fria").json()
    e2 = essencia_antiga(client, a, {"nome": "Jasmim", "familia": "Floral", "v1": 6, "v2": 5, "v3": 6, "v4": 7}).json()
    perfil = post("/perfis", {"respostas": {"emocoes": ["amor"], "publico": "teen"}})
    criacao = post("/criacoes", {"nome": "Primavera", "perfil_id": perfil["id"]})
    acorde = post(
        f"/criacoes/{criacao['id']}/acordes",
        {"itens": [{"essencia_id": e1["id"], "peso": "pouco"}, {"essencia_id": e2["id"], "peso": 3}]},
    )
    teste = post(f"/criacoes/{criacao['id']}/testes", {"acorde_id": acorde["id"], "nota": 8})
    referencia = post("/referencias", {"nome": "Perfume X", "notas_conhecidas": ["jasmim"]})
    r = client.put(f"/criacoes/{criacao['id']}", json={"status": "aprovada"}, headers=a)
    assert r.status_code == 200
    colecao = post("/colecoes", {"nome": "Verão"})
    post(f"/colecoes/{colecao['id']}/criacoes", {"criacao_id": criacao["id"]})

    return {
        "a": a, "b": b, "essencia": e1, "essencia2": e2, "perfil": perfil, "criacao": criacao,
        "acorde": acorde, "teste": teste, "referencia": referencia, "colecao": colecao,
    }


def test_b_ve_listas_vazias(client, cenario):
    for rota in ["/essencias", "/criacoes", "/referencias", "/perfis", "/colecoes"]:
        assert client.get(rota, headers=cenario["b"]).json() == [], rota


def test_b_nao_le_registros_de_a(client, cenario):
    c, b = cenario, cenario["b"]
    cid = c["criacao"]["id"]
    rotas = [
        f"/essencias/{c['essencia']['id']}",
        f"/criacoes/{cid}",
        f"/criacoes/{cid}/acordes",
        f"/criacoes/{cid}/acordes/{c['acorde']['id']}",
        f"/criacoes/{cid}/testes",
        f"/criacoes/{cid}/testes/{c['teste']['id']}",
        f"/referencias/{c['referencia']['id']}",
        f"/perfis/{c['perfil']['id']}",
        f"/perfis/{c['perfil']['id']}/recomendacoes",
        f"/colecoes/{c['colecao']['id']}",
    ]
    for rota in rotas:
        assert client.get(rota, headers=c["a"]).status_code == 200, f"A deveria ler {rota}"
        r = client.get(rota, headers=b)
        assert r.status_code == 404, f"B leu {rota}: {r.status_code}"


def test_b_nao_edita_nem_apaga_registros_de_a(client, cenario):
    c, b = cenario, cenario["b"]
    edicoes = [
        (f"/essencias/{c['essencia']['id']}", {"nome": "hackeada"}),
        (f"/criacoes/{c['criacao']['id']}", {"nome": "hackeada"}),
        (f"/referencias/{c['referencia']['id']}", {"nome": "hackeada"}),
        (f"/perfis/{c['perfil']['id']}", {"respostas": {"emocoes": []}}),
        (f"/colecoes/{c['colecao']['id']}", {"nome": "hackeada"}),
        (f"/colecoes/{c['colecao']['id']}/ordem", {"criacao_ids": [c["criacao"]["id"]]}),
    ]
    for rota, corpo in edicoes:
        assert client.put(rota, json=corpo, headers=b).status_code == 404, rota

    remocoes = [
        f"/colecoes/{c['colecao']['id']}/criacoes/{c['criacao']['id']}",
        f"/essencias/{c['essencia']['id']}",
        f"/referencias/{c['referencia']['id']}",
        f"/perfis/{c['perfil']['id']}",
        f"/colecoes/{c['colecao']['id']}",
        f"/criacoes/{c['criacao']['id']}",
    ]
    for rota in remocoes:
        assert client.delete(rota, headers=b).status_code == 404, rota

    # Os dados de A continuam intactos.
    a = c["a"]
    assert client.get(f"/essencias/{c['essencia']['id']}", headers=a).json()["nome"] == "Bergamota"
    assert client.get(f"/criacoes/{c['criacao']['id']}", headers=a).json()["nome"] == "Primavera"
    col = client.get(f"/colecoes/{c['colecao']['id']}", headers=a).json()
    assert col["nome"] == "Verão" and len(col["itens"]) == 1
    assert len(client.get(f"/criacoes/{c['criacao']['id']}/acordes", headers=a).json()) == 1


def test_b_nao_usa_dados_de_a_como_insumo(client, cenario):
    """Mesmo dentro dos PRÓPRIOS recursos, B não pode referenciar ids de A."""
    c, b = cenario, cenario["b"]

    def post(url, json):
        return client.post(url, json=json, headers=b)

    # Criar acorde/teste/ajuste na criação de A.
    cid_a = c["criacao"]["id"]
    itens_a = {"itens": [{"essencia_id": c["essencia"]["id"], "peso": 1},
                         {"essencia_id": c["essencia2"]["id"], "peso": 1}]}
    assert post(f"/criacoes/{cid_a}/acordes", itens_a).status_code == 404
    assert post(f"/criacoes/{cid_a}/testes", {"nota": 1}).status_code == 404
    assert post(f"/criacoes/{cid_a}/acordes/{c['acorde']['id']}/ajuste",
                {"movimento": "mais_fresco"}).status_code == 404

    # Criação própria de B usando o perfil de A.
    assert post("/criacoes", {"nome": "x", "perfil_id": c["perfil"]["id"]}).status_code == 404

    # Acorde na criação de B com essências de A (regra 3: só o repertório dela).
    criacao_b = post("/criacoes", {"nome": "Minha"}).json()
    r = post(f"/criacoes/{criacao_b['id']}/acordes", itens_a)
    assert r.status_code == 404
    assert "repertório" in r.json()["detail"]

    # Teste na criação de B apontando para o acorde de A.
    r = post(f"/criacoes/{criacao_b['id']}/testes", {"acorde_id": c["acorde"]["id"]})
    assert r.status_code == 404

    # Coleção de B recebendo a criação (aprovada) de A.
    colecao_b = post("/colecoes", {"nome": "Minha"}).json()
    r = post(f"/colecoes/{colecao_b['id']}/criacoes", {"criacao_id": cid_a})
    assert r.status_code == 404


def test_posse_nao_pode_ser_informada_no_corpo(client, cenario):
    """`user_id`/`criacao_id` no corpo são rejeitados (422), nunca aceitos."""
    b = cenario["b"]
    r = client.post("/essencias", json={"nome": "x", "user_id": 1}, headers=b)
    assert r.status_code == 422
    r = client.put(f"/essencias/{cenario['essencia']['id']}", json={"user_id": 2},
                   headers=cenario["a"])
    assert r.status_code == 422


def test_motor_de_b_nao_enxerga_repertorio_de_a(client, cenario):
    b = cenario["b"]
    lacunas = client.get("/essencias/lacunas", headers=b).json()
    assert [lac["tipo"] for lac in lacunas] == ["repertorio_vazio"]

    perfil_b = client.post("/perfis", json={"respostas": {"emocoes": ["amor"]}}, headers=b).json()
    rec = client.get(f"/perfis/{perfil_b['id']}/recomendacoes", headers=b).json()
    assert rec["recomendacoes"] == []

    # E as recomendações de A são só de A.
    rec_a = client.get(f"/perfis/{cenario['perfil']['id']}/recomendacoes",
                       headers=cenario["a"]).json()
    ids_a = {cenario["essencia"]["id"], cenario["essencia2"]["id"]}
    assert {r["essencia_id"] for r in rec_a["recomendacoes"]} <= ids_a


@pytest.mark.parametrize("metodo", ["post", "put", "delete", "patch"])
@pytest.mark.parametrize(
    "rota", ["/conhecimento/familias", "/conhecimento/notas", "/conhecimento/regras",
             "/conhecimento/relacoes", "/conhecimento/mapas"]
)
def test_conhecimento_nao_aceita_escrita(client, nova_usuaria, metodo, rota):
    h = nova_usuaria("k@exemplo.com")
    r = getattr(client, metodo)(rota, headers=h)
    assert r.status_code == 405, (metodo, rota, r.status_code)


# ------------------------------------------------ nível de repositório
def test_repositorio_exige_dona(db):
    for invalido in (None, 0, -1, True, "1"):
        with pytest.raises(ValueError):
            EssenciaRepository(db, invalido)


def test_repositorio_forca_dona_no_insert_e_filtra_leitura(client, cenario, db):
    """Mesmo um service descuidado não consegue gravar/ler como outra usuária."""
    id_a = client.get("/auth/me", headers=cenario["a"]).json()["id"]
    id_b = client.get("/auth/me", headers=cenario["b"]).json()["id"]

    repo_b = EssenciaRepository(db, id_b)
    intrusa = Essencia(user_id=id_a, nome="Intrusa", nome_canonico="intrusa")
    repo_b.add(intrusa)
    db.commit()
    assert intrusa.user_id == id_b  # user_id foi sobrescrito pela dona do repo

    assert repo_b.get(cenario["essencia"]["id"]) is None
    assert cenario["essencia"]["id"] not in repo_b.get_many([cenario["essencia"]["id"]])
    assert AcordeRepository(db, id_b).get(cenario["criacao"]["id"], cenario["acorde"]["id"]) is None
    assert AcordeRepository(db, id_a).get(cenario["criacao"]["id"], cenario["acorde"]["id"]) is not None


# ---------------------------------------------------------------------------
# Motor de criação ("O que você quer criar?")
# ---------------------------------------------------------------------------
def _pedido():
    return {"genero": "feminino", "idade": 15, "emocoes": ["amor", "paz"], "preferencias": ["doce", "floral"]}


@pytest.fixture()
def cenario_sugestao(client, nova_usuaria):
    """A com repertório e uma criação nascida de uma sugestão; B recém-criada."""
    from tests.test_sugestao_api import cadastrar

    a = nova_usuaria("sa@exemplo.com", nome="A")
    b = nova_usuaria("sb@exemplo.com", nome="B")
    ids = cadastrar(client, a)
    r = client.post("/criacoes", json={"nome": "Luna", "sugestao": _pedido()}, headers=a)
    assert r.status_code == 201, r.text
    return {"a": a, "b": b, "ids": ids, "criacao": r.json()}


def test_sugestao_de_b_nunca_usa_essencia_de_a(client, cenario_sugestao):
    c = cenario_sugestao
    r = client.post("/criacoes/sugerir", json=_pedido(), headers=c["b"])
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "insuficiente" and corpo["acorde"] is None  # usuária sem essências
    # A, com o mesmo pedido, recebe acorde: a diferença é só o repertório.
    assert client.post("/criacoes/sugerir", json=_pedido(), headers=c["a"]).json()["acorde"]["itens"]


def test_b_nao_passa_ids_de_a_em_essencias_disponiveis(client, cenario_sugestao):
    c = cenario_sugestao
    alheios = list(c["ids"].values())[:3]
    r = client.post("/criacoes/sugerir", json={**_pedido(), "essencias_disponiveis": alheios}, headers=c["b"])
    assert r.status_code == 404
    # misturar id próprio com id alheio também é recusado por inteiro
    proprio = essencia_antiga(client, c["b"], {"nome": "Minha"}).json()["id"]
    r = client.post("/criacoes/sugerir", json={**_pedido(), "essencias_disponiveis": [proprio, alheios[0]]},
                    headers=c["b"])
    assert r.status_code == 404


def test_b_nao_cria_criacao_com_essencias_de_a(client, cenario_sugestao):
    c = cenario_sugestao
    r = client.post("/criacoes", json={"nome": "X", "sugestao": {**_pedido(),
                    "essencias_disponiveis": list(c["ids"].values())}}, headers=c["b"])
    assert r.status_code == 404
    assert client.get("/criacoes", headers=c["b"]).json() == []


def test_b_nao_le_perfil_criacao_nem_acorde_nascidos_da_sugestao_de_a(client, cenario_sugestao):
    c = cenario_sugestao
    cid = c["criacao"]["id"]
    perfil_id = c["criacao"]["direcao"]["perfil_id"]
    acorde_id = client.get(f"/criacoes/{cid}/acordes", headers=c["a"]).json()[0]["id"]
    for rota in (f"/criacoes/{cid}", f"/criacoes/{cid}/acordes", f"/criacoes/{cid}/acordes/{acorde_id}",
                 f"/perfis/{perfil_id}"):
        assert client.get(rota, headers=c["a"]).status_code == 200, rota
        assert client.get(rota, headers=c["b"]).status_code == 404, rota
    assert client.get("/perfis", headers=c["b"]).json() == []


def test_usuaria_nova_comeca_com_repertorio_vazio(client, nova_usuaria):
    h = nova_usuaria("nova@exemplo.com")
    assert client.get("/essencias", headers=h).json() == []
    assert client.post("/criacoes/sugerir", json=_pedido(), headers=h).json()["status"] == "insuficiente"
