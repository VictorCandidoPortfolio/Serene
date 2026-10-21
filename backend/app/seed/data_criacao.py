"""Regras do MOTOR DE CRIAÇÃO ("O que você quer criar?") — ver app/engine/criacao.py.

TODOS os números abaixo são VALORES INICIAIS A CALIBRAR pela professora com
testes olfativos reais (heurística pedagógica, não ciência exata). Por isso
são gravados como `ilustrativo=True` e a descrição de cada regra começa com
"CALIBRAR". Calibrar = editar/inserir linhas em `knowledge_engine_rules`, sem
mexer em código; território, emoção ou faixa de idade novos são só INSERTs.

Formatos (contrato lido por app/engine/criacao.py):

- criacao_emocao / criacao_preferencia
      {"rotulo": str,                    # como aparece nas frases ("você pediu amor")
       "target": {eixo: deslocamento},   # somado ao vetor-alvo (v4 é IGNORADO ali:
                                         #   a presença vem da intensidade pedida)
       "terr": {território: pontos},     # somado ao placar de territórios
       só emoções: "atributo" (personalidade), "substantivo"/"adjetivo" (nome sugerido)}
- criacao_idade
      {"rotulo", "anos_de", "anos_ate",  # conversão número -> faixa (em dados)
       "delta": {eixo: n}, "v4_max": n|None, "max_itens": n}
- criacao_territorio
      {"nome", "familias": [slug de knowledge_families], "adjetivo", "atributo", "ordem"}
- criacao_vocabulario/identidade: faixas de adjetivos e frases-base dos textos
- peso_score/criacao_score e peso_score/criacao_padrao_pesos: parâmetros numéricos
"""

_CAL = "CALIBRAR (valor inicial). "


def _emo(chave, rotulo, target, terr, atributo, substantivo, adjetivo):
    return ("criacao_emocao", chave,
            {"rotulo": rotulo, "target": target, "terr": terr, "atributo": atributo,
             "substantivo": substantivo, "adjetivo": adjetivo},
            _CAL + f"Emoção '{rotulo}'.")


def _pref(chave, rotulo, target, terr):
    return ("criacao_preferencia", chave, {"rotulo": rotulo, "target": target, "terr": terr},
            _CAL + f"Preferência '{rotulo}'.")


_ALERTA_INFANTIL = (
    "Produto infantil: a fórmula calculada NÃO está aprovada para uso. Antes de qualquer teste é preciso "
    "avaliação de segurança específica para a faixa etária (limite de uso de cada ingrediente, alérgenos, "
    "teste dermatológico e documentação do fornecedor) e, quando aplicável, responsável técnico."
)


def _idade(chave, rotulo, de, ate, delta, v4_max, max_itens, infantil=False):
    return ("criacao_idade", chave,
            {"rotulo": rotulo, "anos_de": de, "anos_ate": ate, "delta": delta,
             "v4_max": v4_max, "max_itens": max_itens,
             "infantil": infantil, "alerta_seguranca": _ALERTA_INFANTIL if infantil else None},
            _CAL + f"Idade: {rotulo} ({de} a {ate} anos).")


def _terr(chave, nome, familias, adjetivo, atributo, ordem):
    return ("criacao_territorio", chave,
            {"nome": nome, "familias": familias, "adjetivo": adjetivo,
             "atributo": atributo, "ordem": ordem},
            _CAL + f"Território olfativo {nome}.")


REGRAS_CRIACAO = [
    # ------------------------------------------------------------- emoções
    _emo("amor", "amor", {"v3": 1}, {"Floral": 2}, "Romântica", "Amor", "Apaixonado"),
    _emo("paz", "paz", {"v1": -1, "v4": -1}, {"Aromático": 2}, "Calma", "Paz", "Tranquilo"),
    _emo("serenidade", "serenidade", {"v1": -1, "v4": -1}, {"Aromático": 2}, "Serena", "Serenidade", "Sereno"),
    _emo("delicadeza", "delicadeza", {"v4": -1, "v2": -1}, {"Floral": 1}, "Delicada", "Delicadeza", "Suave"),
    _emo("encanto", "encanto", {"v5": 1, "v3": 0.5}, {"Floral": 1, "Frutado": 1}, "Encantadora", "Encanto", "Encantado"),
    _emo("acolhimento", "acolhimento", {"v1": 1, "v3": 1}, {"Gourmand/Doce": 1, "Almiscarado": 1}, "Acolhedora", "Abraço", "Acolhedor"),
    _emo("alegria", "alegria", {"v3": 1}, {"Frutado": 2}, "Alegre", "Alegria", "Radiante"),
    _emo("renovacao", "renovação", {"v1": -1.5}, {"Fresco": 2, "Aromático": 1}, "Renovadora", "Renovo", "Renovado"),
    _emo("frescor", "frescor", {"v1": -2}, {"Fresco": 2}, "Fresca", "Frescor", "Fresco"),
    _emo("elegancia", "elegância", {"v5": 1}, {"Amadeirado": 1, "Floral": 1}, "Elegante", "Elegância", "Refinado"),
    _emo("magnetismo", "magnetismo", {"v4": 2}, {"Âmbar/Envolvente": 2}, "Magnética", "Magnetismo", "Envolvente"),
    _emo("romance", "romance", {"v3": 1, "v1": 0.5}, {"Floral": 2, "Âmbar/Envolvente": 1}, "Romântica", "Romance", "Apaixonado"),
    _emo("conforto", "conforto", {"v1": 1, "v3": 1}, {"Gourmand/Doce": 2}, "Aconchegante", "Conforto", "Aconchegante"),
    _emo("presenca", "presença", {"v4": 1, "v2": 1}, {"Amadeirado": 1, "Âmbar/Envolvente": 1}, "Marcante", "Presença", "Marcante"),
    _emo("energia", "energia", {"v1": -1, "v4": 1}, {"Frutado": 1, "Fresco": 1}, "Enérgica", "Energia", "Vibrante"),
    _emo("confianca", "confiança", {"v2": 0.5}, {"Amadeirado": 1, "Aromático": 1, "Fresco": 1},
         "Confiante", "Confiança", "Seguro"),
    _emo("liberdade", "liberdade", {"v1": -1, "v2": -1}, {"Fresco": 1, "Aromático": 1}, "Livre", "Liberdade", "Leve"),
    # -------------------------------------------------------- preferências
    _pref("doce", "doce", {"v3": 1}, {"Gourmand/Doce": 2}),
    _pref("citrico", "cítrico", {"v1": -1}, {"Fresco": 2}),
    _pref("floral", "floral", {}, {"Floral": 2}),
    _pref("frutado", "frutado", {}, {"Frutado": 2}),
    _pref("fresco", "fresco", {"v1": -1.5}, {"Fresco": 2}),
    _pref("amadeirado", "amadeirado", {"v2": 1}, {"Amadeirado": 2}),
    _pref("limpo", "limpo", {}, {"Almiscarado": 2}),
    _pref("cremoso", "cremoso", {"v3": 0.5, "v2": 0.5}, {"Almiscarado": 1, "Gourmand/Doce": 1}),
    _pref("aromatico", "aromático", {"v1": -0.5}, {"Aromático": 2}),
    # O v4 de "suave"/"marcante" é ignorado pelo motor (a presença vem da
    # intensidade): na interface, escolher uma delas MOVE o controle.
    _pref("marcante", "marcante", {"v4": 2}, {}),
    _pref("suave", "suave", {"v4": -2}, {}),
    _pref("sofisticado", "sofisticado", {"v5": 1, "v2": 0.5}, {"Amadeirado": 1, "Floral": 1}),
    # ---------------------------------------------------------------- idade
    _idade("recem-nascido", "recém-nascido", 0, 0, {"v2": -1.5, "v5": -1.5}, 3, 3, infantil=True),
    _idade("bebe", "bebê", 1, 2, {"v2": -1.5, "v5": -1.5}, 3, 3, infantil=True),
    _idade("crianca", "criança", 3, 11, {"v2": -0.5, "v5": -0.5}, 4.5, 4, infantil=True),
    _idade("adolescente", "adolescente", 12, 17, {}, None, 4),
    _idade("jovem", "jovem", 18, 29, {}, None, 4),
    _idade("adulto", "adulto", 30, 59, {}, None, 4),
    _idade("idoso", "idoso", 60, 120, {"v2": 0.5, "v5": 0.5}, None, 4),
    # ---------------------------------------------------------- territórios
    # `familias` liga o território às famílias de `knowledge_families`: é assim
    # que uma essência DA ALUNA (família cadastrada) cai num território.
    _terr("floral", "Floral", ["floral", "floral_branco"], "floral", "Delicada", 3),
    _terr("fresco", "Fresco", ["citrico", "aquatico_marinho", "verde"], "fresca", "Luminosa", 1),
    _terr("frutado", "Frutado", ["frutado"], "frutada", "Jovem", 2),
    _terr("aromatico", "Aromático", ["aromatico", "fougere"], "aromática", "Serena", 4),
    _terr("amadeirado", "Amadeirado", ["amadeirado", "chipre"], "amadeirada", "Sofisticada", 5),
    _terr("gourmand_doce", "Gourmand/Doce", ["gourmand"], "gourmand", "Aconchegante", 6),
    _terr("almiscarado", "Almiscarado", ["almiscarado"], "almiscarada", "Macia", 7),
    _terr("ambar_envolvente", "Âmbar/Envolvente", ["ambarado", "especiado", "couro"],
          "ambarada e envolvente", "Magnética", 8),
    # ----------------------------------------------------------- vocabulário
    # Faixas lidas em ordem: vale a primeira cujo `ate` ainda não foi superado.
    ("criacao_vocabulario", "identidade",
     {"temperatura": [{"ate": 3.5, "texto": "fresca"}, {"ate": 6, "texto": "de temperatura equilibrada"},
                      {"ate": 10, "texto": "quente e envolvente"}],
      "docura": [{"ate": 3.5, "texto": "seca"}, {"ate": 6, "texto": "delicadamente doce"},
                 {"ate": 10, "texto": "doce"}],
      "presenca": [{"ate": 3.5, "texto": "com presença suave"},
                   {"ate": 6.5, "texto": "com presença equilibrada"},
                   {"ate": 10, "texto": "com presença marcante"}],
      "frase_papel": {"saida": "Abre a criação com leveza.", "coracao": "Dá corpo ao coração da criação.",
                      "fundo": "Sustenta a fixação no fundo."},
      "papel_dominante_acima_de": 0.5},
     _CAL + "Adjetivos por faixa de eixo e frases-base dos textos da identidade."),
    # ------------------------------------------------------ parâmetros de score
    ("peso_score", "criacao_score",
     {"ponto_neutro": {"v1": 5, "v2": 5, "v3": 5, "v5": 4},
      "segundo_territorio_fracao": 0.5,
      "bonus_territorio_alvo": 3, "fator_territorio_fora": 0.4, "multiplicador_bonus": 2,
      "proximidade_neutra": 5, "min_eixos_proximidade": 2,
      "proximidade_muito": 7, "proximidade_razoavel": 4,
      "score_fraco": 8, "max_itens_padrao": 4,
      "peso_proximidade": 0.6, "peso_compat": 0.4, "compat_neutra": 5,
      "bonus_presenca_por_item": 0.6, "v5_por_territorio": 2, "v5_por_distancia": 0.5,
      "familia_segunda_fracao": 0.5,
      "coerencia_ideal": 3.5, "coerencia_sigma": 2.2,
      "peso_coerencia": 0.4, "peso_complementaridade": 0.35, "peso_risco": 0.25,
      "risco_atencao": 3, "margem_isolada": 2,
      "lacuna_eixo_minima": 1.5, "cobertura_minima": 0.5, "tolerancia_eixo": 1.5,
      "pontos_familia_desejada": 2,
      "intensidade_padrao": 5},
     _CAL + "Parâmetros do motor de criação (score das essências, montagem e compatibilidade)."),
    ("peso_score", "validacao",
     {"cobertura_minima_eixo": 0.5},
     _CAL + "Fração mínima do peso do acorde que precisa ter dado para um eixo/pirâmide ser exibido."),
    ("peso_score", "criacao_padrao_pesos",
     {"1": [2], "2": [2, 2], "3": [3, 2, 1], "4": [3, 2, 2, 1]},
     _CAL + "Pesos relativos (1 pouco, 2 médio, 3 bastante) por tamanho do acorde."),
]


# ===========================================================================
# LINGUAGEM NATURAL — app/engine/linguagem.py
# ===========================================================================
# Palavras que a aluna pode escrever e a regra a que correspondem (além da
# chave e do rótulo). Comparação sem acento, palavra inteira. Termo novo é só
# editar a lista da regra: nenhum código muda. Vocabulário de EXEMPLO a ampliar.
_SINONIMOS = {
    ("criacao_emocao", "amor"): ["amorosa", "amoroso", "apaixonada", "apaixonado", "paixao", "carinho"],
    ("criacao_emocao", "paz"): ["pacifica", "pacifico", "tranquila", "tranquilo", "tranquilidade",
                                "calma", "calmo", "calmaria", "relaxante", "relaxar"],
    ("criacao_emocao", "serenidade"): ["serena", "sereno"],
    ("criacao_emocao", "delicadeza"): ["delicada", "delicado", "sutil", "gentil", "meiga"],
    ("criacao_emocao", "encanto"): ["encantadora", "encantador", "magica", "magico", "fantasia"],
    ("criacao_emocao", "acolhimento"): ["acolhedora", "acolhedor", "abraco", "aconchego", "aconchegante"],
    ("criacao_emocao", "alegria"): ["alegre", "feliz", "felicidade", "divertida", "divertido", "radiante"],
    ("criacao_emocao", "renovacao"): ["renovar", "renovada", "renovado", "recomeco"],
    ("criacao_emocao", "frescor"): ["refrescante"],
    ("criacao_emocao", "elegancia"): ["elegante", "refinada", "refinado", "chique"],
    ("criacao_emocao", "magnetismo"): ["magnetica", "magnetico", "sedutora", "sedutor", "sensual", "sensualidade"],
    ("criacao_emocao", "romance"): ["romantica", "romantico"],
    ("criacao_emocao", "conforto"): ["confortavel", "macia", "macio"],
    ("criacao_emocao", "presenca"): ["destaque"],
    ("criacao_emocao", "energia"): ["energetica", "energetico", "vitalidade", "disposicao"],
    ("criacao_emocao", "liberdade"): ["livre", "solta", "solto"],
    ("criacao_emocao", "confianca"): ["confiante", "segura", "seguro", "firme", "autoconfianca"],
    ("criacao_preferencia", "doce"): ["doces", "docinho", "docura", "adocicada", "adocicado"],
    ("criacao_preferencia", "citrico"): ["citrica", "citricos", "citricas", "citrus"],
    ("criacao_preferencia", "floral"): ["florais", "flor", "flores", "florida", "florido"],
    ("criacao_preferencia", "frutado"): ["frutada", "frutados", "frutadas", "fruta", "frutas", "frutal", "frutais"],
    ("criacao_preferencia", "fresco"): ["fresca", "frescos", "frescas"],
    ("criacao_preferencia", "amadeirado"): ["amadeirada", "amadeirados", "madeira", "madeiras"],
    ("criacao_preferencia", "limpo"): ["limpa", "limpeza", "roupa limpa"],
    ("criacao_preferencia", "cremoso"): ["cremosa", "cremosos"],
    ("criacao_preferencia", "aromatico"): ["aromatica", "ervas", "erva", "herbal"],
    ("criacao_preferencia", "marcante"): ["marcantes"],
    ("criacao_preferencia", "suave"): ["suaves"],
    ("criacao_preferencia", "sofisticado"): ["sofisticada", "sofisticacao"],
}
REGRAS_CRIACAO = [
    (t, c, ({**v, "sinonimos": _SINONIMOS[(t, c)]} if (t, c) in _SINONIMOS else v), d)
    for t, c, v, d in REGRAS_CRIACAO
]
REGRAS_CRIACAO.append((
    "criacao_vocabulario", "ocasioes",
    {"opcoes": {
        "dia_a_dia": {"rotulo": "dia a dia", "target": {}, "terr": {"Fresco": 1, "Floral": 1}},
        "trabalho": {"rotulo": "trabalho", "target": {"v5": 0.5}, "terr": {"Aromático": 1, "Fresco": 1}},
        "esporte": {"rotulo": "esporte e movimento", "target": {"v1": -1}, "terr": {"Fresco": 2}},
        "noite": {"rotulo": "noite", "target": {"v1": 1, "v2": 1}, "terr": {"Âmbar/Envolvente": 1, "Amadeirado": 1}},
        "festa": {"rotulo": "festa", "target": {"v3": 0.5}, "terr": {"Frutado": 1, "Gourmand/Doce": 1}},
        "dormir": {"rotulo": "hora de dormir", "target": {"v1": 0.5, "v2": -0.5}, "terr": {"Almiscarado": 1, "Aromático": 1}},
    }},
    _CAL + "Ocasiões de uso do briefing: deslocamentos pequenos e pontos de território (v4 vem só da intensidade)."))
REGRAS_CRIACAO.append((
    "criacao_vocabulario", "linguagem",
    {"intensidade": {"suave": 2, "discreto": 2, "discreta": 2, "leve": 3, "moderado": 5, "moderada": 5,
                     "forte": 8, "marcante": 8, "intenso": 9, "intensa": 9, "potente": 9},
     "negacao": ["sem", "nao", "nem", "evitar", "evite", "menos"]},
    _CAL + "Palavras de intensidade (0 a 10) e de negação reconhecidas na descrição em linguagem natural."))


# ===========================================================================
# CADASTRO SIMPLES DE ESSÊNCIA (Nome + Família + Percepção) — engine/essencia_simples.py
# ===========================================================================
# A aluna informa só nome, família e percepção; o servidor DEDUZ o resto a
# partir destas tabelas. Os 8 grupos de cheiro são os territórios olfativos
# acima (`criacao_territorio`); `perfil` é o perfil típico do grupo.
#
# VALORES INICIAIS A CALIBRAR: vieram da média de poucas notas de demonstração
# por grupo (v2 e papel) e da correlação grupo->vetor do protótipo (v3 e v4).
# Não são dado científico. Papel em pontos percentuais, somando 100.
_PERFIS = {
    "fresco": {"v2": 2, "v3": 3, "v4": 6, "papel": {"saida": 88, "coracao": 12, "fundo": 0}},
    "frutado": {"v2": 3, "v3": 7, "v4": 4, "papel": {"saida": 80, "coracao": 20, "fundo": 0}},
    "floral": {"v2": 5, "v3": 5, "v4": 5, "papel": {"saida": 15, "coracao": 73, "fundo": 12}},
    "aromatico": {"v2": 3, "v3": 3, "v4": 4, "papel": {"saida": 45, "coracao": 47, "fundo": 8}},
    "amadeirado": {"v2": 7, "v3": 4, "v4": 5, "papel": {"saida": 2, "coracao": 32, "fundo": 66}},
    "gourmand_doce": {"v2": 8, "v3": 8, "v4": 5, "papel": {"saida": 0, "coracao": 15, "fundo": 85}},
    "almiscarado": {"v2": 3, "v3": 4, "v4": 3, "papel": {"saida": 3, "coracao": 22, "fundo": 75}},
    "ambar_envolvente": {"v2": 8, "v3": 7, "v4": 6, "papel": {"saida": 0, "coracao": 10, "fundo": 90}},
}
REGRAS_CRIACAO = [
    (t, c, ({**v, "perfil": _PERFIS[c]} if t == "criacao_territorio" else v), d)
    for t, c, v, d in REGRAS_CRIACAO
]
REGRAS_CRIACAO.append((
    "peso_score", "percepcao",
    {"v1": {"fria": 3, "neutra": 5, "quente": 8},
     "fria_ate": 3.5, "neutra_ate": 6.5,      # v1_ref <= 3.5 Fria; <= 6.5 Neutra; senão Quente
     "v5_neutro": 4,                          # complexidade de uma essência isolada
     "rotulos": {"fria": "Fria", "neutra": "Neutra", "quente": "Quente"}},
    _CAL + "Percepção -> temperatura (v1) e limiares para converter v1 de uma nota em percepção."))


# ===========================================================================
# CALCULADORA DE FORMULAÇÃO — app/engine/formulacao.py
# ===========================================================================
# Um produto = uma regra peso_score/formulacao_<produto>; produto novo é só um
# INSERT. Concentrações: as definidas pela especificação do produto.
#
# COMPOSIÇÃO DA BASE: valores de EXEMPLO a confirmar (professora/fornecedor da
# base). O sistema nunca presume "o resto é álcool": a base é sempre uma lista
# de componentes com percentual da base somando 100. Densidade só se conhecida
# (sem densidade, a massa daquele componente não é calculada).
def _produto(chave, nome, concentracoes, componentes):
    return ("peso_score", f"formulacao_{chave}",
            {"nome": nome, "concentracoes": concentracoes,
             "volume_ml": {"min": 10, "max": 5000, "padrao": 100},
             "precisao_ml": 0.05, "min_essencias": 1,
             "base": {"componentes": componentes}},
            _CAL + f"Concentrações e composição da base de {nome} (composição de EXEMPLO a confirmar).")


REGRAS_FORMULACAO = [
    _produto("body_splash", "Body splash", [7, 10, 15], [
        {"chave": "alcool", "nome": "Álcool de cereais", "percentual": 55, "densidade_g_ml": None},
        {"chave": "agua", "nome": "Água desmineralizada", "percentual": 40, "densidade_g_ml": None},
        {"chave": "umectante", "nome": "Glicerina vegetal", "percentual": 2, "densidade_g_ml": None},
        {"chave": "solubilizante", "nome": "Solubilizante", "percentual": 3, "densidade_g_ml": None},
    ]),
    _produto("perfume", "Perfume", [20, 25, 30], [
        {"chave": "alcool", "nome": "Álcool de perfumaria", "percentual": 95, "densidade_g_ml": None},
        {"chave": "agua", "nome": "Água desmineralizada", "percentual": 5, "densidade_g_ml": None},
    ]),
]
REGRAS_CRIACAO = REGRAS_CRIACAO + REGRAS_FORMULACAO
