import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { criacoes, formulacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import FormulaTabela from '../components/FormulaTabela';
import { Campo, Carregando, Chips, Erro, Grupo, Pill } from '../components/ui';

/**
 * Fluxo de formulação: produto -> concentração -> volume -> descrição em
 * linguagem natural -> proposta (acorde só com as essências dela) -> fórmula.
 * Concentrações e base vêm da API. A fórmula só aparece quando há fundamento;
 * sem ele, a tela mostra apenas a orientação necessária.
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

  async function propor(e) {
    e.preventDefault();
    setErro(null);
    setCalculando(true);
    try {
      const corpo = {
        produto,
        concentracao_pct: conc,
        volume_ml: Number(volume.replace(',', '.')),
        descricao: descricao.trim(),
      };
      setProposta(await formulacoes.propor(corpo));
      setPedidoEnviado(corpo);
      window.scrollTo({ top: 0 });
    } catch (err) {
      setErro(err);
    } finally {
      setCalculando(false);
    }
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
        <Proposta proposta={proposta} pedido={pedidoEnviado} atual={atual} onCriada={(id) => navigate(`/criacoes/${id}`)} />
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
            {calculando ? 'Criando…' : '✨ Criar proposta'}
          </button>
        </form>
      )}
    </div>
  );
}

function Proposta({ proposta, pedido, atual, onCriada }) {
  const { sugestao, formulacao, sem_formulacao: semFormulacao } = proposta;
  const { identidade, acorde, entendimento } = sugestao;
  const [nome, setNome] = useState(identidade?.nome_sugerido || '');
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);
  const pode = formulacao?.valido;

  const entendi = entendimento
    ? [...entendimento.emocoes, ...entendimento.preferencias, ...(entendimento.intensidade != null ? [`intensidade ${entendimento.intensidade}`] : [])]
    : [];
  const avisos = [...new Set([...(sugestao.avisos || []), ...(formulacao?.avisos || [])])];

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

  return (
    <>
      {entendimento && (
        <section className="cartao">
          <h2 className="secao-titulo">O que entendi</h2>
          {entendi.length ? (
            <div className="chips">{entendi.map((t) => <Pill key={t}>{t}</Pill>)}</div>
          ) : null}
          {entendimento.negados.length > 0 && (
            <small className="texto-suave">Não usei (você disse que não quer): {entendimento.negados.join(', ')}.</small>
          )}
        </section>
      )}

      {sugestao.status !== 'ok' && sugestao.mensagem && <p className="aviso">{sugestao.mensagem}</p>}

      {identidade && (
        <section className="cartao-amarelo">
          <h2>{identidade.nome_sugerido || 'Sua fragrância'}</h2>
          <p><strong>Direção:</strong> {identidade.direcao}</p>
        </section>
      )}

      {acorde && (
        <section>
          <h2 className="secao-titulo">Acorde proposto{acorde.familia_resultante ? ` · ${acorde.familia_resultante}` : ''}</h2>
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

      {semFormulacao && <p className="aviso">{semFormulacao}</p>}
      {formulacao && !formulacao.valido && (
        <section className="cartao">
          <h2 className="secao-titulo">Não foi possível calcular</h2>
          {formulacao.erros.map((m) => <p key={m} className="aviso">{m}</p>)}
        </section>
      )}
      {pode && <FormulaTabela formulacao={formulacao} base={atual?.exemplo} />}

      {avisos.map((a) => <p key={a} className="aviso">{a}</p>)}
      {sugestao.lacunas.map((l) => <p key={l.mensagem} className="aviso">{l.mensagem}</p>)}

      <Erro erro={erro} />
      {acorde && (
        <Campo rotulo="Nome da criação">
          <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={160} />
        </Campo>
      )}
      {acorde && (
        <button className="btn btn-primario" onClick={salvar} disabled={salvando || !pode}>
          {salvando ? 'Salvando…' : 'Salvar como criação'}
        </button>
      )}
    </>
  );
}
