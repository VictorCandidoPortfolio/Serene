import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { conhecimento, criacoes, perfis, referencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { STATUS, capitalizar, data } from '../lib/format';
import Icon from '../components/Icon';
import Sheet from '../components/Sheet';
import { Cabecalho } from '../components/Layout';
import { Avatar, Campo, Carregando, Chips, Erro, Grupo, Pill, Vazio } from '../components/ui';

// De onde vem a direção da criação ("criador de fragrâncias").
const ORIGENS = [
  { chave: 'territorio', nome: 'Território' },
  { chave: 'perfil', nome: 'Perfil' },
  { chave: 'referencia', nome: 'Referência' },
  { chave: 'nenhuma', nome: 'Livre' },
];

export default function Criacoes() {
  const [params, setParams] = useSearchParams();
  const { data: lista, error, loading, reload } = useApi(() => criacoes.listar());
  const novaAberta = params.get('nova') === '1';
  const fecharNova = () => setParams({}, { replace: true });

  return (
    <div className="pagina">
      <Cabecalho titulo="Criações">
        <button className="icone-btn destaque" onClick={() => setParams({ nova: '1' })} aria-label="Nova criação">
          <Icon name="plus" />
        </button>
      </Cabecalho>

      <Erro erro={error} onRetry={reload} />
      {loading && !lista ? (
        <Carregando />
      ) : lista?.length === 0 ? (
        <Vazio titulo="Nenhuma criação ainda">
          Uma criação reúne as versões de acorde e os testes de uma ideia.{' '}
          <button className="link" onClick={() => setParams({ nova: '1' })}>
            Começar agora
          </button>
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

      {novaAberta && <NovaCriacao onClose={fecharNova} />}
    </div>
  );
}

function NovaCriacao({ onClose }) {
  const navigate = useNavigate();
  const lista = useApi(() => perfis.listar());
  const refs = useApi(() => referencias.listar());
  const opcoes = useApi(() =>
    Promise.all([conhecimento.territorios(), conhecimento.publicos(), conhecimento.regras('emocao')]).then(
      ([t, p, e]) => ({
        territorios: t.map((x) => ({ chave: x.chave, nome: x.nome, dica: x.descricao_curta })),
        publicos: p.map((x) => ({ chave: x.chave, nome: x.nome, dica: x.descricao })),
        emocoes: e.map((x) => ({ chave: x.chave, nome: capitalizar(x.chave), dica: x.descricao })),
      }),
    ),
  );
  const [origem, setOrigem] = useState('territorio');
  const [intencao, setIntencao] = useState({ territorios: [], emocoes: [], publico: null });
  const [form, setForm] = useState({ nome: '', objetivo: '', perfil_id: '', referencia_id: '' });
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const corpo = { nome: form.nome.trim(), objetivo: form.objetivo.trim() || null };
      if (origem === 'perfil' && form.perfil_id) corpo.perfil_id = Number(form.perfil_id);
      if (origem === 'referencia' && form.referencia_id) corpo.referencia_id = Number(form.referencia_id);
      if (origem === 'territorio' && (intencao.territorios.length || intencao.emocoes.length || intencao.publico)) {
        corpo.intencao = { territorios: intencao.territorios, emocoes: intencao.emocoes };
        if (intencao.publico) corpo.intencao.publico = intencao.publico;
      }
      const nova = await criacoes.criar(corpo);
      navigate(`/criacoes/${nova.id}`);
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  return (
    <Sheet titulo="Nova criação" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Campo rotulo="Nome">
          <input autoFocus value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required />
        </Campo>
        <Campo rotulo="Objetivo (opcional)">
          <textarea
            rows={2}
            value={form.objetivo}
            onChange={(e) => setForm({ ...form, objetivo: e.target.value })}
            placeholder="Ex.: um floral leve para o dia a dia"
          />
        </Campo>
        <Grupo rotulo="De onde vem a direção?">
          <div className="segmentos">
            {ORIGENS.map((o) => (
              <button key={o.chave} type="button" className={origem === o.chave ? 'ativo' : ''} onClick={() => setOrigem(o.chave)}>
                {o.nome}
              </button>
            ))}
          </div>
        </Grupo>
        {origem === 'territorio' && opcoes.data && (
          <>
            <Grupo rotulo="Que território a fragrância deve transmitir?">
              <Chips multiplo opcoes={opcoes.data.territorios} valor={intencao.territorios} onChange={(v) => setIntencao({ ...intencao, territorios: v })} />
            </Grupo>
            <Grupo rotulo="Emoções (opcional)">
              <Chips multiplo opcoes={opcoes.data.emocoes} valor={intencao.emocoes} onChange={(v) => setIntencao({ ...intencao, emocoes: v })} />
            </Grupo>
            <Grupo rotulo="Público (opcional)">
              <Chips opcoes={opcoes.data.publicos} valor={intencao.publico} onChange={(v) => setIntencao({ ...intencao, publico: v })} />
            </Grupo>
          </>
        )}
        {origem === 'perfil' && (
          <Campo rotulo="Perfil olfativo" dica="O perfil define a direção: o vetor-alvo que o acorde deve buscar.">
            <select value={form.perfil_id} onChange={(e) => setForm({ ...form, perfil_id: e.target.value })}>
              <option value="">Escolha um perfil</option>
              {lista.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {nomeDoPerfil(p)}
                </option>
              ))}
            </select>
          </Campo>
        )}
        {origem === 'referencia' && (
          <Campo rotulo="Perfume de referência" dica="A direção é estimada pelas notas conhecidas dele. Ele não vira estoque.">
            <select value={form.referencia_id} onChange={(e) => setForm({ ...form, referencia_id: e.target.value })}>
              <option value="">Escolha uma referência</option>
              {refs.data?.map((r) => (
                <option key={r.id} value={r.id}>{r.nome}</option>
              ))}
            </select>
          </Campo>
        )}
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Criando…' : 'Criar'}
          </button>
        </div>
      </form>
    </Sheet>
  );
}

export function nomeDoPerfil(p) {
  const r = p.respostas || {};
  const partes = [...(r.territorios || []), ...(r.emocoes || [])];
  if (r.publico) partes.push(r.publico);
  return `Perfil #${p.id}${partes.length ? ` · ${partes.join(', ')}` : ''}`;
}
