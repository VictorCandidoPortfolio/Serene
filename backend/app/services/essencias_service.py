"""Regras de negócio de essências — o RECURSO DE REFERÊNCIA do projeto.

Os demais services pessoais seguem o mesmo padrão:
1. O service é construído com (sessão, user_id da usuária autenticada).
2. Todo acesso a dados pessoais passa por um repositório escopado nesse
   user_id (nunca uma query solta).
3. A base de conhecimento é consultada só para SUGERIR, nunca para gravar no
   repertório sem confirmação da aluna.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, KnowledgeUnavailableError, NotFoundError
from app.core.text import chave, normalizar
from app.engine.criacao import carregar_territorios, territorio_da_familia
from app.engine.essencia_simples import PERCEPCOES, derivar, percepcao_de_v1, valores_da_nota
from app.engine.axes import EIXOS, Lacuna
from app.engine.gaps import lacunas_repertorio
from app.engine.reconhecimento import NotaRef, buscar_correspondencias
from app.models.knowledge import KnowledgeNote
from app.models.repertorio import Essencia
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.repertorio import EssenciaRepository
from app.schemas.essencias import (
    EssenciaCreate,
    EssenciaCriadaOut,
    EssenciaUpdate,
    OpcaoCadastroOut,
    OpcoesCadastroOut,
    SugestaoNomeOut,
    SugestaoReferencia,
)
from app.services.motor import ContextoMotor, regras_obrigatorias

PERCEPCOES_SIMPLES = PERCEPCOES

# Campos que podem vir da referência; alterá-los numa essência vinculada
# marca `editado_da_referencia`.
CAMPOS_DA_REFERENCIA = (
    "familia", "subfamilia", "tipo", "papel", "v1", "v2", "v3", "v4", "v6", "descritores",
)


# Campos numéricos de uma nota: vetores e papel na pirâmide. Numa nota de
# EXEMPLO (`ilustrativo`) eles são calibração de demonstração, não medida, e
# por isso nunca são oferecidos nem copiados para o repertório da aluna.
CAMPOS_NUMERICOS_DA_REFERENCIA = ("papel", "v1", "v2", "v3", "v4", "v6")


def valores_da_referencia(nota: KnowledgeNote) -> dict[str, Any]:
    """Classificação sugerida por uma nota de conhecimento.

    Nota de exemplo (`nota.ilustrativo`): só a classificação (família,
    subfamília, tipo, características) é sugerida; os números ficam None.

    Se a família da nota é uma subfamília, `familia` recebe a mãe e
    `subfamilia` a própria. Valores ausentes na nota ficam None — e continuam
    None na essência (nunca inventamos o que a referência não afirma).
    """
    familia, subfamilia = None, None
    if nota.family is not None:
        if nota.family.parent is not None:
            familia, subfamilia = nota.family.parent.nome, nota.family.nome
        else:
            familia = nota.family.nome
    valores = {
        "familia": familia,
        "subfamilia": subfamilia,
        "tipo": nota.tipo_referencia,
        "papel": nota.papel_tipico,
        "v1": nota.v1_ref,
        "v2": nota.v2_ref,
        "v3": nota.v3_ref,
        "v4": nota.v4_ref,
        "v6": nota.v6_ref,
        "descritores": list(nota.descritores or []),
    }
    if nota.ilustrativo:
        for campo in CAMPOS_NUMERICOS_DA_REFERENCIA:
            valores[campo] = None
    return valores


def difere_da_referencia(valores: dict[str, Any], nota: KnowledgeNote) -> bool:
    """True se algum valor informado é diferente do que a referência afirma.

    Campos sem valor (na essência ou na referência) não contam: não há o que
    comparar.
    """
    ref = valores_da_referencia(nota)
    return any(
        ref[c] is not None and valores.get(c) not in (None, []) and valores[c] != ref[c]
        for c in ref
    )


def _podar(valor):
    """Remove None, listas/dicts vazios, recursivamente (ficha vazia vira None)."""
    if isinstance(valor, dict):
        limpo = {k: _podar(v) for k, v in valor.items()}
        limpo = {k: v for k, v in limpo.items() if v not in (None, {}, [])}
        return limpo or None
    if isinstance(valor, list):
        return [x for x in (_podar(v) for v in valor) if x is not None] or None
    return valor


def _avisos_referencia(nota: KnowledgeNote) -> list[str]:
    """Avisos honestos sobre a qualidade de uma referência."""
    avisos = []
    if nota.ilustrativo:
        avisos.append(
            "Nota de EXEMPLO, ainda não validada: só a classificação é sugerida. "
            "Os valores (frescor, doçura etc.) ficam por sua conta."
        )
    if nota.confianca_referencia == "baixa":
        avisos.append("Referência de baixa confiança: confira antes de aceitar.")
    if nota.tipo_referencia == "composta":
        avisos.append(
            "Referência composta (acorde/efeito comercial): a composição interna do "
            "fornecedor não é conhecida."
        )
    faltando = [e for e in ("v1", "v2", "v3", "v4", "v6") if getattr(nota, f"{e}_ref") is None]
    if faltando and not nota.ilustrativo:
        avisos.append(f"A referência não informa: {', '.join(faltando)}.")
    return avisos


class EssenciasService:
    """Operações sobre as essências de UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.repo = EssenciaRepository(db, user_id)
        self.conhecimento = KnowledgeRepository(db)

    # ------------------------------------------------------------- leitura
    def listar(self) -> list[Essencia]:
        """Todas as essências da usuária (vazio para conta nova)."""
        return list(self.repo.list(Essencia.nome, Essencia.id))

    def obter(self, essencia_id: int) -> Essencia:
        """Uma essência da usuária; 404 se não existir ou for de outra."""
        return self.repo.get_or_404(essencia_id)

    # ---------------------------------------------------------- reconhecimento
    def sugerir_classificacao(self, nome: str) -> list[SugestaoReferencia]:
        """Notas de conhecimento que podem corresponder a `nome`.

        Só leitura: nada é gravado. É o que o front chama enquanto a aluna
        digita o nome, e o que vem em `sugestoes_referencia` no cadastro.
        """
        notas = {n.id: n for n in self.conhecimento.notas()}
        refs = [NotaRef(n.id, n.nome, tuple(n.sinonimos or ())) for n in notas.values()]
        sugestoes = []
        for corr in buscar_correspondencias(nome, refs):
            nota = notas[corr.nota_id]
            valores = valores_da_referencia(nota)
            sugestoes.append(
                SugestaoReferencia(
                    nota_id=nota.id,
                    nome=nota.nome,
                    correspondencia=corr.tipo,
                    termo=corr.termo,
                    familia=valores["familia"],
                    subfamilia=valores["subfamilia"],
                    tipo=valores["tipo"],
                    papel=valores["papel"],
                    v1=valores["v1"],
                    v2=valores["v2"],
                    v3=valores["v3"],
                    v4=valores["v4"],
                    v6=valores["v6"],
                    confianca_referencia=nota.confianca_referencia,
                    ilustrativa=nota.ilustrativo,
                    fonte=nota.fonte,
                    avisos=_avisos_referencia(nota),
                )
            )
        return sugestoes

    def _aplicar_referencia(
        self, dados: dict[str, Any], nota: KnowledgeNote, atual: Essencia | None = None
    ) -> None:
        """Preenche em `dados` os campos VAZIOS com os valores da referência.

        "Vazio" = a aluna não enviou o campo agora E (na edição) a essência
        também não tem valor gravado. Assim, aplicar a referência de novo
        numa essência já corrigida pela aluna nunca apaga a correção dela —
        antes, a edição sobrescrevia tudo que não viesse no payload.
        """
        for campo, valor in valores_da_referencia(nota).items():
            if valor is None or dados.get(campo) is not None:
                continue
            if atual is not None and getattr(atual, campo) not in (None, [], {}):
                continue
            dados[campo] = valor
        # Origem e confiança vêm da referência só no cadastro; na edição, o que
        # a aluna já informou sobre a essência dela continua valendo.
        if atual is None:
            if nota.ilustrativo:
                # Exemplo nunca vira "ficha técnica": a classificação é uma
                # estimativa que a aluna aceitou, com confiança baixa.
                dados.setdefault("origem", "estimado")
                dados.setdefault("confianca", "baixa")
            else:
                dados.setdefault("origem", "tecnico")
                dados.setdefault("confianca", nota.confianca_referencia)

    def _nota_ou_404(self, nota_id: int) -> KnowledgeNote:
        nota = self.conhecimento.nota(nota_id)
        if nota is None:
            raise NotFoundError(f"Nota de referência {nota_id} não encontrada.")
        return nota

    # ------------------------------------------------- cadastro simples (3 campos)
    def _regras_simples(self):
        """Perfis típicos dos grupos de cheiro (para estimar) e a regra de percepção, do banco.

        Raises:
            KnowledgeUnavailableError: seed não executado.
        """
        territorios = carregar_territorios(
            self.conhecimento.regras_por_tipo("criacao_territorio")["criacao_territorio"])
        regra = self.conhecimento.regra("peso_score", "percepcao")
        if not territorios or regra is None:
            raise KnowledgeUnavailableError(
                "Regras do cadastro de essências ausentes na base. Execute o seed (python -m app.seed)."
            )
        return territorios, regra.valor

    @staticmethod
    def _nome_limpo(nome: str) -> str:
        """Nome sem espaços sobrando; de 2 a 100 caracteres."""
        limpo = " ".join((nome or "").split())
        if not 2 <= len(limpo) <= 100:
            raise BusinessRuleError("Digite o nome da essência (de 2 a 100 letras).")
        return limpo

    def _familias_da_base(self) -> list[Any]:
        """TODAS as famílias cadastradas na base (as de topo e as subfamílias), na ordem de exibição."""
        return list(self.conhecimento.familias())

    @staticmethod
    def _familia(texto: str, familias: list[Any]) -> Any:
        """Família escolhida; precisa ser uma das cadastradas na base (nome ou slug, sem acento/caixa)."""
        k = chave(texto)
        for f in familias:
            partes = {chave(p) for p in f.nome.split("/")}     # "Aquático/Marinho" também vale por parte
            if k in {chave(f.nome), f.slug} | partes:
                return f
        raise BusinessRuleError("Escolha uma das famílias da lista.")

    @staticmethod
    def _grupo_da_familia(familia: Any, familias: list[Any], territorios: dict) -> Any:
        """Grupo de cheiro (perfil típico) que cobre a família; a subfamília herda o da mãe.

        É o grupo que fornece v2, v3, v4 e o papel quando a essência é só estimada.
        """
        por_id = {f.id: f for f in familias}
        hierarquia = {f.slug: por_id[f.parent_id].slug for f in familias if f.parent_id in por_id}
        chave_grupo = territorio_da_familia(familia.slug, territorios, hierarquia)
        if chave_grupo is None:
            raise BusinessRuleError("Ainda não sei estimar essa família. Escolha outra ou avise a professora.")
        return territorios[chave_grupo]

    @staticmethod
    def _percepcao(texto: str) -> str:
        k = normalizar(texto)
        if k not in PERCEPCOES_SIMPLES:
            raise BusinessRuleError("Escolha Fria, Neutra ou Quente.")
        return k

    @staticmethod
    def _nomes_da_familia(familia: Any) -> tuple[str, str | None]:
        """(familia, subfamilia) como a essência guarda: subfamília vira (mãe, ela mesma)."""
        if familia.parent is not None:
            return familia.parent.nome, familia.nome
        return familia.nome, None

    def _campos_derivados(
        self, nome: str, familia: Any, percepcao: str, nota: KnowledgeNote | None,
        familias: list[Any], territorios: dict, regra: dict,
    ) -> dict[str, Any]:
        """Monta TODOS os campos da essência a partir dos 3 que a aluna informou.

        Precedência: (1) nota reconhecida, mantida pela aluna (mesma família e mesma
        percepção sugeridas) e NÃO de exemplo -> valores da nota; (2) senão perfil do
        grupo de cheiro da família + temperatura da percepção, com confiança baixa.
        Se havia nota e a aluna mudou a sugestão, o vínculo fica e
        `editado_da_referencia` vira True. Nota de exemplo nunca tem números copiados.
        """
        sug_slug = nota.family.slug if nota is not None and nota.family is not None else None
        sug_perc = percepcao_de_v1(nota.v1_ref, regra) if nota is not None else None
        mantida = nota is not None and familia.slug == sug_slug and percepcao == sug_perc

        derivado = None
        if mantida and not nota.ilustrativo:
            derivado = valores_da_nota(
                {"v1": nota.v1_ref, "v2": nota.v2_ref, "v3": nota.v3_ref, "v4": nota.v4_ref},
                nota.papel_tipico, nota.tipo_referencia, nota.confianca_referencia, regra["v5_neutro"])
        if derivado is None:
            derivado = derivar(self._grupo_da_familia(familia, familias, territorios).perfil, percepcao, regra)
        nome_familia, nome_sub = self._nomes_da_familia(familia)
        return {
            "nome": nome, "nome_canonico": normalizar(nome),
            "familia": nome_familia, "subfamilia": nome_sub, "percepcao": percepcao,
            "v1": derivado.v1, "v2": derivado.v2, "v3": derivado.v3, "v4": derivado.v4, "v5": derivado.v5,
            "papel": derivado.papel, "confianca": derivado.confianca, "origem": derivado.origem,
            "tipo": nota.tipo_referencia if mantida else "desconhecida",
            "knowledge_note_id": nota.id if nota else None,
            "editado_da_referencia": bool(nota is not None and not mantida),
        }

    def opcoes_cadastro(self) -> OpcoesCadastroOut:
        """Chips do formulário: TODAS as famílias da base (na ordem dela) e as 3 percepções."""
        _, regra = self._regras_simples()
        return OpcoesCadastroOut(
            familias=[OpcaoCadastroOut(chave=f.slug, nome=f.nome) for f in self._familias_da_base()],
            percepcoes=[OpcaoCadastroOut(chave=k, nome=regra["rotulos"][k]) for k in PERCEPCOES_SIMPLES],
        )

    def sugerir_por_nome(self, nome: str) -> SugestaoNomeOut:
        """Reconhece o nome na base de conhecimento. SÓ sugestão: nada é gravado.

        "exata": nome ou sinônimo idêntico (sem acento/caixa). "parecida": um nome
        contém o outro como palavra inteira. Usa apenas `knowledge_notes` (camada
        compartilhada); nunca olha o repertório de ninguém.
        """
        _, regra = self._regras_simples()
        notas = {n.id: n for n in self.conhecimento.notas()}
        refs = [NotaRef(n.id, n.nome, tuple(n.sinonimos or ())) for n in notas.values()]
        achadas = buscar_correspondencias(nome, refs, limite=1)
        if not achadas:
            return SugestaoNomeOut(encontrada=False)
        nota = notas[achadas[0].nota_id]
        return SugestaoNomeOut(
            encontrada=True, nivel="exata" if achadas[0].tipo == "exata" else "parecida",
            nota_id=nota.id, nota_nome=nota.nome,
            familia=nota.family.nome if nota.family is not None else None,
            percepcao=percepcao_de_v1(nota.v1_ref, regra),
            aviso_educativo=nota.observacoes or None,
        )

    # ------------------------------------------------------------- escrita
    def criar(self, payload: EssenciaCreate) -> EssenciaCriadaOut:
        """Cadastra uma essência a partir de Nome + Família + Percepção.

        A família é qualquer uma das cadastradas na base. O servidor deduz o resto
        (ver `_campos_derivados`); nada além dos 3 campos (e do id da nota
        confirmada) enviado pelo cliente é usado.
        """
        territorios, regra = self._regras_simples()
        familias = self._familias_da_base()
        nome = self._nome_limpo(payload.nome)
        familia = self._familia(payload.familia, familias)
        percepcao = self._percepcao(payload.percepcao)
        nota = self._nota_ou_404(payload.aceitou_nota_id) if payload.aceitou_nota_id else None

        essencia = Essencia(**self._campos_derivados(nome, familia, percepcao, nota, familias, territorios, regra))
        self.repo.add(essencia)
        self.db.commit()
        return EssenciaCriadaOut.model_validate(essencia)

    def atualizar(self, essencia_id: int, payload: EssenciaUpdate) -> Essencia:
        """Edita nome, família e/ou percepção; os derivados são RECALCULADOS.

        Só recalcula quando família ou percepção realmente mudam (ou a aluna
        confirma uma nota): reenviar os mesmos valores, ou trocar só o nome, não
        mexe nos números. Essência cuja família guardada não é reconhecida: a aluna
        escolhe uma da lista ao trocar a percepção ou a família.
        """
        essencia = self.repo.get_or_404(essencia_id)
        dados = payload.model_dump(exclude_unset=True)
        nome = self._nome_limpo(dados["nome"]) if "nome" in dados else essencia.nome

        mexe = any(c in dados for c in ("familia", "percepcao")) or dados.get("aceitou_nota_id")
        novos: dict[str, Any] = {"nome": nome, "nome_canonico": normalizar(nome)}
        if mexe:
            territorios, regra = self._regras_simples()
            familias = self._familias_da_base()
            if "familia" in dados:
                familia = self._familia(dados["familia"], familias)
            else:
                # Mantém a família atual; o motor também reconhece os nomes de grupo do cadastro anterior.
                familia = ContextoMotor(self.db).familia_por_texto(essencia.subfamilia or essencia.familia)
                if familia is None:
                    raise BusinessRuleError("Escolha uma das famílias da lista.")
            percepcao = self._percepcao(
                dados.get("percepcao") or essencia.percepcao
                or percepcao_de_v1(essencia.v1, regra) or "")
            nota_id = dados.get("aceitou_nota_id") or essencia.knowledge_note_id
            nomes = self._nomes_da_familia(familia)
            mudou = (nomes != (essencia.familia, essencia.subfamilia) or percepcao != essencia.percepcao
                     or dados.get("aceitou_nota_id") not in (None, essencia.knowledge_note_id))
            if mudou:
                nota = self._nota_ou_404(nota_id) if nota_id else None
                novos = self._campos_derivados(nome, familia, percepcao, nota, familias, territorios, regra)
        self.repo.update(essencia, novos)
        self.db.commit()
        return essencia

    def definir_ficha(self, essencia_id: int, ficha: dict[str, Any] | None) -> Essencia:
        """Grava (ou limpa) a ficha técnica DOCUMENTADA. Fora do cadastro simples.

        Usada pelos limites de uso do cálculo de formulação. Vazio/nulo limpa.
        """
        essencia = self.repo.get_or_404(essencia_id)
        self.repo.update(essencia, {"ficha": _podar(ficha)})
        self.db.commit()
        return essencia

    def apagar(self, essencia_id: int) -> None:
        """Remove a essência. Acordes antigos mantêm o snapshot do nome."""
        self.repo.delete(self.repo.get_or_404(essencia_id))
        self.db.commit()

    # ----------------------------------------------------- compatibilidade
    def compatibilidade(self, essencia_ids: list[int]) -> dict:
        """Como estas essências trabalham juntas, SEM criar acorde nem versão.

        Só aceita essências do repertório dela (regra 3): id de outra usuária
        ou inexistente → 404, sem distinguir os dois casos.
        """
        encontradas = self.repo.get_many(essencia_ids)
        faltando = [i for i in essencia_ids if i not in encontradas]
        if faltando:
            raise NotFoundError(
                f"Essência(s) {', '.join(map(str, faltando))} não encontrada(s) no seu repertório."
            )
        ctx = ContextoMotor(self.db)
        motor = [ctx.essencia_motor(encontradas[i]) for i in essencia_ids]
        with regras_obrigatorias():
            resultado = ctx.compatibilidade(motor)
        return resultado.como_dict()

    # ------------------------------------------------------------- lacunas
    def lacunas(self) -> list[Lacuna]:
        """O que falta no repertório (funcionalidade 2.9), só com dados da usuária."""
        ctx = ContextoMotor(self.db)
        repertorio = [ctx.essencia_motor(e) for e in self.repo.list()]
        with regras_obrigatorias():
            return lacunas_repertorio(repertorio, ctx.familias_ref, ctx.parametros("lacunas"))

