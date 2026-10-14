"""Seed da base de conhecimento (`knowledge_*`).

É o ÚNICO caminho de escrita na camada de conhecimento. Nunca escreve em
tabelas pessoais: usuárias novas continuam com repertório vazio.

Idempotente: cada registro é localizado pela chave natural (slug, nome,
título, (tipo, chave)...) e atualizado se já existir. Pode rodar quantas vezes
quiser: `python -m app.seed`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import (
    KnowledgeCompositionFunction,
    KnowledgeDescriptor,
    KnowledgeEngineRule,
    KnowledgeFamily,
    KnowledgeFamilyRelation,
    KnowledgeMap,
    KnowledgeNote,
)
from app.seed import data


def _upsert(db: Session, model, filtro: dict, valores: dict):
    """Busca pelo `filtro` (chave natural); atualiza se existe, cria se não."""
    obj = db.scalar(select(model).filter_by(**filtro))
    if obj is None:
        obj = model(**filtro, **valores)
        db.add(obj)
    else:
        for k, v in valores.items():
            setattr(obj, k, v)
    db.flush()
    return obj


def popular(db: Session) -> dict[str, int]:
    """Popula/atualiza a base de conhecimento com os dados de `data.py`.

    Args:
        db: sessão aberta; o commit é feito aqui.

    Returns:
        {tabela: quantidade de registros processados}.
    """
    familias: dict[str, KnowledgeFamily] = {}
    # 1ª passada sem parent (a mãe pode vir depois da filha na lista).
    for slug, nome, _parent, cor, ordem, descricao in data.FAMILIAS:
        familias[slug] = _upsert(
            db, KnowledgeFamily, {"slug": slug},
            {"nome": nome, "cor": cor, "ordem": ordem, "descricao": descricao, "ilustrativo": False},
        )
    for slug, _nome, parent, *_ in data.FAMILIAS:
        familias[slug].parent_id = familias[parent].id if parent else None

    for nome, categoria in data.DESCRITORES:
        _upsert(db, KnowledgeDescriptor, {"nome": nome}, {"categoria": categoria, "ativo": True})
    # Termos antigos fora do vocabulário atual são desativados, nunca apagados.
    vigentes = {nome for nome, _ in data.DESCRITORES}
    for antigo in db.scalars(select(KnowledgeDescriptor)):
        if antigo.nome not in vigentes:
            antigo.ativo = False

    for slug, nome, descricao, ordem in data.FUNCOES:
        _upsert(db, KnowledgeCompositionFunction, {"slug": slug},
                {"nome": nome, "descricao": descricao, "ordem": ordem})

    for nota in data.NOTAS:
        v1, v2, v3, v4 = nota["v"]
        _upsert(
            db, KnowledgeNote, {"nome": nota["nome"]},
            {
                "sinonimos": nota["sinonimos"],
                "family_id": familias[nota["familia"]].id,
                "tipo_referencia": nota["tipo_referencia"],
                "papel_tipico": nota["papel_tipico"],
                "v1_ref": v1, "v2_ref": v2, "v3_ref": v3, "v4_ref": v4,
                "v6_ref": nota.get("v6"),
                "docura_nivel_ref": nota.get("docura"),
                "confianca_referencia": nota["confianca_referencia"],
                "fonte": data.FONTE_ILUSTRATIVA,
                "descritores": nota["descritores"],
                "observacoes": nota.get("observacoes"),
                "ilustrativo": True,
            },
        )

    for a, b, tipo, peso, descricao in data.RELACOES:
        _upsert(
            db, KnowledgeFamilyRelation,
            {"family_a_id": familias[a].id, "family_b_id": familias[b].id},
            {"tipo_relacao": tipo, "peso": peso, "descricao": descricao, "ilustrativo": True},
        )

    for mapa in data.MAPAS:
        _upsert(
            db, KnowledgeMap, {"titulo": mapa["titulo"]},
            {
                "categoria": mapa["categoria"],
                "family_id": familias[mapa["familia"]].id if mapa["familia"] else None,
                "conteudo": mapa["conteudo"],
                "relacoes": mapa["relacoes"],
                "ordem": mapa["ordem"],
                "ilustrativo": True,
            },
        )

    for tipo, chave, valor, descricao in data.REGRAS:
        _upsert(db, KnowledgeEngineRule, {"tipo": tipo, "chave": chave},
                {"valor": valor, "descricao": descricao, "ativo": True,
                 "ilustrativo": tipo not in data.TIPOS_REGRA_DA_CLIENTE})

    db.commit()
    return {
        "knowledge_families": len(data.FAMILIAS),
        "knowledge_descriptors": len(data.DESCRITORES),
        "knowledge_composition_functions": len(data.FUNCOES),
        "knowledge_notes": len(data.NOTAS),
        "knowledge_family_relations": len(data.RELACOES),
        "knowledge_maps": len(data.MAPAS),
        "knowledge_engine_rules": len(data.REGRAS),
    }
