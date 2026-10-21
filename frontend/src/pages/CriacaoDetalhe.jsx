import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { acordes, conhecimento, criacoes, essencias, testes } from '../api/serene';
import { useApi } from '../lib/useApi';
import { CAMADAS, EIXOS, NOME_PESO, PESOS, STATUS, data, delta, pct, rotulo } from '../lib/format';
import ResultadoCompatibilidade from '../components/Compatibilidade';
import FormulaDaVersao from '../components/FormulaDaVersao';
import Gauge from '../components/Gauge';
import Icon from '../components/Icon';
import { useConfirmar } from '../components/Confirmar';
import Sheet from '../components/Sheet';
import { Cabecalho } from '../components/Layout';
import { Avatar, Carregando, Eixos, Erro, Linhas, Pill, Vazio } from '../components/ui';

export default function CriacaoDetalhe() {
  const confirmar = useConfirmar();
  const { id } = useParams();
  const navigate = useNavigate();
  const criacao = useApi(() => criacoes.obter(id), [id]);
  const versoes = useApi(() => acordes.listar(id), [id]);
  const listaTestes = useApi(() => testes.listar(id), [id]);
  const [selecionado, setSelecionado] = useState(null);
  const [novoAberto, setNovoAberto] = useState(false);
  // Pesos pré-escolhidos ao montar o acorde a partir das sugestões da direção.
  const [preset, setPreset] = useState(null);
  const [comparar, setComparar] = useState(null);
  const [teste, setTeste] = useState(null);
  const [erro, setErro] = useState(null);

  // Sempre que a lista de versões muda, mostra a mais recente.
  useEffect(() => {
    if (versoes.data?.length) setSelecionado(versoes.data[versoes.data.length - 1].id);
  }, [versoes.data]);

  const acorde = versoes.data?.find((a) => a.id === selecionado);
  const c = criacao.data;

  async function mudarStatus(status) {
    setErro(null);
    try {
      criacao.setData(await criacoes.atualizar(id, { status }));
    } catch (err) {
      setErro(err);
    }
  }

  async function apagar() {
    const ok = await confirmar(`A criação “${c.nome}” será excluída com todas as versões e testes. Isso não pode ser desfeito.`, { titulo: 'Excluir criação', botao: 'Excluir' });
    if (!ok) return;
    try {
      await criacoes.apagar(id);
      navigate('/criacoes');
    } catch (err) {
      setErro(err);
    }
  }

  const voltar = (
    <Link to="/criacoes" className="icone-btn" aria-label="Voltar">
      <Icon name="back" />
    </Link>
  );

  if (criacao.loading && !c) return <div className="pagina"><Carregando /></div>;
  if (criacao.error)
    return (
      <div className="pagina">
        <Cabecalho titulo="Criação" voltar={voltar} />
        <Erro erro={criacao.error} onRetry={criacao.reload} />
      </div>
    );

  const alvo = c.direcao?.vetor_alvo;

  return (
    <div className="pagina">
      <Cabecalho titulo={c.nome} voltar={voltar}>
        <button className="icone-btn" onClick={apagar} aria-label="Excluir criação">
          <Icon name="trash" />
        </button>
      </Cabecalho>

      {/* No celular os wrappers "detalhe-*" não existem para o layout (display: contents);
          no desktop viram duas colunas: versões à esquerda, o resto à direita. */}
      <div className="detalhe-grade">
        <div className="detalhe-status">
          <div className="linha-status">
            <select value={c.status} onChange={(e) => mudarStatus(e.target.value)} aria-label="Status da criação">
              {Object.entries(STATUS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            {c.objetivo && <span className="texto-suave">{c.objetivo}</span>}
          </div>
          <Erro erro={erro} />
        </div>

        {c.direcao?.alertas_seguranca?.map((a) => (
          <p key={a} className="aviso aviso-forte">{a}</p>
        ))}
        {c.direcao && (
          <section className="cartao detalhe-direcao">
            <span className="rotulo">Direção</span>
            <p>{c.direcao.texto}</p>
            {c.direcao.resumo_briefing?.length > 0 && (
              <small className="texto-suave">
                {c.direcao.resumo_briefing.map((r) => `${r.rotulo}: ${r.valor}`).join(' · ')}
              </small>
            )}
            {c.direcao.vocabulario?.length > 0 && (
              <div className="chips">
                {c.direcao.vocabulario.map((v) => (
                  <Pill key={v}>{v}</Pill>
                ))}
              </div>
            )}
            {c.direcao.vetor_alvo && (
              <SugestoesDaDirecao
                criacaoId={id}
                onMontar={(ids) => {
                  setPreset(Object.fromEntries(ids.map((i) => [i, 'medio'])));
                  setNovoAberto(true);
                }}
              />
            )}
          </section>
        )}

        <section className="detalhe-versoes">
          <div className="secao-cabeca">
            <h3 className="secao-titulo">Versões do acorde</h3>
            <button className="btn btn-pequeno btn-primario" onClick={() => setNovoAberto(true)}>
              <Icon name="plus" size={16} /> Nova versão
            </button>
          </div>
          <Erro erro={versoes.error} onRetry={versoes.reload} />
          {versoes.loading && !versoes.data ? (
            <Carregando />
          ) : !versoes.data?.length ? (
            <Vazio titulo="Nenhum acorde ainda">Combine duas ou mais essências do seu repertório para ver o resultado do motor.</Vazio>
          ) : (
            <>
              <div className="chips rolagem">
                {versoes.data.map((a) => (
                  <button
                    key={a.id}
                    className={`chip ${a.id === selecionado ? 'ativo' : ''}`}
                    onClick={() => {
                      setSelecionado(a.id);
                      setComparar(null);
                    }}
                  >
                    v{a.versao}
                  </button>
                ))}
              </div>
              {acorde && (
                <div className="linha-versao">
                  <small className="texto-suave">
                    v{acorde.versao} · {data(acorde.criado_em)}
                    {acorde.motivo ? ` — ${acorde.motivo}` : ''}
                  </small>
                  {versoes.data.length > 1 && (
                    <select
                      value={comparar ?? ''}
                      onChange={(e) => setComparar(e.target.value ? Number(e.target.value) : null)}
                      aria-label="Comparar com outra versão"
                    >
                      <option value="">Comparar com…</option>
                      {versoes.data.filter((a) => a.id !== acorde.id).map((a) => (
                        <option key={a.id} value={a.id}>v{a.versao}</option>
                      ))}
                    </select>
                  )}
                </div>
              )}
              {acorde && comparar && (
                <ComparacaoVersoes antes={versoes.data.find((a) => a.id === comparar)} depois={acorde} />
              )}
              {acorde && (
                <ResultadoAcorde
                  key={acorde.id}
                  acorde={acorde}
                  alvo={alvo}
                  criacaoId={id}
                  onNovaVersao={versoes.reload}
                />
              )}
            </>
          )}
        </section>

        {acorde && <FormulaDaVersao key={acorde.id} acorde={acorde} criacaoId={id} onNovaVersao={versoes.reload} />}

        <section className="detalhe-testes">
          <div className="secao-cabeca">
            <h3 className="secao-titulo">Testes</h3>
            <button
              className="btn btn-pequeno btn-contorno"
              onClick={() => navigate(`/criacoes/${id}/teste${acorde ? `?acorde=${acorde.id}` : ''}`)}
            >
              Registrar teste
            </button>
          </div>
          {listaTestes.data?.length ? (
            <ul className="lista">
              {[...listaTestes.data].reverse().map((t) => (
                <li key={t.id}>
                  <button className="item" onClick={() => setTeste(t)}>
                  <span className="nota-circulo">{t.nota ?? '—'}</span>
                  <span className="item-texto">
                    <strong>
                      Teste {t.versao}
                      {t.acorde_id && ` · acorde v${versoes.data?.find((a) => a.id === t.acorde_id)?.versao ?? '?'}`}
                    </strong>
                    <small>{t.resultado_percebido || t.o_que_precisa_mudar || data(t.criado_em)}</small>
                  </span>
                  <Icon name="chevron" size={18} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="texto-suave">Nenhum teste registrado.</p>
          )}
        </section>
      </div>

      {novoAberto && (
        <NovoAcorde
          criacaoId={id}
          base={preset ? null : acorde}
          preset={preset}
          onClose={() => {
            setNovoAberto(false);
            setPreset(null);
          }}
          onCriado={() => {
            setNovoAberto(false);
            setPreset(null);
            versoes.reload();
          }}
        />
      )}
      {teste && (
        <DetalheTeste teste={teste} acorde={versoes.data?.find((a) => a.id === teste.acorde_id)} onClose={() => setTeste(null)} />
      )}
    </div>
  );
}

function ResultadoAcorde({ acorde, alvo, criacaoId, onNovaVersao }) {
  const compat = acorde.compatibilidade;
  const avisos = [...new Set([...(acorde.vetor?.avisos || []), ...(compat?.alertas || [])])];
  const paresAvaliados = (compat?.pares || []).filter((p) => typeof p.score === 'number');

  return (
    <>
      <div className="resultado-grade">
        <div className="cartao-amarelo resultado-amarelo">
          {acorde.familia_resultante && <h2>{acorde.familia_resultante}</h2>}
          {compat && typeof compat.score === 'number' && (
            <Gauge valor={compat.score / 100} rotulo="Compatibilidade" detalhe={`versão ${acorde.versao}`} />
          )}
          {compat?.base_exemplo && typeof compat.score === 'number' && (
            <small className="texto-suave">Calculada com relações de exemplo, ainda não validadas.</small>
          )}
          <Linhas itens={acorde.itens.map((i) => [i.nome, NOME_PESO[i.peso] || i.peso])} />
        </div>

        <div className="cartao resultado-caracteristicas">
          <span className="rotulo">Características {alvo && <small className="legenda-alvo">▍ alvo do perfil</small>}</span>
          <Eixos vetor={acorde.vetor?.valores} alvo={alvo} />
          {acorde.papel && (
            <>
              <span className="rotulo">Pirâmide</span>
              <Linhas itens={CAMADAS.map((c) => [c.nome, pct(acorde.papel[c.chave])])} />
            </>
          )}
          {paresAvaliados.length > 0 && (
            <>
              <span className="rotulo">Por que combina</span>
              {paresAvaliados.map((p, i) => (
                <p key={i} className="texto-suave">
                  <Pill>{p.tipo_relacao}</Pill> {p.explicacao}
                </p>
              ))}
            </>
          )}
          {avisos.map((a, i) => (
            <p key={i} className="aviso">
              {a}
            </p>
          ))}
        </div>
      </div>

      <IdentidadeAcorde acorde={acorde} criacaoId={criacaoId} />
      <Ajuste acorde={acorde} criacaoId={criacaoId} onNovaVersao={onNovaVersao} />
    </>
  );
}

function Ajuste({ acorde, criacaoId, onNovaVersao }) {
  const movimentos = useApi(() => conhecimento.regras('vetor_movimento'));
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  async function pedir(movimento) {
    setErro(null);
    setOcupado(true);
    try {
      setResultado(await acordes.ajuste(criacaoId, acorde.id, movimento));
    } catch (err) {
      setErro(err);
    } finally {
      setOcupado(false);
    }
  }

  // Aplicar uma sugestão grava uma NOVA versão; o acorde atual nunca é sobrescrito.
  async function aplicar(sug) {
    setOcupado(true);
    try {
      await acordes.criar(
        criacaoId,
        sug.itens_resultantes.map(([essencia_id, peso]) => ({ essencia_id, peso })),
        `Ajuste "${resultado.descricao || resultado.movimento}": ${sug.descricao}`.slice(0, 300),
      );
      setResultado(null);
      onNovaVersao();
    } catch (err) {
      setErro(err);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="cartao cartao-ajuste">
      <span className="rotulo">Quero deixar…</span>
      <div className="chips">
        {movimentos.data?.map((m) => (
          <button
            key={m.chave}
            className={`chip ${resultado?.movimento === m.chave ? 'ativo' : ''}`}
            onClick={() => pedir(m.chave)}
            disabled={ocupado}
          >
            {m.descricao || m.chave}
          </button>
        ))}
      </div>
      <Erro erro={erro || movimentos.error} />
      {resultado && (
        <div className="ajuste-resultado">
          {resultado.sugestoes.map((s, i) => (
            <div key={i} className="sugestao">
              <span className="item-texto">
                <strong>{s.descricao}</strong>
                <small>
                  Avança {pct(s.progresso)} no movimento
                  {s.efeito_colateral > 0 && ` · efeito colateral ${s.efeito_colateral.toFixed(1).replace('.', ',')}`}
                </small>
              </span>
              <button className="btn btn-pequeno btn-primario" onClick={() => aplicar(s)} disabled={ocupado}>
                Usar
              </button>
            </div>
          ))}
          {resultado.lacuna && (
            <div className="aviso">
              <strong>Lacuna: </strong>
              {resultado.lacuna.mensagem}
            </div>
          )}
          {!resultado.sugestoes.length && !resultado.lacuna && (
            <p className="texto-suave">Nenhum ajuste possível com o repertório atual.</p>
          )}
        </div>
      )}
    </div>
  );
}

function NovoAcorde({ criacaoId, base, preset, onClose, onCriado }) {
  const lista = useApi(() => essencias.listar());
  // { essencia_id: 'pouco' | 'medio' | 'bastante' }, pré-preenchido com a versão
  // exibida ou com as essências sugeridas pela direção.
  const [pesos, setPesos] = useState(
    () => preset || Object.fromEntries((base?.itens || []).map((i) => [i.essencia_id, i.peso])),
  );
  const [motivo, setMotivo] = useState('');
  const [previa, setPrevia] = useState(null);
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const escolhidas = Object.entries(pesos).filter(([, p]) => p);
  const chaveIds = escolhidas.map(([i]) => i).sort().join(',');

  // Prévia: como as escolhidas trabalham juntas, antes de gravar a versão.
  useEffect(() => {
    const ids = chaveIds ? chaveIds.split(',').map(Number) : [];
    if (ids.length < 2 || ids.length > 20) {
      setPrevia(null);
      return undefined;
    }
    const t = setTimeout(() => {
      essencias.compatibilidade(ids).then(setPrevia).catch(() => setPrevia(null));
    }, 400);
    return () => clearTimeout(t);
  }, [chaveIds]);

  async function salvar() {
    setErro(null);
    setEnviando(true);
    try {
      await acordes.criar(
        criacaoId,
        escolhidas.map(([id, peso]) => ({ essencia_id: Number(id), peso })),
        motivo.trim(),
      );
      onCriado();
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  return (
    <Sheet titulo={base ? `Nova versão (a partir da v${base.versao})` : 'Primeiro acorde'} onClose={onClose}>
      <p className="texto-suave">Escolha o peso relativo de cada essência na mistura. Não é porcentagem de produto.</p>
      {lista.loading && !lista.data ? (
        <Carregando />
      ) : !lista.data?.length ? (
        <Vazio titulo="Repertório vazio">
          <Link to="/essencias?nova=1" className="link">
            Cadastre essências
          </Link>{' '}
          para montar um acorde.
        </Vazio>
      ) : (
        <ul className="lista">
          {lista.data.map((e) => (
            <li key={e.id} className="item item-peso">
              <span className="item-texto">
                <strong>{e.nome}</strong>
                <small>{e.familia || 'Sem família'}</small>
              </span>
              <div className="segmentos pequeno">
                {PESOS.map((p) => (
                  <button
                    key={p.chave}
                    type="button"
                    className={pesos[e.id] === p.chave ? 'ativo' : ''}
                    onClick={() => setPesos({ ...pesos, [e.id]: pesos[e.id] === p.chave ? null : p.chave })}
                  >
                    {p.nome}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
      {previa && (
        <div className="cartao cartao-suave">
          <span className="rotulo">Prévia da compatibilidade</span>
          <ResultadoCompatibilidade resultado={previa} compacto />
        </div>
      )}
      {base && (
        <label className="campo">
          <span>O que mudou e por quê? (opcional)</span>
          <textarea rows={2} maxLength={300} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: mais bergamota para abrir a saída" />
        </label>
      )}
      <Erro erro={erro} />
      <div className="botoes-duplos">
        <button className="btn btn-contorno" onClick={onClose}>
          Cancelar
        </button>
        <button className="btn btn-primario" onClick={salvar} disabled={enviando || escolhidas.length < 2 || escolhidas.length > 20}>
          {escolhidas.length < 2 ? 'Escolha 2 ou mais' : enviando ? 'Calculando…' : 'Calcular acorde'}
        </button>
      </div>
    </Sheet>
  );
}


/** "Criador de fragrâncias": essências DO REPERTÓRIO mais próximas da direção. */
function SugestoesDaDirecao({ criacaoId, onMontar }) {
  const recs = useApi(() => criacoes.recomendacoes(criacaoId), [criacaoId]);
  if (recs.loading && !recs.data) return <Carregando texto="Procurando no seu repertório…" />;
  if (recs.error) return <Erro erro={recs.error} onRetry={recs.reload} />;
  const lista = recs.data.recomendacoes.slice(0, 5);
  return (
    <div className="sugestoes-direcao">
      <span className="rotulo">Do seu repertório, para esta direção</span>
      {lista.length ? (
        <>
          <ul className="lista">
            {lista.map((r) => (
              <li key={r.essencia_id} className="item">
                <Avatar>{r.score}</Avatar>
                <span className="item-texto quebra">
                  <strong>{r.nome}</strong>
                  <small>{r.explicacao}</small>
                </span>
              </li>
            ))}
          </ul>
          {lista.length >= 2 && (
            <button className="btn btn-pequeno btn-primario alinhar-esquerda" onClick={() => onMontar(lista.slice(0, 3).map((r) => r.essencia_id))}>
              Montar acorde com as {Math.min(3, lista.length)} primeiras
            </button>
          )}
        </>
      ) : null}
      {recs.data.avisos.map((a, i) => (
        <p key={i} className="aviso">{a}</p>
      ))}
    </div>
  );
}

/** Que territórios esta versão transmite (o perfil olfativo "ao contrário"). */
function IdentidadeAcorde({ acorde, criacaoId }) {
  const ident = useApi(() => acordes.identidade(criacaoId, acorde.id), [acorde.id]);
  if (!ident.data) return null;
  const { territorios, avisos } = ident.data;
  // Sem território nem orientação a dar, a seção não aparece.
  if (!territorios.length && !avisos.length) return null;
  // Sem porcentagem: ela vinha de uma distância sobre vetores de exemplo, não de uma medida válida.
  return (
    <div className="cartao">
      <span className="rotulo">Identidade desta versão</span>
      {territorios.length > 0 && (
        <ul className="eixos">
          {territorios.map((t) => (
            <li key={t.chave}>
              <strong>{t.nome}</strong>
              <small className="texto-suave"> {t.explicacao}</small>
            </li>
          ))}
        </ul>
      )}
      {avisos.map((a, i) => (
        <p key={i} className="texto-suave">{a}</p>
      ))}
    </div>
  );
}

/** O que mudou de uma versão para outra: itens, pesos, eixos e compatibilidade. */
function ComparacaoVersoes({ antes, depois }) {
  if (!antes || !depois) return null;
  const mapa = (a) => Object.fromEntries(a.itens.map((i) => [i.essencia_id, i]));
  const A = mapa(antes);
  const B = mapa(depois);
  const mudancas = [];
  for (const [id, i] of Object.entries(B)) {
    if (!A[id]) mudancas.push(`+ ${i.nome} (${NOME_PESO[i.peso] || i.peso})`);
    else if (A[id].peso !== i.peso) mudancas.push(`${i.nome}: ${NOME_PESO[A[id].peso]} → ${NOME_PESO[i.peso]}`);
  }
  for (const [id, i] of Object.entries(A)) if (!B[id]) mudancas.push(`− ${i.nome}`);
  const va = antes.vetor?.valores || {};
  const vb = depois.vetor?.valores || {};
  const sa = antes.compatibilidade?.score;
  const sb = depois.compatibilidade?.score;
  return (
    <div className="cartao cartao-suave comparacao">
      <span className="rotulo">
        v{antes.versao} → v{depois.versao}
      </span>
      {depois.motivo && <p className="texto-suave">Motivo: {depois.motivo}</p>}
      <ul className="linhas">
        {mudancas.length ? mudancas.map((m) => <li key={m}><span>{m}</span></li>) : <li><span>Mesmas essências e pesos.</span></li>}
      </ul>
      <Linhas
        itens={[
          ...EIXOS.filter((e) => va[e.chave] != null || vb[e.chave] != null).map((e) => [
            e.nome,
            va[e.chave] != null && vb[e.chave] != null ? delta(vb[e.chave] - va[e.chave]) : '—',
          ]),
          ['Compatibilidade', typeof sa === 'number' && typeof sb === 'number' ? delta(sb - sa) : '—'],
        ]}
      />
    </div>
  );
}

/** Tudo o que foi registrado num teste, com a fórmula (acorde) testada. */
function DetalheTeste({ teste: t, acorde, onClose }) {
  return (
    <Sheet titulo={`Teste ${t.versao}`} onClose={onClose}>
      <div className="grade-dados">
        <div><span>Nota</span><strong>{t.nota ?? '—'}</strong></div>
        <div><span>Data</span><strong className="sem-maiusculas">{data(t.criado_em)}</strong></div>
        <div><span>Intensidade</span><strong>{rotulo(t.intensidade_percebida)}</strong></div>
        <div><span>Persistência</span><strong>{rotulo(t.persistencia_percebida)}</strong></div>
      </div>
      {acorde && (
        <>
          <h3 className="secao-titulo">Fórmula testada (acorde v{acorde.versao})</h3>
          <Linhas itens={acorde.itens.map((i) => [i.nome, NOME_PESO[i.peso] || i.peso])} />
        </>
      )}
      {[
        ['O que senti', t.resultado_percebido],
        ['O que ficou bom', t.o_que_ficou_bom],
        ['O que precisa mudar', t.o_que_precisa_mudar],
        ['Próximo ajuste', t.proximo_ajuste],
      ].map(([titulo, texto]) => (
        <div key={titulo}>
          <h3 className="secao-titulo">{titulo}</h3>
          <p className="texto-suave">{texto || '—'}</p>
        </div>
      ))}
    </Sheet>
  );
}
