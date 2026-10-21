import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { criacoes, essencias, formulacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import FormEssencia from '../components/FormEssencia';
import FormulaTabela from '../components/FormulaTabela';
import Sheet from '../components/Sheet';
import { Campo, Carregando, Chips, Erro, Grupo, Pill } from '../components/ui';

/**
 * Fluxo de formulação: produto -> concentração -> volume -> descrição em
 * linguagem natural -> proposta. A proposta interpreta a descrição, consulta SÓ
 * as essências da aluna, monta o acorde e calcula a "Fórmula proposta"
 * (concentrado, essências, base, volume final). Concentrações e base vêm da API.
 * A fórmula só aparece quando há fundamento; sem ele, a tela diz objetivamente o
 * que falta e deixa a aluna completar as essências ali mesmo.
 */
export default function Formulacao() {
  const navigate = useNavigate();
  const produtos = useApi(() => formulacoes.produtos());
  const [produto, setProduto] = useState(null);
  const [conc, setConc] = useState(null);
  const [volume, setVolume] = useState('100');
  const [descricao, setDescricao] = useState('');
  const [proposta, setProposta] = useState(null);
  const [pedidoEnviado, setPedidoEnviado] = useState(null);
  const [erro, setErro] = useState(null);
  const [calculando, setCalculando] = useState(false);

  const atual = useMemo(() => produtos.data?.find((p) => p.chave === produto), [produtos.data, produto]);

  useEffect(() => {
    if (!produto && produtos.data?.length) setProduto(produtos.data[0].chave);
  }, [produtos.data, produto]);
  // Trocar de produto limpa a concentração (só valem as do produto) e a proposta antiga.
  useEffect(() => {
    setConc(null);
    setProposta(null);
  }, [produto]);

  /** Envia o pedido ao servidor, que faz toda a conta (nada é calculado no navegador). */
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
      produto,
      concentracao_pct: conc,
      volume_ml: Number(volume.replace(',', '.')),
      descricao: descricao.trim(),
    });
  }

  const voltar = (
    <button className="icone-btn" onClick={() => (proposta ? setProposta(null) : navigate(-1))} aria-label="Voltar">
      <Icon name="back" />
    </button>
  );

  return (
    <div className="pagina">
      <Cabecalho titulo="Formulação" voltar={voltar} />
      <Erro erro={erro || produtos.error} onRetry={produtos.reload} />
      {produtos.loading && !produtos.data ? (
        <Carregando />
      ) : proposta ? (
        <Proposta
          proposta={proposta}
          pedido={pedidoEnviado}
          refazendo={calculando}
          onRefazer={() => enviar(pedidoEnviado)}
          onCriada={(id) => navigate(`/criacoes/${id}`)}
        />
      ) : (
        <form className="form" onSubmit={propor}>
          <Grupo rotulo="Produto">
            <Chips
              opcoes={(produtos.data || []).map((p) => ({ chave: p.chave, nome: p.nome.toUpperCase() }))}
              valor={produto}
              onChange={(v) => v && setProduto(v)}
            />
          </Grupo>

          {atual && (
            <Grupo rotulo="Concentração de essência">
              <Chips
                opcoes={atual.concentracoes.map((c) => ({ chave: c, nome: `${c}%` }))}
                valor={conc}
                onChange={setConc}
              />
            </Grupo>
          )}

          <Campo rotulo="Volume final (ml)" dica={atual ? `${atual.volume_ml.min} a ${atual.volume_ml.max} ml` : null}>
            <input inputMode="decimal" value={volume} onChange={(e) => setVolume(e.target.value)} required />
          </Campo>

          <Campo rotulo="Como você quer que seja a fragrância?" dica="Escreva do seu jeito: emoções, notas, intensidade.">
            <textarea
              rows={4}
              maxLength={600}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Ex.: algo doce, floral e bem suave, que passe calma"
              required
            />
          </Campo>

          <button className="btn btn-primario" disabled={calculando || !conc || !descricao.trim()}>
            {calculando ? 'Calculando…' : '✨ Criar proposta'}
          </button>
        </form>
      )}
    </div>
  );
}

function Proposta({ proposta, pedido, refazendo, onRefazer, onCriada }) {
  const { sugestao, formulacao, sem_formulacao: semFormulacao, pode_salvar: podeSalvar, motivo_nao_salvar: motivo } = proposta;
  const { identidade, acorde, entendimento, essencias_sem_dados: semDados = [] } = sugestao;
  const [nome, setNome] = useState(identidade?.nome_sugerido || '');
  const [completando, setCompletando] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);
  const temFormula = formulacao?.valido;

  const entendi = entendimento
    ? [...entendimento.emocoes, ...entendimento.preferencias, ...(entendimento.intensidade != null ? [`intensidade ${entendimento.intensidade}`] : [])]
    : [];
  // Os avisos da fórmula já aparecem em "Pendências técnicas": não se repetem aqui.
  const avisos = sugestao.avisos || [];

  async function salvar() {
    setErro(null);
    setSalvando(true);
    try {
      // O servidor recalcula tudo a partir do pedido: nenhum número do cliente é aceito.
      const nova = await criacoes.criar({
        nome: nome.trim() || 'Minha criação',
        sugestao: { descricao: pedido.descricao },
        formulacao: { produto: pedido.produto, concentracao_pct: pedido.concentracao_pct, volume_ml: pedido.volume_ml },
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

  return (
    <>
      {entendimento && (
        <section className="cartao">
          <h2 className="secao-titulo">O que entendi</h2>
          {entendi.length ? <div className="chips">{entendi.map((t) => <Pill key={t}>{t}</Pill>)}</div> : null}
          {entendimento.negados.length > 0 && (
            <small className="texto-suave">Não usei (você disse que não quer): {entendimento.negados.join(', ')}.</small>
          )}
        </section>
      )}

      {sugestao.status !== 'ok' && sugestao.mensagem && <p className="aviso">{sugestao.mensagem}</p>}

      {semDados.length > 0 && (
        <section className="cartao">
          <h2 className="secao-titulo">Essências para completar</h2>
          <small className="texto-suave">
            Estas essências ainda não têm Família e Percepção, então não entram na fórmula. Complete e refaça a proposta.
          </small>
          <ul className="lista">
            {semDados.map((e) => (
              <li key={e.id} className="item">
                <span className="item-texto"><strong>{e.nome}</strong></span>
                <button type="button" className="btn btn-pequeno btn-contorno" onClick={() => abrirCompletar(e.id)}>
                  Completar
                </button>
              </li>
            ))}
          </ul>
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

      {acorde && (
        <section>
          <h2 className="secao-titulo">
            Por que estas essências{acorde.familia_resultante ? ` · ${acorde.familia_resultante}` : ''}
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
        </section>
      )}

      {avisos.map((a) => <p key={a} className="aviso">{a}</p>)}
      {sugestao.lacunas.map((l) => <p key={l.mensagem} className="aviso">{l.mensagem}</p>)}

      <Erro erro={erro} />
      {acorde && podeSalvar && (
        <>
          <Campo rotulo="Nome da criação">
            <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={160} />
          </Campo>
          <button className="btn btn-primario" onClick={salvar} disabled={salvando}>
            {salvando ? 'Salvando…' : 'Salvar como criação'}
          </button>
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
              onRefazer();           // refaz a proposta já com os dados novos
            }}
          />
        </Sheet>
      )}
      {refazendo && <Carregando texto="Refazendo a proposta…" />}
    </>
  );
}
