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

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.text import normalizar
from app.engine.axes import EIXOS, Lacuna
from app.engine.compatibility import compatibilidade_grupo
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
    SugestaoReferencia,
)
from app.services.motor import ContextoMotor, regras_obrigatorias

# Campos que podem vir da referência; alterá-los numa essência vinculada
# marca `editado_da_referencia`.
CAMPOS_DA_REFERENCIA = (
    "familia", "subfamilia", "tipo", "papel", "v1", "v2", "v3", "v4", "v6", "descritores",
)


def valores_da_referencia(nota: KnowledgeNote) -> dict[str, Any]:
    """Classificação sugerida por uma nota de conhecimento.

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
    return {
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


def _avisos_referencia(nota: KnowledgeNote) -> list[str]:
    """Avisos honestos sobre a qualidade de uma referência."""
    avisos = []
    if nota.confianca_referencia == "baixa":
        avisos.append("Referência de baixa confiança: confira antes de aceitar.")
    if nota.tipo_referencia == "composta":
        avisos.append(
            "Referência composta (acorde/efeito comercial): a composição interna do "
            "fornecedor não é conhecida."
        )
    faltando = [e for e in ("v1", "v2", "v3", "v4", "v6") if getattr(nota, f"{e}_ref") is None]
    if faltando:
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
            dados.setdefault("origem", "tecnico")
            dados.setdefault("confianca", nota.confianca_referencia)

    def _nota_ou_404(self, nota_id: int) -> KnowledgeNote:
        nota = self.conhecimento.nota(nota_id)
        if nota is None:
            raise NotFoundError(f"Nota de referência {nota_id} não encontrada.")
        return nota

    # ------------------------------------------------------------- escrita
    def criar(self, payload: EssenciaCreate) -> EssenciaCriadaOut:
        """Cadastra uma essência no repertório da usuária.

        Fluxo de reconhecimento (nunca automático):
        - sem `knowledge_note_id`: grava só o que a aluna informou e devolve
          `sugestoes_referencia` para ela decidir;
        - com `knowledge_note_id` e `aplicar_referencia=false`: só vincula;
        - com `aplicar_referencia=true`: a aluna confirmou; campos que ela não
          informou são preenchidos pela referência.
        """
        dados = payload.model_dump(exclude_unset=True, exclude={"aplicar_referencia"})
        dados = {k: v for k, v in dados.items() if v is not None}
        nota = None
        if payload.knowledge_note_id is not None:
            nota = self._nota_ou_404(payload.knowledge_note_id)
            if payload.aplicar_referencia:
                self._aplicar_referencia(dados, nota)
        elif payload.aplicar_referencia:
            raise BusinessRuleError("aplicar_referencia exige knowledge_note_id.")

        if "confianca" not in dados:
            # Sem referência, "media" só quando a aluna classificou tudo;
            # caso contrário "baixa" — confiança não se presume.
            completo = dados.get("familia") and all(dados.get(e) is not None for e in EIXOS)
            dados["confianca"] = "media" if completo else "baixa"

        essencia = Essencia(
            **dados,
            nome_canonico=normalizar(payload.nome),
            editado_da_referencia=difere_da_referencia(dados, nota) if nota else False,
        )
        self.repo.add(essencia)
        self.db.commit()

        out = EssenciaCriadaOut.model_validate(essencia)
        if payload.knowledge_note_id is None:
            out.sugestoes_referencia = self.sugerir_classificacao(payload.nome)
        return out

    def atualizar(self, essencia_id: int, payload: EssenciaUpdate) -> Essencia:
        """Edição parcial (só os campos enviados mudam).

        `editado_da_referencia` é recalculado a partir do resultado final:
        fica True quando algum valor da essência DIFERE da referência
        vinculada. Mandar o mesmo valor que a referência já tem não conta
        como edição.
        """
        essencia = self.repo.get_or_404(essencia_id)
        dados = payload.model_dump(exclude_unset=True, exclude={"aplicar_referencia"})

        nota_id = dados.get("knowledge_note_id", essencia.knowledge_note_id)
        nota = self._nota_ou_404(nota_id) if nota_id is not None else None
        if payload.aplicar_referencia:
            if nota is None:
                raise BusinessRuleError("aplicar_referencia exige knowledge_note_id.")
            self._aplicar_referencia(dados, nota, atual=essencia)

        for lista in ("descritores", "tags"):
            if lista in dados and dados[lista] is None:
                dados[lista] = []
        if "nome" in dados:
            dados["nome_canonico"] = normalizar(dados["nome"])
        if nota is not None:
            final = {c: dados.get(c, getattr(essencia, c)) for c in CAMPOS_DA_REFERENCIA}
            dados["editado_da_referencia"] = difere_da_referencia(final, nota)
        elif "knowledge_note_id" in dados:
            dados["editado_da_referencia"] = False  # vínculo removido

        self.repo.update(essencia, dados)
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
            resultado = compatibilidade_grupo(
                motor, ctx.relacoes, ctx.parametros("compatibilidade"), ctx.hierarquia
            )
        return resultado.como_dict()

    # ------------------------------------------------------------- lacunas
    def lacunas(self) -> list[Lacuna]:
        """O que falta no repertório (funcionalidade 2.9), só com dados da usuária."""
        ctx = ContextoMotor(self.db)
        repertorio = [ctx.essencia_motor(e) for e in self.repo.list()]
        with regras_obrigatorias():
            return lacunas_repertorio(repertorio, ctx.familias_ref, ctx.parametros("lacunas"))

