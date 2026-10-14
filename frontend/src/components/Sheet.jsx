import { useEffect } from 'react';
import Icon from './Icon';

/** Painel que sobe de baixo (como "Detail Transactions"). Fecha no X, no fundo ou no Esc. */
export default function Sheet({ titulo, onClose, children, topo }) {
  useEffect(() => {
    const esc = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);

  return (
    <div className="sheet-fundo" onClick={onClose}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={titulo} onClick={(e) => e.stopPropagation()}>
        {topo}
        <div className="sheet-corpo">
          <header className="sheet-cabecalho">
            <h2>{titulo}</h2>
            <button className="icone-btn" onClick={onClose} aria-label="Fechar">
              <Icon name="close" />
            </button>
          </header>
          {children}
        </div>
        <div className="home-indicator" />
      </div>
    </div>
  );
}
