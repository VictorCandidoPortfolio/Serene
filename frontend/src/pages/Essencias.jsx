import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { conhecimento, criacoes, essencias, referencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { CAMADAS, EIXOS, camadaDominante, data, normalizar, pct, rotulo, sensacao } from '../lib/format';
import ClassificacaoEssencia, {
  CLASSIFICACAO_VAZIA,
  classificacaoDe,
  classificacaoParaApi,
} from '../components/ClassificacaoEssencia';
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

/** Sem nenhum eixo informado, o motor não consegue usar a essência. */
export const semClassificacao = (e) => EIXOS.every((x) => e[x.chave] === null || e[x.chave] === undefined);

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
          familias={familias.data || []}
          descritores={descritores.data || []}
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
          familias={familias.data || []}
          descritores={descritores.data || []}
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
              <strong>
                {e.nome} {e.favorito && <Icon name="heart" size={13} filled className="coracao" />}
              </strong>
              <small>
                {[e.familia || 'Sem família', camadaDominante(e.papel)].filter(Boolean).join(' · ')}
              </small>
            </span>
            {semClassificacao(e) ? <Pill tom="amarelo">Classificar</Pill> : <Icon name="chevron" size={18} />}
          </button>
        </li>
      ))}
    </ul>
  );
}

function NovaEssencia({ familias, descritores, onClose, onSalva }) {
  const [form, setForm] = useState({ nome: '', familia: '', fornecedor: '' });
  // Classificação completa já no cadastro (opcional): abre o mesmo formulário da edição.
  const [detalhar, setDetalhar] = useState(false);
  const [classificacao, setClassificacao] = useState(CLASSIFICACAO_VAZIA);
  const [sugestoes, setSugestoes] = useState([]);
  const [escolhida, setEscolhida] = useState(null);
  const [criada, setCriada] = useState(null);
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  // Busca referências na base de conhecimento enquanto a aluna digita (nada é gravado).
  useEffect(() => {
    const nome = form.nome.trim();
    if (nome.length < 3) {
      setSugestoes([]);
      return;
    }
    const t = setTimeout(() => {
      essencias.sugestoes(nome).then(setSugestoes).catch(() => setSugestoes([]));
    }, 350);
    return () => clearTimeout(t);
  }, [form.nome]);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      let corpo = { nome: form.nome.trim() };
      if (escolhida) {
        corpo.knowledge_note_id = escolhida.nota_id;
        corpo.aplicar_referencia = true;
        if (form.fornecedor.trim()) corpo.fornecedor = form.fornecedor.trim();
      } else if (detalhar) {
        // Só o que foi informado: campos vazios ficam de fora (a API entende "não sei").
        const dados = classificacaoParaApi(classificacao);
        corpo = { ...corpo, ...Object.fromEntries(Object.entries(dados).filter(([, v]) => v !== null && !(Array.isArray(v) && !v.length))) };
      } else {
        if (form.familia) corpo.familia = form.familia;
        if (form.fornecedor.trim()) corpo.fornecedor = form.fornecedor.trim();
      }
      const resp = await essencias.criar(corpo);
      onSalva();
      // Sem referência escolhida, a API ainda pode ter achado correspondências: oferecemos aplicar depois.
      if (!escolhida && resp.sugestoes_referencia?.length) setCriada(resp);
      else onClose();
    } catch (err) {
      setErro(err);
    } finally {
      setEnviando(false);
    }
  }

  async function aplicar(sug) {
    setEnviando(true);
    try {
      await essencias.atualizar(criada.id, { knowledge_note_id: sug.nota_id, aplicar_referencia: true });
      onSalva();
      onClose();
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  if (criada) {
    return (
      <Sheet titulo="Referência encontrada" onClose={onClose}>
        <p className="texto-suave">
          “{criada.nome}” foi salva. Encontramos na base de conhecimento uma nota que pode corresponder a ela.
          Aplicar preenche família, papel e eixos com os valores da referência.
        </p>
        {criada.sugestoes_referencia.map((s) => (
          <CartaoSugestao key={s.nota_id} sugestao={s} />
        ))}
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button className="btn btn-contorno" onClick={onClose}>
            Deixar assim
          </button>
          <button className="btn btn-primario" disabled={enviando} onClick={() => aplicar(criada.sugestoes_referencia[0])}>
            Aplicar referência
          </button>
        </div>
      </Sheet>
    );
  }

  return (
    <Sheet titulo="Nova essência" onClose={onClose}>
      <form onSubmit={salvar} className="form">
        <Campo rotulo="Nome">
          <input
            autoFocus
            value={form.nome}
            onChange={(e) => {
              setForm({ ...form, nome: e.target.value });
              setEscolhida(null);
            }}
            placeholder="Ex.: Bergamota"
            required
          />
        </Campo>

        {sugestoes.length > 0 && (
          <div className="sugestoes">
            <span className="rotulo">Referências da base de conhecimento</span>
            {sugestoes.map((s) => (
              <CartaoSugestao
                key={s.nota_id}
                sugestao={s}
                ativo={escolhida?.nota_id === s.nota_id}
                onClick={() => setEscolhida(escolhida?.nota_id === s.nota_id ? null : s)}
              />
            ))}
            <small className="texto-suave">Toque para usar os dados da referência. Nada é aplicado sem sua confirmação.</small>
          </div>
        )}

        {!escolhida && detalhar && (
          <ClassificacaoEssencia
            valor={classificacao}
            onChange={setClassificacao}
            familias={familias}
            descritoresBase={descritores}
          />
        )}
        {!escolhida && (
          <button type="button" className="link alinhar-esquerda" onClick={() => setDetalhar(!detalhar)}>
            {detalhar ? 'Cadastrar só o básico' : 'Informar características sensoriais agora (opcional)'}
          </button>
        )}
        {!escolhida && !detalhar && (
          <Campo rotulo="Família (opcional)">
            <select value={form.familia} onChange={(e) => setForm({ ...form, familia: e.target.value })}>
              <option value="">Não sei ainda</option>
              {familias.map((f) => (
                <option key={f.id} value={f.nome}>
                  {f.nome}
                </option>
              ))}
            </select>
          </Campo>
        )}
        {(escolhida || !detalhar) && (
          <Campo rotulo="Fornecedor (opcional)">
            <input value={form.fornecedor} onChange={(e) => setForm({ ...form, fornecedor: e.target.value })} />
          </Campo>
        )}

        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Adicionar'}
          </button>
        </div>
      </form>
    </Sheet>
  );
}

function CartaoSugestao({ sugestao: s, ativo, onClick }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag type={onClick ? 'button' : undefined} className={`sugestao ${ativo ? 'ativo' : ''}`} onClick={onClick}>
      <span className="item-texto">
        <strong>{s.nome}</strong>
        <small>
          {[s.familia, s.subfamilia, camadaDominante(s.papel)].filter(Boolean).join(' · ')}
        </small>
        {s.ilustrativa && s.avisos?.length > 0 && <small className="texto-suave">{s.avisos[0]}</small>}
      </span>
      {s.ilustrativa && <Exemplo />}
      {ativo ? <Icon name="check" /> : <Pill>{s.correspondencia}</Pill>}
    </Tag>
  );
}

function DetalheEssencia({ essencia: e, cor, onClose, onMudou, onEditar }) {
  const confirmar = useConfirmar();
  const [erro, setErro] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  async function executar(acao) {
    setErro(null);
    setOcupado(true);
    try {
      await acao();
    } catch (err) {
      setErro(err);
    } finally {
      setOcupado(false);
    }
  }

  const favoritar = () => executar(async () => onMudou(await essencias.atualizar(e.id, { favorito: !e.favorito })));
  const apagar = async () => {
    if (!(await confirmar(`“${e.nome}” sairá do seu repertório. Versões de acordes antigas continuam mostrando o nome.`, { titulo: 'Excluir essência', botao: 'Excluir' }))) return;
    executar(async () => {
      await essencias.apagar(e.id);
      onMudou(null);
      onClose();
    });
  };

  return (
    <Sheet titulo="Detalhe da essência" onClose={onClose} topo={<div className="faixa-topo" style={{ background: cor }} />}>
      <div className="item cabeca-detalhe">
        <Avatar cor={cor}>
          <Icon name="drop" size={19} />
        </Avatar>
        <span className="item-texto">
          <strong>{e.nome}</strong>
          <small>{data(e.criado_em)}</small>
        </span>
      </div>

      {semClassificacao(e) ? (
        <div className="aviso">
          Esta essência ainda não tem características. Sem elas, o motor não consegue usá-la em acordes,
          compatibilidade nem recomendações.{' '}
          <button className="link" onClick={onEditar}>Classificar agora</button>
        </div>
      ) : (
        <button className="btn btn-pequeno btn-contorno alinhar-esquerda" onClick={onEditar}>
          <Icon name="edit" size={16} /> Editar classificação
        </button>
      )}

      <div className="grade-dados">
        <div>
          <span>Família</span>
          <strong>{e.familia || '—'}</strong>
          {e.subfamilia && <small>{e.subfamilia}</small>}
        </div>
        <div>
          <span>Tipo</span>
          <strong>{rotulo(e.tipo)}</strong>
        </div>
        <div>
          <span>Confiança</span>
          <strong>{rotulo(e.confianca)}</strong>
        </div>
        <div>
          <span>Origem</span>
          <strong>{rotulo(e.origem)}</strong>
        </div>
        <div>
          <span>Sensação</span>
          <strong>{sensacao(e.v1) || '—'}</strong>
        </div>
        {e.editado_da_referencia && (
          <div>
            <span>Referência</span>
            <strong>Ajustada por você</strong>
          </div>
        )}
      </div>

      <h3 className="secao-titulo">Características</h3>
      <Eixos vetor={e} />

      <h3 className="secao-titulo">Papel na pirâmide</h3>
      {e.papel ? (
        <Linhas itens={CAMADAS.map((c) => [c.nome, pct(e.papel[c.chave])])} />
      ) : (
        <p className="texto-suave">Ainda não informado.</p>
      )}

      {e.tags?.length > 0 && (
        <div className="chips">
          {e.tags.map((t) => (
            <Pill key={t} tom="branco">#{t}</Pill>
          ))}
        </div>
      )}

      {e.descritores?.length > 0 && (
        <>
          <h3 className="secao-titulo">Descritores</h3>
          <div className="chips">
            {e.descritores.map((d) => (
              <Pill key={d}>{d}</Pill>
            ))}
          </div>
        </>
      )}

      <h3 className="secao-titulo">Observações</h3>
      <p className="texto-suave">{e.observacoes || e.fornecedor ? [e.fornecedor, e.observacoes].filter(Boolean).join(' — ') : 'Nenhuma observação.'}</p>

      <Erro erro={erro} />
      <div className="botoes-duplos">
        <button className="btn btn-contorno" onClick={apagar} disabled={ocupado}>
          <Icon name="trash" size={18} /> Excluir
        </button>
        <button className="btn btn-primario" onClick={favoritar} disabled={ocupado}>
          <Icon name="heart" size={18} filled={e.favorito} /> {e.favorito ? 'Favorita' : 'Favoritar'}
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


/**
 * Edição completa da classificação (funcionalidade "Classificação olfativa").
 * A aluna pode corrigir qualquer valor que veio da referência: a API marca a
 * essência como "ajustada" e nunca sobrescreve a correção dela.
 */
function EditarEssencia({ essencia, familias, descritores, onClose, onSalva }) {
  const [nome, setNome] = useState(essencia.nome);
  const [valor, setValor] = useState(() => classificacaoDe(essencia));
  const [sugestoes, setSugestoes] = useState(null);
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function salvar(ev) {
    ev.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      onSalva(await essencias.atualizar(essencia.id, { nome: nome.trim(), ...classificacaoParaApi(valor) }));
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  async function buscarReferencias() {
    setErro(null);
    try {
      setSugestoes(await essencias.sugestoes(nome.trim()));
    } catch (err) {
      setErro(err);
    }
  }

  // Aplicar preenche só o que está VAZIO; o que a aluna já informou continua.
  async function aplicar(s) {
    setEnviando(true);
    try {
      const nova = await essencias.atualizar(essencia.id, { knowledge_note_id: s.nota_id, aplicar_referencia: true });
      setValor(classificacaoDe(nova));
      setSugestoes(null);
    } catch (err) {
      setErro(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Sheet titulo="Classificar essência" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Campo rotulo="Nome">
          <input value={nome} onChange={(e) => setNome(e.target.value)} required maxLength={160} />
        </Campo>
        <div className="cartao cartao-suave">
          <span className="rotulo">Usar a base de conhecimento</span>
          <small className="texto-suave">
            Busca uma nota de referência com este nome. Aplicar preenche só os campos que você ainda não informou.
          </small>
          {sugestoes === null ? (
            <button type="button" className="btn btn-pequeno btn-contorno alinhar-esquerda" onClick={buscarReferencias}>
              Buscar referência
            </button>
          ) : sugestoes.length ? (
            sugestoes.map((s) => (
              <div key={s.nota_id} className="linha-sugestao">
                <CartaoSugestao sugestao={s} />
                <button type="button" className="btn btn-pequeno btn-primario" onClick={() => aplicar(s)} disabled={enviando}>
                  Aplicar
                </button>
              </div>
            ))
          ) : (
            <small className="texto-suave">Nenhuma nota da base corresponde a “{nome}”. Classifique você mesma abaixo.</small>
          )}
        </div>
        <ClassificacaoEssencia valor={valor} onChange={setValor} familias={familias} descritoresBase={descritores} />
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Salvar'}
          </button>
        </div>
      </form>
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
  const navigate = useNavigate();
  const analise = useApi(() => referencias.caminhos(r.id), [r.id]);
  const [erro, setErro] = useState(null);
  const a = analise.data;

  async function criarInspirada() {
    setErro(null);
    try {
      const c = await criacoes.criar({ nome: `Inspirada em ${r.nome}`.slice(0, 160), referencia_id: r.id });
      navigate(`/criacoes/${c.id}`);
    } catch (err) {
      setErro(err);
    }
  }

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

          <Erro erro={erro} />
          <button className="btn btn-primario" onClick={criarInspirada}>
            Criar uma criação inspirada nesta referência
          </button>
        </>
      )}
    </Sheet>
  );
}
