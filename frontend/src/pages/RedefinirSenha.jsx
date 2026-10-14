import { useEffect, useRef, useState } from 'react';
import { auth } from '../api/serene';
import Illustration from '../components/Illustration';
import RequisitosSenha from '../components/RequisitosSenha';
import { Campo, Erro } from '../components/ui';
import { senhaForte } from '../lib/senha';

const DIGITOS = 4;

/**
 * "Esqueci minha senha" em duas etapas, no mesmo estilo da confirmação de email:
 * 1. a usuária informa o email e a API envia um código de 4 dígitos;
 * 2. ela digita o código e a nova senha. Depois volta ao login (a API não
 *    devolve token: entrar é um passo separado, com a senha nova).
 *
 * @param {object} props
 * @param {string} [props.emailInicial]  email já digitado na tela de login
 * @param {() => void} props.onVoltar    volta para o login
 */
export default function RedefinirSenha({ emailInicial = '', onVoltar }) {
  const [etapa, setEtapa] = useState('email'); // 'email' | 'codigo' | 'pronto'
  const [email, setEmail] = useState(emailInicial);
  const [codigo, setCodigo] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [erro, setErro] = useState(null);
  const [info, setInfo] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [espera, setEspera] = useState(0);
  const codigoRef = useRef(null);

  // Contagem regressiva do botão "Reenviar código".
  useEffect(() => {
    if (espera <= 0) return undefined;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  async function pedirCodigo(e) {
    e?.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      const r = await auth.esqueciSenha(email.trim());
      setInfo(r.mensagem);
      setEspera(r.reenvio_em_segundos);
      setEtapa('codigo');
    } catch (err) {
      setErro(err);
      if (err.retryAfter) setEspera(err.retryAfter);
    } finally {
      setEnviando(false);
    }
  }

  async function redefinir(e) {
    e.preventDefault();
    if (!senhaForte(novaSenha)) {
      setErro(new Error('A senha ainda não atende a todos os requisitos.'));
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      await auth.redefinirSenha(email.trim(), codigo, novaSenha);
      setEtapa('pronto');
    } catch (err) {
      setErro(err);
      setCodigo('');
      codigoRef.current?.focus();
    } finally {
      setEnviando(false);
    }
  }

  if (etapa === 'pronto') {
    return (
      <div className="tela tela-login">
        <Illustration altura={200} />
        <div className="cartao-sobreposto">
          <p className="marca">Sérené</p>
          <h1 className="titulo-centro">Senha redefinida</h1>
          <p className="subtitulo-centro">Pronto! Entre com a sua nova senha.</p>
          <button type="button" className="btn btn-primario" onClick={onVoltar}>
            Ir para o login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="tela tela-login">
      <Illustration altura={200} />
      <form className="cartao-sobreposto" onSubmit={etapa === 'email' ? pedirCodigo : redefinir}>
        <p className="marca">Sérené</p>
        <h1 className="titulo-centro">Redefinir senha</h1>

        {etapa === 'email' ? (
          <>
            <p className="subtitulo-centro">Enviaremos um código de {DIGITOS} dígitos para o seu email.</p>
            <Campo rotulo="Email">
              <input
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setErro(null);
                }}
                autoComplete="email"
                autoFocus
                required
              />
            </Campo>
          </>
        ) : (
          <>
            {info && (
              <p className="aviso" role="status">
                {info}
              </p>
            )}
            <Campo rotulo="Código" dica="Não chegou? Confira a caixa de spam ou peça outro código.">
              <input
                ref={codigoRef}
                className="codigo-input"
                value={codigo}
                onChange={(e) => {
                  setCodigo(e.target.value.replace(/\D/g, '').slice(0, DIGITOS));
                  setErro(null);
                }}
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern={`\\d{${DIGITOS}}`}
                maxLength={DIGITOS}
                placeholder="••••"
                autoFocus
                required
              />
            </Campo>
            <Campo rotulo="Nova senha">
              <input
                type="password"
                value={novaSenha}
                onChange={(e) => {
                  setNovaSenha(e.target.value);
                  setErro(null);
                }}
                autoComplete="new-password"
                minLength={8}
                maxLength={72}
                aria-describedby="requisitos-senha"
                required
              />
            </Campo>
            <RequisitosSenha senha={novaSenha} />
          </>
        )}

        <Erro erro={erro} />

        <button
          type="submit"
          className="btn btn-primario"
          disabled={enviando || (etapa === 'codigo' && codigo.length !== DIGITOS)}
        >
          {enviando ? 'Aguarde…' : etapa === 'email' ? 'Enviar código' : 'Redefinir senha'}
        </button>

        <div className="linha-acoes">
          <button type="button" className="link" onClick={onVoltar}>
            Voltar para o login
          </button>
          {etapa === 'codigo' && (
            <button type="button" className="link" onClick={pedirCodigo} disabled={enviando || espera > 0}>
              {espera > 0 ? `Reenviar em ${espera}s` : 'Reenviar código'}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
