import { Linhas, Pill } from './ui';

const br = (n, casas = 2) => Number(n).toFixed(casas).replace('.', ',');

/**
 * "Fórmula proposta": tabela de uma fórmula JÁ calculada pelo servidor (nada é
 * recalculado aqui). Mostra o nome do acorde, o concentrado aromático dividido
 * entre as essências (% do concentrado, ml e, se houver densidade, g), os
 * componentes da base, o volume final e as pendências técnicas.
 *
 * @param {object} props.formulacao  resultado de /formulacoes/* (valido === true)
 * @param {string} [props.nome]      nome sugerido do acorde (só um nome; não é a fórmula)
 * @param {string} [props.titulo]    título da seção
 */
export default function FormulaTabela({ formulacao: f, nome = null, titulo = 'Fórmula proposta' }) {
  const essencias = f.ingredientes.filter((i) => i.tipo === 'essencia');
  const componentes = f.ingredientes.filter((i) => i.tipo === 'base');
  const totalBase = componentes.reduce((s, i) => s + i.volume_ml, 0);
  const totalEssencias = essencias.reduce((s, i) => s + i.percentual_concentrado, 0);
  const pendencias = [...new Set([...(f.pendencias || []), ...(f.avisos || [])])];
  const detalhe = (i, extras = []) =>
    [...extras, i.massa_g != null ? `${br(i.massa_g)} g` : null, `${br(i.percentual_produto)} % do produto`]
      .filter(Boolean).join(' · ');

  return (
    <section className="cartao">
      <div className="secao-cabeca">
        <h2 className="secao-titulo">{titulo}</h2>
        <Pill>{f.produto} {br(f.concentracao_pct, 0)}%</Pill>
      </div>
      {nome && <small className="texto-suave">Nome sugerido do acorde: {nome}</small>}

      <span className="rotulo">
        Concentrado aromático · {br(f.concentrado_ml)} ml ({br(f.concentracao_pct, 0)}% de {br(f.volume_ml, f.volume_ml % 1 ? 2 : 0)} ml)
      </span>
      <Linhas itens={essencias.map((i) => [
        i.nome,
        `${br(i.volume_ml)} ml`,
        detalhe(i, [i.rotulo_peso, `${br(i.percentual_concentrado)} % do concentrado`]),
      ])} />
      <small className="texto-suave">
        Total das essências: {br(totalEssencias)} % do concentrado
        {f.criterio === 'manual' ? ' · proporções definidas por você' : ' · divididas pelos pesos do acorde (Pouco 1 : Médio 2 : Bastante 3)'}
      </small>

      <span className="rotulo">Base · {br(totalBase)} ml</span>
      <Linhas itens={componentes.map((i) => [i.nome, `${br(i.volume_ml)} ml`, detalhe(i)])} />

      <Linhas itens={[[
        'Volume final',
        `${br(f.volume_ml, f.volume_ml % 1 ? 2 : 0)} ml`,
        f.massa_total_g != null ? `Massa total: ${br(f.massa_total_g)} g` : null,
      ]]} />

      {pendencias.length > 0 && (
        <>
          <span className="rotulo">Pendências técnicas</span>
          <ul className="lista-pendencias">
            {pendencias.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </>
      )}
      <small className="texto-suave">{f.validacao}</small>
    </section>
  );
}
