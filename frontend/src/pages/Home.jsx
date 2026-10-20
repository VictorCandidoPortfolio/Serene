import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useSair } from '../auth/useSair';
import FotoPerfil from '../components/FotoPerfil';
import { conhecimento, criacoes, essencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { STATUS, data, normalizar } from '../lib/format';
import Gauge from '../components/Gauge';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import { Avatar, Carregando, Erro, Pill, Vazio } from '../components/ui';

export default function Home() {
  const { user } = useAuth();
  const sair = useSair();
  const navigate = useNavigate();
  const { data: dados, error, loading, reload } = useApi(() =>
    Promise.all([essencias.listar(), criacoes.listar(), conhecimento.familias()]).then(
      ([ess, cri, fam]) => ({ ess, cri, fam }),
    ),
  );

  const primeiroNome = user?.nome?.split(' ')[0];

  return (
    <div className="pagina">
      <Cabecalho
        titulo={`Olá, ${primeiroNome}`}
        voltar={
          <Link to="/conta" className="home-avatar" aria-label="Minha conta">
            <FotoPerfil user={user} tamanho={44} />
          </Link>
        }
      >
        <Link className="icone-btn" to="/essencias?aba=lacunas" aria-label="Lacunas do repertório">
          <Icon name="bell" />
        </Link>
        <button className="icone-btn so-celular" onClick={sair} aria-label="Sair">
          <Icon name="logout" />
        </button>
      </Cabecalho>

      <Erro erro={error} onRetry={reload} />
      {loading && !dados ? <Carregando /> : dados && <Painel {...dados} navigate={navigate} />}
    </div>
  );
}

function Painel({ ess, cri, fam, navigate }) {
  // Cobertura = famílias raiz da base de conhecimento que têm ao menos uma essência no repertório.
  const raizes = fam.filter((f) => f.parent_id === null);
  const presentes = new Set(ess.map((e) => normalizar(e.familia)));
  const cobertas = raizes.filter((f) => {
    const filhas = fam.filter((x) => x.parent_id === f.id).map((x) => normalizar(x.nome));
    // "Aquático/Marinho" também conta quando a essência diz só "Aquático" ou "Marinho".
    const nomes = [f.nome, ...f.nome.split('/')].map(normalizar);
    return nomes.some((n) => presentes.has(n)) || filhas.some((n) => presentes.has(n));
  });
  const cobertura = raizes.length ? cobertas.length / raizes.length : 0;
  const aprovadas = cri.filter((c) => c.status === 'aprovada').length;
  const recentes = [...cri].sort((a, b) => (b.atualizado_em || '').localeCompare(a.atualizado_em || '')).slice(0, 4);

  return (
    <div className="home-grade">
      <section className="saldo home-saldo">
        <span className="rotulo">Seu repertório</span>
        <div className="saldo-numero">
          <sup>✦</sup>
          {ess.length}
          <span className="saldo-unidade">{ess.length === 1 ? 'essência' : 'essências'}</span>
        </div>
        <div className="botoes-duplos">
          <button className="btn btn-primario" onClick={() => navigate('/essencias?nova=1')}>
            Nova essência
          </button>
          <button className="btn btn-primario" onClick={() => navigate('/criacoes/laboratorio')}>
            ✨ Criar com o laboratório
          </button>
        </div>
      </section>

      <section className="cartao-amarelo home-cobertura">
        <h2>Cobertura olfativa</h2>
        <Gauge valor={cobertura} rotulo="Famílias" detalhe={`(${cobertas.length} de ${raizes.length})`} />
        <div className="cartao-rodape">
          <div>
            <strong>Criações</strong>
            <small>{cri.length} no total</small>
          </div>
          <div className="direita">
            <strong>{aprovadas}</strong>
            <small>Aprovadas</small>
          </div>
        </div>
      </section>

      <section className="home-recentes">
        <h3 className="secao-titulo">Últimas criações</h3>
        {recentes.length === 0 ? (
          <Vazio titulo="Nenhuma criação ainda">Cadastre algumas essências e comece sua primeira criação.</Vazio>
        ) : (
          <ul className="lista">
            {recentes.map((c) => (
              <li key={c.id}>
                <Link to={`/criacoes/${c.id}`} className="item">
                  <Avatar>
                    <Icon name="spark" size={20} />
                  </Avatar>
                  <span className="item-texto">
                    <strong>{c.nome}</strong>
                    <small>{data(c.atualizado_em)}</small>
                  </span>
                  <Pill tom={c.status === 'aprovada' ? 'verde' : 'lilac'}>{STATUS[c.status] || c.status}</Pill>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
