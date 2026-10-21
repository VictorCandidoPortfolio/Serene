"""Formulação: pedido em linguagem natural -> acorde -> quantidades finais.

O service carrega e valida posse; a conta e as regras técnicas estão em
`app.engine.formulacao`. As essências saem SEMPRE do repertório da usuária
(id alheio ou inexistente -> 404 sem distinguir), e criação/acorde também
passam por repositórios filtrados pela dona. A base de conhecimento fornece
apenas as REGRAS dos produtos (concentrações e composição da base).
"""

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, KnowledgeUnavailableError, NotFoundError
from app.engine.axes import PESOS_RELATIVOS, RegraInvalidaError
from app.engine.formulacao import ItemFormulacao, ResultadoFormulacao, calcular_formulacao, validar_regra
from app.models.knowledge import KnowledgeEngineRule
from app.models.repertorio import Essencia
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.repertorio import AcordeRepository, CriacaoRepository, EssenciaRepository
from app.schemas.formulacao import (
    ComponenteBaseOut,
    FaixaOut,
    FormulacaoIn,
    FormulacaoOut,
    IngredienteOut,
    PropostaIn,
    PropostaOut,
    ProdutoOut,
)
from app.schemas.formulacao_pedido import FormulacaoPedidoIn
from app.schemas.sugestao import SugestaoIn
from app.services.sugestao_service import SugestaoService

PREFIXO = "formulacao_"
MSG_SEM_FUNDAMENTO = (
    "As proporções só são calculadas quando o acorde tem fundamento: com as essências atuais ele chega "
    "só parcialmente na direção pedida. Você pode montar a fórmula manualmente com as essências que escolher."
)


def _f(x) -> float:
    return float(x)


def _item(e: Essencia, peso: int, categoria: str, densidade: Decimal | None) -> ItemFormulacao:
    """Essência do repertório -> item da calculadora, com limites/restrições DOCUMENTADOS.

    Só entra o que a ficha traz: sem ficha, não há limite nem restrição
    (e a calculadora avisa, uma vez, que não há limite documentado).
    """
    ficha: dict[str, Any] = e.ficha or {}
    limite = (ficha.get("limites_uso") or {}).get(categoria)
    restr = ficha.get("restricoes") or {}
    dens = densidade
    if dens is None and (ficha.get("identificacao") or {}).get("densidade_g_ml"):
        dens = Decimal(str(ficha["identificacao"]["densidade_g_ml"]))
    return ItemFormulacao(
        essencia_id=e.id, nome=e.nome, peso=peso, densidade_g_ml=dens,
        limite_pct_produto=Decimal(str(limite["max_pct_produto"])) if limite else None,
        limite_fonte=limite.get("fonte") if limite else None,
        bloqueada_na_categoria=categoria in (restr.get("categorias_nao_indicadas") or []),
        restricao_texto=restr.get("observacoes"),
    )


def saida_de(r: ResultadoFormulacao) -> FormulacaoOut:
    """Resultado do motor -> schema de saída (floats arredondados a 2 casas)."""
    return FormulacaoOut(
        valido=r.valido, produto=r.produto, erros=r.erros, avisos=r.avisos,
        volume_ml=_f(r.volume_ml) if r.volume_ml is not None else None,
        concentracao_pct=_f(r.concentracao_pct) if r.concentracao_pct is not None else None,
        concentrado_ml=_f(r.concentrado_ml) if r.concentrado_ml is not None else None,
        criterio=r.criterio,
        ingredientes=[IngredienteOut(
            tipo=i.tipo, nome=i.nome, essencia_id=i.essencia_id, peso=i.peso, rotulo_peso=i.rotulo_peso,
            percentual_produto=_f(i.percentual_produto),
            percentual_concentrado=_f(i.percentual_concentrado) if i.percentual_concentrado is not None else None,
            volume_ml=_f(i.volume_ml), massa_g=_f(i.massa_g) if i.massa_g is not None else None,
        ) for i in r.ingredientes],
        massa_total_g=_f(r.massa_total_g) if r.massa_total_g is not None else None,
        validacao=r.validacao,
    )


class FormulacaoService:
    """Formulação para UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.knowledge = KnowledgeRepository(db)
        self.essencias = EssenciaRepository(db, user_id)
        self.criacoes = CriacaoRepository(db, user_id)
        self.acordes = AcordeRepository(db, user_id)

    # ------------------------------------------------------------ produtos
    def _regras(self) -> dict[str, KnowledgeEngineRule]:
        regras = {r.chave[len(PREFIXO):]: r for r in self.knowledge.regras("peso_score")
                  if r.chave.startswith(PREFIXO)}
        if not regras:
            raise KnowledgeUnavailableError(
                "Regras de formulação ausentes na base de conhecimento. Execute o seed (python -m app.seed)."
            )
        return regras

    @staticmethod
    def _valida(rule: KnowledgeEngineRule) -> dict:
        try:
            return dict(validar_regra(rule.valor, rule.chave))
        except RegraInvalidaError as exc:
            raise KnowledgeUnavailableError(str(exc)) from exc

    def produtos(self) -> list[ProdutoOut]:
        """Produtos, concentrações permitidas e composição da base (do banco)."""
        out = []
        for chave, rule in sorted(self._regras().items()):
            v = self._valida(rule)
            vol = v["volume_ml"]
            out.append(ProdutoOut(
                chave=chave, nome=v["nome"], concentracoes=[_f(c) for c in v["concentracoes"]],
                volume_ml=FaixaOut(min=_f(vol["min"]), max=_f(vol["max"]), padrao=_f(vol["padrao"])),
                base=[ComponenteBaseOut(nome=c["nome"], percentual=_f(c["percentual"]))
                      for c in v["base"]["componentes"]],
                exemplo=rule.ilustrativo,
            ))
        return out

    # ------------------------------------------------------------- cálculo
    def _regra_do_produto(self, produto: str) -> tuple[dict, bool]:
        """(regra validada, é de exemplo?) do produto."""
        regras = self._regras()
        if produto not in regras:
            raise BusinessRuleError(
                f"Produto '{produto}' desconhecido. Disponíveis: {', '.join(sorted(regras))}."
            )
        return self._valida(regras[produto]), regras[produto].ilustrativo

    def calcular_itens(
        self,
        pedido: FormulacaoPedidoIn,
        pares: list[tuple[int, int]],
        densidades: dict[int, Decimal] | None = None,
    ) -> FormulacaoOut:
        """Formula [(essencia_id, peso 1..3)] do repertório da usuária.

        Raises:
            NotFoundError: id fora do repertório dela (de outra usuária ou inexistente).
        """
        regra, base_de_exemplo = self._regra_do_produto(pedido.produto)
        achadas = self.essencias.get_many([i for i, _ in pares])
        faltando = [i for i, _ in pares if i not in achadas]
        if faltando:
            raise NotFoundError(
                f"Essência(s) {', '.join(map(str, faltando))} não encontrada(s) no seu repertório."
            )
        dens = densidades or {}
        itens = [_item(achadas[i], peso, pedido.produto, dens.get(i)) for i, peso in pares]
        r = calcular_formulacao(regra, itens, pedido.volume_ml, pedido.concentracao_pct, pedido.proporcoes_pct)
        saida = saida_de(r)
        if saida.valido:
            saida.pendencias = self._pendencias(
                base_de_exemplo, [achadas[i] for i, _ in pares], saida.massa_total_g is None)
        return saida

    @staticmethod
    def _pendencias(base_de_exemplo: bool, essencias: list[Essencia], sem_massa: bool) -> list[str]:
        """O que ainda precisa de confirmação técnica antes de produzir (cada item só se for verdade)."""
        out = []
        if base_de_exemplo:
            out.append("A composição da base e as concentrações do produto são valores de exemplo: "
                       "confirme com a professora ou com o fornecedor da base.")
        estimadas = sorted(e.nome for e in essencias if e.origem == "estimado")
        if estimadas:
            out.append("Valores olfativos estimados por família e percepção (sem ficha técnica) em: "
                       + ", ".join(estimadas) + ". As proporções refletem essa estimativa.")
        if sem_massa:
            out.append("Quantidades em gramas não calculadas: faltam as densidades das essências e da base.")
        return out

    def calcular(self, pedido: FormulacaoIn) -> FormulacaoOut:
        """Valida e calcula. Pedido tecnicamente inválido => 200 com `valido=false` e `erros`."""
        dens: dict[int, Decimal] = dict(pedido.densidades)
        if pedido.criacao_id is not None:
            criacao = self.criacoes.get_or_404(pedido.criacao_id)
            if pedido.acorde_id is not None:
                acorde = self.acordes.get_or_404(criacao.id, pedido.acorde_id)
            else:
                versoes = self.acordes.list_by_criacao(criacao.id)
                if not versoes:
                    raise BusinessRuleError("Esta criação ainda não tem acorde para formular.")
                acorde = versoes[-1]
            pares = [(i["essencia_id"], PESOS_RELATIVOS[i["peso"]]) for i in acorde.itens]
            existentes = self.essencias.get_many([i for i, _ in pares])
            sumidas = [i["nome"] for i in acorde.itens if i["essencia_id"] not in existentes]
            if sumidas:
                raise BusinessRuleError(
                    "Estas essências do acorde não estão mais no seu repertório: "
                    + ", ".join(sumidas) + ". Crie uma nova versão sem elas."
                )
        else:
            pares = [(i.essencia_id, PESOS_RELATIVOS[i.peso]) for i in pedido.itens]
            for i in pedido.itens:
                if i.densidade_g_ml is not None:
                    dens[i.essencia_id] = i.densidade_g_ml
        return self.calcular_itens(pedido, pares, dens)

    # ------------------------------------------------------------- proposta
    def propor(self, pedido: PropostaIn) -> PropostaOut:
        """Intenção em linguagem natural -> acorde (só repertório dela) -> fórmula.

        A fórmula só sai quando há fundamento: acorde montado com essências
        classificadas e que alcança a direção pedida. Caso contrário, o motivo
        vem em `sem_formulacao` e nenhuma quantidade é inventada.
        """
        self._regra_do_produto(pedido.produto)   # falha cedo se o produto não existe
        sugestao = SugestaoService(self.db, self.user_id).sugerir(SugestaoIn(
            genero=pedido.genero, idade=pedido.idade, emocoes=pedido.emocoes,
            preferencias=pedido.preferencias, intensidade=pedido.intensidade,
            descricao=pedido.descricao, essencias_disponiveis=pedido.essencias_disponiveis,
            modo=pedido.modo,
        ))
        if sugestao.status != "ok" or sugestao.acorde is None:
            return PropostaOut(sugestao=sugestao, motivo_nao_salvar=sugestao.mensagem)
        if not sugestao.dados_suficientes:
            return PropostaOut(sugestao=sugestao, sem_formulacao=MSG_SEM_FUNDAMENTO,
                               motivo_nao_salvar=MSG_SEM_FUNDAMENTO)
        formulacao = self.calcular_itens(
            FormulacaoPedidoIn(produto=pedido.produto, volume_ml=pedido.volume_ml,
                               concentracao_pct=pedido.concentracao_pct),
            [(i.essencia_id, i.peso) for i in sugestao.acorde.itens],
        )
        # Salvar como criação cria o acorde da versão 1, que exige 2 ou mais essências.
        n = len(sugestao.acorde.itens)
        pode = formulacao.valido and n >= 2
        motivo = None
        if not formulacao.valido:
            motivo = " ".join(formulacao.erros)
        elif n < 2:
            motivo = ("Para salvar como criação são necessárias pelo menos 2 essências com Família e Percepção. "
                      "A fórmula acima já pode ser usada como referência.")
        return PropostaOut(sugestao=sugestao, formulacao=formulacao, pode_salvar=pode, motivo_nao_salvar=motivo)
