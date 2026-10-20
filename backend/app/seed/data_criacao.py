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
      {"nome", "familias": [slug de knowledge_families], "adjetivo", "frase",
       "frase_feminino", "atributo", "ordem"}
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


def _idade(chave, rotulo, de, ate, delta, v4_max, max_itens):
    return ("criacao_idade", chave,
            {"rotulo": rotulo, "anos_de": de, "anos_ate": ate, "delta": delta,
             "v4_max": v4_max, "max_itens": max_itens},
            _CAL + f"Idade: {rotulo} ({de} a {ate} anos).")


def _terr(chave, nome, familias, adjetivo, frase, atributo, ordem, frase_feminino=None):
    return ("criacao_territorio", chave,
            {"nome": nome, "familias": familias, "adjetivo": adjetivo, "frase": frase,
             "frase_feminino": frase_feminino or frase, "atributo": atributo, "ordem": ordem},
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
    _idade("recem-nascido", "recém-nascido", 0, 0, {"v2": -1.5, "v5": -1.5}, 3, 3),
    _idade("bebe", "bebê", 1, 2, {"v2": -1.5, "v5": -1.5}, 3, 3),
    _idade("crianca", "criança", 3, 11, {"v2": -0.5, "v5": -0.5}, 4.5, 4),
    _idade("adolescente", "adolescente", 12, 17, {}, None, 4),
    _idade("jovem", "jovem", 18, 29, {}, None, 4),
    _idade("adulto", "adulto", 30, 59, {}, None, 4),
    _idade("idoso", "idoso", 60, 120, {"v2": 0.5, "v5": 0.5}, None, 4),
    # ---------------------------------------------------------- territórios
    # `familias` liga o território às famílias de `knowledge_families`: é assim
    # que uma essência DA ALUNA (família cadastrada) cai num território.
    _terr("floral", "Floral", ["floral", "floral_branco"], "floral",
          "delicadeza floral", "Delicada", 1, frase_feminino="delicadeza e feminilidade"),
    _terr("fresco", "Fresco", ["citrico", "aquatico_marinho", "verde"], "fresca",
          "luminosidade e leveza", "Luminosa", 2),
    _terr("frutado", "Frutado", ["frutado"], "frutada",
          "jovialidade e doçura frutada", "Jovem", 3),
    _terr("aromatico", "Aromático", ["aromatico", "fougere"], "aromática",
          "serenidade e calma", "Serena", 4),
    _terr("amadeirado", "Amadeirado", ["amadeirado", "chipre"], "amadeirada",
          "profundidade e sofisticação seca", "Sofisticada", 5),
    _terr("gourmand_doce", "Gourmand/Doce", ["gourmand"], "gourmand",
          "conforto e doçura envolvente", "Aconchegante", 6),
    _terr("almiscarado", "Almiscarado", ["almiscarado"], "almiscarada",
          "limpeza, conforto e suavidade", "Macia", 7),
    _terr("ambar_envolvente", "Âmbar/Envolvente", ["ambarado", "especiado", "couro"],
          "ambarada e envolvente", "calor e magnetismo envolvente", "Magnética", 8),
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
      "frase_sem_territorio": "Entra pelo perfil sensorial que tem em comum com a direção pedida.",
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
      "lacuna_eixo_minima": 1.5, "repertorio_minimo_confianca": 6},
     _CAL + "Parâmetros do motor de criação (score das essências, montagem e compatibilidade)."),
    ("peso_score", "criacao_padrao_pesos",
     {"1": [2], "2": [2, 2], "3": [3, 2, 1], "4": [3, 2, 2, 1]},
     _CAL + "Pesos relativos (1 pouco, 2 médio, 3 bastante) por tamanho do acorde."),
]
