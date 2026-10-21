"""Conhecimento olfativo GERAL: matérias-primas comuns, por nome (camada compartilhada).

Serve para o motor entender de que família é, em geral, "pêssego" ou "chá branco"
quando a aluna ainda não classificou a essência dela. Isto é conhecimento SOBRE O
NOME, nunca sobre o produto específico que ela comprou:

- conhecimento geral (aqui, `knowledge_notes`) ≠ informação confirmada do produto
  (ficha técnica da essência) ≠ avaliação sensorial da aluna ≠ desconhecido;
- o motor usa uma nota daqui só com nome IGUAL (ou sinônimo) e sempre diz que usou
  o perfil geral; nome apenas PARECIDO ("Flor de lavanda" × "Lavanda") exige a
  confirmação da aluna;
- todas as notas são `ilustrativo=True` (conteúdo inicial a confirmar pela
  professora) e seus números nunca são copiados para o cadastro da aluna.

Cada item: (nome, sinônimos, família (slug), percepção, tipo, observação).
`tipo` "composta" = acorde/efeito comercial, cuja composição varia por fornecedor.
v1 vem da percepção (Fria 3 / Neutra 5 / Quente 8); v2, v3, v4 e papel, do perfil
típico do grupo de cheiro da família (mesma tabela do cadastro simples).
"""

from app.seed.data_criacao import _PERFIS

# família (slug de knowledge_families) -> grupo de cheiro (chave de `criacao_territorio`)
_GRUPO_DA_FAMILIA = {
    "citrico": "fresco", "verde": "fresco", "aquatico_marinho": "fresco",
    "floral": "floral", "floral_branco": "floral", "frutado": "frutado",
    "aromatico": "aromatico", "fougere": "aromatico", "amadeirado": "amadeirado", "chipre": "amadeirado",
    "gourmand": "gourmand_doce", "almiscarado": "almiscarado",
    "ambarado": "ambar_envolvente", "especiado": "ambar_envolvente", "couro": "ambar_envolvente",
}
_V1 = {"fria": 3.0, "neutra": 5.0, "quente": 8.0}
_OBS_COMPOSTA = "Efeito/acorde comercial: a composição varia por fornecedor."

GERAIS = [
    # --- cítricos
    ("Limão", ["Limao", "Limão siciliano", "Lemon"], "citrico", "fria", "simples", None),
    ("Laranja", ["Laranja doce", "Orange"], "citrico", "neutra", "simples", None),
    ("Tangerina", ["Mandarina", "Mandarin", "Tangerine"], "citrico", "fria", "simples", None),
    ("Toranja", ["Grapefruit", "Pomelo"], "citrico", "fria", "simples", None),
    ("Lima", ["Lime"], "citrico", "fria", "simples", None),
    ("Capim-limão", ["Capim limao", "Lemongrass"], "citrico", "fria", "simples", None),
    # --- verdes e aquáticos
    ("Chá verde", ["Cha verde", "Green tea"], "verde", "fria", "composta", _OBS_COMPOSTA),
    ("Chá branco", ["Cha branco", "White tea"], "verde", "fria", "composta", _OBS_COMPOSTA),
    ("Folha verde", ["Folhas verdes", "Green leaves"], "verde", "fria", "simples", None),
    ("Pepino", ["Cucumber"], "verde", "fria", "simples", None),
    ("Brisa marinha", ["Sea breeze", "Marine", "Ozônio", "Ozonio", "Ozone"], "aquatico_marinho", "fria", "composta", _OBS_COMPOSTA),
    # --- aromáticas
    ("Alecrim", ["Rosemary"], "aromatico", "fria", "simples", None),
    ("Hortelã", ["Hortela", "Menta", "Mint"], "aromatico", "fria", "simples", None),
    ("Sálvia", ["Salvia", "Sage"], "aromatico", "neutra", "simples", None),
    ("Manjericão", ["Manjericao", "Basil"], "aromatico", "fria", "simples", None),
    ("Eucalipto", ["Eucalyptus"], "aromatico", "fria", "simples", None),
    # --- florais
    ("Rosa", ["Rose"], "floral", "neutra", "simples", None),
    ("Peônia", ["Peonia", "Peony"], "floral", "neutra", "composta",
     "Peônia costuma ser um efeito/acorde composto, não uma matéria-prima isolada."),
    ("Lírio", ["Lirio", "Lily"], "floral", "neutra", "simples", None),
    ("Violeta", ["Violet"], "floral", "neutra", "simples", None),
    ("Frésia", ["Fresia", "Freesia"], "floral", "fria", "simples", None),
    ("Lótus", ["Lotus"], "floral", "fria", "composta", _OBS_COMPOSTA),
    ("Magnólia", ["Magnolia"], "floral", "neutra", "simples", None),
    ("Lilás", ["Lilas", "Lilac"], "floral", "neutra", "composta", _OBS_COMPOSTA),
    ("Flor de cerejeira", ["Cerejeira", "Cherry blossom", "Sakura"], "floral", "neutra", "composta", _OBS_COMPOSTA),
    ("Hibisco", ["Hibiscus"], "floral", "neutra", "simples", None),
    ("Gardênia", ["Gardenia"], "floral_branco", "neutra", "simples", None),
    ("Tuberosa", ["Tuberose"], "floral_branco", "quente", "simples", None),
    ("Ylang-ylang", ["Ylang", "Ilangue"], "floral_branco", "quente", "simples", None),
    ("Flor de laranjeira", ["Neroli", "Orange blossom"], "floral_branco", "neutra", "simples", None),
    # --- frutados
    ("Pera", ["Pear"], "frutado", "fria", "simples", None),
    ("Pêssego", ["Pessego", "Peach"], "frutado", "neutra", "simples", None),
    ("Maçã", ["Maca", "Apple"], "frutado", "fria", "simples", None),
    ("Morango", ["Strawberry"], "frutado", "neutra", "simples", None),
    ("Framboesa", ["Raspberry"], "frutado", "neutra", "simples", None),
    ("Melancia", ["Watermelon"], "frutado", "fria", "simples", None),
    ("Melão", ["Melao", "Melon"], "frutado", "fria", "simples", None),
    ("Abacaxi", ["Pineapple"], "frutado", "neutra", "simples", None),
    ("Cassis", ["Blackcurrant"], "frutado", "neutra", "simples", None),
    ("Figo", ["Fig"], "frutado", "neutra", "simples", None),
    ("Manga", ["Mango"], "frutado", "neutra", "simples", None),
    ("Maracujá", ["Maracuja", "Passion fruit"], "frutado", "neutra", "simples", None),
    ("Cereja", ["Cherry"], "frutado", "neutra", "simples", None),
    # --- gourmand
    ("Baunilha", ["Vanilla", "Vanilla absolute"], "gourmand", "quente", "simples", None),
    ("Caramelo", ["Caramel"], "gourmand", "quente", "composta", _OBS_COMPOSTA),
    ("Chocolate", ["Cacau", "Cocoa"], "gourmand", "quente", "composta", _OBS_COMPOSTA),
    ("Café", ["Cafe", "Coffee"], "gourmand", "quente", "simples", None),
    ("Mel", ["Honey"], "gourmand", "quente", "simples", None),
    ("Coco", ["Coconut"], "gourmand", "neutra", "simples", None),
    ("Amêndoa", ["Amendoa", "Almond"], "gourmand", "neutra", "simples", None),
    ("Fava tonka", ["Tonka"], "gourmand", "quente", "simples", None),
    ("Algodão-doce", ["Algodao doce", "Cotton candy"], "gourmand", "neutra", "composta", _OBS_COMPOSTA),
    # --- especiados
    ("Canela", ["Cinnamon"], "especiado", "quente", "simples", None),
    ("Cravo-da-índia", ["Cravo da india", "Clove"], "especiado", "quente", "simples", None),
    ("Cardamomo", ["Cardamom"], "especiado", "neutra", "simples", None),
    ("Gengibre", ["Ginger"], "especiado", "neutra", "simples", None),
    ("Pimenta rosa", ["Pink pepper"], "especiado", "neutra", "simples", None),
    # --- amadeirados
    ("Sândalo", ["Sandalo", "Sandalwood"], "amadeirado", "neutra", "simples", None),
    ("Vetiver", ["Vetiver"], "amadeirado", "neutra", "simples", None),
    ("Patchouli", ["Patchuli"], "amadeirado", "quente", "simples", None),
    ("Cipreste", ["Cypress"], "amadeirado", "fria", "simples", None),
    ("Bambu", ["Bamboo"], "amadeirado", "fria", "composta", _OBS_COMPOSTA),
    ("Oud", ["Agarwood"], "amadeirado", "quente", "simples", None),
    # --- almiscarados
    ("Musk", ["Almíscar", "Almiscar", "Musk branco", "White musk"], "almiscarado", "neutra", "composta",
     "Musk é uma família de materiais; o produto do fornecedor pode ser bem diferente de outro."),
    ("Algodão", ["Algodao", "Cotton"], "almiscarado", "neutra", "composta", _OBS_COMPOSTA),
    ("Talco", ["Powder", "Talc"], "almiscarado", "neutra", "composta", _OBS_COMPOSTA),
    # --- ambarados
    ("Benjoim", ["Benzoin"], "ambarado", "quente", "simples", None),
    ("Incenso", ["Olíbano", "Olibano", "Frankincense"], "ambarado", "quente", "simples", None),
    ("Mirra", ["Myrrh"], "ambarado", "quente", "simples", None),
]


def _nota(nome, sinonimos, familia, percepcao, tipo, obs) -> dict:
    perfil = _PERFIS[_GRUPO_DA_FAMILIA[familia]]
    return {
        "nome": nome, "sinonimos": sinonimos, "familia": familia, "tipo_referencia": tipo,
        "papel_tipico": {c: v / 100 for c, v in perfil["papel"].items()},
        "v": (_V1[percepcao], float(perfil["v2"]), float(perfil["v3"]), float(perfil["v4"])),
        "confianca_referencia": "baixa", "descritores": [], "observacoes": obs,
    }


NOTAS_GERAIS = [_nota(*g) for g in GERAIS]
