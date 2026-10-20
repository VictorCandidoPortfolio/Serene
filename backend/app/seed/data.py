"""Base de conhecimento do SÉRENÉ: estrutura definida + conteúdo de EXEMPLO.

Dois tipos de conteúdo convivem aqui, e a diferença é gravada no banco
(coluna `ilustrativo`) e exibida na interface:

- ESTRUTURA definida pela cliente: as 14 famílias, "Floral Branco" como
  subfamília de Floral, as 9 características sensoriais, os níveis da
  pirâmide, e os nomes dos territórios e dos públicos. `ilustrativo=False`.
- EXEMPLO (`ilustrativo=True`): notas, relações entre famílias, mapas e os
  números do motor (vetores, pesos, limites). Existem só para exercitar o
  motor e NÃO são a base oficial do SÉRENÉ (34 notas, 28 relações, 14 mapas
  e todas as regras virão à parte). Quando a base oficial entrar, basta
  substituir estas linhas: a marca some junto com o exemplo.

Uma linha de exemplo nunca é apresentada como validada e seus números nunca
são copiados para o repertório de uma aluna.

Formato de `valor` por tipo de regra (contrato lido pelo motor):
- territorio            {"nome": str, "descricao_curta": str}
- correlacao_territorio {"vetor": {eixo: 0..10}, "peso": float}
- emocao / preferencia  {"vetor": {eixo: 0..10}, "peso": float, ["territorio": chave]}
- publico               {"nome": str, "vetor": {...}, "peso": float,
                         "limites": {eixo: {"min"/"max": n}}, "vocabulario": [str]}
- vetor_movimento       {"delta": {eixo: variação}}
- peso_score            parâmetros numéricos por chave (compatibilidade,
                         movimento, lacunas, recomendacao) — ver docstrings
                         dos módulos em app/engine/.
"""

FONTE_ILUSTRATIVA = "EXEMPLO — não validado; será substituído pela base oficial SÉRENÉ"

# Tipos de regra cujo CONTEÚDO é definido pela cliente (não é exemplo): só o
# nome e a descrição dos territórios. Todo o resto é calibração de exemplo.
TIPOS_REGRA_DA_CLIENTE = ("territorio",)

FAMILIAS = [
    # (slug, nome, parent_slug, cor, ordem, descricao)
    ("citrico", "Cítrico", None, "#F2C14E", 1, "Notas frescas, luminosas e voláteis de frutas cítricas."),
    ("floral", "Floral", None, "#E8A0BF", 2, "Flores em geral; o coração clássico da perfumaria."),
    ("floral_branco", "Floral Branco", "floral", "#F5E6E8", 3, "Subfamília de Floral: flores brancas cremosas e envolventes."),
    ("amadeirado", "Amadeirado", None, "#8B5E3C", 4, "Madeiras secas ou cremosas; estrutura e fundo."),
    ("ambarado", "Ambarado", None, "#C8742C", 5, "Resinas e acordes quentes, doces e envolventes."),
    ("aromatico", "Aromático", None, "#7FA36B", 6, "Ervas e folhas aromáticas; frescor verde e limpo."),
    ("frutado", "Frutado", None, "#E4572E", 7, "Frutas, exceto as cítricas; suculento e adocicado."),
    ("verde", "Verde", None, "#4F9D69", 8, "Folhas, caules e grama cortada; frescor vegetal."),
    ("aquatico_marinho", "Aquático/Marinho", None, "#4FA3C7", 9, "Brisa do mar, água e ozônio; sensação de ar livre e umidade."),
    ("gourmand", "Gourmand", None, "#B5651D", 10, "Notas comestíveis: doces, cremosas e de confeitaria."),
    ("especiado", "Especiado", None, "#A63D2F", 11, "Especiarias: calor picante, seco ou adocicado."),
    ("chipre", "Chipre", None, "#6B705C", 12, "Estrutura clássica de contraste entre frescor de saída e fundo musgoso e amadeirado."),
    ("almiscarado", "Almiscarado", None, "#D9C7B8", 13, "Almíscar e notas de pele limpa; macias e envolventes."),
    ("fougere", "Fougère", None, "#5C7457", 14, "Estrutura aromática e amadeirada associada a lavanda, musgo e cumarina."),
    ("couro", "Couro", None, "#3E2C23", 15, "Notas de couro, seco, defumado ou macio."),
]

# Características sensoriais: entidade distinta das famílias.
# (nome, categoria) — `categoria` só agrupa na exibição.
DESCRITORES = [
    ("doce", "gosto"),
    ("seco", "gosto"),
    ("fresco", "temperatura"),
    ("cremoso", "textura"),
    ("atalcado", "textura"),
    ("limpo", "impressão"),
    ("intenso", "impressão"),
    ("balsâmico", "impressão"),
    ("esfumaçado", "impressão"),
]

FUNCOES = [
    ("saida", "Saída", "Primeira impressão; costuma reunir notas voláteis, que evaporam mais rápido.", 1),
    ("coracao", "Coração", "Identidade da fragrância; aparece depois da saída.", 2),
    ("fundo", "Fundo", "Base e fixação; costuma reunir o que permanece por mais tempo.", 3),
]

NOTAS = [
    {
        "nome": "Bergamota", "sinonimos": ["Bergamot", "Óleo de Bergamota"],
        "familia": "citrico", "tipo_referencia": "simples",
        "papel_tipico": {"saida": 0.9, "coracao": 0.1, "fundo": 0.0},
        "v": (2.0, 1.5, 3.0, 6.0), "v6": 1.0, "confianca_referencia": "media",
        "descritores": ["fresco"], "docura": "baixa",
    },
    {
        "nome": "Lavanda", "sinonimos": ["Lavender", "Alfazema"],
        "familia": "aromatico", "tipo_referencia": "simples",
        "papel_tipico": {"saida": 0.5, "coracao": 0.5, "fundo": 0.0},
        "v": (3.0, 3.0, 3.0, 5.0), "v6": 3.0, "confianca_referencia": "media",
        "descritores": ["limpo"], "docura": "baixa",
    },
    {
        "nome": "Jasmim", "sinonimos": ["Jasmine", "Jasmin"],
        "familia": "floral_branco", "tipo_referencia": "simples",
        "papel_tipico": {"saida": 0.1, "coracao": 0.8, "fundo": 0.1},
        "v": (6.0, 5.0, 6.0, 7.0), "v6": 9.0, "confianca_referencia": "media",
        "descritores": ["cremoso"], "docura": "media",
    },
    {
        "nome": "Cedro", "sinonimos": ["Cedarwood", "Cedro Atlas"],
        "familia": "amadeirado", "tipo_referencia": "simples",
        "papel_tipico": {"saida": 0.0, "coracao": 0.2, "fundo": 0.8},
        "v": (5.0, 8.0, 2.0, 5.0), "v6": 0.0, "confianca_referencia": "media",
        "descritores": ["seco"], "docura": "baixa",
    },
    {
        "nome": "Âmbar", "sinonimos": ["Amber", "Ambar"],
        "familia": "ambarado", "tipo_referencia": "composta",
        "papel_tipico": {"saida": 0.0, "coracao": 0.1, "fundo": 0.9},
        "v": (8.5, 9.0, 7.0, 7.0), "v6": 1.0, "confianca_referencia": "baixa",
        "descritores": ["balsâmico", "doce"], "docura": "alta",
        "observacoes": "Acorde comercial: composição varia por fornecedor.",
    },
]

RELACOES = [
    # (familia_a, familia_b, tipo, peso, descricao)
    ("citrico", "floral", "classico", 1.0, "Cítrico e floral: dupla clássica; o cítrico ilumina a flor."),
    ("floral", "amadeirado", "classico", 0.8, "A madeira dá estrutura e fixação ao floral."),
    ("citrico", "amadeirado", "complementar", 0.7, "O cítrico abre, a madeira sustenta."),
    ("citrico", "ambarado", "contraste", 0.6, "Frescor contra calor: interessante, pede dosagem."),
    ("aromatico", "floral_branco", "atencao", 0.6, "Ervas podem brigar com a cremosidade das flores brancas."),
]

MAPAS = [
    {
        "titulo": "Território Floral", "categoria": "familia", "familia": "floral", "ordem": 1,
        "conteudo": {"centro": "floral", "pontos": [{"slug": "floral_branco", "x": 0.3, "y": 0.6}]},
        "relacoes": [{"para": "citrico", "tipo": "classico"}],
    },
    {
        "titulo": "Pirâmide Olfativa", "categoria": "piramide", "familia": None, "ordem": 2,
        "conteudo": {"camadas": ["saida", "coracao", "fundo"]},
        "relacoes": None,
    },
    {
        "titulo": "Eixo Frio ↔ Quente", "categoria": "eixo", "familia": None, "ordem": 3,
        "conteudo": {"eixo": "v1", "extremos": {"0": "fresco", "10": "quente"}},
        "relacoes": None,
    },
]

REGRAS = [
    # ------------------------------------------------ territórios (seção 2.15)
    ("territorio", "acolhimento", {"nome": "Acolhimento", "descricao_curta": "Abraço, calor, conforto."},
     "Território de conforto e aconchego."),
    ("territorio", "delicadeza", {"nome": "Delicadeza", "descricao_curta": "Suave, leve, gentil."},
     "Território de leveza e sutileza."),
    ("territorio", "frescor", {"nome": "Frescor", "descricao_curta": "Limpo, luminoso, arejado."},
     "Território de frescor e luz."),
    ("territorio", "alegria", {"nome": "Alegria", "descricao_curta": "Vibrante, solar, efervescente."},
     "Território de energia e leveza alegre."),
    ("territorio", "amor", {"nome": "Amor", "descricao_curta": "Romântico, caloroso, florido."},
     "Território romântico e afetuoso."),
    ("territorio", "encanto", {"nome": "Encanto", "descricao_curta": "Mágico, delicado, surpreendente."},
     "Território de encantamento e fantasia."),
    ("territorio", "renovacao", {"nome": "Renovação", "descricao_curta": "Verde, limpo, recomeço."},
     "Território de frescor verde e recomeço."),
    ("territorio", "elegancia", {"nome": "Elegância", "descricao_curta": "Sofisticado, seco, estruturado."},
     "Território de sofisticação e sobriedade."),
    ("territorio", "magnetismo", {"nome": "Magnetismo", "descricao_curta": "Intenso, quente, envolvente."},
     "Território de presença e sedução."),
    ("territorio", "sensualidade", {"nome": "Sensualidade", "descricao_curta": "Envolvente, quente, sedutor."},
     "Território de sedução e presença na pele."),
    ("correlacao_territorio", "acolhimento", {"vetor": {"v1": 7.0, "v2": 6.0, "v3": 6.5}, "peso": 1.0},
     "Acolhimento puxa para quente, persistente e levemente doce."),
    ("correlacao_territorio", "delicadeza", {"vetor": {"v1": 5.0, "v3": 5.5, "v4": 3.5}, "peso": 1.0},
     "Delicadeza pede presença discreta."),
    ("correlacao_territorio", "frescor", {"vetor": {"v1": 2.5, "v2": 2.5}, "peso": 1.0},
     "Frescor puxa para frio e leve."),
    ("correlacao_territorio", "alegria", {"vetor": {"v1": 3.5, "v3": 5.5, "v4": 6.0}, "peso": 1.0},
     "Alegria: fresca, levemente doce e presente."),
    ("correlacao_territorio", "amor", {"vetor": {"v1": 6.0, "v3": 7.0, "v6": 7.0}, "peso": 1.0},
     "Amor: morno, doce e floral."),
    ("correlacao_territorio", "encanto", {"vetor": {"v3": 6.5, "v5": 6.5, "v6": 6.5}, "peso": 1.0},
     "Encanto: doce, complexo e floral."),
    ("correlacao_territorio", "renovacao", {"vetor": {"v1": 2.5, "v2": 3.0, "v4": 5.0}, "peso": 1.0},
     "Renovação: fresca, leve e presente."),
    ("correlacao_territorio", "elegancia", {"vetor": {"v2": 6.5, "v3": 3.5, "v5": 7.0}, "peso": 1.0},
     "Elegância: persistente, seca e complexa."),
    ("correlacao_territorio", "sensualidade", {"vetor": {"v1": 7.0, "v2": 7.0, "v4": 6.5}, "peso": 1.0},
     "Sensualidade: quente, persistente e presente."),
    ("correlacao_territorio", "magnetismo", {"vetor": {"v1": 7.5, "v2": 8.0, "v4": 7.5}, "peso": 1.0},
     "Magnetismo: quente, persistente e marcante."),
    # ------------------------------------------------------------- emoções
    ("emocao", "amor", {"vetor": {"v1": 6.0, "v3": 7.0}, "peso": 1.0, "territorio": "acolhimento"},
     "Amor: calor e doçura."),
    ("emocao", "serenidade", {"vetor": {"v1": 4.5, "v4": 3.5}, "peso": 1.0},
     "Serenidade: neutra e discreta."),
    ("emocao", "alegria", {"vetor": {"v1": 3.5, "v4": 6.0}, "peso": 1.0},
     "Alegria: fresca e presente."),
    # --------------------------------------------------------- preferências
    ("preferencia", "doce", {"vetor": {"v3": 8.0}, "peso": 1.0}, "Gosta de doce."),
    ("preferencia", "fresco", {"vetor": {"v1": 2.0}, "peso": 1.0}, "Gosta de fresco."),
    ("preferencia", "floral", {"vetor": {"v6": 8.0}, "peso": 1.0}, "Gosta de floral."),
    # ------------------------------------------------------ públicos (2.16)
    ("publico", "kids",
     {"nome": "Kids", "vetor": {"v4": 3.0, "v5": 2.0}, "peso": 0.5,
      "limites": {"v4": {"max": 4.5}}, "vocabulario": ["fofinho", "docinho", "brincadeira"]},
     "Kids: presença baixa e estrutura simples."),
    ("publico", "teen",
     {"nome": "Teen", "vetor": {"v5": 4.0}, "peso": 0.5,
      "limites": {"v4": {"max": 6.5}}, "vocabulario": ["vibrante", "leve", "divertido"]},
     "Teen: presença moderada."),
    ("publico", "adulta",
     {"nome": "Adulta", "vetor": {}, "peso": 0.0, "limites": {},
      "vocabulario": ["sofisticado", "envolvente", "elegante"]},
     "Adulta: sem limites de intensidade."),
    # ------------------------------------------------------------ movimentos
    ("vetor_movimento", "mais_fresco", {"delta": {"v1": -2.0}}, "mais fresco"),
    ("vetor_movimento", "mais_quente", {"delta": {"v1": 2.0}}, "mais quente"),
    ("vetor_movimento", "mais_doce", {"delta": {"v3": 2.0}}, "mais doce"),
    ("vetor_movimento", "mais_marcante", {"delta": {"v4": 2.0, "v2": 1.0}}, "mais marcante"),
    ("vetor_movimento", "mais_suave", {"delta": {"v4": -2.0}}, "mais suave"),
    ("vetor_movimento", "mais_floral", {"delta": {"v6": 2.0}}, "mais floral"),
    # ------------------------------------------------------ pesos de score
    ("peso_score", "compatibilidade",
     {"base": 0.5, "mesma_familia": 0.3, "sem_relacao": 0.0, "classico": 0.5,
      "complementar": 0.3, "contraste": 0.1, "atencao": -0.3, "limiar_alerta": 0.4},
     "Pesos do score de compatibilidade entre famílias."),
    ("peso_score", "movimento",
     {"progresso_minimo": 0.15, "max_sugestoes": 3, "penalidade_colateral": 0.5},
     "Parâmetros do motor de ajuste."),
    ("peso_score", "lacunas",
     {"papel_minimo": 0.5, "min_essencias_por_camada": 1, "amplitude_minima": 4,
      "eixos_amplitude": ["v1", "v3"]},
     "Limiares de identificação de lacunas."),
    ("peso_score", "recomendacao",
     {"peso_intensidade": 2.0, "min_eixos_comparados": 2},
     "Parâmetros do vetor-alvo e da pontuação de recomendações."),
    ("peso_score", "identidade",
     {"min_eixos_comparados": 2, "proximidade_minima": 50, "max_territorios": 3},
     "Parâmetros da identificação dos territórios de um acorde."),
]


# Regras do motor de criação (arquivo próprio: valores iniciais a calibrar).
from app.seed.data_criacao import REGRAS_CRIACAO  # noqa: E402

REGRAS = REGRAS + REGRAS_CRIACAO
