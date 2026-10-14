import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { conhecimento } from '../api/serene';
import { useApi } from '../lib/useApi';
import { camadaDominante, normalizar, rotulo } from '../lib/format';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import { Avatar, Carregando, Erro, Pill, Vazio } from '../components/ui';

const ABAS = [
  { chave: 'familias', nome: 'Famílias' },
  { chave: 'notas', nome: 'Notas' },
  { chave: 'relacoes', nome: 'Relações' },
  { chave: 'territorios', nome: 'Territórios' },
  { chave: 'piramide', nome: 'Pirâmide' },
];

/**
 * Base de conhecimento olfativo (só leitura): o mesmo conteúdo que o motor usa
 * para sugerir classificação, explicar compatibilidade e nomear lacunas.
 * As notas daqui NÃO são essências da aluna — são referência de estudo.
 */
export default function Conhecimento() {
  const [params, setParams] = useSearchParams();
  const aba = params.get('aba') || 'familias';
  const base = useApi(() =>
    Promise.all([
      conhecimento.familias(),
      conhecimento.notas(),
      conhecimento.relacoes(),
      conhecimento.territorios(),
      conhecimento.publicos(),
      conhecimento.funcoes(),
      conhecimento.descritores(),
    ]).then(([familias, notas, relacoes, territorios, publicos, funcoes, descritores]) => ({
      familias, notas, relacoes, territorios, publicos, funcoes, descritores,
    })),
  );

  return (
    <div className="pagina">
      <Cabecalho
        titulo="Conhecimento olfativo"
        voltar={
          <Link to="/mapa" className="icone-btn" aria-label="Voltar ao mapa">
            <Icon name="back" />
          </Link>
        }
      />
      <p className="texto-suave">
        A base do SÉRENÉ: é com ela que o sistema sugere classificações, explica combinações e aponta lacunas.
        As notas aqui são de estudo — o que entra nas suas criações é só o seu repertório.
      </p>
      <div className="segmentos rolagem" role="tablist">
        {ABAS.map((a) => (
          <button
            key={a.chave} role="tab" aria-selected={aba === a.chave}
            className={aba === a.chave ? 'ativo' : ''}
            onClick={() => setParams(a.chave === 'familias' ? {} : { aba: a.chave }, { replace: true })}
          >
            {a.nome}
          </button>
        ))}
      </div>
      <Erro erro={base.error} onRetry={base.reload} />
      {base.loading && !base.data ? (
        <Carregando />
      ) : base.data ? (
        <>
          {aba === 'familias' && <Familias {...base.data} />}
          {aba === 'notas' && <Notas {...base.data} />}
          {aba === 'relacoes' && <Relacoes {...base.data} />}
          {aba === 'territorios' && <Territorios {...base.data} />}
          {aba === 'piramide' && <Piramide {...base.data} />}
        </>
      ) : null}
    </div>
  );
}

function Familias({ familias }) {
  const raizes = familias.filter((f) => !f.parent_id);
  return (
    <ul className="cartoes grade-desktop">
      {raizes.map((f) => (
        <li key={f.id} className="cartao">
          <div className="item cabeca-detalhe">
            <Avatar cor={f.cor}><Icon name="drop" size={18} /></Avatar>
            <span className="item-texto quebra">
              <strong>{f.nome}</strong>
              <small>{f.descricao}</small>
            </span>
          </div>
          {familias.filter((s) => s.parent_id === f.id).map((s) => (
            <p key={s.id} className="texto-suave">
              <Pill>{s.nome}</Pill> {s.descricao}
            </p>
          ))}
        </li>
      ))}
    </ul>
  );
}

function Notas({ notas, familias }) {
  const [busca, setBusca] = useState('');
  const nomeFamilia = (id) => familias.find((f) => f.id === id)?.nome;
  const termo = normalizar(busca);
  const filtradas = notas.filter(
    (n) => !termo || normalizar(n.nome).includes(termo) || n.sinonimos.some((s) => normalizar(s).includes(termo)),
  );
  return (
    <>
      <label className="campo">
        <span>Buscar nota</span>
        <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Ex.: bergamota" />
      </label>
      {!filtradas.length ? (
        <Vazio titulo="Nenhuma nota encontrada">A base ainda não tem uma nota com esse nome.</Vazio>
      ) : (
        <ul className="cartoes grade-desktop">
          {filtradas.map((n) => (
            <li key={n.id} className="cartao">
              <span className="item-texto quebra">
                <strong>{n.nome}</strong>
                <small>
                  {[nomeFamilia(n.family_id), rotulo(n.tipo_referencia), camadaDominante(n.papel_tipico)].filter(Boolean).join(' · ')}
                </small>
              </span>
              {n.sinonimos.length > 0 && <small className="texto-suave">Também conhecida como: {n.sinonimos.join(', ')}</small>}
              <div className="chips">
                <Pill tom={n.confianca_referencia === 'baixa' ? 'amarelo' : 'verde'}>confiança {rotulo(n.confianca_referencia)}</Pill>
                {n.descritores.map((d) => <Pill key={d}>{d}</Pill>)}
              </div>
              {n.observacoes && <p className="texto-suave">{n.observacoes}</p>}
              {n.fonte && <small className="texto-suave">Fonte: {n.fonte}</small>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Relacoes({ relacoes, familias }) {
  const nome = (id) => familias.find((f) => f.id === id)?.nome || '?';
  const TIPO = { classico: ['Clássico', 'verde'], complementar: ['Complementar', 'lilac'], contraste: ['Contraste', 'amarelo'], atencao: ['Atenção', 'erro'] };
  return (
    <ul className="cartoes grade-desktop">
      {relacoes.map((r) => (
        <li key={r.id} className="cartao">
          <strong>{nome(r.family_a_id)} + {nome(r.family_b_id)}</strong>
          <Pill tom={TIPO[r.tipo_relacao]?.[1]}>{TIPO[r.tipo_relacao]?.[0] || r.tipo_relacao}</Pill>
          <p className="texto-suave">{r.descricao}</p>
        </li>
      ))}
    </ul>
  );
}

function Territorios({ territorios, publicos }) {
  return (
    <>
      <h2 className="secao-titulo">Territórios</h2>
      <ul className="cartoes grade-desktop">
        {territorios.map((t) => (
          <li key={t.chave} className="cartao">
            <strong>{t.nome}</strong>
            <small className="texto-suave">{t.descricao_curta}</small>
            <p className="texto-suave">{t.descricao}</p>
          </li>
        ))}
      </ul>
      <h2 className="secao-titulo">Públicos</h2>
      <ul className="cartoes grade-desktop">
        {publicos.map((p) => (
          <li key={p.chave} className="cartao">
            <strong>{p.nome}</strong>
            <p className="texto-suave">{p.descricao}</p>
            {p.vocabulario?.length > 0 && (
              <div className="chips">{p.vocabulario.map((v) => <Pill key={v}>{v}</Pill>)}</div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function Piramide({ funcoes, descritores }) {
  return (
    <>
      <ul className="cartoes">
        {funcoes.map((f) => (
          <li key={f.id} className="cartao">
            <strong>{f.nome}</strong>
            <p className="texto-suave">{f.descricao}</p>
          </li>
        ))}
      </ul>
      <h2 className="secao-titulo">Descritores</h2>
      <div className="chips">
        {descritores.map((d) => (
          <Pill key={d.id}>{d.nome}{d.categoria ? ` · ${d.categoria}` : ''}</Pill>
        ))}
      </div>
    </>
  );
}
