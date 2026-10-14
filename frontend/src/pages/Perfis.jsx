import { useEffect, useState } from 'react';
import { conhecimento, perfis, referencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { capitalizar, data } from '../lib/format';
import Icon from '../components/Icon';
import { useConfirmar } from '../components/Confirmar';
import Sheet from '../components/Sheet';
import { Cabecalho } from '../components/Layout';
import { Avatar, Campo, Carregando, Chips, Eixos, Erro, Grupo, Pill, Vazio } from '../components/ui';
import { nomeDoPerfil } from './Criacoes';

export default function Perfis() {
  const lista = useApi(() => perfis.listar());
  const [aberto, setAberto] = useState(null);
  const [novo, setNovo] = useState(false);

  // Abre o perfil mais recente por padrão.
  useEffect(() => {
    if (lista.data?.length && !lista.data.some((p) => p.id === aberto)) setAberto(lista.data[lista.data.length - 1].id);
  }, [lista.data, aberto]);

  const perfil = lista.data?.find((p) => p.id === aberto);

  return (
    <div className="pagina">
      <Cabecalho titulo="Perfis olfativos">
        <button className="icone-btn destaque" onClick={() => setNovo(true)} aria-label="Novo perfil">
          <Icon name="plus" />
        </button>
      </Cabecalho>

      <Erro erro={lista.error} onRetry={lista.reload} />
      {lista.loading && !lista.data ? (
        <Carregando />
      ) : !lista.data?.length ? (
        <Vazio titulo="Nenhum perfil ainda">
          Responda um questionário curto (emoções, territórios, público) e o motor calcula o alvo.{' '}
          <button className="link" onClick={() => setNovo(true)}>
            Criar perfil
          </button>
        </Vazio>
      ) : (
        <>
          <div className="chips rolagem">
            {lista.data.map((p) => (
              <button key={p.id} className={`chip ${p.id === aberto ? 'ativo' : ''}`} onClick={() => setAberto(p.id)}>
                #{p.id}
              </button>
            ))}
          </div>
          {perfil && (
            <DetalhePerfil
              key={perfil.id}
              perfil={perfil}
              onApagado={() => {
                setAberto(null);
                lista.reload();
              }}
            />
          )}
        </>
      )}

      {novo && (
        <NovoPerfil
          onClose={() => setNovo(false)}
          onCriado={(p) => {
            setNovo(false);
            setAberto(p.id);
            lista.reload();
          }}
        />
      )}
    </div>
  );
}

function DetalhePerfil({ perfil, onApagado }) {
  const confirmar = useConfirmar();
  const recs = useApi(() => perfis.recomendacoes(perfil.id), [perfil.id]);
  const alvo = perfil.vetor_alvo;
  const [erro, setErro] = useState(null);

  async function apagar() {
    if (!(await confirmar('Este perfil será excluído. As criações que usaram a direção dele continuam como estão.', { titulo: 'Excluir perfil', botao: 'Excluir' }))) return;
    try {
      await perfis.apagar(perfil.id);
      onApagado();
    } catch (err) {
      setErro(err);
    }
  }

  // "perfil-grade" e "perfil-recs" só existem para o layout no desktop (display: contents no celular).
  return (
    <div className="perfil-grade">
      <section className="cartao-amarelo perfil-alvo">
        <h2>{nomeDoPerfil(perfil).replace(/^Perfil #\d+ · /, '')}</h2>
        <Eixos vetor={alvo?.vetor} />
        {alvo?.vocabulario?.length > 0 && (
          <div className="chips">
            {alvo.vocabulario.map((v) => (
              <Pill key={v} tom="branco">
                {v}
              </Pill>
            ))}
          </div>
        )}
        <div className="cartao-rodape">
          <div>
            <strong>Criado em</strong>
            <small>{data(perfil.criado_em)}</small>
          </div>
          <button className="btn btn-pequeno btn-contorno" onClick={apagar}>
            Excluir
          </button>
        </div>
      </section>
      <div className="perfil-recs">
        <Erro erro={erro} />
        {alvo?.nao_reconhecidos?.length > 0 && (
          <p className="aviso">Respostas sem regra no motor: {alvo.nao_reconhecidos.join(', ')}.</p>
        )}

        <h3 className="secao-titulo">Recomendações do seu repertório</h3>
        <Erro erro={recs.error} onRetry={recs.reload} />
        {recs.loading && !recs.data ? (
          <Carregando />
        ) : (
          recs.data && (
            <>
              {recs.data.avisos.map((a) => (
                <p key={a} className="aviso">
                  {a}
                </p>
              ))}
              <ul className="lista">
                {recs.data.recomendacoes.map((r) => (
                  <li key={r.essencia_id} className="item">
                    <Avatar>{r.score}</Avatar>
                    <span className="item-texto quebra">
                      <strong>{r.nome}</strong>
                      <small>{r.explicacao}</small>
                    </span>
                    <span className="pontuacao">
                      <span style={{ width: `${r.score}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
              {recs.data.nao_avaliadas.length > 0 && (
                <p className="texto-suave">Sem dados para comparar: {recs.data.nao_avaliadas.join(', ')}.</p>
              )}
            </>
          )
        )}
      </div>
    </div>
  );
}

function NovoPerfil({ onClose, onCriado }) {
  const opcoes = useApi(() =>
    Promise.all([
      conhecimento.regras('emocao'),
      conhecimento.regras('preferencia'),
      conhecimento.territorios(),
      conhecimento.publicos(),
    ]).then(([emo, pref, terr, pub]) => ({
      emocoes: emo.map((r) => ({ chave: r.chave, nome: capitalizar(r.chave), dica: r.descricao })),
      preferencias: pref.map((r) => ({ chave: r.chave, nome: capitalizar(r.chave), dica: r.descricao })),
      territorios: terr.map((t) => ({ chave: t.chave, nome: t.nome, dica: t.descricao_curta })),
      publicos: pub.map((p) => ({ chave: p.chave, nome: p.nome, dica: p.descricao })),
    })),
  );
  const refs = useApi(() => referencias.listar());
  const [r, setR] = useState({
    emocoes: [], territorios: [], preferencias: [], publico: null, genero: '',
    intensidade: null, idade: '', referencia_id: '',
  });
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const set = (campo) => (valor) => setR({ ...r, [campo]: valor });

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const respostas = { emocoes: r.emocoes, territorios: r.territorios, preferencias: r.preferencias };
      if (r.publico) respostas.publico = r.publico;
      if (r.genero.trim()) respostas.genero = r.genero.trim();
      if (r.intensidade !== null) respostas.intensidade = r.intensidade;
      if (r.idade) respostas.idade = Number(r.idade);
      if (r.referencia_id) respostas.referencia_id = Number(r.referencia_id);
      onCriado(await perfis.criar(respostas));
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  return (
    <Sheet titulo="Novo perfil" onClose={onClose}>
      {opcoes.loading ? (
        <Carregando />
      ) : (
        <form className="form" onSubmit={salvar}>
          <Erro erro={opcoes.error} onRetry={opcoes.reload} />
          {opcoes.data && (
            <>
              <Grupo rotulo="Que emoções o perfume deve despertar?">
                <Chips multiplo opcoes={opcoes.data.emocoes} valor={r.emocoes} onChange={set('emocoes')} />
              </Grupo>
              <Grupo rotulo="Territórios">
                <Chips multiplo opcoes={opcoes.data.territorios} valor={r.territorios} onChange={set('territorios')} />
              </Grupo>
              <Grupo rotulo="Preferências">
                <Chips multiplo opcoes={opcoes.data.preferencias} valor={r.preferencias} onChange={set('preferencias')} />
              </Grupo>
              <Grupo rotulo="Público">
                <Chips opcoes={opcoes.data.publicos} valor={r.publico} onChange={set('publico')} />
              </Grupo>
            </>
          )}
          <Campo rotulo="Gênero (opcional)" dica="Insumo flexível: nunca exclui famílias.">
            <input value={r.genero} onChange={(e) => set('genero')(e.target.value)} />
          </Campo>
          <div className="eixo-campo">
            <div className="eixo-topo">
              <span>Intensidade desejada</span>
              <span className="eixo-valor">
                {r.intensidade === null ? <small>não importa</small> : r.intensidade}
              </span>
            </div>
            <div className="eixo-entrada">
              <input
                type="range" min={0} max={10} step={1}
                value={r.intensidade ?? 5}
                className={r.intensidade === null ? 'inativo' : ''}
                onChange={(e) => set('intensidade')(Number(e.target.value))}
                aria-label="Intensidade desejada, de discreta (0) a marcante (10)"
              />
              <button type="button" className="link" onClick={() => set('intensidade')(r.intensidade === null ? 5 : null)}>
                {r.intensidade === null ? 'Definir' : 'Não importa'}
              </button>
            </div>
          </div>
          <Campo rotulo="Idade de quem vai usar (opcional)">
            <input type="number" min={0} max={120} value={r.idade} onChange={(e) => set('idade')(e.target.value)} />
          </Campo>
          <Campo rotulo="Perfume de referência (opcional)" dica="Das suas Referências: a direção estimada dele entra no alvo.">
            <select value={r.referencia_id} onChange={(e) => set('referencia_id')(e.target.value)}>
              <option value="">Nenhum</option>
              {refs.data?.map((x) => (
                <option key={x.id} value={x.id}>{x.nome}</option>
              ))}
            </select>
          </Campo>
          <Erro erro={erro} />
          <div className="botoes-duplos">
            <button type="button" className="btn btn-contorno" onClick={onClose}>
              Cancelar
            </button>
            <button className="btn btn-primario" disabled={enviando}>
              {enviando ? 'Calculando…' : 'Calcular alvo'}
            </button>
          </div>
        </form>
      )}
    </Sheet>
  );
}
