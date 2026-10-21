import { Linhas, Pill } from './ui';

const br = (n, casas = 2) => Number(n).toFixed(casas).replace('.', ',');

/**
 * Tabela de uma fórmula JÁ calculada pelo servidor (nada é recalculado aqui):
 * concentrado, cada essência (ml/g, % do concentrado, % do produto) e a base.
 * Sempre acompanhada da nota de que a fórmula NÃO é validada.
 *
 * @param {object} props.formulacao  resultado de /formulacoes/* (valido === true)
 * @param {boolean} [props.base]     composição da base ainda é de exemplo
 */
export default function FormulaTabela({ formulacao: f, base = false }) {
  const essencias = f.ingredientes.filter((i) => i.tipo === 'essencia');
  const componentes = f.ingredientes.filter((i) => i.tipo === 'base');
  const detalhe = (i, extras = []) =>
    [...extras, i.massa_g != null ? `${br(i.massa_g)} g` : null, `${br(i.percentual_produto)} % do produto`]
      .filter(Boolean).join(' · ');

  return (
    <section className="cartao">
      <div className="secao-cabeca">
        <h2 className="secao-titulo">{f.produto} · {br(f.volume_ml, f.volume_ml % 1 ? 2 : 0)} ml</h2>
        <Pill>{br(f.concentracao_pct, 0)}% de concentrado</Pill>
      </div>

      <span className="rotulo">Concentrado aromático · {br(f.concentrado_ml)} ml</span>
      <Linhas itens={essencias.map((i) => [
        i.nome,
        `${br(i.volume_ml)} ml`,
        detalhe(i, [i.rotulo_peso, `${br(i.percentual_concentrado)} % do concentrado`]),
      ])} />
      {f.criterio === 'manual' && <small className="texto-suave">Proporções definidas manualmente por você.</small>}

      <span className="rotulo">Base{base ? ' · composição de exemplo, a confirmar' : ''}</span>
      <Linhas itens={componentes.map((i) => [i.nome, `${br(i.volume_ml)} ml`, detalhe(i)])} />

      {f.massa_total_g != null && <small className="texto-suave">Massa total: {br(f.massa_total_g)} g</small>}
      <small className="texto-suave">{f.validacao}</small>
    </section>
  );
}
