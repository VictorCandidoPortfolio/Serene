"""Regras de negócio. Orquestram repositórios (dados) e o motor (cálculo).

Services não importam FastAPI: levantam exceções de `app.core.exceptions`,
que `app.main` traduz para HTTP.
"""
