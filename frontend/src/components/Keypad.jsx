import Icon from './Icon';

/**
 * Teclado numérico da tela "Top Up" da referência.
 * `max` limita o valor: um dígito que estouraria o limite recomeça o número.
 */
export default function Keypad({ valor, onChange, max = 10 }) {
  function digitar(d) {
    const atual = valor === null ? '' : String(valor);
    const novo = Number(atual + d);
    onChange(novo > max ? d : novo);
  }

  function apagar() {
    const atual = valor === null ? '' : String(valor);
    onChange(atual.length > 1 ? Number(atual.slice(0, -1)) : null);
  }

  return (
    <div className="keypad">
      {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
        <button key={d} type="button" onClick={() => digitar(d)}>
          {d}
        </button>
      ))}
      <span />
      <button type="button" onClick={() => digitar(0)}>
        0
      </button>
      <button type="button" onClick={apagar} aria-label="Apagar">
        <Icon name="del" size={22} />
      </button>
    </div>
  );
}
