import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { testes } from '../api/serene';
import Illustration from '../components/Illustration';
import Keypad from '../components/Keypad';
import { Campo, Chips, Erro, Grupo } from '../components/ui';

const PERCEPCAO = [
  { chave: 'baixa', nome: 'Baixa' },
  { chave: 'media', nome: 'Média' },
  { chave: 'alta', nome: 'Alta' },
];

/** Tela no formato "Top Up": ilustração amarela em cima e a nota digitada no teclado. */
export default function RegistrarTeste() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const acordeId = params.get('acorde');

  const [nota, setNota] = useState(null);
  const [intensidade, setIntensidade] = useState(null);
  const [persistencia, setPersistencia] = useState(null);
  const [resultado, setResultado] = useState('');
  const [bom, setBom] = useState('');
  const [mudar, setMudar] = useState('');
  const [proximo, setProximo] = useState('');
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const voltar = () => navigate(`/criacoes/${id}`);

  async function salvar() {
    setErro(null);
    setEnviando(true);
    try {
      await testes.criar(id, {
        acorde_id: acordeId ? Number(acordeId) : null,
        nota,
        intensidade_percebida: intensidade,
        persistencia_percebida: persistencia,
        resultado_percebido: resultado.trim() || null,
        o_que_ficou_bom: bom.trim() || null,
        o_que_precisa_mudar: mudar.trim() || null,
        proximo_ajuste: proximo.trim() || null,
      });
      voltar();
    } catch (err) {
      setErro(err);
      setEnviando(false);
    }
  }

  return (
    <div className="tela tela-teste">
      <Illustration altura={170} />
      <div className="cartao-sobreposto">
        <h1 className="titulo-centro">Registrar teste</h1>
        <div className="valor-grande">
          <sup>nota</sup>
          {nota ?? 0}
          <sub>/10</sub>
        </div>
        <hr className="traco" />
        <Keypad valor={nota} onChange={setNota} max={10} />

        <div className="form">
          <Grupo rotulo="Intensidade percebida">
            <Chips opcoes={PERCEPCAO} valor={intensidade} onChange={setIntensidade} />
          </Grupo>
          <Grupo rotulo="Persistência percebida">
            <Chips opcoes={PERCEPCAO} valor={persistencia} onChange={setPersistencia} />
          </Grupo>
          <Campo rotulo="Como ficou?">
            <textarea rows={2} value={resultado} onChange={(e) => setResultado(e.target.value)} placeholder="Toque para anotar…" />
          </Campo>
          <Campo rotulo="O que ficou bom?">
            <textarea rows={2} value={bom} onChange={(e) => setBom(e.target.value)} />
          </Campo>
          <Campo rotulo="O que precisa mudar?">
            <textarea rows={2} value={mudar} onChange={(e) => setMudar(e.target.value)} />
          </Campo>
          <Campo rotulo="Próximo ajuste" dica="A direção para a próxima versão (ex.: mais fresco na saída).">
            <textarea rows={2} value={proximo} onChange={(e) => setProximo(e.target.value)} />
          </Campo>
        </div>

        <Erro erro={erro} />
        <div className="botoes-duplos">
          <button className="btn btn-contorno" onClick={voltar}>
            Cancelar
          </button>
          <button className="btn btn-primario" onClick={salvar} disabled={enviando}>
            {enviando ? 'Salvando…' : 'Salvar teste'}
          </button>
        </div>
      </div>
    </div>
  );
}
