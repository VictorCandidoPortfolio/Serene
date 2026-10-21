import { Link } from 'react-router-dom';
import { criacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import { STATUS, data } from '../lib/format';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import { Avatar, Carregando, Erro, Pill, Vazio } from '../components/ui';

/**
 * Lista de criações. Há UM só caminho para criar: "Criar formulação"
 * (produto, concentração, volume e descrição -> acorde -> fórmula).
 */
export default function Criacoes() {
  const { data: lista, error, loading, reload } = useApi(() => criacoes.listar());

  return (
    <div className="pagina">
      <Cabecalho titulo="Criações" />

      <Link to="/formulacao" className="btn btn-primario">
        ✨ Criar formulação
      </Link>

      <Erro erro={error} onRetry={reload} />
      {loading && !lista ? (
        <Carregando />
      ) : lista?.length === 0 ? (
        <Vazio titulo="Nenhuma criação ainda">
          Uma criação reúne as versões de acorde, a fórmula e os testes de uma ideia. Toque em “Criar formulação” para começar.
        </Vazio>
      ) : (
        <ul className="lista grade-desktop">
          {lista?.map((c) => (
            <li key={c.id}>
              <Link to={`/criacoes/${c.id}`} className="item">
                <Avatar>
                  <Icon name="spark" size={20} />
                </Avatar>
                <span className="item-texto">
                  <strong>{c.nome}</strong>
                  <small>{c.objetivo || data(c.criado_em)}</small>
                </span>
                <Pill tom={c.status === 'aprovada' ? 'verde' : 'lilac'}>{STATUS[c.status] || c.status}</Pill>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Nome legível de um perfil olfativo (usado na tela de Perfis). */

export function nomeDoPerfil(p) {

  const r = p.respostas || {};

  const partes = [...(r.territorios || []), ...(r.emocoes || [])];

  if (r.publico) partes.push(r.publico);

  return `Perfil #${p.id}${partes.length ? ` · ${partes.join(", ")}` : ""}`;

}
