import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { criacoes, essencias, formulacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import { capitalizar } from '../lib/format';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import FormEssencia from '../components/FormEssencia';
import FormulaTabela from '../components/FormulaTabela';
import Sheet from '../components/Sheet';
import { Campo, Carregando, Chips, Erro, Grupo, Linhas, Pill } from '../components/ui';

/**
 * Criar formulação: BRIEFING (público, idade, identidade, intenção, famílias, preferências,
 * intensidade, ocasião, referência, essências) + produto + concentração + volume.
 * O servidor interpreta o briefing, consulta SÓ as essências da aluna, monta os acordes e
 * calcula a fórmula; esta tela só envia o pedido e mostra o resultado (nada é calculado aqui).
 */
const NAO_SEI = 'nao_sei';
// Escolher "suave"/"marcante" MOVE o controle de intensidade (o motor lê só a intensidade).
const INTENSIDADE_DA_PREFERENCIA = { suave: 2, marcante: 8 };

const INICIAL = {
  para_quem: '',
  publico: null,          // 'infantil' | 'adulto'
  faixa: null,
  idadeAnos: '',
  genero: 'nao_definir',
  emocoes: [],
  familias: [],
  preferencias: [],
  intensidade: null,      // null = "não importa" (o servidor usa o padrão ou a palavra da descrição)
  ocasiao: null,
  perfume_referencia: '',
  descricao: '',
  todasEssencias: true,
  essenciasEscolhidas: [],
  mostrarLacunas: false,
};

/** O briefing no formato da API (sem produto/concentração/volume). */
function montarBriefing(f) {
  const b = {
    genero: f.genero,
    emocoes: f.emocoes,
    preferencias: f.preferencias.filter((p) => p !== NAO_SEI),
    familias_desejadas: f.familias,
    modo: f.mostrarLacunas ? 'mostrar_lacunas' : 'somente_minhas',
    essencias_disponiveis: f.todasEssencias ? 'todas' : f.essenciasEscolhidas,
  };
  if (f.intensidade !== null) b.intensidade = Number(f.intensidade);
  if (f.para_quem.trim()) b.para_quem = f.para_quem.trim();
  if (f.ocasiao) b.ocasiao = f.ocasiao;
  if (f.perfume_referencia.trim()) b.perfume_referencia = f.perfume_referencia.trim();
  if (f.descricao.trim()) b.descricao = f.descricao.trim();
  if (f.idadeAnos !== '') b.idade = Number(f.idadeAnos);
  else if (f.faixa) b.idade = f.faixa;
  return b;
}

export default function Formulacao() {
  const navigate = useNavigate();
  const produtos = useApi(() => formulacoes.produtos());
  const opcoes = useApi(() => criacoes.opcoesSugestao());
  const repertorio = useApi(() => essencias.listar());
  const [form, setForm] = useState(INICIAL);
  const [produto, setProduto] = useState(null);
  const [conc, setConc] = useState(null);
  const [volume, setVolume] = useState('100');
  const [proposta, setProposta] = useState(null);
  const [pedidoEnviado, setPedidoEnviado] = useState(null);
  const [erro, setErro] = useState(null);
  const [calculando, setCalculando] = useState(false);

  const mudar = (campo, valor) => setForm((f) => ({ ...f, [campo]: valor }));
  const atual = useMemo(() => produtos.data?.find((p) => p.chave === produto), [produtos.data, produto]);

  useEffect(() => {
    if (!produto && produtos.data?.length) setProduto(produtos.data[0].chave);
  }, [produtos.data, produto]);
  // Trocar de produto limpa a concentração (só valem as do produto) e a proposta antiga.
  useEffect(() => {
    setConc(null);
    setProposta(null);
  }, [produto]);

  const chips = useMemo(() => {
    const cv = (lista) => (lista || []).map((o) => ({ chave: o.chave, nome: capitalizar(o.rotulo) }));
    const faixas = opcoes.data?.faixas_idade || [];
    return {
      emocoes: cv(opcoes.data?.emocoes),
      familias: cv(opcoes.data?.familias),
      ocasioes: cv(opcoes.data?.ocasioes),
      preferencias: [...cv(opcoes.data?.preferencias), { chave: NAO_SEI, nome: 'Não sei' }],
      generos: (opcoes.data?.generos || []).map((g) => ({ chave: g.chave, nome: g.rotulo })),
      faixasInfantis: faixas.filter((f) => f.infantil).map((f) => ({ chave: f.chave, nome: capitalizar(f.rotulo) })),
      faixasAdultas: faixas.filter((f) => !f.infantil).map((f) => ({ chave: f.chave, nome: capitalizar(f.rotulo) })),
    };
  }, [opcoes.data]);

  function mudarPreferencias(valor) {
    // "Não sei" exclui as demais; as demais retiram "Não sei".
    let novo = valor;
    if (valor.includes(NAO_SEI) && !form.preferencias.includes(NAO_SEI)) novo = [NAO_SEI];
    else novo = valor.filter((v) => v !== NAO_SEI);
    const nova = novo.find((p) => INTENSIDADE_DA_PREFERENCIA[p] && !form.preferencias.includes(p));
    setForm((f) => ({ ...f, preferencias: novo, intensidade: nova ? INTENSIDADE_DA_PREFERENCIA[nova] : f.intensidade }));
  }

  /** Envia o pedido ao servidor, que faz toda a conta. */
  async function enviar(corpo) {
    setErro(null);
    setCalculando(true);
    try {
      setProposta(await formulacoes.propor(corpo));
      setPedidoEnviado(corpo);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setErro(err);
    } finally {
      setCalculando(false);
    }
  }

  function propor(e) {
    e.preventDefault();
    enviar({
      ...montarBriefing(form),
      produto,
      concentracao_pct: conc,
      volume_ml: Number(volume.replace(',', '.')),
    });
  }

  const algoPedido = form.emocoes.length || form.familias.length || form.preferencias.some((p) => p !== NAO_SEI)
    || form.ocasiao || form.descricao.trim();

  const voltar = (
    <button className="icone-btn" onClick={() => (proposta ? setProposta(null) : navigate(-1))} aria-label="Voltar">
      <Icon name="back" />
    </button>
  );

  return (
    <div className="pagina">
      <Cabecalho titulo="Criar formulação" voltar={voltar} />
      <Erro erro={erro || produtos.error || opcoes.error} onRetry={opcoes.reload} />
      {(produtos.loading && !produtos.data) || (opcoes.loading && !opcoes.data) ? (
        <Carregando />
      ) : proposta ? (
        <Resultado
          proposta={proposta}
          pedido={pedidoEnviado}
          refazendo={calculando}
          onRefazer={() => enviar(pedidoEnviado)}
          onCriada={(id) => navigate(`/criacoes/${id}`)}
        />
      ) : (
        <form className="form" onSubmit={propor}>
          <Campo rotulo="Para quem é? (opcional)">
            <input value={form.para_quem} onChange={(e) => mudar('para_quem', e.target.value)} placeholder="Nome ou uma descrição" maxLength={160} />
          </Campo>

          <Grupo rotulo="Público">
            <Chips
              opcoes={[{ chave: 'infantil', nome: 'Infantil' }, { chave: 'adulto', nome: 'Adolescente ou adulto' }]}
              valor={form.publico}
              onChange={(v) => setForm((f) => ({ ...f, publico: v, faixa: null, idadeAnos: '' }))}
            />
          </Grupo>
          {form.publico && (
            <>
              <Grupo rotulo="Faixa etária">
                <Chips
                  opcoes={form.publico === 'infantil' ? chips.faixasInfantis : chips.faixasAdultas}
                  valor={form.faixa}
                  onChange={(v) => setForm((f) => ({ ...f, faixa: v, idadeAnos: '' }))}
                />
              </Grupo>
              <Campo rotulo="…ou a idade em anos">
                <input type="number" inputMode="numeric" min={0} max={120} value={form.idadeAnos}
                  onChange={(e) => setForm((f) => ({ ...f, idadeAnos: e.target.value, faixa: null }))} />
              </Campo>
            </>
          )}

          <Grupo rotulo="Identidade olfativa (só uma pista, não limita nada)">
            <Chips opcoes={chips.generos} valor={form.genero} onChange={(v) => mudar('genero', v || 'nao_definir')} />
          </Grupo>

          <Grupo rotulo="Intenção: o que a fragrância deve transmitir?">
            <Chips multiplo opcoes={chips.emocoes} valor={form.emocoes} onChange={(v) => mudar('emocoes', v)} />
          </Grupo>

          <Grupo rotulo="Famílias olfativas desejadas">
            <Chips multiplo opcoes={chips.familias} valor={form.familias} onChange={(v) => mudar('familias', v)} />
          </Grupo>

          <Grupo rotulo="Preferências sensoriais">
            <Chips multiplo opcoes={chips.preferencias} valor={form.preferencias} onChange={mudarPreferencias} />
          </Grupo>

          <Campo rotulo="Intensidade" dica={form.intensidade === null ? 'Não importa (toque no controle para escolher).' : 'De suave a marcante.'}>
            <div className="eixo-entrada">
              <small>Suave</small>
              <input type="range" min={0} max={10} step={1} value={form.intensidade ?? 5}
                className={form.intensidade === null ? 'inativo' : ''}
                onChange={(e) => mudar('intensidade', e.target.value)} aria-label="Intensidade, de suave a marcante" />
              <small>Marcante</small>
            </div>
          </Campo>

          <Grupo rotulo="Ocasião de uso (opcional)">
            <Chips opcoes={chips.ocasioes} valor={form.ocasiao} onChange={(v) => mudar('ocasiao', v)} />
          </Grupo>

          <Campo rotulo="Perfume de referência (opcional)" dica="Serve só como pista de direção; não é copiado nem entra como essência.">
            <input value={form.perfume_referencia} onChange={(e) => mudar('perfume_referencia', e.target.value)} maxLength={160} />
          </Campo>

          <Campo rotulo="Quer acrescentar algo? (opcional)" dica="Escreva do seu jeito; reconhecemos emoções, notas e intensidade.">
            <textarea rows={3} maxLength={600} value={form.descricao} onChange={(e) => mudar('descricao', e.target.value)}
              placeholder="Ex.: um floral que transmita paz" />
          </Campo>

          <Grupo rotulo="Quais essências usar?">
            <label className="campo-check">
              <input type="checkbox" checked={form.todasEssencias} onChange={(e) => mudar('todasEssencias', e.target.checked)} />
              <span>Usar somente as minhas essências (todas)</span>
            </label>
            {!form.todasEssencias && (
              (repertorio.data || []).length ? (
                <Chips multiplo opcoes={repertorio.data.map((e) => ({ chave: e.id, nome: e.nome }))}
                  valor={form.essenciasEscolhidas} onChange={(v) => mudar('essenciasEscolhidas', v)} />
              ) : <p className="aviso">Você ainda não cadastrou essências.</p>
            )}
          </Grupo>
          <label className="campo-check">
            <input type="checkbox" checked={form.mostrarLacunas} onChange={(e) => mudar('mostrarLacunas', e.target.checked)} />
            <span>Quero saber o que está faltando</span>
          </label>

          <Grupo rotulo="Produto">
            <Chips
              opcoes={(produtos.data || []).map((p) => ({ chave: p.chave, nome: p.nome.toUpperCase() }))}
              valor={produto}
              onChange={(v) => v && setProduto(v)}
            />
          </Grupo>
          {atual && (
            <Grupo rotulo="Concentração de essência">
              <Chips opcoes={atual.concentracoes.map((c) => ({ chave: c, nome: `${c}%` }))} valor={conc} onChange={setConc} />
            </Grupo>
          )}
          <Campo rotulo="Volume final (ml)" dica={atual ? `${atual.volume_ml.min} a ${atual.volume_ml.max} ml` : null}>
            <input inputMode="decimal" value={volume} onChange={(e) => setVolume(e.target.value)} required />
          </Campo>

          {!algoPedido && <small className="texto-suave">Escolha ao menos uma intenção, família, preferência ou ocasião (ou escreva algo) para o laboratório começar.</small>}
          <button className="btn btn-primario" disabled={calculando || !conc || !algoPedido}>
            {calculando ? 'Calculando…' : '✨ Criar proposta'}
          </button>
        </form>
      )}
    </div>
  );
}

/** Resultado: nome, briefing, direção, acordes, justificativa, fórmula, alertas e ações. */
function Resultado({ proposta, pedido, refazendo, onRefazer, onCriada }) {
  const { sugestao, formulacao, sem_formulacao: semFormulacao, pode_salvar: podeSalvar, motivo_nao_salvar: motivo } = proposta;
  const { identidade, acorde, resumo_briefing: resumo = [], alertas_seguranca: alertasSeg = [] } = sugestao;
  const semDados = sugestao.essencias_sem_dados || [];
  const estimadas = sugestao.estimadas_pelo_nome || [];
  const [nome, setNome] = useState(identidade?.nome_sugerido || '');
  const [completando, setCompletando] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [ocupada, setOcupada] = useState(null);
  const [erro, setErro] = useState(null);
  const temFormula = formulacao?.valido;
  // "Ficaram de fora…" já aparece no painel de essências para completar.
  const avisos = (sugestao.avisos || []).filter((a) => !(semDados.length && a.startsWith('Ficaram de fora')));
  const { produto, concentracao_pct: concentracao, volume_ml: volume, ...briefing } = pedido;

  async function salvar() {
    setErro(null);
    setSalvando(true);
    try {
      // O servidor recalcula tudo a partir do briefing: nenhum número do cliente é aceito.
      const nova = await criacoes.criar({
        nome: nome.trim() || 'Minha criação',
        sugestao: briefing,
        formulacao: { produto, concentracao_pct: concentracao, volume_ml: volume },
      });
      onCriada(nova.id);
    } catch (err) {
      setErro(err);
      setSalvando(false);
    }
  }

  async function abrirCompletar(id) {
    setErro(null);
    try {
      setCompletando(await essencias.obter(id));
    } catch (err) {
      setErro(err);
    }
  }

  /** Confirma o perfil de uma matéria-prima conhecida para a essência (a aluna decidiu). */
  async function usarSugestao(e) {
    setErro(null);
    setOcupada(e.id);
    try {
      await essencias.atualizar(e.id, { familia: e.sugestao.familia, percepcao: e.sugestao.percepcao, aceitou_nota_id: e.sugestao.nota_id });
      onRefazer();
    } catch (err) {
      setErro(err);
    } finally {
      setOcupada(null);
    }
  }

  return (
    <>
      {acorde && (
        <Campo rotulo="Nome da criação">
          <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={160} />
        </Campo>
      )}

      {alertasSeg.map((a) => <p key={a} className="aviso aviso-forte">{a}</p>)}

      {resumo.length > 0 && (
        <section className="cartao">
          <h2 className="secao-titulo">Resumo do briefing</h2>
          <Linhas itens={resumo.map((r) => [r.rotulo, r.valor])} />
          {sugestao.entendimento && (sugestao.entendimento.emocoes.length > 0 || sugestao.entendimento.preferencias.length > 0) && (
            <small className="texto-suave">
              Entendi da sua descrição: {[...sugestao.entendimento.emocoes, ...sugestao.entendimento.preferencias].join(', ')}.
            </small>
          )}
        </section>
      )}

      {sugestao.status !== 'ok' && sugestao.mensagem && <p className="aviso">{sugestao.mensagem}</p>}

      {identidade && (
        <section className="cartao-amarelo">
          <h2>Direção olfativa proposta</h2>
          <p>{identidade.direcao}</p>
          <small>{identidade.por_que}</small>
        </section>
      )}

      {semDados.length > 0 && (
        <section className="cartao">
          <h2 className="secao-titulo">Essências sem dados</h2>
          <small className="texto-suave">
            Sem Família e Percepção, estas essências não entram na conta{acorde ? ' (a proposta seguiu sem elas)' : ''}.
            Complete só o que for indispensável.
          </small>
          <ul className="lista">
            {semDados.map((e) => (
              <li key={e.id} className="item">
                <span className="item-texto">
                  <strong>{e.nome}</strong>
                  {e.sugestao && (
                    <small>Parece “{e.sugestao.nota_nome}” ({e.sugestao.familia}, {e.sugestao.percepcao}). Confirme se é o mesmo produto.</small>
                  )}
                </span>
                {e.sugestao && (
                  <button type="button" className="btn btn-pequeno btn-primario" disabled={ocupada === e.id} onClick={() => usarSugestao(e)}>
                    Confirmar
                  </button>
                )}
                <button type="button" className="btn btn-pequeno btn-contorno" onClick={() => abrirCompletar(e.id)}>
                  Completar
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {acorde && (
        <section>
          <h2 className="secao-titulo">
            Acordes e ingredientes selecionados{acorde.familia_resultante ? ` · ${acorde.familia_resultante}` : ''}
          </h2>
          <ul className="cartoes">
            {acorde.itens.map((i) => (
              <li key={i.essencia_id} className="cartao">
                <div className="secao-cabeca">
                  <strong>{i.nome}</strong>
                  <Pill>{i.rotulo_peso}</Pill>
                </div>
                {i.papel_na_criacao && <p>{i.papel_na_criacao}</p>}
              </li>
            ))}
          </ul>
          <p className="texto-suave" style={{ marginTop: 12 }}>{acorde.explicacao}</p>
          {estimadas.length > 0 && (
            <small className="texto-suave">
              Perfil geral usado (conhecimento sobre o nome, não sobre o seu produto): {estimadas.map((e) => (e.nome.toLowerCase() === e.nota_nome.toLowerCase() ? e.nome : `${e.nome} (como ${e.nota_nome})`)).join(', ')}.
            </small>
          )}
        </section>
      )}

      {temFormula && <FormulaTabela formulacao={formulacao} nome={identidade?.nome_sugerido} />}
      {formulacao && !formulacao.valido && (
        <section className="cartao">
          <h2 className="secao-titulo">Não foi possível calcular</h2>
          {formulacao.erros.map((m) => <p key={m} className="aviso">{m}</p>)}
        </section>
      )}
      {semFormulacao && <p className="aviso">{semFormulacao}</p>}

      {avisos.map((a) => <p key={a} className="aviso">{a}</p>)}
      {sugestao.lacunas.map((l) => <p key={l.mensagem} className="aviso">{l.mensagem}</p>)}

      <Erro erro={erro} />
      {acorde && podeSalvar && (
        <>
          <button className="btn btn-primario" onClick={salvar} disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar como criação'}
          </button>
          <small className="texto-suave">
            Depois de salvar você pode editar a composição, criar novas versões e registrar testes.
          </small>
        </>
      )}
      {acorde && !podeSalvar && motivo && <p className="aviso">{motivo}</p>}

      {completando && (
        <Sheet titulo="Completar essência" onClose={() => setCompletando(null)}>
          <FormEssencia
            essencia={completando}
            onClose={() => setCompletando(null)}
            onSalva={() => {
              setCompletando(null);
              onRefazer();
            }}
          />
        </Sheet>
      )}
      {refazendo && <Carregando texto="Refazendo a proposta…" />}
    </>
  );
}
