import { useEffect, useState } from 'react';
import { acordes, formulacoes } from '../api/serene';
import { useApi } from '../lib/useApi';
import FormulaTabela from './FormulaTabela';
import Sheet from './Sheet';
import { Campo, Chips, Erro, Grupo } from './ui';

/**
 * Fórmula de uma versão do acorde: mostra a gravada na versão e permite
 * editá-la (produto, concentração, volume, proporções manuais). Editar cria
 * uma NOVA versão do acorde (versões nunca são sobrescritas).
 */
export default function FormulaDaVersao({ acorde, criacaoId, onNovaVersao }) {
  const [editando, setEditando] = useState(false);
  const f = acorde.formulacao;
  const resultado = f?.resultado;

  return (
    <section className="cartao">
      <div className="secao-cabeca">
        <h3 className="secao-titulo">Formulação</h3>
        <button className="btn btn-pequeno btn-contorno" onClick={() => setEditando(true)}>
          {f ? 'Editar fórmula' : 'Adicionar fórmula'}
        </button>
      </div>
      {!f && <p className="texto-suave">Esta versão ainda não tem fórmula quantitativa.</p>}
      {resultado && !resultado.valido && (
        <>
          <p className="texto-suave">A fórmula desta versão deixou de ser válida com as essências atuais:</p>
          {resultado.erros.map((m) => <p key={m} className="aviso">{m}</p>)}
        </>
      )}
      {resultado?.valido && (
        <>
          <FormulaTabela formulacao={resultado} titulo="Fórmula desta versão" />
          {[...new Set(resultado.avisos)].map((a) => <p key={a} className="aviso">{a}</p>)}
        </>
      )}
      {editando && (
        <EditarFormula
          acorde={acorde}
          criacaoId={criacaoId}
          onClose={() => setEditando(false)}
          onSalva={() => {
            setEditando(false);
            onNovaVersao();
          }}
        />
      )}
    </section>
  );
}

function EditarFormula({ acorde, criacaoId, onClose, onSalva }) {
  const produtos = useApi(() => formulacoes.produtos());
  const atual = acorde.formulacao?.pedido;
  const [produto, setProduto] = useState(atual?.produto || null);
  const [conc, setConc] = useState(atual?.concentracao_pct ?? null);
  const [volume, setVolume] = useState(String(atual?.volume_ml ?? 100));
  const [manual, setManual] = useState(Boolean(atual?.proporcoes_pct));
  const [partes, setPartes] = useState(() => {
    const ja = atual?.proporcoes_pct;
    const iguais = 100 / acorde.itens.length;
    return Object.fromEntries(acorde.itens.map((i) => [i.essencia_id, String(ja?.[i.essencia_id] ?? iguais.toFixed(2))]));
  });
  const [motivo, setMotivo] = useState('');
  const [erro, setErro] = useState(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!produto && produtos.data?.length) setProduto(produtos.data[0].chave);
  }, [produtos.data, produto]);
  const p = produtos.data?.find((x) => x.chave === produto);
  const soma = Object.values(partes).reduce((s, v) => s + (Number(String(v).replace(',', '.')) || 0), 0);
  const somaOk = !manual || Math.abs(soma - 100) <= 0.01;

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setSalvando(true);
    try {
      const formulacao = {
        produto,
        concentracao_pct: conc,
        volume_ml: Number(volume.replace(',', '.')),
        ...(manual
          ? { proporcoes_pct: Object.fromEntries(Object.entries(partes).map(([k, v]) => [k, Number(String(v).replace(',', '.'))])) }
          : {}),
      };
      await acordes.criar(
        criacaoId,
        acorde.itens.map((i) => ({ essencia_id: i.essencia_id, peso: i.peso })),
        motivo.trim() || 'Fórmula editada',
        formulacao,
      );
      onSalva();
    } catch (err) {
      setErro(err);
      setSalvando(false);
    }
  }

  return (
    <Sheet titulo="Editar fórmula" onClose={onClose}>
      <form className="form" onSubmit={salvar}>
        <Grupo rotulo="Produto">
          <Chips
            opcoes={(produtos.data || []).map((x) => ({ chave: x.chave, nome: x.nome.toUpperCase() }))}
            valor={produto}
            onChange={(v) => {
              if (v) {
                setProduto(v);
                setConc(null);
              }
            }}
          />
        </Grupo>
        {p && (
          <Grupo rotulo="Concentração">
            <Chips opcoes={p.concentracoes.map((c) => ({ chave: c, nome: `${c}%` }))} valor={conc} onChange={setConc} />
          </Grupo>
        )}
        <Campo rotulo="Volume final (ml)">
          <input inputMode="decimal" value={volume} onChange={(e) => setVolume(e.target.value)} required />
        </Campo>

        <label className="campo-check">
          <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />
          <span>Definir as proporções manualmente</span>
        </label>
        {manual && (
          <>
            {acorde.itens.map((i) => (
              <Campo key={i.essencia_id} rotulo={`${i.nome} (% do concentrado)`}>
                <input
                  inputMode="decimal"
                  value={partes[i.essencia_id]}
                  onChange={(e) => setPartes({ ...partes, [i.essencia_id]: e.target.value })}
                />
              </Campo>
            ))}
            <small className={somaOk ? 'texto-suave' : 'aviso'}>Soma: {soma.toFixed(2).replace('.', ',')} % (precisa ser 100 %)</small>
          </>
        )}

        <Campo rotulo="O que mudou (opcional)">
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={300} />
        </Campo>
        <Erro erro={erro} />
        <button className="btn btn-primario" disabled={salvando || !conc || !somaOk}>
          {salvando ? 'Salvando…' : 'Salvar como nova versão'}
        </button>
      </form>
    </Sheet>
  );
}
