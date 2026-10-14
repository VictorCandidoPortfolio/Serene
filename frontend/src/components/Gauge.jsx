/**
 * Medidor em meia-lua: a parte preenchida é branca e o restante é hachurado,
 * como o cartão "Monthly Expenses" da referência visual.
 */
export default function Gauge({ valor, rotulo, detalhe }) {
  const p = Math.max(0, Math.min(100, Math.round(valor * 100)));
  const arco = 'M 30 120 A 90 90 0 0 1 210 120';
  return (
    <div className="gauge">
      <svg viewBox="0 0 240 132" role="img" aria-label={`${rotulo}: ${p}%`}>
        <defs>
          <pattern id="hachura" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="7" height="7" fill="var(--yellow)" />
            <line x1="0" y1="0" x2="0" y2="7" stroke="var(--ink)" strokeWidth="2.4" />
          </pattern>
        </defs>
        <path d={arco} pathLength="100" fill="none" stroke="url(#hachura)" strokeWidth="34"
          strokeDasharray={`${100 - p} 100`} strokeDashoffset={-p} />
        {p > 0 && (
          <path d={arco} pathLength="100" fill="none" stroke="#fff" strokeWidth="34" strokeDasharray={`${p} 100`} />
        )}
      </svg>
      <div className="gauge-centro">
        <span className="gauge-rotulo">{rotulo}</span>
        <strong className="gauge-valor">{p}%</strong>
        {detalhe && <span className="gauge-detalhe">{detalhe}</span>}
      </div>
    </div>
  );
}
