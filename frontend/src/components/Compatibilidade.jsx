import Gauge from './Gauge';
import { Pill } from './ui';

const TOM_RELACAO = { classico: 'verde', complementar: 'lilac', contraste: 'amarelo', atencao: 'erro', mesma_familia: 'lilac' };
const NOME_RELACAO = {
  classico: 'clássico', complementar: 'complementar', contraste: 'contraste',
  atencao: 'atenção', mesma_familia: 'mesma família',
};

/**
 * Resultado de compatibilidade (do acorde salvo ou da análise avulsa):
 * nota do grupo, explicação de cada par e alertas.
 *
 * @param {{score: number|null, pares: object[], alertas: string[]}} props.resultado
 * @param {Record<number, string>} [props.nomes] id da essência → nome (para os pares)
 */
export default function ResultadoCompatibilidade({ resultado, nomes = {}, compacto = false }) {
  if (!resultado) return null;
  const { score, alertas = [], base_exemplo: exemplo } = resultado;
  // Só pares efetivamente avaliados (dados antigos podem trazer pares sem nota).
  const pares = (resultado.pares || []).filter((p) => typeof p.score === 'number');
  return (
    <div className="compat">
      {typeof score === 'number' && (
        <>
          <Gauge valor={score / 100} rotulo="Compatibilidade" detalhe={`${pares.length} par(es) avaliado(s)`} />
          {exemplo && <small className="texto-suave">Calculada com relações de exemplo, ainda não validadas.</small>}
        </>
      )}
      {!compacto &&
        pares.map((p, i) => (
          <p key={i} className="texto-suave compat-par">
            {p.tipo_relacao && <Pill tom={TOM_RELACAO[p.tipo_relacao]}>{NOME_RELACAO[p.tipo_relacao] || p.tipo_relacao}</Pill>}{' '}
            {nomes[p.essencia_a] && nomes[p.essencia_b] && (
              <strong>
                {nomes[p.essencia_a]} + {nomes[p.essencia_b]}:{' '}
              </strong>
            )}
            {p.explicacao}
          </p>
        ))}
      {[...new Set(alertas)].map((a, i) => (
        <p key={i} className="aviso">
          {a}
        </p>
      ))}
    </div>
  );
}
