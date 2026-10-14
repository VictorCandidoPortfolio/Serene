"""Mapa Olfativo (funcionalidade 2.4): os dados para o frontend desenhar.

O backend não desenha nada: entrega, numa resposta só, tudo o que o mapa
precisa posicionar.
- O que é DA ALUNA (filtrado pela dona): as essências do repertório e a
  versão mais recente do acorde de cada criação, com seus vetores.
- O que é da BASE (igual para todas): famílias (com o vetor médio das notas
  de referência), territórios (com a correlação em vetor), relações entre
  famílias (os "caminhos") e os mapas de estudo cadastrados.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.engine.axes import EIXOS, ROTULOS_EIXOS
from app.repositories.repertorio import AcordeRepository, CriacaoRepository, EssenciaRepository
from app.services.motor import ContextoMotor


class MapaService:
    """Monta o mapa de UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.essencias = EssenciaRepository(db, user_id)
        self.criacoes = CriacaoRepository(db, user_id)
        self.acordes = AcordeRepository(db, user_id)

    def montar(self) -> dict[str, Any]:
        """Pontos da aluna + territórios e caminhos da base."""
        ctx = ContextoMotor(self.db)
        familias_bd = {f.slug: f for f in ctx.repo.familias()}

        essencias = []
        for e in self.essencias.list():
            m = ctx.essencia_motor(e)
            fam = familias_bd.get(m.familia_chave) if m.familia_chave else None
            essencias.append({
                "id": e.id, "nome": e.nome, "familia": e.familia, "familia_chave": m.familia_chave,
                "cor": fam.cor if fam else None, "vetor": m.vetor, "favorito": e.favorito,
            })

        criacoes = []
        for c in self.criacoes.list():
            versoes = self.acordes.list_by_criacao(c.id)
            if not versoes:
                continue
            ultima = versoes[-1]
            criacoes.append({
                "id": c.id, "nome": c.nome, "status": c.status, "versao": ultima.versao,
                "familia": ultima.familia_resultante,
                "vetor": (ultima.vetor or {}).get("valores") or {},
            })

        regras = ctx.repo.regras_por_tipo("territorio", "correlacao_territorio")
        territorios = [
            {
                "chave": chave,
                "nome": (valor or {}).get("nome", chave),
                "descricao": (valor or {}).get("descricao_curta"),
                "vetor": (regras["correlacao_territorio"].get(chave) or {}).get("vetor", {}),
            }
            for chave, valor in regras["territorio"].items()
        ]

        familias = [
            {
                "chave": f.chave, "nome": f.nome, "mae": f.parent_chave,
                "cor": familias_bd[f.chave].cor if f.chave in familias_bd else None,
                "vetor": f.vetor_medio or {},
            }
            for f in ctx.familias_ref
        ]
        relacoes = [
            {"a": r.familia_a, "b": r.familia_b, "tipo": r.tipo, "peso": r.peso, "descricao": r.descricao}
            for r in ctx.relacoes
        ]
        slug_por_id = {f.id: f.slug for f in familias_bd.values()}
        mapas = [
            {"titulo": m.titulo, "categoria": m.categoria, "familia": slug_por_id.get(m.family_id),
             "conteudo": m.conteudo, "relacoes": m.relacoes}
            for m in ctx.repo.mapas()
        ]
        eixos = [
            {"chave": e, "nome": ROTULOS_EIXOS[e][0], "baixo": ROTULOS_EIXOS[e][1], "alto": ROTULOS_EIXOS[e][2]}
            for e in EIXOS
        ]
        return {
            "eixos": eixos, "essencias": essencias, "criacoes": criacoes, "territorios": territorios,
            "familias": familias, "relacoes": relacoes, "mapas": mapas,
        }
