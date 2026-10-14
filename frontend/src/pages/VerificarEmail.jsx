import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import Illustration from '../components/Illustration';
import { Campo, Erro } from '../components/ui';

const DIGITOS = 4;

/**
 * Tela "Confirme seu email": a usuária digita o código de 4 dígitos que a
 * API enviou. Ao acertar, a API já devolve o token e o AuthContext troca para
 * a área logada sozinho.
 *
 * @param {object} props
 * @param {string} props.email            email que recebeu o código
 * @param {string} props.senha            senha digitada no cadastro/login (a API
 *                                        exige código + senha para confirmar)
 * @param {number} [props.expiraMinutos]  validade do código (vem do cadastro)
 * @param {number} [props.reenvioEm]      segundos até poder pedir outro código
 * @param {string} [props.aviso]          mensagem inicial (ex.: veio do login)
 * @param {() => void} props.onVoltar     volta para a tela de login
 */
export default function VerificarEmail({ email, senha, expiraMinutos, reenvioEm = 0, aviso, onVoltar }) {
  const { verificarEmail, reenviarCodigo } = useAuth();
  const [codigo, setCodigo] = useState('');
  const [erro, setErro] = useState(null);
  const [info, setInfo] = useState(aviso || null);
  const [enviando, setEnviando] = useState(false);
  const [reenviando, setReenviando] = useState(false);
  const [espera, setEspera] = useState(reenvioEm);
  const inputRef = useRef(null);
  // Evita dois envios quando o 4º dígito dispara o envio automático e a
  // usuária também aperta Enter.
  const enviandoRef = useRef(false);

  // Contagem regressiva do botão "Reenviar código".
  useEffect(() => {
    if (espera <= 0) return undefined;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  async function confirmar(valor) {
    if (enviandoRef.current || valor.length !== DIGITOS) return;
    enviandoRef.current = true;
    setEnviando(true);
    setErro(null);
    try {
      await verificarEmail(email, valor, senha);
    } catch (err) {
      setErro(err);
      setCodigo('');
      inputRef.current?.focus();
    } finally {
      enviandoRef.current = false;
      setEnviando(false);
    }
  }

  function digitar(e) {
    // Aceita colar "1 2 3 4" ou "Código: 1234": fica só com os dígitos.
    const valor = e.target.value.replace(/\D/g, '').slice(0, DIGITOS);
    setCodigo(valor);
    if (valor.length === DIGITOS) confirmar(valor);
  }

  async function reenviar() {
    setReenviando(true);
    setErro(null);
    setInfo(null);
    try {
      const r = await reenviarCodigo(email);
      setInfo(`Enviamos um novo código para ${email}. O anterior deixou de valer.`);
      setEspera(r.reenvio_em_segundos);
      setCodigo('');
      inputRef.current?.focus();
    } catch (err) {
      setErro(err);
      if (err.retryAfter) setEspera(err.retryAfter);
    } finally {
      setReenviando(false);
    }
  }

  return (
    <div className="tela tela-login">
      <Illustration altura={200} />
      <form
        className="cartao-sobreposto"
        onSubmit={(e) => {
          e.preventDefault();
          confirmar(codigo);
        }}
      >
        <p className="marca">Sérené</p>
        <h1 className="titulo-centro">Confirme seu email</h1>
        <p className="subtitulo-centro">
          Enviamos um código de {DIGITOS} dígitos para <strong>{email}</strong>
          {expiraMinutos ? `. Ele vale por ${expiraMinutos} minutos.` : '.'}
        </p>

        <Campo rotulo="Código" dica="Não chegou? Confira a caixa de spam ou peça outro código.">
          <input
            ref={inputRef}
            className="codigo-input"
            value={codigo}
            onChange={digitar}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern={`\\d{${DIGITOS}}`}
            maxLength={DIGITOS}
            placeholder="••••"
            autoFocus
            required
          />
        </Campo>

        {info && (
          <p className="aviso" role="status">
            {info}
          </p>
        )}
        <Erro erro={erro} />

        <button type="submit" className="btn btn-primario" disabled={enviando || codigo.length !== DIGITOS}>
          {enviando ? 'Confirmando…' : 'Confirmar'}
        </button>

        <div className="linha-acoes">
          <button type="button" className="link" onClick={onVoltar}>
            Voltar para o login
          </button>
          <button type="button" className="link" onClick={reenviar} disabled={reenviando || espera > 0}>
            {espera > 0 ? `Reenviar em ${espera}s` : reenviando ? 'Enviando…' : 'Reenviar código'}
          </button>
        </div>
      </form>
    </div>
  );
}
