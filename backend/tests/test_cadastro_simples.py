"""Cadastro simples de essência (Nome + Família + Percepção): derivação, API e isolamento."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.engine.essencia_simples import (
    derivar,
    papel_em_fracao,
    percepcao_de_v1,
    valores_da_nota,
)
from app.seed.data_criacao import REGRAS_CRIACAO

REGRAS: dict[str, dict] = {}
for _t, _c, _v, _ in REGRAS_CRIACAO:
    REGRAS.setdefault(_t, {})[_c] = _v
GRUPOS = REGRAS["criacao_territorio"]
PERC = REGRAS["peso_score"]["percepcao"]
# Todas as famílias cadastradas na base (14 de topo + a subfamília Floral Branco), na ordem do banco.
FAMILIAS_DA_BASE = ["Cítrico", "Floral", "Floral Branco", "Amadeirado", "Ambarado", "Aromático", "Frutado", "Verde",
                    "Aquático/Marinho", "Gourmand", "Especiado", "Chipre", "Almiscarado", "Fougère", "Couro"]


def d(grupo, percepcao):
    return derivar(GRUPOS[grupo]["perfil"], percepcao, PERC)


# ------------------------------------------------------- derivação (funções puras)
def test_fresco_fria():
    r = d("fresco", "fria")
    assert (r.v1, r.v2, r.v3, r.v4, r.v5) == (3, 2, 3, 6, 4)
    assert r.papel == {"saida": 0.88, "coracao": 0.12, "fundo": 0.0}
    assert (r.confianca, r.origem, r.tipo) == ("baixa", "estimado", "desconhecida")


def test_gourmand_quente():
    r = d("gourmand_doce", "quente")
    assert (r.v1, r.v2, r.v3, r.v4) == (8, 8, 8, 5)
    assert r.papel == {"saida": 0.0, "coracao": 0.15, "fundo": 0.85}


@pytest.mark.parametrize("grupo", list(GRUPOS))
@pytest.mark.parametrize("percepcao", ["fria", "neutra", "quente"])
def test_papel_soma_100_e_valores_ficam_em_0_a_10(grupo, percepcao):
    r = d(grupo, percepcao)
    assert round(sum(r.papel.values()), 9) == 1.0
    assert all(0 <= x <= 10 for x in (r.v1, r.v2, r.v3, r.v4, r.v5))
    assert all(0 <= x <= 1 for x in r.papel.values())


def test_percepcao_muda_so_a_temperatura():
    assert [d("floral", p).v1 for p in ("fria", "neutra", "quente")] == [3, 5, 8]
    assert d("floral", "fria").v2 == d("floral", "quente").v2 == 5


def test_conversao_de_v1_em_percepcao_nos_limites():
    assert [percepcao_de_v1(x, PERC) for x in (0, 3.5, 3.6, 6.5, 6.6, 10)] == \
        ["fria", "fria", "neutra", "neutra", "quente", "quente"]
    assert percepcao_de_v1(None, PERC) is None


def test_papel_malformado_falha_alto():
    with pytest.raises(ValueError):
        papel_em_fracao({"saida": 50, "coracao": 40, "fundo": 5})


def test_nota_incompleta_nao_serve_para_preencher():
    assert valores_da_nota({"v1": 2, "v2": None, "v3": 3, "v4": 4}, {"saida": 1}, "simples", "alta", 4) is None
    assert valores_da_nota({"v1": 2, "v2": 1, "v3": 3, "v4": 4}, None, "simples", "alta", 4) is None


def test_os_8_grupos_tem_perfil_completo_no_seed():
    assert len(GRUPOS) == 8 and all({"v2", "v3", "v4", "papel"} <= set(g["perfil"]) for g in GRUPOS.values())


# --------------------------------------------------------------------- API
def cadastrar(client, h, nome="Rosa", familia="Floral", percepcao="neutra", **extra):
    return client.post("/essencias", headers=h, json={"nome": nome, "familia": familia, "percepcao": percepcao, **extra})


@pytest.fixture()
def h(client, nova_usuaria):
    return nova_usuaria("simples@exemplo.com")


def test_tres_campos_criam_a_essencia_completa(client, h):
    r = cadastrar(client, h, "  Rosa   Búlgara ", "Floral", "quente")
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["nome"] == "Rosa Búlgara" and e["familia"] == "Floral" and e["percepcao"] == "quente"
    assert (e["v1"], e["v2"], e["v3"], e["v4"], e["v5"]) == (8, 5, 5, 5, 4)
    assert e["papel"] == {"saida": 0.15, "coracao": 0.73, "fundo": 0.12}
    assert e["confianca"] == "baixa" and e["origem"] == "estimado" and e["tipo"] == "desconhecida"
    assert e["subfamilia"] is None and e["knowledge_note_id"] is None and e["favorito"] is False
    assert e["descritores"] == [] and e["tags"] == [] and e["fornecedor"] is None and e["observacoes"] is None


def test_campos_tecnicos_enviados_pelo_cliente_sao_ignorados(client, h):
    e = cadastrar(client, h, "Rosa", "Floral", "neutra", v1=0, v2=0, v3=0, v4=0, v5=0,
                  papel={"saida": 1, "coracao": 0, "fundo": 0}, confianca="alta", origem="tecnico",
                  tipo="simples", tags=["x"], favorito=True, fornecedor="F", subfamilia="Floral Branco",
                  descritores=["doce"], observacoes="obs", inventado=1)
    assert e.status_code == 201
    e = e.json()
    assert (e["v1"], e["v2"]) == (5, 5) and e["confianca"] == "baixa" and e["origem"] == "estimado"
    assert e["tags"] == [] and e["favorito"] is False and e["fornecedor"] is None and e["subfamilia"] is None
    editada = client.put(f"/essencias/{e['id']}", headers=h, json={"percepcao": "fria", "v1": 9, "confianca": "alta"}).json()
    assert editada["v1"] == 3 and editada["confianca"] == "baixa"


@pytest.mark.parametrize("corpo,trecho", [
    ({"nome": "", "familia": "Floral", "percepcao": "neutra"}, "nome da essência"),
    ({"nome": "   ", "familia": "Floral", "percepcao": "neutra"}, "nome da essência"),
    ({"nome": "A", "familia": "Floral", "percepcao": "neutra"}, "nome da essência"),
    ({"nome": "x" * 101, "familia": "Floral", "percepcao": "neutra"}, "nome da essência"),
    ({"nome": "Rosa", "familia": "", "percepcao": "neutra"}, "famílias da lista"),
    ({"nome": "Rosa", "familia": "Inventada", "percepcao": "neutra"}, "famílias da lista"),
    ({"nome": "Rosa", "familia": "Fresco", "percepcao": "neutra"}, "famílias da lista"),   # nome de grupo, não de família
    ({"nome": "Rosa", "familia": "Floral", "percepcao": ""}, "Fria, Neutra ou Quente"),
    ({"nome": "Rosa", "familia": "Floral", "percepcao": "morna"}, "Fria, Neutra ou Quente"),
    ({"nome": "Rosa"}, "famílias da lista"),
])
def test_erros_em_portugues_simples(client, h, corpo, trecho):
    r = client.post("/essencias", json=corpo, headers=h)
    assert r.status_code in (400, 422), r.text
    assert trecho in r.text
    assert client.get("/essencias", headers=h).json() == []     # nada foi gravado


def test_aceita_maiusculas_e_acentos_nas_escolhas(client, h):
    assert cadastrar(client, h, "Doce", "GOURMAND", "Quente").status_code == 201
    assert cadastrar(client, h, "Marinha", "aquatico", "FRIA").status_code == 201      # parte do nome "Aquático/Marinho"


def test_opcoes_trazem_todas_as_familias_da_base_na_ordem_dela(client, h):
    o = client.get("/essencias/opcoes", headers=h).json()
    assert [f["nome"] for f in o["familias"]] == FAMILIAS_DA_BASE
    assert [f["nome"] for f in client.get("/conhecimento/familias", headers=h).json()] == FAMILIAS_DA_BASE
    assert [p["nome"] for p in o["percepcoes"]] == ["Fria", "Neutra", "Quente"]


def test_lista_traz_familia_e_percepcao(client, h):
    cadastrar(client, h, "Rosa", "Floral", "quente")
    [e] = client.get("/essencias", headers=h).json()
    assert e["familia"] == "Floral" and e["percepcao"] == "quente"


# ------------------------------------------------- reconhecimento pelo nome
def sugestao(client, h, nome):
    return client.get("/essencias/sugestao", params={"nome": nome}, headers=h).json()


def test_nome_igual_a_uma_nota_sugere_familia_e_percepcao(client, h):
    s = sugestao(client, h, "  BERGAMOTA ")
    assert s["encontrada"] and s["nivel"] == "exata" and s["nota_nome"] == "Bergamota"
    assert (s["familia"], s["percepcao"]) == ("Cítrico", "fria")     # família real da nota; v1_ref 2,0 -> Fria
    assert sugestao(client, h, "jasmin")["encontrada"] is True        # sinônimo
    assert sugestao(client, h, "Jasmim")["familia"] == "Floral Branco"      # a nota é da subfamília


def test_nome_parecido_devolve_nivel_parecida(client, h):
    s = sugestao(client, h, "Bergamota Calabresa")
    assert s["encontrada"] and s["nivel"] == "parecida" and s["nota_nome"] == "Bergamota"


def test_nome_desconhecido_nao_encontra(client, h):
    assert sugestao(client, h, "Nuvem Azul") == {
        "encontrada": False, "nivel": None, "nota_id": None, "nota_nome": None,
        "familia": None, "percepcao": None, "aviso_educativo": None}


def test_aviso_educativo_vem_da_observacao_da_nota(client, h):
    s = sugestao(client, h, "Âmbar")
    assert s["familia"] == "Ambarado" and s["percepcao"] == "quente"
    assert s["aviso_educativo"] and "fornecedor" in s["aviso_educativo"]
    assert sugestao(client, h, "Bergamota")["aviso_educativo"] is None


def test_sugerir_nunca_grava_nada(client, h):
    sugestao(client, h, "Bergamota")
    assert client.get("/essencias", headers=h).json() == []


def test_nota_de_exemplo_mantida_vincula_mas_nao_copia_numeros(client, h):
    s = sugestao(client, h, "Bergamota")
    e = cadastrar(client, h, "Bergamota", s["familia"], s["percepcao"], aceitou_nota_id=s["nota_id"]).json()
    assert e["knowledge_note_id"] == s["nota_id"] and e["editado_da_referencia"] is False
    assert e["tipo"] == "simples"                                        # tipo da nota, vínculo mantido
    assert (e["v1"], e["v2"], e["v3"], e["v4"]) == (3, 2, 3, 6)          # derivação (a nota é de exemplo)
    assert e["confianca"] == "baixa" and e["origem"] == "estimado"


def test_aluna_muda_a_sugestao_vinculo_fica_e_marca_editado(client, h):
    s = sugestao(client, h, "Bergamota")
    e = cadastrar(client, h, "Bergamota", "Floral", s["percepcao"], aceitou_nota_id=s["nota_id"]).json()
    assert e["knowledge_note_id"] == s["nota_id"] and e["editado_da_referencia"] is True
    assert e["familia"] == "Floral" and e["tipo"] == "desconhecida" and e["v2"] == 5


def test_sem_aceitar_a_nota_nao_ha_vinculo(client, h):
    e = cadastrar(client, h, "Bergamota", "Cítrico", "fria").json()
    assert e["knowledge_note_id"] is None and e["editado_da_referencia"] is False


def test_nota_inexistente_e_404(client, h):
    assert cadastrar(client, h, "Rosa", "Floral", "neutra", aceitou_nota_id=99999).status_code == 404


def test_nota_validada_mantida_usa_os_valores_e_a_confianca_dela(client, h, nota_validada):
    # nota_validada: Cedro, Amadeirado, v1_ref 5,0 (Neutra), v2 8, v3 2, v4 5, confiança alta
    e = cadastrar(client, h, "Cedro", "Amadeirado", "neutra", aceitou_nota_id=nota_validada).json()
    assert (e["v1"], e["v2"], e["v3"], e["v4"]) == (5, 8, 2, 5) and e["v5"] == 4
    assert e["papel"] == {"saida": 0.0, "coracao": 0.2, "fundo": 0.8}
    assert e["confianca"] == "alta" and e["origem"] == "inferido" and e["tipo"] == "simples"
    assert e["editado_da_referencia"] is False and e["knowledge_note_id"] == nota_validada


def test_nota_validada_com_sugestao_alterada_usa_a_derivacao(client, h, nota_validada):
    e = cadastrar(client, h, "Cedro", "Amadeirado", "quente", aceitou_nota_id=nota_validada).json()
    assert e["v1"] == 8 and e["v2"] == 7 and e["confianca"] == "baixa" and e["origem"] == "estimado"
    assert e["editado_da_referencia"] is True and e["knowledge_note_id"] == nota_validada


# ------------------------------------------------------------------- edição
def test_editar_familia_ou_percepcao_recalcula(client, h):
    e = cadastrar(client, h, "Rosa", "Floral", "neutra").json()
    r = client.put(f"/essencias/{e['id']}", headers=h, json={"familia": "Gourmand", "percepcao": "quente"}).json()
    assert (r["familia"], r["percepcao"]) == ("Gourmand", "quente")
    assert (r["v1"], r["v2"], r["v3"], r["v4"]) == (8, 8, 8, 5)
    assert r["papel"] == {"saida": 0.0, "coracao": 0.15, "fundo": 0.85}
    so_perc = client.put(f"/essencias/{e['id']}", headers=h, json={"percepcao": "fria"}).json()
    assert so_perc["v1"] == 3 and so_perc["v2"] == 8 and so_perc["familia"] == "Gourmand"


def test_trocar_so_o_nome_ou_reenviar_o_mesmo_nao_mexe_nos_numeros(client, h):
    e = cadastrar(client, h, "Rosa", "Floral", "neutra").json()
    from tests.util import definir_tecnico
    definir_tecnico(e["id"], v2=9.5)                       # ajuste fino antigo
    r = client.put(f"/essencias/{e['id']}", headers=h,
                   json={"nome": "Rosa Nova", "familia": "Floral", "percepcao": "neutra"}).json()
    assert r["nome"] == "Rosa Nova" and r["v2"] == 9.5
    r = client.put(f"/essencias/{e['id']}", headers=h, json={"nome": "Outra"}).json()
    assert r["nome"] == "Outra" and r["v2"] == 9.5


def test_essencia_antiga_continua_abrindo_e_na_edicao_usa_a_familia_da_base(client, h):
    from tests.util import essencia_antiga
    antiga = essencia_antiga(client, h, {"nome": "Antiga", "familia": "Cítrico", "v1": 2, "v2": 1, "v3": 3, "v4": 6,
                                         "percepcao": None}).json()
    assert client.get(f"/essencias/{antiga['id']}", headers=h).json()["familia"] == "Cítrico"
    assert client.put(f"/essencias/{antiga['id']}", headers=h, json={"nome": "Antiga 2"}).status_code == 200
    r = client.put(f"/essencias/{antiga['id']}", headers=h, json={"percepcao": "fria"}).json()
    assert r["familia"] == "Cítrico" and r["percepcao"] == "fria"          # família reconhecida e mantida
    solta = essencia_antiga(client, h, {"nome": "Solta", "familia": "Texto livre", "v1": 5}).json()
    bad = client.put(f"/essencias/{solta['id']}", headers=h, json={"percepcao": "fria"})
    assert bad.status_code in (400, 422) and "famílias da lista" in bad.text    # texto livre: escolhe da lista
    ok = client.put(f"/essencias/{solta['id']}", headers=h, json={"familia": "Floral"}).json()
    assert ok["familia"] == "Floral" and ok["percepcao"] == "neutra"            # percepção vinda do v1 antigo (5)


def test_cada_familia_da_base_cadastra_e_a_subfamilia_vai_para_o_campo_certo(client, h):
    for nome in FAMILIAS_DA_BASE:
        r = cadastrar(client, h, f"Essência {nome}", nome, "neutra")
        assert r.status_code == 201, (nome, r.text)
        e = r.json()
        assert round(sum(e["papel"].values()), 9) == 1.0 and 0 <= e["v2"] <= 10
    fb = client.get("/essencias", headers=h).json()
    branco = next(e for e in fb if e["nome"] == "Essência Floral Branco")
    assert (branco["familia"], branco["subfamilia"]) == ("Floral", "Floral Branco")
    assert branco["v2"] == 5                                                   # perfil do grupo Floral (herdado da mãe)
    assert next(e for e in fb if e["nome"] == "Essência Verde")["v2"] == 2     # Verde usa o perfil do grupo Fresco
    assert next(e for e in fb if e["nome"] == "Essência Couro")["v2"] == 8     # Couro usa o do grupo Âmbar/Envolvente


def test_essencia_com_a_familia_real_e_reconhecida_pelo_motor(client, h):
    ids = [cadastrar(client, h, n, f, p).json()["id"] for n, f, p in
           (("Bergamota", "Cítrico", "fria"), ("Jasmim", "Floral Branco", "neutra"))]
    c = client.post("/essencias/compatibilidade", headers=h, json={"essencia_ids": ids}).json()
    assert c["pares_avaliados"] == 1


def test_edicao_com_valores_invalidos(client, h):
    e = cadastrar(client, h, "Rosa", "Floral", "neutra").json()
    for corpo in ({"nome": ""}, {"familia": "Nada"}, {"percepcao": "morna"}):
        assert client.put(f"/essencias/{e['id']}", headers=h, json=corpo).status_code in (400, 422), corpo


# ------------------------------------------------- uso pelo motor de criação
def test_essencias_simples_alimentam_o_motor_sem_avisos_por_essencia(client, h):
    for nome, fam, perc in (("Pera", "Frutado", "neutra"), ("Peônia", "Floral", "neutra"), ("Rosa", "Floral", "neutra"),
                            ("Lavanda", "Aromático", "fria"), ("Musk", "Almiscarado", "neutra"),
                            ("Baunilha", "Gourmand", "quente"), ("Sândalo", "Amadeirado", "quente")):
        assert cadastrar(client, h, nome, fam, perc).status_code == 201
    r = client.post("/criacoes/sugerir", headers=h, json={
        "emocoes": ["amor", "paz"], "preferencias": ["doce", "floral"], "intensidade": 4}).json()
    assert r["status"] == "ok" and r["acorde"]["itens"]
    textos = " ".join(r["avisos"])
    assert "Ficaram de fora" not in textos and "classifique" not in textos.lower()
    # Todas as essências são de confiança baixa: UMA frase suave, sem jargão.
    suave = [a for a in r["avisos"] if "reconhecidas pela nossa base" in a]
    assert len(suave) == 1 and not any(t in suave[0].lower() for t in ("confiança", "score", "vetor"))
    # Percepção/dados técnicos não vazam para a resposta mostrada.
    assert "v1" not in str({k: v for k, v in r.items() if k != "tecnico"})


def test_motor_reconhece_o_grupo_como_familia_para_compatibilidade(client, h):
    ids = [cadastrar(client, h, n, f, p).json()["id"] for n, f, p in
           (("Bergamota", "Cítrico", "fria"), ("Jasmim", "Floral", "neutra"))]
    c = client.post("/essencias/compatibilidade", headers=h, json={"essencia_ids": ids}).json()
    assert c["score"] is not None and c["pares_avaliados"] == 1    # Fresco(cítrico) × Floral: relação cadastrada


def test_formulacao_funciona_com_essencias_simples(client, h):
    for n, f, p in (("Pera", "Frutado", "neutra"), ("Rosa", "Floral", "neutra"), ("Baunilha", "Gourmand", "quente")):
        cadastrar(client, h, n, f, p)
    r = client.post("/formulacoes/propor", headers=h, json={
        "produto": "body_splash", "concentracao_pct": 10, "volume_ml": 100,
        "descricao": "algo doce e floral"}).json()
    assert r["formulacao"] and r["formulacao"]["valido"] and r["formulacao"]["concentrado_ml"] == 10.0


# --------------------------------------------------------------- isolamento
def test_b_nao_le_edita_nem_apaga_essencia_de_a(client, nova_usuaria):
    a, b = nova_usuaria("a1@exemplo.com"), nova_usuaria("b1@exemplo.com")
    e = cadastrar(client, a, "Zorba", "Floral", "neutra").json()
    assert client.get(f"/essencias/{e['id']}", headers=b).status_code == 404
    assert client.put(f"/essencias/{e['id']}", headers=b, json={"nome": "Hackeada"}).status_code == 404
    assert client.put(f"/essencias/{e['id']}", headers=b, json={"familia": "Cítrico"}).status_code == 404
    assert client.delete(f"/essencias/{e['id']}", headers=b).status_code == 404
    assert client.get(f"/essencias/{e['id']}", headers=a).json()["nome"] == "Zorba"


def test_sugestao_de_b_nao_enxerga_o_repertorio_de_a(client, nova_usuaria):
    a, b = nova_usuaria("a2@exemplo.com"), nova_usuaria("b2@exemplo.com")
    cadastrar(client, a, "Zorba Exclusiva", "Floral", "neutra")
    assert sugestao(client, b, "Zorba Exclusiva")["encontrada"] is False
    assert sugestao(client, a, "Zorba Exclusiva")["encontrada"] is False   # nem A: sugestão vem só da base
    assert client.get("/essencias", headers=b).json() == []


def test_usuaria_nova_comeca_vazia_e_o_cadastro_nao_cria_nada_sozinho(client, nova_usuaria):
    h = nova_usuaria("nova2@exemplo.com")
    assert client.get("/essencias", headers=h).json() == []
    client.get("/essencias/opcoes", headers=h)
    sugestao(client, h, "Bergamota")
    assert client.get("/essencias", headers=h).json() == []


def test_cliente_nao_informa_posse(client, h):
    assert client.post("/essencias", headers=h, json={"nome": "Rosa", "familia": "Floral", "percepcao": "neutra",
                                                      "user_id": 1}).status_code == 422


def test_exige_login(client):
    assert client.get("/essencias/opcoes").status_code in (401, 403)
    assert client.get("/essencias/sugestao", params={"nome": "x"}).status_code in (401, 403)


# --------------------------------------------------------------- migration
def test_migration_0012_gera_a_derivacao_e_e_reversivel():
    """Gera o SQL offline (sem banco) da subida e da descida da migration 0012."""
    raiz = Path(__file__).resolve().parents[1]
    def sql(intervalo, *args):
        r = subprocess.run([sys.executable, "-m", "alembic", *args, intervalo, "--sql"], cwd=raiz,
                           capture_output=True, text=True, env={**__import__("os").environ, "DATABASE_URL":
                           "mysql+pymysql://u:p@localhost/x", "JWT_SECRET_KEY": "x" * 40}, timeout=60)
        assert r.returncode == 0, r.stderr[-600:]
        return r.stdout
    subida = sql("0011:0012", "upgrade")
    assert "ADD COLUMN percepcao" in subida
    assert "SET percepcao='fria' WHERE essencias.v1 <= 3.5" in subida
    assert "SET percepcao='neutra' WHERE essencias.v1 > 3.5 AND essencias.v1 <= 6.5" in subida
    assert "SET percepcao='quente' WHERE essencias.v1 > 6.5" in subida
    descida = sql("0012:0011", "downgrade")
    assert "DROP COLUMN percepcao" in descida
