/**
 * Painel amarelo com grade isométrica e objetos de perfumaria em traço,
 * no espírito da ilustração da tela "Top Up" da referência.
 */
export default function Illustration({ altura = 190 }) {
  return (
    // A altura vai como variável CSS (e não `height` direto) para o desktop poder trocá-la.
    <div className="ilustracao" style={{ '--altura': `${altura}px` }}>
      <svg viewBox="0 0 320 190" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <pattern id="grade" width="46" height="26.5" patternUnits="userSpaceOnUse">
            <path d="M0 13.25 23 0 46 13.25 23 26.5z" fill="none" stroke="#E9B94F" strokeWidth="1.2" />
          </pattern>
        </defs>
        {/* No desktop o fundo some daqui e vira o padrão do painel inteiro (ver styles.css). */}
        <rect className="ilustracao-fundo" width="320" height="190" fill="var(--yellow)" />
        <rect className="ilustracao-fundo" width="320" height="190" fill="url(#grade)" />

        <g stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round">
          {/* frasco principal */}
          <path d="M150 62h36v12h-36z" fill="var(--ink)" />
          <path d="M156 50h24v12h-24z" fill="var(--lilac)" />
          <path d="M136 74h64a8 8 0 0 1 8 8v58a10 10 0 0 1-10 10h-60a10 10 0 0 1-10-10V82a8 8 0 0 1 8-8z" fill="#fff" />
          <path d="M140 104h56v36a4 4 0 0 1-4 4h-48a4 4 0 0 1-4-4z" fill="var(--lilac)" />
          <path d="M152 86h14" />

          {/* frasco redondo */}
          <path d="M244 96h14v10h-14z" fill="#fff" />
          <circle cx="251" cy="128" r="22" fill="#fff" />
          <path d="M231 132a20 20 0 0 0 40 0z" fill="var(--lilac)" />

          {/* gotas */}
          <path d="M92 70s10 11 10 18a10 10 0 0 1-20 0c0-7 10-18 10-18z" fill="var(--lilac)" />
          <path d="M70 116s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z" fill="#fff" />

          {/* folha */}
          <path d="M96 150c-2-18 14-30 32-28-2 18-14 30-32 28z" fill="#fff" />
          <path d="M96 150l20-18" />

          {/* brilhos */}
          <path d="M226 42l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" fill="var(--ink)" />
          <path d="M252 62l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="var(--ink)" />
        </g>
      </svg>
    </div>
  );
}
