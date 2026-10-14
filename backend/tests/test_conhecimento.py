"""Fase 1: conhecimento olfativo (famílias, características, doçura, marca de exemplo)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.knowledge import KnowledgeDescriptor, KnowledgeNote
from app.seed import popular
from app.services.motor import ContextoMotor

FAMILIAS_DA_CLIENTE = {
    "Cítrico", "Floral", "Amadeirado", "Ambarado", "Aromático", "Frutado", "Verde",
    "Aquático/Marinho", "Gourmand", "Especiado", "Chipre", "Almiscarado", "Fougère", "Couro",
}
CARACTERISTICAS = {
    "doce", "fresco", "cremoso", "atalcado", "limpo", "intenso", "seco", "balsâmico", "esfumaçado",
}


@pytest.fixture()
def h(nova_usuaria):
    return nova_usuaria("k@exemplo.com")


def _get(client, rota, h):
    r = client.get(rota, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_as_14_familias_estao_completas(client, h):
    familias = _get(client, "/conhecimento/familias", h)
    principais = {f["nome"] for f in familias if f["parent_id"] is None}
    assert principais == FAMILIAS_DA_CLIENTE
    assert not any(f["ilustrativo"] for f in familias)


def test_floral_branco_e_subfamilia_de_floral_e_nao_familia_principal(client, h):
    familias = _get(client, "/conhecimento/familias", h)
    por_id = {f["id"]: f for f in familias}
    branco = next(f for f in familias if f["nome"] == "Floral Branco")
    assert por_id[branco["parent_id"]]["nome"] == "Floral"
    # Hoje é a única subfamília definida; as demais dependem da lista da cliente.
    assert [f["nome"] for f in familias if f["parent_id"] is not None] == ["Floral Branco"]


def test_caracteristicas_sao_entidade_separada_das_familias(client, h):
    caracteristicas = {d["nome"] for d in _get(client, "/conhecimento/descritores", h)}
    assert caracteristicas == CARACTERISTICAS
    nomes_familias = {f["nome"].lower() for f in _get(client, "/conhecimento/familias", h)}
    assert caracteristicas.isdisjoint(nomes_familias)


def test_termo_antigo_do_vocabulario_e_desativado_e_nao_apagado(client, h, db):
    db.add(KnowledgeDescriptor(nome="luminoso", categoria="temperatura"))
    db.commit()
    popular(db)  # rodar o seed de novo desativa o que saiu do vocabulário
    assert "luminoso" not in {d["nome"] for d in _get(client, "/conhecimento/descritores", h)}
    antigo = db.query(KnowledgeDescriptor).filter_by(nome="luminoso").one()
    assert antigo.ativo is False


def test_conteudo_de_exemplo_vem_marcado_e_o_da_cliente_nao(client, h):
    notas = _get(client, "/conhecimento/notas", h)
    assert notas and all(n["ilustrativo"] for n in notas)
    assert all("EXEMPLO" in n["fonte"] for n in notas)
    assert all(r["ilustrativo"] for r in _get(client, "/conhecimento/relacoes", h))
    assert all(m["ilustrativo"] for m in _get(client, "/conhecimento/mapas", h))

    regras = _get(client, "/conhecimento/regras", h)
    por_tipo = {}
    for r in regras:
        por_tipo.setdefault(r["tipo"], set()).add(r["ilustrativo"])
    assert por_tipo["territorio"] == {False}  # nomes definidos pela cliente
    for tipo, marcas in por_tipo.items():
        if tipo != "territorio":
            assert marcas == {True}, tipo  # vetores, pesos e limites são calibração de exemplo

    territorios = _get(client, "/conhecimento/territorios", h)
    assert all(t["ilustrativo"] is False for t in territorios)


def test_sensualidade_existe_como_territorio_com_correlacao(client, h):
    chaves = {t["chave"] for t in _get(client, "/conhecimento/territorios", h)}
    assert "sensualidade" in chaves
    correlacoes = {r["chave"] for r in _get(client, "/conhecimento/regras?tipo=correlacao_territorio", h)}
    assert "sensualidade" in correlacoes


def test_docura_em_tres_niveis_nas_notas_e_check_no_banco(client, h, db):
    niveis = {n["docura_nivel_ref"] for n in _get(client, "/conhecimento/notas", h)}
    assert niveis <= {"baixa", "media", "alta", None} and niveis - {None}
    nota = db.query(KnowledgeNote).first()
    nota.docura_nivel_ref = "enjoativa"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_piramide_e_descritiva_e_a_essencia_pode_ficar_sem_nivel(client, h):
    niveis = _get(client, "/conhecimento/funcoes", h)
    assert [n["slug"] for n in niveis] == ["saida", "coracao", "fundo"]
    # "Não sei ainda": uma essência sem papel definido é aceita e o motor segue funcionando.
    e = client.post("/essencias", json={"nome": "Sem nível"}, headers=h)
    assert e.status_code == 201 and e.json()["papel"] is None
    assert client.get("/essencias/lacunas", headers=h).status_code == 200


def test_familia_com_barra_e_reconhecida_por_cada_parte(db):
    ctx = ContextoMotor(db)
    for texto in ("Aquático/Marinho", "aquatico", "Marinho", "Fougère", "fougere"):
        assert ctx.familia_por_texto(texto) is not None, texto
    assert ctx.familia_por_texto("Aquático").slug == "aquatico_marinho"


def test_seed_e_idempotente_e_nao_duplica_familias(client, h, db):
    popular(db)
    popular(db)
    assert len(_get(client, "/conhecimento/familias", h)) == 15  # 14 principais + Floral Branco


def test_nota_de_exemplo_nao_copia_numeros_para_a_essencia(client, h):
    sug = client.get("/essencias/sugestao-classificacao", params={"nome": "jasmim"}, headers=h).json()[0]
    e = client.post("/essencias", json={
        "nome": "Jasmim", "knowledge_note_id": sug["nota_id"], "aplicar_referencia": True,
    }, headers=h).json()
    assert e["familia"] == "Floral" and e["subfamilia"] == "Floral Branco"
    assert e["descritores"] == ["cremoso"]
    assert all(e[eixo] is None for eixo in ("v1", "v2", "v3", "v4", "v5", "v6")) and e["papel"] is None
    assert e["origem"] == "estimado" and e["confianca"] == "baixa"
