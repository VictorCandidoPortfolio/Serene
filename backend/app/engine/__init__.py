"""Motor olfativo do SÉRENÉ — funções PURAS.

Regras deste pacote:
- Nada aqui acessa banco, HTTP ou variáveis de ambiente. Os services carregam
  os dados (essências da usuária, regras de `knowledge_engine_rules`, relações
  entre famílias) e passam como parâmetro. Isso torna o motor testável com
  pytest puro e impede, por construção, que ele "descubra" essências fora do
  repertório que o service entregou.
- Nenhum número de domínio (peso de score, delta de movimento, limiar) é
  constante aqui: tudo chega como parâmetro vindo das regras. As únicas
  constantes são DEFINIÇÕES do sistema de eixos (ver `axes.py`).
- `None` significa "não sabemos". O motor nunca substitui um `None` por um
  valor estimado (regra de negócio 2 — nunca inventar dado técnico).
"""
