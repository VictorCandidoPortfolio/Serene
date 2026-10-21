/** Peças pequenas reutilizadas pelas telas. */
import { EIXOS, num, leituraEixo } from '../lib/format';

export function Carregando({ texto = 'Carregando…' }) {
  return (
    <div className="estado">
      <span className="spinner" aria-hidden="true" />
      {texto}
    </div>
  );
}

export function Erro({ erro, onRetry }) {
  if (!erro) return null;
  return (
    <div className="erro" role="alert">
      <span>{erro.message || String(erro)}</span>
      {onRetry && (
        <button className="link" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Vazio({ titulo, children }) {
  return (
    <div className="vazio">
      <strong>{titulo}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}

/** Círculo lilás com ícone, como os avatares de "Last Spendings". */
export function Avatar({ cor, children }) {
  return (
    <span className="avatar" style={cor ? { background: cor } : undefined}>
      {children}
    </span>
  );
}

export function Pill({ children, tom = 'lilac' }) {
  return <span className={`pill pill-${tom}`}>{children}</span>;
}

/** Marca de conteúdo de EXEMPLO: ainda não validado pela SÉRENÉ. */
export function Exemplo() {
  return <Pill tom="amarelo">Exemplo</Pill>;
}

/** Linhas "rótulo ........ valor" separadas por fio, como a lista "Items". */
export function Linhas({ itens }) {
  return (
    <ul className="linhas">
      {itens.map(([rotulo, valor, sub]) => (
        <li key={rotulo}>
          <span>
            {rotulo}
            {sub && <small>{sub}</small>}
          </span>
          <strong>{valor}</strong>
        </li>
      ))}
    </ul>
  );
}

/** Barras 0–10 dos cinco eixos. `alvo` (opcional) desenha a marca do perfil. */
export function Eixos({ vetor, alvo }) {
  // Só eixos COM valor: linha "sem dado" e barra vazia seriam indicador sem base.
  const comValor = EIXOS.filter((e) => vetor?.[e.chave] !== null && vetor?.[e.chave] !== undefined);
  if (!comValor.length) return null;
  return (
    <ul className="eixos">
      {comValor.map((e) => {
        const v = vetor?.[e.chave];
        const a = alvo?.[e.chave];
        return (
          <li key={e.chave}>
            <div className="eixo-topo">
              <span>{e.nome}</span>
              <span className="eixo-valor">
                {num(v)} <small>{leituraEixo(e.chave, v)}</small>
              </span>
            </div>
            <div className="eixo-trilho">
              {v !== null && v !== undefined && <div className="eixo-barra" style={{ width: `${v * 10}%` }} />}
              {a !== null && a !== undefined && (
                <div className="eixo-alvo" style={{ left: `${a * 10}%` }} title={`Alvo ${num(a)}`} />
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function Campo({ rotulo, children, dica }) {
  return (
    <label className="campo">
      <span>{rotulo}</span>
      {children}
      {dica && <small>{dica}</small>}
    </label>
  );
}

/**
 * Como `Campo`, mas para grupos de botões (chips): um <label> daria o texto da
 * pergunta como nome acessível ao primeiro botão do grupo.
 */
export function Grupo({ rotulo, children }) {
  return (
    <div className="campo" role="group" aria-label={rotulo}>
      <span aria-hidden="true">{rotulo}</span>
      {children}
    </div>
  );
}

/** Grupo de chips selecionáveis (um ou vários). */
export function Chips({ opcoes, valor, onChange, multiplo = false }) {
  const selecionado = (c) => (multiplo ? valor.includes(c) : valor === c);
  function alternar(c) {
    if (multiplo) onChange(selecionado(c) ? valor.filter((v) => v !== c) : [...valor, c]);
    else onChange(selecionado(c) ? null : c);
  }
  return (
    <div className="chips">
      {opcoes.map((o) => (
        <button
          key={o.chave}
          type="button"
          className={`chip ${selecionado(o.chave) ? 'ativo' : ''}`}
          onClick={() => alternar(o.chave)}
          title={o.dica}
        >
          {o.nome}
        </button>
      ))}
    </div>
  );
}
