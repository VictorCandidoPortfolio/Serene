import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

const ConfirmarContext = createContext(null);

/**
 * Diálogo de confirmação no visual do app, no lugar do `window.confirm`
 * (que não segue o estilo, varia por navegador e trava a página inteira).
 *
 * Uso: `const confirmar = useConfirmar();`
 *      `if (!(await confirmar('Excluir X?', { botao: 'Excluir' }))) return;`
 */
export function ConfirmarProvider({ children }) {
  const [pedido, setPedido] = useState(null);
  const resolver = useRef(null);

  const confirmar = useCallback(
    (mensagem, { titulo = 'Confirmar', botao = 'Confirmar' } = {}) =>
      new Promise((resolve) => {
        resolver.current = resolve;
        setPedido({ mensagem, titulo, botao });
      }),
    [],
  );

  const responder = useCallback((sim) => {
    resolver.current?.(sim);
    resolver.current = null;
    setPedido(null);
  }, []);

  return (
    <ConfirmarContext.Provider value={confirmar}>
      {children}
      {pedido && <DialogoConfirmar {...pedido} onResponder={responder} />}
    </ConfirmarContext.Provider>
  );
}

function DialogoConfirmar({ titulo, mensagem, botao, onResponder }) {
  const cancelarRef = useRef(null);

  useEffect(() => {
    // O foco começa no "Cancelar": Enter por engano não apaga nada.
    const anterior = document.activeElement;
    cancelarRef.current?.focus();
    // Fase de captura + stopPropagation: o Esc fecha só este diálogo, e não
    // o painel (Sheet) que está por baixo dele.
    const esc = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onResponder(false);
      }
    };
    window.addEventListener('keydown', esc, true);
    return () => {
      window.removeEventListener('keydown', esc, true);
      anterior?.focus?.();
    };
  }, [onResponder]);

  return (
    <div className="sheet-fundo confirmar-fundo" onClick={() => onResponder(false)}>
      <div
        className="confirmar"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmar-titulo"
        aria-describedby="confirmar-mensagem"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirmar-titulo">{titulo}</h2>
        <p id="confirmar-mensagem">{mensagem}</p>
        <div className="botoes-duplos">
          <button ref={cancelarRef} className="btn btn-contorno" onClick={() => onResponder(false)}>
            Cancelar
          </button>
          <button className="btn btn-perigo" onClick={() => onResponder(true)}>
            {botao}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useConfirmar() {
  return useContext(ConfirmarContext);
}
