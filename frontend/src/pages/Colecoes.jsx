import { useState } from 'react';
import { Link } from 'react-router-dom';
import { colecoes, criacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import Icon from '../components/Icon';
import { useConfirmar } from '../components/Confirmar';
import Sheet from '../components/Sheet';
import { Cabecalho } from '../components/Layout';
import { Campo, Carregando, Eixos, Erro, Pill, Vazio } from '../components/ui';

export default function Colecoes() {
  const confirmar = useConfirmar();
  const lista = useApi(() => colecoes.listar());
  const aprovadas = useApi(() => criacoes.listar().then((cs) => cs.filter((c) => c.status === 'aprovada')));
  const [nova, setNova] = useState(false);
  const [editando, setEditando] = useState(null);
  const [erro, setErro] = useState(null);

  async function executar(acao) {
    setErro(null);
    try {
      await acao();
      lista.reload();
    } catch (err) {
      setErro(err);
    }
  }

  return (
    <div className="pagina">
      <Cabecalho titulo="Coleções">
        <button className="icone-btn destaque" onClick={() => setNova(true)} aria-label="Nova coleção">
          <Icon name="plus" />
        </button>
      </Cabecalho>

      <Erro erro={erro || lista.error} onRetry={lista.error ? lista.reload : undefined} />
      {lista.loading && !lista.data ? (
        <Carregando />
      ) : !lista.data?.length ? (
        <Vazio titulo="Nenhuma coleção ainda">Agrupe criações aprovadas em uma linha de perfumes.</Vazio>
      ) : (
        <ul className="cartoes grade-desktop">
          {lista.data.map((col) => {
            const fora = (aprovadas.data || []).filter((c) => !col.itens.some((i) => i.criacao_id === c.id));
            return (
              <li key={col.id} className="cartao">
                <div className="secao-cabeca">
                  <span className="item-texto">
                    <strong>{col.nome}</strong>
                    {col.descricao && <small>{col.descricao}</small>}
                  </span>
                  <button className="icone-btn" aria-label={`Editar ${col.nome}`} onClick={() => setEditando(col)}>
                    <Icon name="edit" size={18} />
                  </button>
                  <button
                    className="icone-btn"
                    aria-label={`Excluir ${col.nome}`}
                    onClick={async () =>
                      (await confirmar(`A coleção “${col.nome}” será excluída. As criações continuam existindo.`, { titulo: 'Excluir coleção', botao: 'Excluir' })) &&
                      executar(() => colecoes.apagar(col.id))
                    }
                  >
                    <Icon name="trash" size={18} />
                  </button>
                </div>

                {col.itens.length ? (
                  <ul className="linhas">
                    {col.itens.map((i, pos) => (
                      <li key={i.criacao_id}>
                        <span className="item-colecao">
                          <span className="ordem">{pos + 1}</span>
                          <Link to={`/criacoes/${i.criacao_id}`}>{i.nome}</Link>
                        </span>
                        <span className="acoes-linha">
                          <button
                            className="icone-btn pequeno"
                            disabled={pos === 0}
                            onClick={() => executar(() => colecoes.reordenar(col.id, mover(col.itens, pos, -1)))}
                            aria-label={`Subir ${i.nome}`}
                          >
                            <Icon name="up" size={16} />
                          </button>
                          <button
                            className="icone-btn pequeno"
                            disabled={pos === col.itens.length - 1}
                            onClick={() => executar(() => colecoes.reordenar(col.id, mover(col.itens, pos, 1)))}
                            aria-label={`Descer ${i.nome}`}
                          >
                            <Icon name="down" size={16} />
                          </button>
                          <button
                            className="link"
                            onClick={() => executar(() => colecoes.removerCriacao(col.id, i.criacao_id))}
                          >
                            remover
                          </button>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="texto-suave">Vazia.</p>
                )}
                <IdentidadeColecao identidade={col.identidade_geral} />

                {fora.length > 0 ? (
                  <select
                    value=""
                    onChange={(e) => e.target.value && executar(() => colecoes.adicionarCriacao(col.id, Number(e.target.value)))}
                    aria-label="Adicionar criação"
                  >
                    <option value="">+ Adicionar criação aprovada</option>
                    {fora.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nome}
                      </option>
                    ))}
                  </select>
                ) : (
                  <small className="texto-suave">Só criações com status “Aprovada” entram em coleções.</small>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {editando && (
        <EditarColecao
          colecao={editando}
          onClose={() => setEditando(null)}
          onSalva={() => {
            setEditando(null);
            lista.reload();
          }}
        />
      )}
      {nova && (
        <NovaColecao
          onClose={() => setNova(false)}
          onCriada={() => {
            setNova(false);
            lista.reload();
          }}
        />
      )}
    </div>
  );
}

function NovaColecao({ onClose, onCriada }) {
  const [form, setForm] = useState({ nome: '', descricao: '' });
  const [erro, setErro] = useState(null);

  async function salvar(e) {
    e.preventDefault();
    try {
      await colecoes.criar({ nome: form.nome.trim(), descricao: form.descricao.trim() || null });
      onCriada();
    } catch (err) {
      setErro(err);
    }
  }

  return (
    <Sheet titulo="Nova coleção" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Campo rotulo="Nome">
          <input autoFocus value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required />
        </Campo>
        <Campo rotulo="Descrição (opcional)">
          <textarea rows={2} value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
        </Campo>
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primario">Criar</button>
        </div>
      </form>
    </Sheet>
  );
}


/** Nova ordem com o item da posição `pos` trocado com o vizinho (`passo` = −1 sobe, +1 desce). */
function mover(itens, pos, passo) {
  const ids = itens.map((i) => i.criacao_id);
  [ids[pos], ids[pos + passo]] = [ids[pos + passo], ids[pos]];
  return ids;
}

/** Identidade geral da linha: média dos acordes atuais das criações. */
function IdentidadeColecao({ identidade: id }) {
  if (!id || !id.criacoes) return null;
  if (!id.criacoes_com_acorde)
    return <p className="texto-suave">A identidade aparece quando as criações tiverem acorde.</p>;
  return (
    <div className="identidade-colecao">
      <span className="rotulo">Identidade da linha ({id.criacoes_com_acorde} de {id.criacoes} com acorde)</span>
      <Eixos vetor={id.vetor_medio} />
      {(id.familias.length > 0 || id.territorios.length > 0) && (
        <div className="chips">
          {id.familias.map((f) => (
            <Pill key={f}>{f}</Pill>
          ))}
          {id.territorios.map((t) => (
            <Pill key={t.chave} tom="amarelo">{t.nome}</Pill>
          ))}
        </div>
      )}
    </div>
  );
}

function EditarColecao({ colecao, onClose, onSalva }) {
  const [form, setForm] = useState({ nome: colecao.nome, descricao: colecao.descricao || '' });
  const [erro, setErro] = useState(null);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    try {
      await colecoes.atualizar(colecao.id, { nome: form.nome.trim(), descricao: form.descricao.trim() || null });
      onSalva();
    } catch (err) {
      setErro(err);
    }
  }

  return (
    <Sheet titulo="Editar coleção" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Campo rotulo="Nome">
          <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required />
        </Campo>
        <Campo rotulo="Descrição">
          <textarea rows={3} value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
        </Campo>
        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button type="button" className="btn btn-contorno" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primario">Salvar</button>
        </div>
      </form>
    </Sheet>
  );
}
