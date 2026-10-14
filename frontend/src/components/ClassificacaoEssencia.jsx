import { useState } from 'react';
import { CAMADAS, EIXOS, leituraEixo, normalizar, num, sensacao } from '../lib/format';
import { Campo, Grupo } from './ui';

const TIPOS = [
  { chave: 'simples', nome: 'Simples' },
  { chave: 'composta', nome: 'Composta' },
  { chave: 'desconhecida', nome: 'Não sei' },
];
const CONFIANCAS = [
  { chave: 'alta', nome: 'Alta' },
  { chave: 'media', nome: 'Média' },
  { chave: 'baixa', nome: 'Baixa' },
];
const ORIGENS = [
  { chave: 'informado', nome: 'Eu avaliei' },
  { chave: 'tecnico', nome: 'Ficha técnica' },
  { chave: 'estimado', nome: 'Estimativa' },
];

/** Classificação vazia: tudo "não sei" (null), como a API entende. */
export const CLASSIFICACAO_VAZIA = {
  familia: '', subfamilia: '', tipo: 'desconhecida', papel: null,
  v1: null, v2: null, v3: null, v4: null, v5: null, v6: null,
  confianca: 'baixa', origem: 'informado', fornecedor: '', descritores: [], observacoes: '', tags: [],
};

/** Lê os campos de classificação de uma essência da API. */
export function classificacaoDe(e) {
  return Object.fromEntries(
    Object.keys(CLASSIFICACAO_VAZIA).map((k) => [k, e?.[k] ?? CLASSIFICACAO_VAZIA[k]]),
  );
}

/**
 * Corpo para a API: texto vazio vira null; listas e eixos passam como estão
 * (eixo null = "não sei", e o motor nunca troca isso por um chute).
 */
export function classificacaoParaApi(c) {
  const texto = (t) => (t || '').trim() || null;
  return {
    familia: texto(c.familia),
    subfamilia: texto(c.subfamilia),
    tipo: c.tipo,
    papel: c.papel,
    v1: c.v1, v2: c.v2, v3: c.v3, v4: c.v4, v5: c.v5, v6: c.v6,
    confianca: c.confianca,
    origem: c.origem,
    fornecedor: texto(c.fornecedor),
    descritores: c.descritores,
    observacoes: texto(c.observacoes),
    tags: c.tags,
  };
}

function Segmentos({ opcoes, valor, onChange, rotulo }) {
  return (
    <div className="segmentos" role="group" aria-label={rotulo}>
      {opcoes.map((o) => (
        <button key={o.chave} type="button" className={valor === o.chave ? 'ativo' : ''} onClick={() => onChange(o.chave)}>
          {o.nome}
        </button>
      ))}
    </div>
  );
}

/** Um eixo 0–10 com a opção "não sei" (null). */
function CampoEixo({ eixo, valor, onChange }) {
  const sabe = valor !== null && valor !== undefined;
  return (
    <div className="eixo-campo">
      <div className="eixo-topo">
        <span>
          {eixo.nome} <small className="texto-suave">{eixo.dica}</small>
        </span>
        <span className="eixo-valor">
          {sabe ? (
            <>
              {num(valor)} <small>{leituraEixo(eixo.chave, valor)}</small>
            </>
          ) : (
            <small>não sei</small>
          )}
        </span>
      </div>
      <div className="eixo-entrada">
        <input
          type="range" min={0} max={10} step={0.5}
          value={sabe ? valor : 5}
          className={sabe ? '' : 'inativo'}
          onChange={(e) => onChange(Number(e.target.value))}
          aria-label={`${eixo.nome}: de ${eixo.baixo} (0) a ${eixo.alto} (10)`}
          aria-valuetext={sabe ? `${num(valor)}, ${leituraEixo(eixo.chave, valor)}` : 'não informado'}
        />
        <button type="button" className="link" onClick={() => onChange(sabe ? null : 5)}>
          {sabe ? 'Não sei' : 'Informar'}
        </button>
      </div>
      {eixo.chave === 'v1' && sabe && <small className="texto-suave">Sensação: {sensacao(valor)}</small>}
    </div>
  );
}

/**
 * Formulário de classificação olfativa de uma essência (cadastro e edição).
 *
 * @param {object} props
 * @param {object} props.valor          classificação atual (ver CLASSIFICACAO_VAZIA)
 * @param {(v: object) => void} props.onChange
 * @param {object[]} props.familias     famílias da base de conhecimento
 * @param {string[]} [props.descritoresBase] vocabulário de descritores da base
 */
export default function ClassificacaoEssencia({ valor, onChange, familias = [], descritoresBase = [] }) {
  const [novoDescritor, setNovoDescritor] = useState('');
  // Texto das tags como a aluna digita (com vírgulas); a lista vai para o valor.
  const [tagsTexto, setTagsTexto] = useState(() => valor.tags.join(', '));
  const set = (campo) => (v) => onChange({ ...valor, [campo]: v });

  const raizes = familias.filter((f) => !f.parent_id);
  const mae = raizes.find((f) => normalizar(f.nome) === normalizar(valor.familia));
  const filhas = familias.filter((f) => f.parent_id && (!mae || f.parent_id === mae.id));

  function alternarDescritor(d) {
    const tem = valor.descritores.includes(d);
    set('descritores')(tem ? valor.descritores.filter((x) => x !== d) : [...valor.descritores, d]);
  }
  function adicionarDescritor() {
    const d = novoDescritor.trim().toLowerCase();
    if (d && !valor.descritores.includes(d)) set('descritores')([...valor.descritores, d]);
    setNovoDescritor('');
  }
  const papel = valor.papel;

  return (
    <div className="form classificacao">
      <div className="duas-colunas">
        <Campo rotulo="Família">
          <input list="lista-familias" value={valor.familia} onChange={(e) => set('familia')(e.target.value)} placeholder="Ex.: Floral" />
          <datalist id="lista-familias">
            {raizes.map((f) => <option key={f.id} value={f.nome} />)}
          </datalist>
        </Campo>
        <Campo rotulo="Subfamília">
          <input list="lista-subfamilias" value={valor.subfamilia} onChange={(e) => set('subfamilia')(e.target.value)} placeholder="Opcional" />
          <datalist id="lista-subfamilias">
            {filhas.map((f) => <option key={f.id} value={f.nome} />)}
          </datalist>
        </Campo>
      </div>

      <Grupo rotulo="Tipo">
        <Segmentos rotulo="Tipo" opcoes={TIPOS} valor={valor.tipo} onChange={set('tipo')} />
      </Grupo>

      <fieldset className="grupo-eixos">
        <legend className="rotulo">Características sensoriais</legend>
        {EIXOS.map((e) => (
          <CampoEixo key={e.chave} eixo={e} valor={valor[e.chave]} onChange={set(e.chave)} />
        ))}
      </fieldset>

      <fieldset className="grupo-eixos">
        <legend className="rotulo">
          Papel na pirâmide{' '}
          <button type="button" className="link" onClick={() => set('papel')(papel ? null : { saida: 0.3, coracao: 0.4, fundo: 0.3 })}>
            {papel ? 'Não sei' : 'Informar'}
          </button>
        </legend>
        {papel ? (
          CAMADAS.map((c) => (
            <div key={c.chave} className="eixo-campo">
              <div className="eixo-topo">
                <span>{c.nome}</span>
                <span className="eixo-valor">{Math.round((papel[c.chave] || 0) * 100)}%</span>
              </div>
              <input
                type="range" min={0} max={100} step={5}
                value={Math.round((papel[c.chave] || 0) * 100)}
                onChange={(e) => set('papel')({ ...papel, [c.chave]: Number(e.target.value) / 100 })}
                aria-label={`Afinidade com a ${c.nome}`}
              />
            </div>
          ))
        ) : (
          <small className="texto-suave">Em que momento a essência aparece: saída, coração ou fundo.</small>
        )}
      </fieldset>

      <Grupo rotulo="Descritores">
        <div className="chips">
          {[...new Set([...descritoresBase, ...valor.descritores])].map((d) => (
            <button key={d} type="button" className={`chip ${valor.descritores.includes(d) ? 'ativo' : ''}`} onClick={() => alternarDescritor(d)}>
              {d}
            </button>
          ))}
        </div>
        <div className="linha-adicionar">
          <input
            value={novoDescritor}
            onChange={(e) => setNovoDescritor(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                adicionarDescritor();
              }
            }}
            placeholder="Outro descritor (ex.: verde)"
            aria-label="Novo descritor"
          />
          <button type="button" className="btn btn-pequeno btn-contorno" onClick={adicionarDescritor}>
            Adicionar
          </button>
        </div>
      </Grupo>

      <div className="duas-colunas">
        <Grupo rotulo="Confiança da classificação">
          <Segmentos rotulo="Confiança" opcoes={CONFIANCAS} valor={valor.confianca} onChange={set('confianca')} />
        </Grupo>
        <Grupo rotulo="De onde vieram os valores">
          <Segmentos rotulo="Origem" opcoes={ORIGENS} valor={valor.origem} onChange={set('origem')} />
        </Grupo>
      </div>

      <Campo rotulo="Fornecedor">
        <input value={valor.fornecedor} onChange={(e) => set('fornecedor')(e.target.value)} />
      </Campo>
      <Campo rotulo="Tags" dica="Separadas por vírgula.">
        <input
          value={tagsTexto}
          onChange={(e) => {
            setTagsTexto(e.target.value);
            set('tags')(e.target.value.split(',').map((t) => t.trim()).filter(Boolean));
          }}
        />
      </Campo>
      <Campo rotulo="Observações">
        <textarea rows={2} value={valor.observacoes} onChange={(e) => set('observacoes')(e.target.value)} />
      </Campo>
    </div>
  );
}
