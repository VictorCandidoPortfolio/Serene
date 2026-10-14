"""Perfil olfativo: questionário → vetor-alvo → recomendações do repertório.

O cálculo do alvo e a recomendação são funções de módulo (e não só métodos
do service de perfis) porque três lugares as usam:
- o perfil olfativo (questionário completo);
- a criação com "intenção rápida" (território/público escolhidos na hora);
- a criação inspirada num perfume de referência.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.engine.axes import ROTULOS_EIXOS
from app.engine.recommendation import calcular_vetor_alvo, pontuar_essencias
from app.models.repertorio import PerfilOlfativo
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.repertorio import EssenciaRepository, PerfilRepository
from app.schemas.outros import EssenciaRecomendadaOut, PerfilCreate, RecomendacoesOut
from app.services.motor import ContextoMotor, regras_obrigatorias
from app.services.outros_service import ReferenciasService

# Tipos de regra consultados para montar o vetor-alvo.
TIPOS_REGRAS_PERFIL = ("emocao", "preferencia", "territorio", "correlacao_territorio", "publico")


def texto_direcao(alvo: dict[str, Any], nomes_territorios: dict[str, str] | None = None) -> str:
    """Resumo legível do vetor-alvo, usado em `criacoes.direcao.texto`.

    Ex.: "Territórios: Acolhimento. Público: teen. Temperatura ≈ 6.5 (quente);
    doçura ≈ 7 (doce)."
    """
    nomes = nomes_territorios or {}
    partes = []
    if alvo.get("territorios"):
        partes.append("Territórios: " + ", ".join(nomes.get(t, t) for t in alvo["territorios"]) + ".")
    if alvo.get("publico"):
        partes.append(f"Público: {alvo['publico'].capitalize()}.")
    eixos = []
    for eixo, valor in (alvo.get("vetor") or {}).items():
        if valor is None:
            continue
        nome, baixo, alto = ROTULOS_EIXOS[eixo]
        lado = alto if valor > 5.5 else baixo if valor < 4.5 else "equilibrado"
        eixos.append(f"{nome} ≈ {valor:.1f} ({lado})".replace(".", ",", 1))
    if eixos:
        partes.append("; ".join(eixos).capitalize() + ".")
    if alvo.get("nao_reconhecidos"):
        partes.append(
            "Sem regra na base (não usados): " + ", ".join(alvo["nao_reconhecidos"]) + "."
        )
    return " ".join(partes) or "Sem direção definida."


def _nomes_territorios(db: Session) -> dict[str, str]:
    regras = KnowledgeRepository(db).regras_por_tipo("territorio")["territorio"]
    return {k: (v or {}).get("nome", k) for k, v in regras.items()}


def calcular_alvo(
    db: Session, user_id: int, respostas: dict[str, Any]
) -> dict[str, Any]:
    """Vetor-alvo a partir de respostas + regras ativas da base.

    Se `respostas.referencia_id` vier, a direção estimada daquele perfume de
    referência DA ALUNA entra como mais uma contribuição (o serviço de
    referências filtra pela dona: referência de outra usuária → 404). A
    referência só orienta a direção; nunca vira essência candidata.
    """
    extras: list[dict[str, Any]] = []
    referencia_id = respostas.get("referencia_id")
    if referencia_id is not None:
        servico = ReferenciasService(db, user_id)
        ref = servico.obter(referencia_id)
        analise = servico.analisar(referencia_id)
        extras.append(
            {"origem": "referencia", "chave": ref.nome, "vetor": {
                e: v for e, v in analise.vetor_estimado.items() if v is not None}, "peso": 1.0}
        )
    ctx = ContextoMotor(db)
    regras = KnowledgeRepository(db).regras_por_tipo(*TIPOS_REGRAS_PERFIL)
    with regras_obrigatorias():
        return calcular_vetor_alvo(respostas, regras, ctx.parametros("recomendacao"), extras).como_dict()


def direcao_de(db: Session, alvo: dict[str, Any], respostas: dict[str, Any], **origem: Any) -> dict[str, Any]:
    """Monta `criacoes.direcao` a partir de um alvo já calculado.

    Args:
        origem: de onde veio a direção — `perfil_id`, `referencia_id`, ou
            nada (intenção escolhida na hora). Fica gravado para a aluna saber.
    """
    return {
        **{k: v for k, v in origem.items() if v is not None},
        "vetor_alvo": alvo.get("vetor"),
        "territorios": alvo.get("territorios", []),
        "emocoes": (respostas or {}).get("emocoes", []),
        "publico": alvo.get("publico"),
        "vocabulario": alvo.get("vocabulario", []),
        "texto": texto_direcao(alvo, _nomes_territorios(db)),
    }


def direcao_do_perfil(db: Session, perfil: PerfilOlfativo) -> dict[str, Any]:
    """Direção de uma criação a partir de um perfil JÁ validado como da dona."""
    return direcao_de(db, perfil.vetor_alvo or {}, perfil.respostas or {}, perfil_id=perfil.id)


def recomendar(db: Session, user_id: int, alvo: dict[str, float | None]) -> RecomendacoesOut:
    """Essências DO REPERTÓRIO DA USUÁRIA ordenadas pela proximidade com `alvo`.

    Regra 3: as candidatas vêm de `EssenciaRepository(db, user_id)` (filtrado
    pela dona) — a tabela de conhecimento nunca entra aqui.
    """
    ctx = ContextoMotor(db)
    alvo = alvo or {}
    repertorio = [ctx.essencia_motor(e) for e in EssenciaRepository(db, user_id).list()]
    avisos: list[str] = []
    if not repertorio:
        avisos.append("Seu repertório está vazio: cadastre suas essências para receber sugestões.")
    if all(v is None for v in alvo.values()):
        avisos.append("A direção não define nenhum eixo; revise as respostas.")
    with regras_obrigatorias():
        pontuadas, nao_avaliadas = pontuar_essencias(alvo, repertorio, ctx.parametros("recomendacao"))
    if nao_avaliadas:
        avisos.append(
            "Algumas essências não têm características suficientes para comparar com a direção. "
            "Classifique-as na tela de Essências."
        )
    return RecomendacoesOut(
        vetor_alvo=alvo,
        recomendacoes=[EssenciaRecomendadaOut.model_validate(p) for p in pontuadas],
        nao_avaliadas=nao_avaliadas,
        avisos=avisos,
    )


class PerfisService:
    """Perfis olfativos de UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.repo = PerfilRepository(db, user_id)

    def listar(self) -> list[PerfilOlfativo]:
        """Perfis da usuária."""
        return list(self.repo.list(PerfilOlfativo.id.desc()))

    def obter(self, perfil_id: int) -> PerfilOlfativo:
        """Um perfil da usuária."""
        return self.repo.get_or_404(perfil_id)

    def criar(self, payload: PerfilCreate) -> PerfilOlfativo:
        """Grava as respostas e o vetor-alvo calculado."""
        respostas = payload.respostas.model_dump(exclude_none=True)
        perfil = PerfilOlfativo(
            respostas=respostas, vetor_alvo=calcular_alvo(self.db, self.user_id, respostas)
        )
        self.repo.add(perfil)
        self.db.commit()
        return perfil

    def atualizar(self, perfil_id: int, payload: PerfilCreate) -> PerfilOlfativo:
        """Substitui as respostas e recalcula o alvo."""
        perfil = self.repo.get_or_404(perfil_id)
        respostas = payload.respostas.model_dump(exclude_none=True)
        self.repo.update(
            perfil, {"respostas": respostas, "vetor_alvo": calcular_alvo(self.db, self.user_id, respostas)}
        )
        self.db.commit()
        return perfil

    def apagar(self, perfil_id: int) -> None:
        """Remove o perfil (criações guardam cópia da direção, não são afetadas)."""
        self.repo.delete(self.repo.get_or_404(perfil_id))
        self.db.commit()

    def recomendacoes(self, perfil_id: int) -> RecomendacoesOut:
        """Essências do repertório dela mais próximas do alvo do perfil."""
        perfil = self.repo.get_or_404(perfil_id)
        return recomendar(self.db, self.user_id, (perfil.vetor_alvo or {}).get("vetor") or {})
