import { requisitosSenha, senhaLongaDemais } from '../lib/senha';
import Icon from './Icon';

/** Checklist ao vivo da senha forte (a API valida de novo no cadastro). */
export default function RequisitosSenha({ senha }) {
  return (
    <ul className="requisitos" id="requisitos-senha" aria-label="Requisitos da senha">
      {requisitosSenha(senha).map((r) => (
        <li key={r.id} className={r.ok ? 'ok' : undefined}>
          <span className="requisito-marca" aria-hidden="true">
            {r.ok && <Icon name="check" size={12} />}
          </span>
          {r.texto}
          <span className="sr-only">{r.ok ? ' (atendido)' : ' (pendente)'}</span>
        </li>
      ))}
      {senhaLongaDemais(senha) && (
        <li className="falha">Longa demais: use até 72 caracteres simples (acentos contam em dobro).</li>
      )}
    </ul>
  );
}
