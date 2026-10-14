"""Services dos recursos secundários: referências, coleções e conhecimento.

Referências e coleções seguem exatamente o padrão de `essencias_service`:
construídos com (sessão, user_id) e acessando dados só por repositórios
escopados.
"""

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError
from app.engine.recommendation import identificar_territorios
from app.engine.reconhecimento import NotaRef, buscar_correspondencias
from app.engine.referencias import AnaliseReferencia, NotaDaReferencia, analisar_referencia
from app.engine.vectors import media_vetores
from app.models.repertorio import Colecao, Referencia
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.repertorio import (
    AcordeRepository,
    ColecaoItemRepository,
    ColecaoRepository,
    CriacaoRepository,
    EssenciaRepository,
    ReferenciaRepository,
)
from app.schemas.outros import (
    ColecaoCreate,
    ColecaoItemIn,
    ColecaoOut,
    ColecaoUpdate,
    ReferenciaCreate,
    ReferenciaUpdate,
)
from app.services.motor import ContextoMotor, regras_obrigatorias


class ReferenciasService:
    """Fragrâncias de referência de UMA usuária.

    Regra 5: referência não vira estoque. Ela nunca entra na lista de
    essências candidatas do motor; serve só para APONTAR DIREÇÃO (vetor
    estimado a partir das notas conhecidas) e nomear famílias.
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repo = ReferenciaRepository(db, user_id)

    def analisar(self, referencia_id: int) -> AnaliseReferencia:
        """Caminhos de uma referência: direção estimada + famílias que a aluna tem/não tem.

        As notas citadas pela aluna são reconhecidas na base de conhecimento
        (mesma busca do cadastro de essências: exata antes de parcial). A
        família percebida também conta, se existir na base.
        """
        ref = self.repo.get_or_404(referencia_id)
        ctx = ContextoMotor(self.db)
        notas = {n.id: n for n in ctx.repo.notas()}
        refs = [NotaRef(n.id, n.nome, tuple(n.sinonimos or ())) for n in notas.values()]
        reconhecidas, desconhecidas = [], []
        for citada in ref.notas_conhecidas or []:
            achou = buscar_correspondencias(citada, refs, limite=1)
            if not achou:
                desconhecidas.append(citada)
                continue
            nota = notas[achou[0].nota_id]
            fam = nota.family
            reconhecidas.append(NotaDaReferencia(
                citada_como=citada,
                nota=nota.nome,
                familia_chave=fam.slug if fam else None,
                familia=fam.nome if fam else None,
                vetor={e: getattr(nota, f"{e}_ref", None) for e in ("v1", "v2", "v3", "v4", "v6")},
            ))
        percebida = ctx.familia_por_texto(ref.familia_percebida)
        if percebida and all(n.familia_chave != percebida.slug for n in reconhecidas):
            reconhecidas.append(NotaDaReferencia(
                citada_como=ref.familia_percebida, nota=f"família percebida: {percebida.nome}",
                familia_chave=percebida.slug, familia=percebida.nome, vetor={},
            ))

        presentes: set[str] = set()
        for e in EssenciaRepository(self.db, self.user_id).list():
            chave = ctx.essencia_motor(e).familia_chave
            if chave:
                presentes.add(chave)
                if chave in ctx.hierarquia:
                    presentes.add(ctx.hierarquia[chave])
        return analisar_referencia(reconhecidas, desconhecidas, presentes)

    def caminhos(self, referencia_id: int) -> dict:
        """Análise da referência + essências DELA que apontam na mesma direção.

        As recomendações vêm do repertório da aluna (nunca da referência nem
        da base de conhecimento).
        """
        # Import local por ciclo real: perfis_service importa este módulo.
        from app.services.perfis_service import recomendar

        analise = self.analisar(referencia_id)
        alvo = {e: v for e, v in analise.vetor_estimado.items() if v is not None}
        return {**analise.como_dict(), "recomendacoes": recomendar(self.db, self.user_id, alvo)}

    def listar(self) -> list[Referencia]:
        """Referências da usuária."""
        return list(self.repo.list(Referencia.nome))

    def obter(self, referencia_id: int) -> Referencia:
        """Uma referência da usuária."""
        return self.repo.get_or_404(referencia_id)

    def criar(self, payload: ReferenciaCreate) -> Referencia:
        """Cadastra uma referência."""
        ref = self.repo.add(Referencia(**payload.model_dump()))
        self.db.commit()
        return ref

    def atualizar(self, referencia_id: int, payload: ReferenciaUpdate) -> Referencia:
        """Edição parcial."""
        ref = self.repo.get_or_404(referencia_id)
        self.repo.update(ref, payload.model_dump(exclude_unset=True))
        self.db.commit()
        return ref

    def apagar(self, referencia_id: int) -> None:
        """Remove a referência."""
        self.repo.delete(self.repo.get_or_404(referencia_id))
        self.db.commit()


class ColecoesService:
    """Coleções de UMA usuária e os vínculos com criações."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repo = ColecaoRepository(db, user_id)
        self.itens = ColecaoItemRepository(db, user_id)
        self.criacoes = CriacaoRepository(db, user_id)

    def identidade(self, colecao: Colecao) -> dict:
        """Identidade geral da coleção, calculada a partir dos acordes atuais.

        Para cada criação, usa a versão MAIS RECENTE do acorde. Calculada na
        leitura (e não gravada) porque as criações ganham versões novas depois
        de entrar na coleção. Criações sem acorde são contadas, mas ficam de
        fora da média.
        """
        acordes = AcordeRepository(self.db, self.user_id)
        vetores, familias = [], Counter()
        itens = self.itens.list_by_colecao(colecao.id)
        for item in itens:
            versoes = acordes.list_by_criacao(item.criacao_id)
            if not versoes:
                continue
            ultima = versoes[-1]
            vetores.append((ultima.vetor or {}).get("valores") or {})
            if ultima.familia_resultante:
                familias[ultima.familia_resultante] += 1
        vetor = media_vetores(vetores)
        territorios = []
        if vetores:
            ctx = ContextoMotor(self.db)
            regras = ctx.repo.regras_por_tipo("correlacao_territorio", "territorio")
            nomes = {k: (v or {}).get("nome", k) for k, v in regras["territorio"].items()}
            with regras_obrigatorias():
                territorios = [t.__dict__ for t in identificar_territorios(
                    vetor, regras["correlacao_territorio"], nomes, ctx.parametros("identidade"))]
        return {
            "vetor_medio": vetor,
            "familias": [f for f, _ in familias.most_common()],
            "territorios": territorios,
            "criacoes": len(itens),
            "criacoes_com_acorde": len(vetores),
        }

    def saida(self, colecao: Colecao) -> ColecaoOut:
        """Monta a resposta com os itens ordenados, o resumo de cada criação e a identidade."""
        itens = [
            {"criacao_id": i.criacao_id, "ordem": i.ordem, "nome": i.criacao.nome,
             "status": i.criacao.status}
            for i in self.itens.list_by_colecao(colecao.id)
        ]
        return ColecaoOut.model_validate(
            {
                "id": colecao.id,
                "nome": colecao.nome,
                "descricao": colecao.descricao,
                "identidade_geral": self.identidade(colecao),
                "itens": itens,
                "criado_em": colecao.criado_em,
                "atualizado_em": colecao.atualizado_em,
            }
        )

    def listar(self) -> list[Colecao]:
        """Coleções da usuária."""
        return list(self.repo.list(Colecao.nome))

    def obter(self, colecao_id: int) -> Colecao:
        """Uma coleção da usuária."""
        return self.repo.get_or_404(colecao_id)

    def criar(self, payload: ColecaoCreate) -> Colecao:
        """Cria uma coleção vazia."""
        colecao = self.repo.add(Colecao(**payload.model_dump()))
        self.db.commit()
        return colecao

    def atualizar(self, colecao_id: int, payload: ColecaoUpdate) -> Colecao:
        """Edição parcial (nome/descrição)."""
        colecao = self.repo.get_or_404(colecao_id)
        self.repo.update(colecao, payload.model_dump(exclude_unset=True))
        self.db.commit()
        return colecao

    def apagar(self, colecao_id: int) -> None:
        """Apaga a coleção (as criações continuam existindo)."""
        self.repo.delete(self.repo.get_or_404(colecao_id))
        self.db.commit()

    def adicionar(self, colecao_id: int, payload: ColecaoItemIn) -> Colecao:
        """Adiciona uma criação APROVADA e DA MESMA DONA à coleção.

        Coleções organizam o que já foi aprovado (funcionalidade 2.10); uma
        criação em rascunho ainda está em desenvolvimento.
        """
        colecao = self.repo.get_or_404(colecao_id)
        # CriacaoRepository filtra pela dona: criação alheia → 404.
        criacao = self.criacoes.get_or_404(payload.criacao_id)
        if criacao.status != "aprovada":
            raise BusinessRuleError("Só criações aprovadas podem entrar numa coleção.")
        if self.itens.get(colecao.id, criacao.id) is not None:
            raise ConflictError("Esta criação já está na coleção.")
        ordem = payload.ordem if payload.ordem is not None else self.itens.proxima_ordem(colecao)
        self.itens.add(colecao, criacao, ordem)
        self.db.commit()
        return colecao

    def remover(self, colecao_id: int, criacao_id: int) -> None:
        """Tira a criação da coleção (sem apagar a criação)."""
        colecao = self.repo.get_or_404(colecao_id)
        item = self.itens.get(colecao.id, criacao_id)
        if item is None:
            raise BusinessRuleError("Esta criação não está na coleção.")
        self.itens.delete(item)
        self.db.commit()

    def reordenar(self, colecao_id: int, criacao_ids: list[int]) -> Colecao:
        """Redefine a ordem. A lista precisa conter exatamente os itens atuais."""
        colecao = self.repo.get_or_404(colecao_id)
        atuais = {i.criacao_id: i for i in self.itens.list_by_colecao(colecao.id)}
        if sorted(criacao_ids) != sorted(atuais):
            raise BusinessRuleError(
                "A nova ordem deve listar exatamente as criações que estão na coleção."
            )
        for posicao, cid in enumerate(criacao_ids):
            atuais[cid].ordem = posicao
        self.db.commit()
        return colecao


class ConhecimentoService:
    """Leitura da base de conhecimento compartilhada (sem escrita, por design)."""

    def __init__(self, db: Session):
        self.repo = KnowledgeRepository(db)

    def familias(self):
        """Famílias e subfamílias."""
        return self.repo.familias()

    def descritores(self):
        """Descritores sensoriais."""
        return self.repo.descritores()

    def funcoes(self):
        """Funções da pirâmide."""
        return self.repo.funcoes()

    def notas(self):
        """Notas de referência."""
        return self.repo.notas()

    def relacoes(self):
        """Relações entre famílias."""
        return self.repo.relacoes()

    def mapas(self):
        """Mapas/territórios."""
        return self.repo.mapas()

    def regras(self, tipo: str | None = None):
        """Regras ativas do motor (opcionalmente de um tipo)."""
        return self.repo.regras(tipo)

    def catalogo(self, tipo: str) -> list[dict[str, Any]]:
        """Lista de territórios ou públicos vinda do banco (nunca hardcoded).

        Um território novo aparece aqui assim que alguém insere a regra
        `territorio/<chave>` — sem deploy.
        """
        return [
            {"chave": r.chave, "descricao": r.descricao, **(r.valor if isinstance(r.valor, dict) else {})}
            for r in self.repo.regras(tipo)
        ]
