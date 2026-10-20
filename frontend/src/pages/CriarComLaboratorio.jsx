import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { criacoes, essencias as essenciasApi } from '../api/serene';
import { useApi } from '../lib/useApi';
import { capitalizar } from '../lib/format';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import { Campo, Carregando, Chips, Erro, Grupo, Pill } from '../components/ui';

/**
 * "✨ O que você quer criar?": a aluna conta para quem e o que quer transmitir;
 * o laboratório responde com uma identidade e um acorde sugerido, SÓ com as
 * essências dela. Nada aqui mostra vetor, score ou termo técnico: o servidor
 * devolve texto pronto e o front só o exibe.
 */

const NAO_SEI = 'nao_sei';
// Escolher "suave"/"marcante" MOVE o controle de intensidade (o motor lê só a intensidade).
const INTENSIDADE_DA_PREFERENCIA = { suave: 2, marcante: 8 };

const INICIAL = {
  para_quem: '',
  genero: 'nao_definir',
  idadeAnos: '',
  faixa: null,
  emocoes: [],
  preferencias: [],
  intensidade: 5,
  perfume_referencia: '',
  todasEssencias: true,
  essenciasEscolhidas: [],
  mostrarLacunas: false,
};

/** Corpo enviado à API a partir do formulário (o servidor recalcula tudo). */
function montarPedido(f) {
  const pedido = {
    genero: f.genero,
    emocoes: f.emocoes,
    preferencias: f.preferencias.filter((p) => p !== NAO_SEI),
    intensidade: Number(f.intensidade),
    modo: f.mostrarLacunas ? 'mostrar_lacunas' : 'somente_minhas',
    essencias_disponiveis: f.todasEssencias ? 'todas' : f.essenciasEscolhidas,
  };
  if (f.para_quem.trim()) pedido.para_quem = f.para_quem.trim();
  if (f.perfume_referencia.trim()) pedido.perfume_referencia = f.perfume_referencia.trim();
  if (f.idadeAnos !== '') pedido.idade = Number(f.idadeAnos);
  else if (f.faixa) pedido.idade = f.faixa;
  return pedido;
}

export default function CriarComLaboratorio() {
  const navigate = useNavigate();
  const opcoes = useApi(() => criacoes.opcoesSugestao());
  const repertorio = useApi(() => essenciasApi.listar());
  const [form, setForm] = useState(INICIAL);
  const [resultado, setResultado] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const mudar = (campo, valor) => setForm((f) => ({ ...f, [campo]: valor }));

  const chips = useMemo(() => {
    const cv = (lista) => (lista || []).map((o) => ({ chave: o.chave, nome: capitalizar(o.rotulo) }));
    return {
      emocoes: cv(opcoes.data?.emocoes),
      preferencias: [...cv(opcoes.data?.preferencias), { chave: NAO_SEI, nome: 'Não sei' }],
      generos: opcoes.data?.generos || [],
      faixas: cv(opcoes.data?.faixas_idade),
    };
  }, [opcoes.data]);

  function mudarPreferencias(valor) {
    // "Não sei" exclui as demais; as demais retiram "Não sei".
    let novo = valor;
    if (valor.includes(NAO_SEI) && !form.preferencias.includes(NAO_SEI)) novo = [NAO_SEI];
    else novo = valor.filter((v) => v !== NAO_SEI);
    const nova = novo.find((p) => INTENSIDADE_DA_PREFERENCIA[p] && !form.preferencias.includes(p));
    setForm((f) => ({
      ...f,
      preferencias: novo,
      intensidade: nova ? INTENSIDADE_DA_PREFERENCIA[nova] : f.intensidade,
    }));
  }

  async function sugerir(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      setResultado(await criacoes.sugerir(montarPedido(form)));
      window.scrollTo({ top: 0 });
    } catch (err) {
      setErro(err);
    } finally {
      setEnviando(false);
    }
  }

  const voltar = (
    <button className="icone-btn" onClick={() => (resultado ? setResultado(null) : navigate('/criacoes'))} aria-label="Voltar">
      <Icon name="back" />
    </button>
  );

  return (
    <div className="pagina">
      <Cabecalho titulo="O que você quer criar?" voltar={voltar} />
      <Erro erro={erro || opcoes.error} onRetry={opcoes.reload} />
      {opcoes.loading && !opcoes.data ? (
        <Carregando />
      ) : resultado ? (
        <Resultado
          resultado={resultado}
          pedido={montarPedido(form)}
          para_quem={form.para_quem}
          onAjustar={() => setResultado(null)}
          onCriada={(id) => navigate(`/criacoes/${id}`)}
        />
      ) : (
        <form className="form" onSubmit={sugerir}>
          <Campo rotulo="Para quem é? (opcional)">
            <input value={form.para_quem} onChange={(e) => mudar('para_quem', e.target.value)} placeholder="Nome ou uma descrição" maxLength={160} />
          </Campo>

          <Grupo rotulo="Gênero (só uma pista, não limita nada)">
            <Chips opcoes={chips.generos.map((g) => ({ chave: g.chave, nome: g.rotulo }))} valor={form.genero} onChange={(v) => mudar('genero', v || 'nao_definir')} />
          </Grupo>

          <Grupo rotulo="Idade">
            <Chips opcoes={chips.faixas} valor={form.faixa} onChange={(v) => setForm((f) => ({ ...f, faixa: v, idadeAnos: '' }))} />
          </Grupo>
          <Campo rotulo="…ou a idade em anos">
            <input type="number" inputMode="numeric" min={0} max={120} value={form.idadeAnos}
              onChange={(e) => setForm((f) => ({ ...f, idadeAnos: e.target.value, faixa: null }))} />
          </Campo>

          <Grupo rotulo="O que a fragrância deve transmitir?">
            <Chips multiplo opcoes={chips.emocoes} valor={form.emocoes} onChange={(v) => mudar('emocoes', v)} />
          </Grupo>

          <Grupo rotulo="Alguma preferência?">
            <Chips multiplo opcoes={chips.preferencias} valor={form.preferencias} onChange={mudarPreferencias} />
          </Grupo>

          <Campo rotulo="Intensidade" dica="De suave a marcante.">
            <div className="eixo-entrada">
              <small>Suave</small>
              <input type="range" min={0} max={10} step={1} value={form.intensidade} onChange={(e) => mudar('intensidade', e.target.value)} aria-label="Intensidade, de suave a marcante" />
              <small>Marcante</small>
            </div>
          </Campo>

          <Campo rotulo="Perfume de referência (opcional)" dica="Serve só como pista de direção; não é copiado nem entra como essência.">
            <input value={form.perfume_referencia} onChange={(e) => mudar('perfume_referencia', e.target.value)} maxLength={160} />
          </Campo>

          <Grupo rotulo="Quais essências usar?">
            <label className="campo-check">
              <input type="checkbox" checked={form.todasEssencias} onChange={(e) => mudar('todasEssencias', e.target.checked)} />
              <span>Usar somente as minhas essências (todas)</span>
            </label>
            {!form.todasEssencias && (
              <SeletorEssencias
                lista={repertorio.data || []}
                valor={form.essenciasEscolhidas}
                onChange={(v) => mudar('essenciasEscolhidas', v)}
              />
            )}
          </Grupo>

          <label className="campo-check">
            <input type="checkbox" checked={form.mostrarLacunas} onChange={(e) => mudar('mostrarLacunas', e.target.checked)} />
            <span>Quero saber o que está faltando</span>
          </label>

          <button className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Criando…' : '✨ Criar com o laboratório'}
          </button>
        </form>
      )}
    </div>
  );
}

function SeletorEssencias({ lista, valor, onChange }) {
  if (!lista.length) return <p className="aviso">Você ainda não cadastrou essências.</p>;
  return (
    <Chips multiplo opcoes={lista.map((e) => ({ chave: e.id, nome: e.nome }))} valor={valor} onChange={onChange} />
  );
}

const TOM_CONFIANCA = { alta: 'verde', media: 'lilac', baixa: 'lilac' };
const TEXTO_CONFIANCA = {
  alta: 'Confiança alta',
  media: 'Confiança média',
  baixa: 'Ainda não tenho informação suficiente para afirmar isso com segurança',
};

function Resultado({ resultado, pedido, para_quem, onAjustar, onCriada }) {
  const { identidade, acorde, avisos, lacunas, confianca } = resultado;
  const [nome, setNome] = useState(identidade?.nome_sugerido || (para_quem ? `Para ${para_quem}` : ''));
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);

  async function aprovar() {
    setErro(null);
    setSalvando(true);
    try {
      // O servidor recalcula a sugestão a partir do pedido: nenhum número do cliente é aceito.
      const nova = await criacoes.criar({ nome: nome.trim() || 'Minha criação', sugestao: pedido });
      onCriada(nova.id);
    } catch (err) {
      setErro(err);
      setSalvando(false);
    }
  }

  return (
    <>
      {resultado.status === 'insuficiente' && <p className="aviso">{resultado.mensagem}</p>}

      {identidade && (
        <section className="cartao-amarelo">
          <h2>{identidade.nome_sugerido || 'Sua fragrância'}</h2>
          <div className="chips" style={{ justifyContent: 'center' }}>
            {identidade.personalidade.map((p) => (
              <Pill key={p}>{p}</Pill>
            ))}
          </div>
          <p><strong>Direção:</strong> {identidade.direcao}</p>
          <p><strong>Por que escolhi essa direção:</strong> {identidade.por_que}</p>
        </section>
      )}

      {acorde && (
        <section>
          <div className="secao-cabeca">
            <h2 className="secao-titulo">Acorde sugerido{acorde.familia_resultante ? ` · ${acorde.familia_resultante}` : ''}</h2>
            <Pill tom={TOM_CONFIANCA[confianca]}>{TEXTO_CONFIANCA[confianca]}</Pill>
          </div>
          <ul className="cartoes">
            {acorde.itens.map((i) => (
              <li key={i.essencia_id} className="cartao">
                <div className="secao-cabeca">
                  <strong>{i.nome}</strong>
                  <Pill>{i.rotulo_peso}</Pill>
                </div>
                <p>{i.papel_na_criacao}</p>
              </li>
            ))}
          </ul>
          <p className="aviso" style={{ marginTop: 12 }}>{acorde.explicacao}</p>
        </section>
      )}

      {avisos.map((a) => (
        <p key={a} className="aviso">{a}</p>
      ))}
      {lacunas.length > 0 && (
        <section className="cartao">
          <h2 className="secao-titulo">O que está faltando</h2>
          {lacunas.map((l) => (
            <p key={l.mensagem}>{l.mensagem}</p>
          ))}
        </section>
      )}

      <Erro erro={erro} />
      {acorde && (
        <Campo rotulo="Nome da criação">
          <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={160} />
        </Campo>
      )}
      <div className="botoes-duplos">
        <button className="btn btn-contorno" onClick={onAjustar}>Ajustar o pedido</button>
        {(acorde || identidade) && (
          <button className="btn btn-primario" onClick={aprovar} disabled={salvando}>
            {salvando ? 'Salvando…' : 'Aprovar e criar'}
          </button>
        )}
      </div>
    </>
  );
}
