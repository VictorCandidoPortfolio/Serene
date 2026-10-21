"""Sugestão de criação: orquestra repertório + regras do banco + motor puro.

Camadas: o router valida e delega; este service carrega os dados (SÓ pelos
repositórios filtrados pela dona), chama `app.engine.criacao` e monta a
resposta. Não há SQL aqui e não há chamada a modelo de linguagem.

Isolamento: as candidatas vêm de `EssenciaRepository(db, user_id)`. A base
`knowledge_*` entra apenas como REGRAS e como referência para NOMEAR lacunas
— nunca como candidata. Por isso uma nota de conhecimento não pode aparecer no
acorde, mesmo que a usuária não tenha cadastrado nada.

Regra de confiabilidade: nada é afirmado sem dado. Pedido sem direção,
repertório sem características e essência sem características NÃO geram
identidade, acorde ou justificativa inventados; cada limitação aparece uma vez.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, KnowledgeUnavailableError, NotFoundError
from app.core.text import chave
from app.engine import criacao as motor
from app.engine import linguagem
from app.engine.axes import ROTULOS_PESO, EssenciaMotor
from app.engine.gaps import lacuna_para_movimento, lacunas_repertorio
from app.models.repertorio import Essencia
from app.repositories.repertorio import EssenciaRepository
from app.schemas.sugestao import (
    AcordeSugeridoOut,
    EntendimentoOut,
    EssenciaPendenteOut,
    IdentidadeOut,
    ItemSugeridoOut,
    LacunaSugestaoOut,
    OpcaoOut,
    OpcoesSugestaoOut,
    SugestaoIn,
    SugestaoOut,
)
from app.services.motor import ContextoMotor, regras_obrigatorias

TIPOS_REGRAS = (
    "criacao_emocao", "criacao_preferencia", "criacao_idade", "criacao_territorio",
    "criacao_vocabulario",
)
GENEROS = [("feminino", "Feminino"), ("masculino", "Masculino"), ("unissex", "Unissex"),
           ("nao_definir", "Prefiro não definir")]
MSG_INSUFICIENTE = "Cadastre pelo menos 2 essências para o laboratório criar com você."
MSG_SEM_DIRECAO = "Escolha ao menos uma emoção ou preferência para o laboratório criar com você."
MSG_SEM_ENTENDER = ("Não identifiquei emoções ou preferências na sua descrição. Use palavras como amor, "
                    "calma, doce, floral, fresco, amadeirado… ou escolha as opções.")
# Uma essência só entra nos cálculos com Família e Percepção (é o que gera os valores internos).
# Para a PROPOSTA basta uma; para SALVAR como criação são necessárias duas (um acorde tem 2 ou mais).
MSG_SEM_DADOS = ("Para calcular a fórmula, ao menos uma essência precisa ter Família e Percepção. "
                 "Complete as essências abaixo e refaça a proposta.")
MSG_BASE = "As sugestões ficam mais precisas quando suas essências são reconhecidas pela nossa base."
MSG_FRACO = "Com as essências que você tem hoje, a proposta chega só parcialmente nessa direção."


class SugestaoService:
    """Sugere identidade + acorde para UMA usuária."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.essencias = EssenciaRepository(db, user_id)
        self.ctx = ContextoMotor(db)

    # ------------------------------------------------------------- regras
    def _regras(self) -> dict[str, dict[str, Any]]:
        """Regras ativas do motor de criação; falha alto se o seed não rodou."""
        regras = self.ctx.repo.regras_por_tipo(*TIPOS_REGRAS)
        faltando = [t for t in ("criacao_emocao", "criacao_territorio", "criacao_vocabulario")
                    if not regras[t]]
        if faltando or "identidade" not in regras["criacao_vocabulario"]:
            raise KnowledgeUnavailableError(
                "Regras do motor de criação ausentes na base de conhecimento. "
                "Execute o seed (python -m app.seed)."
            )
        return regras

    def opcoes(self) -> OpcoesSugestaoOut:
        """Chips do formulário, lidos do banco (emoção nova = só um INSERT)."""
        regras = self._regras()

        def lista(tipo: str) -> list[OpcaoOut]:
            return [OpcaoOut(chave=k, rotulo=str(v.get("rotulo", k)))
                    for k, v in regras[tipo].items()]

        faixas = sorted(regras["criacao_idade"].items(), key=lambda kv: float(kv[1].get("anos_de", 0)))
        return OpcoesSugestaoOut(
            emocoes=lista("criacao_emocao"), preferencias=lista("criacao_preferencia"),
            generos=[OpcaoOut(chave=c, rotulo=r) for c, r in GENEROS],
            faixas_idade=[OpcaoOut(chave=k, rotulo=str(v.get("rotulo", k))) for k, v in faixas],
        )

    # ---------------------------------------------------------- repertório
    def _repertorio(self, pedido: SugestaoIn) -> list[Essencia]:
        """Essências que o motor pode usar: SÓ as da usuária.

        `essencias_disponiveis` com id que não é dela (de outra usuária, de
        nota de conhecimento, inexistente) -> 404, sem distinguir o caso.
        """
        if pedido.essencias_disponiveis == "todas":
            return list(self.essencias.list())
        ids = list(dict.fromkeys(pedido.essencias_disponiveis))
        achadas = self.essencias.get_many(ids)
        faltando = [i for i in ids if i not in achadas]
        if faltando:
            raise NotFoundError(
                f"Essência(s) {', '.join(map(str, faltando))} não encontrada(s) no seu repertório."
            )
        return sorted(achadas.values(), key=lambda e: e.id)

    @staticmethod
    def _faixa(idade: int | str | None, regras_idade: dict[str, Any]) -> str | None:
        """Número -> faixa (regra em dados); texto -> chave da faixa, que precisa existir."""
        if idade is None:
            return None
        if isinstance(idade, str) and idade.strip().isdigit():
            idade = int(idade.strip())
        if isinstance(idade, int):
            return motor.faixa_da_idade(idade, regras_idade)
        faixa = chave(idade).replace("_", "-")
        if faixa not in regras_idade:
            raise BusinessRuleError(
                f"Faixa de idade '{idade}' desconhecida. Use: {', '.join(regras_idade)} ou um número."
            )
        return faixa

    # ------------------------------------------------------------- sugerir
    def sugerir(self, entrada: SugestaoIn) -> SugestaoOut:
        """Calcula identidade + acorde sugerido. NÃO grava nada.

        Determinístico: o mesmo pedido, com o mesmo repertório e as mesmas
        regras, devolve exatamente a mesma resposta.
        """
        regras = self._regras()
        with regras_obrigatorias():
            params = self.ctx.parametros("criacao_score")
            padrao_pesos = self.ctx.parametros("criacao_padrao_pesos")
        territorios = motor.carregar_territorios(regras["criacao_territorio"])
        vocab = regras["criacao_vocabulario"]["identidade"]
        # Descrição em linguagem natural: só palavras cadastradas; soma-se ao que veio nos chips.
        interp = linguagem.interpretar(
            entrada.descricao, regras["criacao_emocao"], regras["criacao_preferencia"],
            regras["criacao_vocabulario"].get("linguagem", {}))
        intensidade = (entrada.intensidade if entrada.intensidade is not None
                       else interp.intensidade if interp.intensidade is not None
                       else float(params["intensidade_padrao"]))
        pedido = motor.Pedido(
            genero=entrada.genero,
            faixa_idade=self._faixa(entrada.idade, regras["criacao_idade"]),
            emocoes=tuple(dict.fromkeys([*entrada.emocoes, *interp.emocoes])),
            preferencias=tuple(dict.fromkeys([*entrada.preferencias, *interp.preferencias])),
            intensidade=intensidade,
        )
        entendimento = None
        if entrada.descricao and entrada.descricao.strip():
            entendimento = EntendimentoOut(
                emocoes=linguagem.rotulos(interp.emocoes, regras["criacao_emocao"]),
                preferencias=linguagem.rotulos(interp.preferencias, regras["criacao_preferencia"]),
                intensidade=interp.intensidade, negados=interp.negados)
        repertorio_db = self._repertorio(entrada)

        with regras_obrigatorias():
            alvo = motor.calcular_vetor_alvo(
                pedido, regras["criacao_emocao"], regras["criacao_preferencia"],
                regras["criacao_idade"], params,
            )
        ordem = {k: t.ordem for k, t in territorios.items()}
        top = motor.pick_territorios(
            alvo.territorios, ordem, params, self._perfis_de_territorio(territorios), alvo.vetor)

        repertorio: list[EssenciaMotor] = [self.ctx.essencia_motor(e) for e in repertorio_db]
        territorio_de = {e.id: motor.territorio_da_familia(e.familia_chave, territorios, self.ctx.hierarquia)
                         for e in repertorio}
        papel_de = {e.id: e.papel for e in repertorio}

        avisos: list[str] = []
        if alvo.nao_reconhecidos:
            avisos.append("Não reconheci estes itens e não os usei: "
                          + ", ".join(n.split(":", 1)[1] for n in alvo.nao_reconhecidos) + ".")
        tecnico: dict[str, Any] = {
            "vetor_alvo": alvo.vetor, "territorios": alvo.territorios, "dominantes": list(top),
            "faixa_idade": pedido.faixa_idade, "max_itens": alvo.max_itens,
        }
        if not alvo.tem_direcao:
            # Só o ponto neutro de partida: descrevê-lo como "direção" seria inventar.
            return SugestaoOut(
                status="pedido_incompleto",
                mensagem=MSG_SEM_ENTENDER if entendimento else MSG_SEM_DIRECAO, identidade=None, acorde=None,
                avisos=avisos, lacunas=[], dados_suficientes=False, tecnico=tecnico, entendimento=entendimento,
            )

        ident = motor.identidade(pedido, alvo, top, territorios, regras["criacao_emocao"],
                                 regras["criacao_preferencia"], vocab)
        if not repertorio:
            return SugestaoOut(
                status="insuficiente", mensagem=MSG_INSUFICIENTE,
                identidade=IdentidadeOut(**ident), acorde=None, avisos=avisos, lacunas=[],
                dados_suficientes=False, tecnico=tecnico, entendimento=entendimento,
            )

        ranking_completo = motor.pontuar_essencias(
            repertorio, territorio_de, alvo.vetor, alvo.territorios, top, params)
        # Essência sem características suficientes não pode ser comparada com o
        # pedido: fica de fora (e é citada UMA vez), em vez de entrar com nota inventada.
        ranking = [p for p in ranking_completo if p.nivel_proximidade != "sem_dado"]
        sem_dado = sorted(p.essencia.nome for p in ranking_completo if p.nivel_proximidade == "sem_dado")
        pendentes = [EssenciaPendenteOut(id=p.essencia.id, nome=p.essencia.nome)
                     for p in sorted(ranking_completo, key=lambda x: x.essencia.nome) if p.nivel_proximidade == "sem_dado"]
        if not ranking:
            return SugestaoOut(
                status="dados_insuficientes", mensagem=MSG_SEM_DADOS, identidade=IdentidadeOut(**ident),
                acorde=None, avisos=avisos, lacunas=[], dados_suficientes=False, tecnico=tecnico, entendimento=entendimento,
                essencias_sem_dados=pendentes,
            )
        if sem_dado:
            avisos.append("Ficaram de fora por falta de características: " + ", ".join(sem_dado)
                          + ". Abra cada uma em Essências e escolha Família e Percepção.")

        relacoes, hierarquia = self.ctx.relacoes, self.ctx.hierarquia
        montagem = motor.montar_acorde(
            ranking, alvo.vetor, alvo.max_itens, territorios, relacoes, hierarquia, params)
        itens = motor.atribuir_pesos(montagem.escolhidas, padrao_pesos)
        calculo = motor.vetor_do_acorde([(i.pontuada, i.peso) for i in itens], territorios, params)
        tecnico["vetor_acorde"] = calculo.vetor
        tecnico["scores"] = {p.essencia.id: round(p.score, 4) for p in ranking}

        # ---- avisos e lacunas: cada causa uma vez; sempre categorias, nunca essências ----
        if len(ranking) == 1 and not sem_dado:
            avisos.append("Seu repertório tem só uma essência: o acorde fica com pouca variedade.")
        # Cadastro simples: os valores são estimados (confiança baixa) e válidos. Não há aviso
        # por essência; só UMA frase suave quando TODAS as do acorde são assim.
        baixa = {e.id for e in repertorio_db if e.confianca == "baixa"}
        if montagem.escolhidas and all(p.essencia.id in baixa for p in montagem.escolhidas):
            avisos.append(MSG_BASE)

        nomes_familias = {f.chave: f.nome for f in self.ctx.familias_ref}
        presentes_t = {t for t in territorio_de.values() if t}
        lacunas = [LacunaSugestaoOut(**d) for d in motor.lacunas_de_territorio(
            top, [p.territorio for p in montagem.escolhidas], presentes_t, territorios, nomes_familias)]
        if montagem.fraco:
            avisos.insert(0, MSG_FRACO)
        if montagem.fraco or entrada.modo == "mostrar_lacunas":
            delta = motor.delta_de_lacuna(calculo.vetor, alvo.vetor, params)
            if delta and not lacunas:
                presentes_f = {e.familia_chave for e in repertorio if e.familia_chave}
                presentes_f |= {self.ctx.hierarquia[f] for f in presentes_f if f in self.ctx.hierarquia}
                with regras_obrigatorias():
                    g = lacuna_para_movimento(delta, calculo.vetor, self.ctx.familias_ref,
                                              presentes_f, motor.descrever_delta(delta))
                lacunas.append(LacunaSugestaoOut(
                    tipo="eixo", categoria=", ".join(g.detalhe.get("familias", [])) or None,
                    mensagem=g.mensagem))
        if entrada.modo == "mostrar_lacunas":
            # Visão geral do repertório: só CATEGORIAS que faltam (famílias, camadas).
            with regras_obrigatorias():
                geral = lacunas_repertorio(repertorio, self.ctx.familias_ref,
                                           self.ctx.parametros("lacunas"))
            ja = {lac.mensagem for lac in lacunas}
            lacunas += [LacunaSugestaoOut(tipo=g.tipo, mensagem=g.mensagem)
                        for g in geral if g.tipo not in ("repertorio_vazio", "dados_incompletos")
                        and g.mensagem not in ja][:3]

        out_itens = [
            ItemSugeridoOut(
                essencia_id=i.pontuada.essencia.id, nome=i.pontuada.essencia.nome, peso=i.peso,
                rotulo_peso=ROTULOS_PESO[i.peso],
                papel_na_criacao=motor.explicar_essencia(
                    i.pontuada, papel_de[i.pontuada.essencia.id], territorios, top, alvo.vetor,
                    params, vocab),
            ) for i in itens
        ]
        funcoes: dict[str, list[str]] = {"saida": [], "coracao": [], "fundo": []}
        for i in itens:
            papel = papel_de[i.pontuada.essencia.id]
            if papel:
                dominante = max(motor.CAMADAS, key=lambda c: (float(papel.get(c) or 0), -motor.CAMADAS.index(c)))
                if float(papel.get(dominante) or 0) > float(vocab.get("papel_dominante_acima_de", 0.5)):
                    funcoes[dominante].append(i.pontuada.essencia.nome)
        acorde = AcordeSugeridoOut(
            itens=out_itens, familia_resultante=calculo.familia_resultante, piramide=calculo.papel,
            funcoes={k: v for k, v in funcoes.items() if v},
            explicacao=motor.explicacao_do_acorde(
                [i.nome for i in out_itens], alvo, regras["criacao_emocao"], calculo.vetor, params),
        )
        return SugestaoOut(
            status="ok", mensagem=None, identidade=IdentidadeOut(**ident), acorde=acorde,
            avisos=avisos, lacunas=lacunas,
            dados_suficientes=motor.dados_suficientes(montagem.fraco, montagem.escolhidas),
            tecnico=tecnico, entendimento=entendimento, essencias_sem_dados=pendentes,
        )

    def _perfis_de_territorio(self, territorios: dict[str, motor.Territorio]) -> dict[str, dict[str, float]]:
        """Perfil médio (v1–v3) das notas de referência de cada território.

        Só serve ao fallback de `pick_territorios` (nenhuma emoção apontou
        território). É referência para escolher um RUMO, nunca candidata.
        """
        por_familia = {f.chave: f.vetor_medio for f in self.ctx.familias_ref if f.vetor_medio}
        out: dict[str, dict[str, float]] = {}
        for k, t in territorios.items():
            medias: dict[str, float] = {}
            for eixo in motor.EIXOS_DOCURA_TEMP:
                vals = [por_familia[f][eixo] for f in t.familias
                        if f in por_familia and por_familia[f].get(eixo) is not None]
                if vals:
                    medias[eixo] = sum(vals) / len(vals)
            if medias:
                out[k] = medias
        return out
