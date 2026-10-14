import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useSair } from '../auth/useSair';
import FotoPerfil from './FotoPerfil';
import Icon from './Icon';

const ABAS = [
  { to: '/', icone: 'home', nome: 'Início', end: true },
  { to: '/essencias', icone: 'flask', nome: 'Essências' },
  { to: '/criacoes', icone: 'spark', nome: 'Criações' },
  { to: '/perfis', icone: 'compass', nome: 'Perfis' },
  { to: '/colecoes', icone: 'layers', nome: 'Coleções' },
  { to: '/mapa', icone: 'map', nome: 'Mapa' },
];

// Só na barra lateral (no celular, a base de conhecimento abre pelo Mapa).
const EXTRAS = [{ to: '/conhecimento', icone: 'book', nome: 'Conhecimento' }];

/**
 * Moldura das telas logadas. No celular a navegação são as abas de baixo;
 * a partir de 1024px elas somem e a barra lateral aparece (só CSS decide).
 */
export default function Layout() {
  return (
    <div className="tela tela-app">
      <BarraLateral />
      <main className="tela-conteudo">
        <Outlet />
      </main>
      <nav className="abas" aria-label="Navegação principal">
        {ABAS.map((a) => (
          <NavLink key={a.to} to={a.to} end={a.end} className={({ isActive }) => `aba ${isActive ? 'ativa' : ''}`}>
            <Icon name={a.icone} size={21} />
            <span>{a.nome}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function BarraLateral() {
  const { user } = useAuth();
  const sair = useSair();
  const navigate = useNavigate();

  return (
    <aside className="lateral">
      <div className="lateral-marca">
        <span className="lateral-logo" aria-hidden="true">
          <Icon name="flask" size={20} />
        </span>
        Sérené
      </div>

      <nav className="lateral-nav" aria-label="Navegação principal">
        {[...ABAS, ...EXTRAS].map((a) => (
          <NavLink key={a.to} to={a.to} end={a.end} className={({ isActive }) => `lateral-link ${isActive ? 'ativa' : ''}`}>
            <Icon name={a.icone} size={20} />
            {a.nome}
          </NavLink>
        ))}
      </nav>

      <div className="lateral-cartao">
        <strong>Nova ideia?</strong>
        <small>Comece uma criação e monte o primeiro acorde.</small>
        <button className="btn btn-pequeno btn-contorno" onClick={() => navigate('/criacoes?nova=1')}>
          <Icon name="plus" size={16} /> Nova criação
        </button>
      </div>

      <div className="lateral-usuaria">
        <NavLink to="/conta" className={({ isActive }) => `lateral-conta ${isActive ? 'ativa' : ''}`} title="Minha conta">
          <FotoPerfil user={user} tamanho={38} />
          <span className="item-texto">
            <strong>{user?.nome}</strong>
            <small>{user?.email}</small>
          </span>
        </NavLink>
        <button className="icone-btn" onClick={sair} aria-label="Sair">
          <Icon name="logout" size={20} />
        </button>
      </div>
    </aside>
  );
}

/** Cabeçalho de página: título à esquerda, ações à direita (sino/engrenagem na referência). */
export function Cabecalho({ titulo, children, voltar }) {
  return (
    <header className="cabecalho">
      {voltar}
      <h1>{titulo}</h1>
      <div className="cabecalho-acoes">{children}</div>
    </header>
  );
}
