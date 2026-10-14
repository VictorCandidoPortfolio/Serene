import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import Illustration from '../components/Illustration';
import { Campo, Erro } from '../components/ui';
import RequisitosSenha from '../components/RequisitosSenha';
import { senhaForte } from '../lib/senha';
import RedefinirSenha from './RedefinirSenha';
import VerificarEmail from './VerificarEmail';

export default function Login() {
  const { login, register } = useAuth();
  const [modo, setModo] = useState('entrar');
  const [form, setForm] = useState({ nome: '', email: '', senha: '' });
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);
  // Conta criada (ou encontrada) aguardando o código: { email, senha, expiraMinutos, reenvioEm, aviso }.
  const [pendente, setPendente] = useState(null);
  const [esqueci, setEsqueci] = useState(false);

  const cadastro = modo === 'cadastrar';
  // Editar qualquer campo apaga o erro anterior: antes, "a senha não atende
  // aos requisitos" continuava na tela mesmo depois de a senha ficar válida.
  const set = (campo) => (e) => {
    setForm({ ...form, [campo]: e.target.value });
    setErro(null);
  };

  async function enviar(e) {
    e.preventDefault();
    setErro(null);
    const email = form.email.trim();
    if (cadastro && !senhaForte(form.senha)) {
      setErro(new Error('A senha ainda não atende a todos os requisitos.'));
      return;
    }
    setEnviando(true);
    try {
      if (cadastro) {
        const r = await register({ nome: form.nome.trim(), email, senha: form.senha });
        setPendente({
          email: r.email,
          senha: form.senha,
          expiraMinutos: r.codigo_expira_minutos,
          reenvioEm: r.reenvio_em_segundos,
        });
      } else {
        await login(email, form.senha);
      }
    } catch (err) {
      // Login de conta pendente (403): a senha já foi conferida pela API, então
      // leva direto à tela do código (que precisa dela para confirmar).
      if (err.codigo === 'email_nao_verificado') {
        setPendente({ email: email.toLowerCase(), senha: form.senha, aviso: err.message });
      } else {
        setErro(err);
      }
    } finally {
      setEnviando(false);
    }
  }

  if (esqueci) {
    return (
      <RedefinirSenha
        emailInicial={form.email.trim()}
        onVoltar={() => {
          setEsqueci(false);
          setModo('entrar');
          setForm((f) => ({ ...f, senha: '' }));
        }}
      />
    );
  }

  if (pendente) {
    return (
      <VerificarEmail
        {...pendente}
        onVoltar={() => {
          setPendente(null);
          setModo('entrar');
          setForm((f) => ({ ...f, senha: '' }));
        }}
      />
    );
  }

  return (
    <div className="tela tela-login">
      <Illustration altura={250} />
      <form className="cartao-sobreposto" onSubmit={enviar}>
        <p className="marca">Sérené</p>
        <h1 className="titulo-centro">{cadastro ? 'Criar conta' : 'Entrar'}</h1>
        <p className="subtitulo-centro">Seu mapa olfativo, do repertório ao acorde.</p>

        {cadastro && (
          <Campo rotulo="Nome">
            <input value={form.nome} onChange={set('nome')} autoComplete="name" required />
          </Campo>
        )}
        <Campo rotulo="Email">
          <input type="email" value={form.email} onChange={set('email')} autoComplete="email" required />
        </Campo>
        <Campo rotulo="Senha">
          <input
            type="password"
            value={form.senha}
            onChange={set('senha')}
            autoComplete={cadastro ? 'new-password' : 'current-password'}
            minLength={cadastro ? 8 : undefined}
            maxLength={72}
            aria-describedby={cadastro ? 'requisitos-senha' : undefined}
            required
          />
        </Campo>
        {cadastro && <RequisitosSenha senha={form.senha} />}
        {!cadastro && (
          <button type="button" className="link link-esqueci" onClick={() => setEsqueci(true)}>
            Esqueci minha senha
          </button>
        )}

        <Erro erro={erro} />

        <div className="botoes-duplos">
          <button
            type="button"
            className="btn btn-contorno"
            onClick={() => {
              setModo(cadastro ? 'entrar' : 'cadastrar');
              setErro(null);
            }}
          >
            {cadastro ? 'Já tenho conta' : 'Criar conta'}
          </button>
          <button type="submit" className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Aguarde…' : cadastro ? 'Cadastrar' : 'Entrar'}
          </button>
        </div>
      </form>
    </div>
  );
}
