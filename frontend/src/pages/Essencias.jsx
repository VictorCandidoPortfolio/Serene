import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { conhecimento, criacoes, essencias, referencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { CAMADAS, EIXOS, camadaDominante, data, normalizar, pct, rotulo, sensacao } from '../lib/format';
import FormEssencia from '../components/FormEssencia';
import ResultadoCompatibilidade from '../components/Compatibilidade';
import Icon from '../components/Icon';
import { useConfirmar } from '../components/Confirmar';
import Sheet from '../components/Sheet';
import { Cabecalho } from '../components/Layout';
import { Avatar, Campo, Carregando, Eixos, Erro, Exemplo, Linhas, Pill, Vazio } from '../components/ui';

const ABAS = [
  { chave: 'repertorio', nome: 'Repertório' },
  { chave: 'combinar', nome: 'Combinar' },
  { chave: 'lacunas', nome: 'Lacunas' },
  { chave: 'referencias', nome: 'Referências' },
];

export default function Essencias() {
  const [params, setParams] = useSearchParams();
  const aba = params.get('aba') || 'repertorio';
  const novaAberta = params.get('nova') === '1';

  const familias = useApi(() => conhecimento.familias());
  const descritores = useApi(() => conhecimento.descritores().then((ds) => ds.map((d) => d.nome)));
  const lista = useApi(() => essencias.listar());
  const [detalhe, setDetalhe] = useState(null);
  const [editando, setEditando] = useState(null);

  const corDaFamilia = (nome) =>
    familias.data?.find((f) => normalizar(f.nome) === normalizar(nome))?.cor;

  const mudarParam = (chave, valor) => {
    const p = new URLSearchParams(params);
    if (valor) p.set(chave, valor);
    else p.delete(chave);
    setParams(p, { replace: true });
  };

  return (
    <div className="pagina">
      <Cabecalho titulo="Essências">
        {aba === 'repertorio' && (
          <button className="icone-btn destaque" onClick={() => mudarParam('nova', '1')} aria-label="Nova essência">
            <Icon name="plus" />
          </button>
        )}
      </Cabecalho>

      <div className="segmentos" role="tablist">
        {ABAS.map((a) => (
          <button
            key={a.chave}
            role="tab"
            aria-selected={aba === a.chave}
            className={aba === a.chave ? 'ativo' : ''}
            onClick={() => mudarParam('aba', a.chave === 'repertorio' ? null : a.chave)}
          >
            {a.nome}
          </button>
        ))}
      </div>

      {aba === 'repertorio' && (
        <Repertorio lista={lista} corDaFamilia={corDaFamilia} onAbrir={setDetalhe} onNova={() => mudarParam('nova', '1')} />
      )}
      {aba === 'combinar' && <Combinar lista={lista} />}
      {aba === 'lacunas' && <Lacunas />}
      {aba === 'referencias' && <Referencias />}

      {novaAberta && (
        <NovaEssencia
          onClose={() => mudarParam('nova', null)}
          onSalva={lista.reload}
        />
      )}
      {detalhe && (
        <DetalheEssencia
          essencia={detalhe}
          cor={corDaFamilia(detalhe.familia)}
          onClose={() => setDetalhe(null)}
          onEditar={() => setEditando(detalhe)}
          onMudou={(nova) => {
            setDetalhe(nova);
            lista.reload();
          }}
        />
      )}
      {editando && (
        <EditarEssencia
          essencia={editando}
          onClose={() => setEditando(null)}
          onSalva={(nova) => {
            setEditando(null);
            setDetalhe(nova);
            lista.reload();
          }}
        />
      )}
    </div>
  );
}

function Repertorio({ lista, corDaFamilia, onAbrir, onNova }) {
  if (lista.loading && !lista.data) return <Carregando />;
  if (lista.error) return <Erro erro={lista.error} onRetry={lista.reload} />;
  if (!lista.data?.length)
    return (
      <Vazio titulo="Seu repertório está vazio">
        Cadastre as essências que você tem em mãos. <button className="link" onClick={onNova}>Adicionar a primeira</button>
      </Vazio>
    );

  return (
    <ul className="lista grade-desktop">
      {lista.data.map((e) => (
        <li key={e.id}>
          <button className="item" onClick={() => onAbrir(e)}>
            <Avatar cor={corDaFamilia(e.familia)}>
              <Icon name="drop" size={19} />
            </Avatar>
            <span className="item-texto">
              <strong>{e.nome}</strong>
              <span className="chips">
                {e.familia && <Pill>{e.familia}</Pill>}
                {e.percepcao && <Pill tom="branco">{NOME_PERCEPCAO[e.percepcao]}</Pill>}
              </span>
            </span>
            <Icon name="chevron" size={18} />
          </button>
        </li>
      ))}
    </ul>
  );
}

const NOME_PERCEPCAO = { fria: 'Fria', neutra: 'Neutra', quente: 'Quente' };

/** Cadastro: 3 campos (Nome, Família, Percepção). Ver components/FormEssencia.jsx. */
function NovaEssencia({ onClose, onSalva }) {
  return (
    <Sheet titulo="Nova essência" onClose={onClose}>
      <FormEssencia
        onClose={onClose}
        onSalva={() => {
          onSalva();
          onClose();
        }}
      />
    </Sheet>
  );
}

/** Detalhe simples: nome, família e percepção. Nada técnico. */
function DetalheEssencia({ essencia: e, cor, onClose, onMudou, onEditar }) {
  const confirmar = useConfirmar();
  const [erro, setErro] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  const apagar = async () => {
    if (!(await confirmar(`“${e.nome}” sairá do seu repertório. Versões de acordes antigas continuam mostrando o nome.`, { titulo: 'Excluir essência', botao: 'Excluir' }))) return;
    setErro(null);
    setOcupado(true);
    try {
      await essencias.apagar(e.id);
      onMudou(null);
      onClose();
    } catch (err) {
      setErro(err);
      setOcupado(false);
    }
  };

  return (
    <Sheet titulo="Essência" onClose={onClose} topo={<div className="faixa-topo" style={{ background: cor }} />}>
      <div className="item cabeca-detalhe">
        <Avatar cor={cor}>
          <Icon name="drop" size={19} />
        </Avatar>
        <span className="item-texto">
          <strong>{e.nome}</strong>
          <small>{data(e.criado_em)}</small>
        </span>
      </div>
      <div className="chips">
        {e.familia && <Pill>{e.familia}</Pill>}
        {e.percepcao && <Pill tom="branco">{NOME_PERCEPCAO[e.percepcao]}</Pill>}
      </div>
      <Erro erro={erro} />
      <div className="botoes-duplos">
        <button className="btn btn-contorno" onClick={apagar} disabled={ocupado}>
          <Icon name="trash" size={18} /> Excluir
        </button>
        <button className="btn btn-primario" onClick={onEditar} disabled={ocupado}>
          <Icon name="edit" size={18} /> Editar
        </button>
      </div>
    </Sheet>
  );
}

function Lacunas() {
  const { data: lacunas, error, loading, reload } = useApi(() => essencias.lacunas());
  if (loading && !lacunas) return <Carregando />;
  if (error) return <Erro erro={error} onRetry={reload} />;
  if (!lacunas.length) return <Vazio titulo="Nenhuma lacuna encontrada">Seu repertório cobre o que a base de conhecimento consegue avaliar.</Vazio>;

  return (
    <ul className="cartoes grade-desktop">
      {lacunas.map((l, i) => (
        <li key={i} className="cartao">
          <Pill tom="amarelo">{l.tipo.replace(/_/g, ' ')}</Pill>
          <p>{l.mensagem}</p>
          {Object.values(l.detalhe || {})
            .filter(Array.isArray)
            .map((valores, j) => (
              <div key={j} className="chips">
                {valores.map((v) => (
                  <Pill key={String(v)}>{String(v)}</Pill>
                ))}
              </div>
            ))}
        </li>
      ))}
    </ul>
  );
}

function Referencias() {
  const confirmar = useConfirmar();
  const { data: lista, error, loading, reload } = useApi(() => referencias.listar());
  const [editando, setEditando] = useState(null);
  const [caminhosDe, setCaminhosDe] = useState(null);
  const [form, setForm] = useState({ nome: '', familia_percebida: '', notas: '' });
  const [erro, setErro] = useState(null);

  async function adicionar(e) {
    e.preventDefault();
    setErro(null);
    try {
      await referencias.criar({
        nome: form.nome.trim(),
        familia_percebida: form.familia_percebida.trim() || null,
        notas_conhecidas: form.notas.split(',').map((n) => n.trim()).filter(Boolean),
      });
      setForm({ nome: '', familia_percebida: '', notas: '' });
      reload();
    } catch (err) {
      setErro(err);
    }
  }

  async function apagar(id) {
    if (!(await confirmar('Esta referência será excluída.', { titulo: 'Excluir referência', botao: 'Excluir' }))) return;
    try {
      await referencias.apagar(id);
      reload();
    } catch (err) {
      setErro(err);
    }
  }

  return (
    <>
      <p className="texto-suave">
        Perfumes que servem de bússola. Uma referência nunca vira essência do seu repertório: ela só mostra
        caminhos — a direção que aponta e o que você tem (ou falta) para ir nela.
      </p>
      <div className="referencias-grade">
        <form className="cartao form" onSubmit={adicionar}>
          <Campo rotulo="Perfume de referência">
            <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required />
          </Campo>
          <Campo rotulo="Família percebida">
            <input value={form.familia_percebida} onChange={(e) => setForm({ ...form, familia_percebida: e.target.value })} />
          </Campo>
          <Campo rotulo="Notas conhecidas" dica="Separadas por vírgula.">
            <input value={form.notas} onChange={(e) => setForm({ ...form, notas: e.target.value })} />
          </Campo>
          <button className="btn btn-primario">Adicionar referência</button>
        </form>
        <div className="referencias-lista">
          <Erro erro={erro || error} onRetry={error ? reload : undefined} />
          {loading && !lista ? (
            <Carregando />
          ) : (
            <ul className="lista">
              {lista?.map((r) => (
                <li key={r.id} className="item">
                  <Avatar>
                    <Icon name="compass" size={19} />
                  </Avatar>
                  <span className="item-texto">
                    <strong>{r.nome}</strong>
                    <small>{[r.familia_percebida, r.notas_conhecidas.join(', ')].filter(Boolean).join(' · ') || 'Sem detalhes'}</small>
                  </span>
                  <button className="btn btn-pequeno btn-contorno" onClick={() => setCaminhosDe(r)}>
                    Caminhos
                  </button>
                  <button className="icone-btn" onClick={() => setEditando(r)} aria-label={`Editar ${r.nome}`}>
                    <Icon name="edit" size={18} />
                  </button>
                  <button className="icone-btn" onClick={() => apagar(r.id)} aria-label={`Excluir ${r.nome}`}>
                    <Icon name="trash" size={18} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {editando && (
        <EditarReferencia
          referencia={editando}
          onClose={() => setEditando(null)}
          onSalva={() => {
            setEditando(null);
            reload();
          }}
        />
      )}
      {caminhosDe && <CaminhosReferencia referencia={caminhosDe} onClose={() => setCaminhosDe(null)} />}
    </>
  );
}


/** Edição: os mesmos 3 campos, pré-preenchidos. */
function EditarEssencia({ essencia, onClose, onSalva }) {
  return (
    <Sheet titulo="Editar essência" onClose={onClose}>
      <FormEssencia essencia={essencia} onClose={onClose} onSalva={onSalva} />
    </Sheet>
  );
}

/** Análise de compatibilidade avulsa: escolhe essências, vê como trabalham juntas. Nada é gravado. */
function Combinar({ lista }) {
  const [escolhidas, setEscolhidas] = useState([]);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const nomes = Object.fromEntries((lista.data || []).map((e) => [e.id, e.nome]));

  function alternar(id) {
    setResultado(null);
    setEscolhidas(escolhidas.includes(id) ? escolhidas.filter((x) => x !== id) : [...escolhidas, id]);
  }

  async function analisar() {
    setErro(null);
    setOcupado(true);
    try {
      setResultado(await essencias.compatibilidade(escolhidas));
    } catch (err) {
      setErro(err);
    } finally {
      setOcupado(false);
    }
  }

  if (lista.loading && !lista.data) return <Carregando />;
  if ((lista.data || []).length < 2)
    return <Vazio titulo="Cadastre pelo menos duas essências">A análise compara as essências do seu repertório.</Vazio>;

  return (
    <div className="combinar-grade">
      <section className="cartao">
        <span className="rotulo">Quais essências podem trabalhar juntas?</span>
        <small className="texto-suave">Escolha de 2 a 20. A análise usa as relações entre famílias da base e não grava nada.</small>
        <div className="chips">
          {lista.data.map((e) => (
            <button key={e.id} type="button" className={`chip ${escolhidas.includes(e.id) ? 'ativo' : ''}`} onClick={() => alternar(e.id)}>
              {e.nome}
            </button>
          ))}
        </div>
        <button className="btn btn-primario" onClick={analisar} disabled={ocupado || escolhidas.length < 2 || escolhidas.length > 20}>
          {escolhidas.length < 2 ? 'Escolha 2 ou mais' : ocupado ? 'Analisando…' : `Analisar ${escolhidas.length} essências`}
        </button>
        <Erro erro={erro} />
      </section>
      {resultado && (
        <section className="cartao">
          <ResultadoCompatibilidade resultado={resultado} nomes={nomes} />
        </section>
      )}
    </div>
  );
}


const lista = (txt) => txt.split(',').map((n) => n.trim()).filter(Boolean);

function EditarReferencia({ referencia: r, onClose, onSalva }) {
  const [form, setForm] = useState({
    nome: r.nome,
    familia_percebida: r.familia_percebida || '',
    notas: (r.notas_conhecidas || []).join(', '),
    caracteristicas: (r.caracteristicas || []).join(', '),
    observacoes: r.observacoes || '',
  });
  const [erro, setErro] = useState(null);
  const set = (c) => (e) => setForm({ ...form, [c]: e.target.value });

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    try {
      await referencias.atualizar(r.id, {
        nome: form.nome.trim(),
        familia_percebida: form.familia_percebida.trim() || null,
        notas_conhecidas: lista(form.notas),
        caracteristicas: lista(form.caracteristicas),
        observacoes: form.observacoes.trim() || null,
      });
      onSalva();
    } catch (err) {
      setErro(err);
    }
  }

  return (
    <Sheet titulo="Editar referência" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Campo rotulo="Perfume de referência">
          <input value={form.nome} onChange={set('nome')} required />
        </Campo>
        <Campo rotulo="Família percebida">
          <input value={form.familia_percebida} onChange={set('familia_percebida')} />
        </Campo>
        <Campo rotulo="Notas conhecidas" dica="Separadas por vírgula. São elas que o SÉRENÉ reconhece na base.">
          <input value={form.notas} onChange={set('notas')} />
        </Campo>
        <Campo rotulo="Características que você percebe" dica="Separadas por vírgula (ex.: cremoso, solar).">
          <input value={form.caracteristicas} onChange={set('caracteristicas')} />
        </Campo>
        <Campo rotulo="Observações">
          <textarea rows={2} value={form.observacoes} onChange={set('observacoes')} />
        </Campo>
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primario">Salvar</button>
        </div>
      </form>
    </Sheet>
  );
}

/** O que a referência ensina: direção estimada, famílias e as essências DELA nessa direção. */
function CaminhosReferencia({ referencia: r, onClose }) {
  const analise = useApi(() => referencias.caminhos(r.id), [r.id]);
  const a = analise.data;

  return (
    <Sheet titulo={`Caminhos de “${r.nome}”`} onClose={onClose}>
      {analise.loading && !a ? (
        <Carregando />
      ) : analise.error ? (
        <Erro erro={analise.error} onRetry={analise.reload} />
      ) : (
        <>
          {a.avisos.map((t, i) => (
            <p key={i} className="aviso">{t}</p>
          ))}
          <h3 className="secao-titulo">Direção estimada</h3>
          <Eixos vetor={a.vetor_estimado} />

          <h3 className="secao-titulo">Notas reconhecidas na base</h3>
          {a.notas_reconhecidas.length ? (
            <Linhas itens={a.notas_reconhecidas.map((n) => [n.nota, n.familia || '—', normalizar(n.citada_como) !== normalizar(n.nota) ? `citada como “${n.citada_como}”` : null])} />
          ) : (
            <p className="texto-suave">Nenhuma. Cadastre as notas conhecidas da referência para ver caminhos.</p>
          )}
          {a.notas_desconhecidas.length > 0 && (
            <p className="texto-suave">Sem informação na base: {a.notas_desconhecidas.join(', ')}.</p>
          )}

          <div className="grade-dados">
            <div>
              <span>Você já tem</span>
              <strong>{a.familias_presentes.join(', ') || '—'}</strong>
            </div>
            <div>
              <span>Falta no seu repertório</span>
              <strong>{a.familias_ausentes.join(', ') || '—'}</strong>
            </div>
          </div>

          <h3 className="secao-titulo">Suas essências nessa direção</h3>
          {a.recomendacoes.recomendacoes.length ? (
            <ul className="lista">
              {a.recomendacoes.recomendacoes.slice(0, 5).map((x) => (
                <li key={x.essencia_id} className="item">
                  <Avatar>{x.score}</Avatar>
                  <span className="item-texto quebra">
                    <strong>{x.nome}</strong>
                    <small>{x.explicacao}</small>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="texto-suave">{a.recomendacoes.avisos[0] || 'Nenhuma essência comparável.'}</p>
          )}

        </>
      )}
    </Sheet>
  );
}
