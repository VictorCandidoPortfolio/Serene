import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { mapa as apiMapa } from '../api/serene';
import { useApi } from '../lib/useApi';
import { EIXOS, num } from '../lib/format';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import { Carregando, Erro, Pill, Vazio } from '../components/ui';

// Área do gráfico (viewBox 360×360): margem para os rótulos dos eixos.
const TAM = 360;
const MARGEM = 40;
const AREA = TAM - MARGEM * 2;
const px = (v) => MARGEM + (v / 10) * AREA; // 0–10 → horizontal
const py = (v) => TAM - MARGEM - (v / 10) * AREA; // 0–10 → vertical (10 em cima)

const COR_RELACAO = {
  classico: 'var(--verde-ink)',
  complementar: 'var(--lilac-forte)',
  contraste: '#c98a12',
  atencao: 'var(--erro)',
};
const NOME_RELACAO = { classico: 'Clássico', complementar: 'Complementar', contraste: 'Contraste', atencao: 'Atenção' };

/**
 * Mapa Olfativo: onde as essências e criações da aluna "vivem" entre os
 * territórios, e os caminhos (relações) entre famílias. O backend entrega
 * os dados (GET /mapa); o desenho é todo aqui, em SVG.
 */
export default function Mapa() {
  const dados = useApi(() => apiMapa.obter());

  return (
    <div className="pagina">
      <Cabecalho titulo="Mapa olfativo">
        <Link to="/conhecimento" className="btn btn-pequeno btn-contorno">
          <Icon name="book" size={16} /> Conhecimento
        </Link>
      </Cabecalho>
      <Erro erro={dados.error} onRetry={dados.reload} />
      {dados.loading && !dados.data ? (
        <Carregando texto="Desenhando o mapa…" />
      ) : dados.data ? (
        <div className="mapa-grade">
          <Territorios dados={dados.data} />
          <Caminhos dados={dados.data} />
          <MapasDeEstudo mapas={dados.data.mapas} />
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------ territórios × repertório */
function Territorios({ dados }) {
  const { essencias, criacoes, territorios } = dados;
  const eixos = EIXOS;
  const [x, setX] = useState('v1');
  const [y, setY] = useState('v3');
  const [mostrar, setMostrar] = useState({ territorios: true, essencias: true, criacoes: true });
  const [selecionado, setSelecionado] = useState(null);
  const ex = eixos.find((e) => e.chave === x);
  const ey = eixos.find((e) => e.chave === y);

  const temXY = (v) => v?.[x] !== null && v?.[x] !== undefined && v?.[y] !== null && v?.[y] !== undefined;
  const terrVisiveis = territorios.filter((t) => temXY(t.vetor));
  const essVisiveis = essencias.filter((e) => temXY(e.vetor));
  const criVisiveis = criacoes.filter((c) => temXY(c.vetor));
  const foraDaVista = [
    ...essencias.filter((e) => !temXY(e.vetor)).map((e) => e.nome),
    ...criacoes.filter((c) => !temXY(c.vetor)).map((c) => c.nome),
  ];
  const terrFora = territorios.filter((t) => !temXY(t.vetor)).map((t) => t.nome);

  const descricao = `Mapa com ${essVisiveis.length} essência(s), ${criVisiveis.length} criação(ões) e ${terrVisiveis.length} território(s), eixo horizontal ${ex.nome} e vertical ${ey.nome}.`;

  return (
    <section className="cartao mapa-cartao">
      <div className="secao-cabeca">
        <h2 className="secao-titulo">Territórios e o seu repertório</h2>
      </div>
      <div className="mapa-controles">
        <label className="campo">
          <span>Horizontal</span>
          <select value={x} onChange={(e) => setX(e.target.value)}>
            {eixos.map((e) => (
              <option key={e.chave} value={e.chave} disabled={e.chave === y}>{e.nome}</option>
            ))}
          </select>
        </label>
        <label className="campo">
          <span>Vertical</span>
          <select value={y} onChange={(e) => setY(e.target.value)}>
            {eixos.map((e) => (
              <option key={e.chave} value={e.chave} disabled={e.chave === x}>{e.nome}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="chips" role="group" aria-label="O que mostrar no mapa">
        {[
          ['territorios', 'Territórios'],
          ['essencias', 'Essências'],
          ['criacoes', 'Criações'],
        ].map(([chave, nome]) => (
          <button
            key={chave} type="button" aria-pressed={mostrar[chave]}
            className={`chip ${mostrar[chave] ? 'ativo' : ''}`}
            onClick={() => setMostrar({ ...mostrar, [chave]: !mostrar[chave] })}
          >
            {nome}
          </button>
        ))}
      </div>

      <svg className="mapa-svg" viewBox={`0 0 ${TAM} ${TAM}`} role="img" aria-label={descricao}>
        {/* grade 0, 2,5, 5, 7,5, 10 */}
        {[0, 2.5, 5, 7.5, 10].map((v) => (
          <g key={v}>
            <line x1={px(v)} y1={py(0)} x2={px(v)} y2={py(10)} className={v === 5 ? 'grade-meio' : 'grade'} />
            <line x1={px(0)} y1={py(v)} x2={px(10)} y2={py(v)} className={v === 5 ? 'grade-meio' : 'grade'} />
          </g>
        ))}
        <text x={px(0)} y={TAM - 12} className="eixo-rotulo">{ex.baixo}</text>
        <text x={px(10)} y={TAM - 12} className="eixo-rotulo" textAnchor="end">{ex.alto}</text>
        <text x={TAM / 2} y={TAM - 12} className="eixo-rotulo forte" textAnchor="middle">{ex.nome}</text>
        <text x={14} y={py(0)} className="eixo-rotulo" transform={`rotate(-90 14 ${py(0)})`}>{ey.baixo}</text>
        <text x={14} y={py(10)} className="eixo-rotulo" textAnchor="end" transform={`rotate(-90 14 ${py(10)})`}>{ey.alto}</text>
        <text x={14} y={TAM / 2} className="eixo-rotulo forte" textAnchor="middle" transform={`rotate(-90 14 ${TAM / 2})`}>{ey.nome}</text>

        {mostrar.territorios &&
          terrVisiveis.map((t) => (
            <g key={t.chave} className="territorio" onClick={() => setSelecionado({ tipo: 'territorio', ...t })}>
              <circle cx={px(t.vetor[x])} cy={py(t.vetor[y])} r={30} />
              <text x={px(t.vetor[x])} y={py(t.vetor[y]) + 4} textAnchor="middle">{t.nome}</text>
              <title>{`Território ${t.nome}: ${t.descricao || ''}`}</title>
            </g>
          ))}
        {mostrar.criacoes &&
          criVisiveis.map((c) => (
            <g key={`c${c.id}`} className="ponto-criacao" onClick={() => setSelecionado({ tipo: 'criacao', ...c })}>
              <rect x={px(c.vetor[x]) - 7} y={py(c.vetor[y]) - 7} width={14} height={14} transform={`rotate(45 ${px(c.vetor[x])} ${py(c.vetor[y])})`} />
              <title>{`Criação ${c.nome} (v${c.versao}): ${ex.nome} ${num(c.vetor[x])}, ${ey.nome} ${num(c.vetor[y])}`}</title>
            </g>
          ))}
        {mostrar.essencias &&
          essVisiveis.map((e) => (
            <g key={`e${e.id}`} className="ponto-essencia" onClick={() => setSelecionado({ tipo: 'essencia', ...e })}>
              <circle cx={px(e.vetor[x])} cy={py(e.vetor[y])} r={6.5} style={{ fill: e.cor || 'var(--lilac)' }} />
              <title>{`${e.nome} (${e.familia || 'sem família'}): ${ex.nome} ${num(e.vetor[x])}, ${ey.nome} ${num(e.vetor[y])}`}</title>
            </g>
          ))}
      </svg>

      <div className="mapa-legenda">
        <span><i className="leg-territorio" /> território</span>
        <span><i className="leg-essencia" /> essência (cor da família)</span>
        <span><i className="leg-criacao" /> criação (última versão)</span>
      </div>

      {selecionado && <PontoSelecionado ponto={selecionado} eixos={EIXOS} onFechar={() => setSelecionado(null)} />}

      {!essencias.length && (
        <Vazio titulo="Seu repertório ainda não aparece aqui">
          <Link to="/essencias?nova=1" className="link">Cadastre e classifique essências</Link> para vê-las entre os territórios.
        </Vazio>
      )}
      {foraDaVista.length > 0 && (
        <p className="texto-suave">
          Sem dado em {ex.nome} ou {ey.nome} (não aparecem nesta vista): {foraDaVista.join(', ')}.
        </p>
      )}
      {mostrar.territorios && terrFora.length > 0 && (
        <p className="texto-suave">Territórios que não definem esses dois eixos: {terrFora.join(', ')}.</p>
      )}

      <details className="mapa-lista">
        <summary>Ver o mapa como lista</summary>
        <ul className="linhas">
          {[...terrVisiveis.map((t) => ['Território', t]), ...essVisiveis.map((e) => ['Essência', e]), ...criVisiveis.map((c) => ['Criação', c])].map(([tipo, p]) => (
            <li key={`${tipo}${p.id ?? p.chave}`}>
              <span>{tipo}: {p.nome}</span>
              <strong>{ex.nome} {num(p.vetor[x])} · {ey.nome} {num(p.vetor[y])}</strong>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}

function PontoSelecionado({ ponto: p, eixos, onFechar }) {
  const link = p.tipo === 'essencia' ? '/essencias' : p.tipo === 'criacao' ? `/criacoes/${p.id}` : null;
  return (
    <div className="cartao cartao-suave ponto-detalhe">
      <div className="secao-cabeca">
        <span className="item-texto">
          <strong>{p.nome}</strong>
          <small>
            {p.tipo === 'territorio' ? `Território · ${p.descricao || ''}` : p.tipo === 'criacao' ? `Criação · v${p.versao} · ${p.familia || ''}` : `Essência · ${p.familia || 'sem família'}`}
          </small>
        </span>
        <button className="icone-btn" onClick={onFechar} aria-label="Fechar detalhe">
          <Icon name="close" size={18} />
        </button>
      </div>
      <div className="chips">
        {eixos.filter((e) => p.vetor?.[e.chave] !== null && p.vetor?.[e.chave] !== undefined).map((e) => (
          <Pill key={e.chave} tom="branco">{e.nome} {num(p.vetor[e.chave])}</Pill>
        ))}
      </div>
      {link && <Link to={link} className="link">Abrir</Link>}
    </div>
  );
}

/* --------------------------------------------- caminhos entre as famílias */
function Caminhos({ dados }) {
  const { familias, relacoes, essencias } = dados;
  const [foco, setFoco] = useState(null);

  // Famílias de topo num círculo; subfamílias um pouco para dentro, perto da mãe.
  const posicoes = useMemo(() => {
    const raizes = familias.filter((f) => !f.mae);
    const pos = {};
    raizes.forEach((f, i) => {
      const ang = (i / raizes.length) * Math.PI * 2 - Math.PI / 2;
      pos[f.chave] = { x: 180 + Math.cos(ang) * 120, y: 170 + Math.sin(ang) * 120, ang };
    });
    familias.filter((f) => f.mae && pos[f.mae]).forEach((f, i) => {
      const a = pos[f.mae].ang + 0.35 * (i % 2 ? -1 : 1);
      pos[f.chave] = { x: 180 + Math.cos(a) * 70, y: 170 + Math.sin(a) * 70, ang: a };
    });
    return pos;
  }, [familias]);

  const presentes = new Set();
  for (const e of essencias) {
    if (!e.familia_chave) continue;
    presentes.add(e.familia_chave);
    const mae = familias.find((f) => f.chave === e.familia_chave)?.mae;
    if (mae) presentes.add(mae);
  }
  const nome = (chave) => familias.find((f) => f.chave === chave)?.nome || chave;
  const daFamilia = foco ? relacoes.filter((r) => r.a === foco || r.b === foco) : relacoes;

  return (
    <section className="cartao mapa-cartao">
      <h2 className="secao-titulo">Caminhos entre famílias</h2>
      <small className="texto-suave">
        As linhas mostram como as famílias se relacionam na base de conhecimento. Famílias cheias você já tem no repertório.
      </small>
      <svg className="mapa-svg" viewBox="0 0 360 340" role="img" aria-label={`Grafo de ${familias.length} famílias e ${relacoes.length} relações`}>
        {relacoes.map((r, i) => {
          const a = posicoes[r.a];
          const b = posicoes[r.b];
          if (!a || !b) return null;
          const apagada = foco && r.a !== foco && r.b !== foco;
          return (
            <line
              key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke={COR_RELACAO[r.tipo] || 'var(--ink-3)'}
              strokeWidth={1.5 + (r.peso || 0) * 2.5}
              strokeDasharray={r.tipo === 'atencao' ? '6 4' : undefined}
              opacity={apagada ? 0.15 : 0.85}
            />
          );
        })}
        {familias.map((f) => {
          const p = posicoes[f.chave];
          if (!p) return null;
          const tem = presentes.has(f.chave);
          return (
            <g key={f.chave} className={`no-familia ${foco === f.chave ? 'foco' : ''}`} onClick={() => setFoco(foco === f.chave ? null : f.chave)}>
              <circle cx={p.x} cy={p.y} r={f.mae ? 16 : 22} style={{ fill: tem ? f.cor || 'var(--lilac)' : 'var(--branco)' }} className={tem ? '' : 'ausente'} />
              <text x={p.x} y={p.y + (f.mae ? 30 : 37)} textAnchor="middle">{f.nome}</text>
              <title>{`${f.nome}: ${tem ? 'você tem' : 'você ainda não tem'} essências desta família`}</title>
            </g>
          );
        })}
      </svg>
      <div className="mapa-legenda">
        {Object.entries(NOME_RELACAO).map(([k, v]) => (
          <span key={k}><i className="leg-linha" style={{ background: COR_RELACAO[k] }} /> {v}</span>
        ))}
      </div>
      <ul className="linhas">
        {daFamilia.map((r, i) => (
          <li key={i}>
            <span>
              {nome(r.a)} + {nome(r.b)}
              <small>{r.descricao}</small>
            </span>
            <strong>{NOME_RELACAO[r.tipo] || r.tipo}</strong>
          </li>
        ))}
      </ul>
      {foco && <button className="link alinhar-esquerda" onClick={() => setFoco(null)}>Ver todas as relações</button>}
    </section>
  );
}

/* ------------------------------------------------------- mapas de estudo */
function MapasDeEstudo({ mapas }) {
  if (!mapas.length) return null;
  const CATEGORIA = { familia: 'Família', piramide: 'Pirâmide', eixo: 'Eixo' };
  return (
    <section className="cartao mapa-cartao">
      <h2 className="secao-titulo">Mapas de estudo</h2>
      <ul className="lista">
        {mapas.map((m) => (
          <li key={m.titulo} className="item">
            <span className="item-texto quebra">
              <strong>{m.titulo}</strong>
              <small>{resumoMapa(m)}</small>
            </span>
            <Pill>{CATEGORIA[m.categoria] || m.categoria}</Pill>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Uma linha legível a partir do conteúdo livre (JSON) do mapa. */
function resumoMapa(m) {
  const c = m.conteudo || {};
  if (Array.isArray(c.camadas)) return `Camadas: ${c.camadas.join(' → ')}`;
  if (c.extremos) return `De ${Object.values(c.extremos).join(' a ')}`;
  if (Array.isArray(c.pontos)) return `${c.pontos.length} ponto(s) ao redor de ${c.centro || m.familia || 'uma família'}`;
  return 'Mapa da base de conhecimento.';
}
