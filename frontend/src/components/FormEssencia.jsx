import { useEffect, useRef, useState } from 'react';
import { essencias } from '../api/serene';
import { useApi } from '../lib/useApi';
import { normalizar } from '../lib/format';
import { Campo, Carregando, Chips, Erro, Grupo } from './ui';

/**
 * Cadastro e edição de essência: SÓ três campos (Nome, Família, Percepção).
 * Nada técnico aparece aqui: o servidor deduz o resto.
 *
 * Reconhecimento pelo nome (só ajuda, nunca impõe): se o nome bate com uma nota
 * da base, a Família e a Percepção já vêm marcadas e continuam editáveis; se é
 * parecido, aparece "Você quis dizer …?" e só aplica ao toque. A escolha da
 * aluna sempre prevalece.
 */
export default function FormEssencia({ essencia = null, onSalva, onClose }) {
  const opcoes = useApi(() => essencias.opcoes());
  const [nome, setNome] = useState(essencia?.nome || '');
  const [familia, setFamilia] = useState(null);
  const [percepcao, setPercepcao] = useState(essencia?.percepcao || null);
  const [notaId, setNotaId] = useState(null);       // nota que a aluna viu e deixou valer
  const [sug, setSug] = useState(null);             // sugestão do servidor para o nome atual
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const nomeOriginal = useRef(essencia?.nome || '');

  // Na edição, marca o chip da família atual (se for uma das opções).
  useEffect(() => {
    if (essencia && opcoes.data && familia === null) {
      // Subfamília (ex.: Floral Branco) é um chip próprio; senão a família.
      const atual = essencia.subfamilia || essencia.familia;
      const f = opcoes.data.familias.find((x) => normalizar(x.nome) === normalizar(atual));
      if (f) setFamilia(f.nome);
    }
  }, [essencia, opcoes.data, familia]);

  // Procura o nome na base enquanto a aluna digita (nada é gravado).
  useEffect(() => {
    const texto = nome.trim();
    if (texto.length < 3 || (essencia && texto === nomeOriginal.current)) {
      setSug(null);
      return undefined;
    }
    const t = setTimeout(async () => {
      try {
        const r = await essencias.sugestaoPorNome(texto);
        setSug(r.encontrada ? r : null);
        if (r.encontrada && r.nivel === 'exata') {
          // Pré-seleciona (visível e editável). Não sobrescreve o que ela já escolheu.
          if (r.familia) setFamilia((atual) => atual ?? r.familia);
          if (r.percepcao) setPercepcao((atual) => atual ?? r.percepcao);
          setNotaId(r.nota_id);
        } else {
          setNotaId(null);
        }
      } catch {
        setSug(null);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [nome, essencia]);

  function aceitarParecida() {
    if (sug.familia) setFamilia(sug.familia);
    if (sug.percepcao) setPercepcao(sug.percepcao);
    setNotaId(sug.nota_id);
  }

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const corpo = { nome: nome.trim(), familia, percepcao };
      if (notaId) corpo.aceitou_nota_id = notaId;
      const resp = essencia ? await essencias.atualizar(essencia.id, corpo) : await essencias.criar(corpo);
      onSalva(resp);
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  if (opcoes.loading && !opcoes.data) return <Carregando />;
  const pronto = nome.trim().length >= 2 && familia && percepcao;
  const rotuloPerc = Object.fromEntries((opcoes.data?.percepcoes || []).map((p) => [p.chave, p.nome]));
  const nomePerc = (chave) => rotuloPerc[chave] || chave;

  return (
    <form className="form" onSubmit={salvar}>
      <Campo rotulo="Nome">
        <input
          autoFocus
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Ex: Bergamota"
          maxLength={100}
          required
        />
      </Campo>

      {sug?.nivel === 'exata' && (
        <small className="texto-suave">
          Reconhecemos {sug.nota_nome}
          {sug.familia && sug.percepcao ? `: sugerimos ${sug.familia} e ${nomePerc(sug.percepcao)}` : ''}. Pode mudar se quiser.
        </small>
      )}
      {sug?.nivel === 'parecida' && (
        <button type="button" className="sugestao" onClick={aceitarParecida}>
          <span className="item-texto">
            <strong>Você quis dizer {sug.nota_nome}?</strong>
            {sug.familia && sug.percepcao && <small>{sug.familia} · {nomePerc(sug.percepcao)}</small>}
          </span>
        </button>
      )}
      {sug?.aviso_educativo && <small className="texto-suave">{sug.aviso_educativo}</small>}

      <Grupo rotulo="Família">
        <small className="texto-suave">
          A família de cheiro que mais combina. Ex.: Bergamota é Cítrico, Baunilha é Gourmand.
        </small>
        <Chips
          opcoes={(opcoes.data?.familias || []).map((f) => ({ chave: f.nome, nome: f.nome }))}
          valor={familia}
          onChange={(v) => v && setFamilia(v)}
        />
      </Grupo>

      <Grupo rotulo="Percepção">
        <small className="texto-suave">
          Fria refresca (cítricos, ervas). Quente aquece e envolve (baunilha, madeiras). Neutra fica no meio.
        </small>
        <Chips
          opcoes={(opcoes.data?.percepcoes || []).map((p) => ({ chave: p.chave, nome: p.nome }))}
          valor={percepcao}
          onChange={(v) => v && setPercepcao(v)}
        />
      </Grupo>

      <Erro erro={erro || opcoes.error} />
      <button type="submit" className="btn btn-primario" disabled={!pronto || enviando}>
        {enviando ? 'Salvando…' : essencia ? 'Salvar' : 'Cadastrar'}
      </button>
      {onClose && (
        <button type="button" className="btn btn-contorno" onClick={onClose}>
          Cancelar
        </button>
      )}
    </form>
  );
}
