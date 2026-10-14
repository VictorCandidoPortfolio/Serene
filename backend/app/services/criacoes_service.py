"""Regras de negócio de criações, acordes (versões) e testes.

Criação é o "guarda-chuva" do fluxo perfil → direção → acorde → ajuste →
teste → aprovação. Acordes e testes seguem o princípio "versionar, nunca
sobrescrever" (regra de negócio 6): só existem operações de INSERIR e LER.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.text import chave
from app.engine.axes import PESOS_RELATIVOS, EssenciaMotor
from app.engine.compatibility import compatibilidade_grupo
from app.engine.movement import sugerir_ajuste
from app.engine.recommendation import identificar_territorios
from app.engine.vectors import calcular_acorde
from app.models.repertorio import Acorde, Criacao, Teste
from app.repositories.repertorio import (
    AcordeRepository,
    CriacaoRepository,
    EssenciaRepository,
    PerfilRepository,
    TesteRepository,
)
from app.schemas.criacoes import (
    AcordeCreate,
    AjusteOut,
    CriacaoCreate,
    CriacaoUpdate,
    TesteCreate,
)
from app.services.motor import ContextoMotor, regras_obrigatorias
from app.services.outros_service import ReferenciasService
from app.services.perfis_service import calcular_alvo, direcao_de, direcao_do_perfil, recomendar


class CriacoesService:
    """CRUD de criações de UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.repo = CriacaoRepository(db, user_id)
        self.perfis = PerfilRepository(db, user_id)

    def listar(self) -> list[Criacao]:
        """Criações da usuária, mais recentes primeiro."""
        return list(self.repo.list(Criacao.id.desc()))

    def obter(self, criacao_id: int) -> Criacao:
        """Uma criação da usuária (404 se de outra)."""
        return self.repo.get_or_404(criacao_id)

    def _direcao(self, payload) -> dict | None:
        """Direção da criação a partir de UMA das três origens possíveis.

        - `perfil_id`: um perfil olfativo dela (questionário completo);
        - `intencao`: território/emoções/público escolhidos na hora, sem
          precisar criar um perfil antes ("quero algo que transmita
          acolhimento");
        - `referencia_id`: um perfume de referência dela — a direção é a
          estimada a partir das notas conhecidas (a referência continua não
          sendo estoque).
        Todos os ids passam por repositórios filtrados pela dona (alheio → 404).
        """
        if payload.perfil_id is not None:
            return direcao_do_perfil(self.db, self.perfis.get_or_404(payload.perfil_id))
        if payload.intencao is not None:
            respostas = payload.intencao.model_dump(exclude_none=True)
            alvo = calcular_alvo(self.db, self.repo.user_id, respostas)
            return direcao_de(self.db, alvo, respostas)
        if payload.referencia_id is not None:
            respostas = {"referencia_id": payload.referencia_id}
            alvo = calcular_alvo(self.db, self.repo.user_id, respostas)
            ref = ReferenciasService(self.db, self.repo.user_id).obter(payload.referencia_id)
            direcao = direcao_de(self.db, alvo, respostas, referencia_id=ref.id)
            direcao["texto"] = f"Inspirada em “{ref.nome}” (direção estimada). " + direcao["texto"]
            return direcao
        return None

    def criar(self, payload: CriacaoCreate) -> Criacao:
        """Cria a criação, com direção vinda de perfil, intenção ou referência (opcional)."""
        criacao = Criacao(nome=payload.nome, objetivo=payload.objetivo, status=payload.status)
        criacao.direcao = self._direcao(payload)
        self.repo.add(criacao)
        self.db.commit()
        return criacao

    def atualizar(self, criacao_id: int, payload: CriacaoUpdate) -> Criacao:
        """Edição parcial (nome, objetivo, status, direção via perfil)."""
        criacao = self.repo.get_or_404(criacao_id)
        dados = payload.model_dump(exclude_unset=True)
        perfil_id = dados.pop("perfil_id", None)
        if perfil_id is not None:
            dados["direcao"] = direcao_do_perfil(self.db, self.perfis.get_or_404(perfil_id))
        self.repo.update(criacao, dados)
        self.db.commit()
        return criacao

    def recomendacoes(self, criacao_id: int):
        """Essências DO REPERTÓRIO DELA mais próximas da direção da criação.

        É o "criador de fragrâncias": dada a intenção, quais das essências que
        ela tem servem para começar o acorde.

        Raises:
            BusinessRuleError: a criação ainda não tem direção.
        """
        criacao = self.repo.get_or_404(criacao_id)
        alvo = (criacao.direcao or {}).get("vetor_alvo")
        if not alvo:
            raise BusinessRuleError(
                "Esta criação ainda não tem direção. Escolha um perfil, um território ou uma referência.",
                codigo="sem_direcao",
            )
        return recomendar(self.db, self.repo.user_id, alvo)

    def apagar(self, criacao_id: int) -> None:
        """Apaga a criação e, em cascata, suas versões e testes."""
        self.repo.delete(self.repo.get_or_404(criacao_id))
        self.db.commit()


def _exigir_editavel(criacao: Criacao) -> None:
    """Criação arquivada é histórico congelado: não recebe versões novas."""
    if criacao.status == "arquivada":
        raise BusinessRuleError("Criação arquivada não aceita novas versões nem testes.")


class AcordesService:
    """Versões de acorde de uma criação + integração com o motor."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.criacoes = CriacaoRepository(db, user_id)
        self.repo = AcordeRepository(db, user_id)
        self.essencias = EssenciaRepository(db, user_id)

    def listar(self, criacao_id: int) -> list[Acorde]:
        """Histórico completo de versões (v1, v2, ...)."""
        self.criacoes.get_or_404(criacao_id)
        return list(self.repo.list_by_criacao(criacao_id))

    def obter(self, criacao_id: int, acorde_id: int) -> Acorde:
        """Uma versão específica."""
        return self.repo.get_or_404(criacao_id, acorde_id)

    def _essencias_do_repertorio(
        self, ctx: ContextoMotor, ids: list[int]
    ) -> dict[int, EssenciaMotor]:
        """Carrega as essências pedidas SÓ do repertório da usuária.

        Regras 3 e 5: um id que não está no repertório dela (de outra usuária,
        inexistente, ou que se refira a uma nota de conhecimento/referência)
        é recusado. O erro não distingue os casos, para não vazar existência.
        """
        encontradas = self.essencias.get_many(ids)
        faltando = [i for i in ids if i not in encontradas]
        if faltando:
            raise NotFoundError(
                f"Essência(s) {', '.join(map(str, faltando))} não encontrada(s) no seu repertório."
            )
        return {i: ctx.essencia_motor(e) for i, e in encontradas.items()}

    def criar(self, criacao_id: int, payload: AcordeCreate) -> Acorde:
        """Calcula e grava uma NOVA versão de acorde (prova ponta a ponta do motor).

        Fluxo: valida posse da criação → carrega essências do repertório →
        `vectors.calcular_acorde` → `compatibility.compatibilidade_grupo` com
        relações e pesos da base → grava com `versao` = última + 1.
        """
        criacao = self.criacoes.get_or_404(criacao_id)
        _exigir_editavel(criacao)
        ctx = ContextoMotor(self.db)
        ids = [i.essencia_id for i in payload.itens]
        motor = self._essencias_do_repertorio(ctx, ids)
        itens_motor = [(motor[i.essencia_id], PESOS_RELATIVOS[i.peso]) for i in payload.itens]

        resultado = calcular_acorde(itens_motor)
        with regras_obrigatorias():
            compat = compatibilidade_grupo(
                [e for e, _ in itens_motor],
                ctx.relacoes,
                ctx.parametros("compatibilidade"),
                ctx.hierarquia,
            )

        acorde = Acorde(
            versao=self.repo.proxima_versao(criacao),
            # Snapshot do nome: o histórico continua legível se a essência
            # for renomeada ou apagada depois.
            itens=[
                {"essencia_id": i.essencia_id, "nome": motor[i.essencia_id].nome, "peso": i.peso}
                for i in payload.itens
            ],
            vetor={
                "valores": resultado.vetor,
                "cobertura": resultado.cobertura,
                "eixos_sem_dado": resultado.eixos_sem_dado,
                "avisos": resultado.avisos,
            },
            papel=resultado.papel,
            familia_resultante=resultado.familia_resultante,
            compatibilidade=compat.como_dict(),
            motivo=(payload.motivo or "").strip() or None,
        )
        try:
            self.repo.add(criacao, acorde)
            if criacao.status == "rascunho":
                criacao.status = "em_ajuste"
            self.db.commit()
        except IntegrityError:
            # Duas versões simultâneas com o mesmo número: a unique barrou.
            self.db.rollback()
            raise ConflictError("Outra versão foi criada ao mesmo tempo; tente novamente.") from None
        return acorde

    def identidade(self, criacao_id: int, acorde_id: int) -> dict:
        """Que territórios esta versão do acorde transmite (perfil "ao contrário").

        Compara o vetor do acorde com a correlação de cada território da base.
        Responde "transmite Acolhimento (82%)" — ou nada, se nenhum território
        estiver perto o bastante (não força uma identidade).
        """
        acorde = self.repo.get_or_404(criacao_id, acorde_id)
        ctx = ContextoMotor(self.db)
        regras = ctx.repo.regras_por_tipo("correlacao_territorio", "territorio")
        nomes = {k: (v or {}).get("nome", k) for k, v in regras["territorio"].items()}
        vetor = (acorde.vetor or {}).get("valores") or {}
        with regras_obrigatorias():
            territorios = identificar_territorios(
                vetor, regras["correlacao_territorio"], nomes, ctx.parametros("identidade")
            )
        avisos = []
        if not territorios:
            avisos.append(
                "Nenhum território está próximo o bastante deste acorde para afirmar uma identidade."
            )
        if (acorde.vetor or {}).get("eixos_sem_dado"):
            avisos.append("Alguns eixos do acorde estão sem dado; a identidade considera só os demais.")
        return {
            "acorde_id": acorde.id,
            "versao": acorde.versao,
            "familia_resultante": acorde.familia_resultante,
            "territorios": [t.__dict__ for t in territorios],
            "avisos": avisos,
        }

    def ajustar(self, criacao_id: int, acorde_id: int, movimento: str) -> AjusteOut:
        """Sugere como mover um acorde ("mais_fresco", ...) com o repertório atual.

        Não grava nada: devolve sugestões (cada uma com `itens_resultantes`
        prontos para virar a próxima versão) ou a lacuna que impede o ajuste.
        Usa os valores ATUAIS das essências (a aluna pode tê-las reclassificado
        desde a versão).
        """
        acorde = self.repo.get_or_404(criacao_id, acorde_id)
        ctx = ContextoMotor(self.db)
        chave_mov = chave(movimento)
        regra = ctx.repo.regra("vetor_movimento", chave_mov)
        if regra is None:
            disponiveis = [r.chave for r in ctx.repo.regras("vetor_movimento")]
            raise BusinessRuleError(
                f"Movimento '{movimento}' não existe. Disponíveis: {', '.join(disponiveis) or 'nenhum'}."
            )

        repertorio = {e.id: ctx.essencia_motor(e) for e in self.essencias.list()}
        faltando = [i["nome"] for i in acorde.itens if i["essencia_id"] not in repertorio]
        if faltando:
            raise BusinessRuleError(
                "Estas essências da versão não estão mais no seu repertório: "
                + ", ".join(faltando) + ". Crie uma nova versão sem elas antes de ajustar."
            )
        itens = [(repertorio[i["essencia_id"]], PESOS_RELATIVOS[i["peso"]]) for i in acorde.itens]

        descricao = regra.descricao or chave_mov.replace("_", " ")
        with regras_obrigatorias():
            resultado = sugerir_ajuste(
                itens,
                list(repertorio.values()),
                regra.valor,
                ctx.parametros("movimento"),
                ctx.familias_ref,
                descricao_movimento=chave_mov.replace("_", " "),
            )
        return AjusteOut(movimento=chave_mov, descricao=descricao, **resultado.como_dict())


class TestesService:
    """Registro de testes (versionados) de uma criação."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.criacoes = CriacaoRepository(db, user_id)
        self.acordes = AcordeRepository(db, user_id)
        self.repo = TesteRepository(db, user_id)

    def listar(self, criacao_id: int) -> list[Teste]:
        """Histórico de testes da criação."""
        self.criacoes.get_or_404(criacao_id)
        return list(self.repo.list_by_criacao(criacao_id))

    def obter(self, criacao_id: int, teste_id: int) -> Teste:
        """Um teste específico."""
        return self.repo.get_or_404(criacao_id, teste_id)

    def criar(self, criacao_id: int, payload: TesteCreate) -> Teste:
        """Grava um NOVO teste. `acorde_id`, se enviado, precisa ser desta criação."""
        criacao = self.criacoes.get_or_404(criacao_id)
        _exigir_editavel(criacao)
        if payload.acorde_id is not None:
            # Impede apontar para acorde de outra criação (mesmo que seja dela).
            self.acordes.get_or_404(criacao_id, payload.acorde_id)
        teste = Teste(versao=self.repo.proxima_versao(criacao), **payload.model_dump())
        try:
            self.repo.add(criacao, teste)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("Outro teste foi registrado ao mesmo tempo; tente novamente.") from None
        return teste

