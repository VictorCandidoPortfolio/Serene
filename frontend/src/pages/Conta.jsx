import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useSair } from '../auth/useSair';
import { useConfirmar } from '../components/Confirmar';
import FotoPerfil from '../components/FotoPerfil';
import Icon from '../components/Icon';
import { Cabecalho } from '../components/Layout';
import RequisitosSenha from '../components/RequisitosSenha';
import { Campo, Erro } from '../components/ui';
import { prepararFoto } from '../lib/imagem';
import { senhaForte } from '../lib/senha';

/** Minha conta: foto, nome, troca de senha (sem deslogar) e sair. */
export default function Conta() {
  const sair = useSair();

  return (
    <div className="pagina">
      <Cabecalho
        titulo="Minha conta"
        voltar={
          <Link to="/" className="icone-btn so-celular" aria-label="Voltar para o início">
            <Icon name="back" />
          </Link>
        }
      />

      <div className="conta-grade">
        <div className="conta-coluna">
          <SecaoFoto />
          <SecaoDados />
        </div>
        <div className="conta-coluna">
          <SecaoSenha />
          <section className="cartao">
            <span className="rotulo">Sair da conta</span>
            <p className="texto-suave">Encerra a sessão neste aparelho. Seus dados continuam salvos.</p>
            <button className="btn btn-contorno" onClick={sair}>
              <Icon name="logout" size={18} /> Sair
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}

function SecaoFoto() {
  const { user, enviarFoto, removerFoto } = useAuth();
  const confirmar = useConfirmar();
  const entrada = useRef(null);
  const [previa, setPrevia] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);

  async function escolher(e) {
    const arquivo = e.target.files?.[0];
    e.target.value = ''; // permite escolher o mesmo arquivo de novo
    if (!arquivo) return;
    setErro(null);
    setAviso(null);
    try {
      setPrevia(await prepararFoto(arquivo));
    } catch (err) {
      setErro(err);
    }
  }

  async function executar(acao, mensagem) {
    setErro(null);
    setAviso(null);
    setOcupado(true);
    try {
      await acao();
      setPrevia(null);
      setAviso(mensagem);
    } catch (err) {
      setErro(err);
    } finally {
      setOcupado(false);
    }
  }

  async function remover() {
    const ok = await confirmar('Sua foto será apagada e as iniciais do seu nome aparecem no lugar.', {
      titulo: 'Remover foto?',
      botao: 'Remover',
    });
    if (ok) executar(removerFoto, 'Foto removida.');
  }

  return (
    <section className="cartao conta-foto">
      <FotoPerfil user={user} src={previa} tamanho={112} className={previa ? 'previa' : ''} />
      <div className="conta-identidade">
        <strong>{user.nome}</strong>
        <small>{user.email}</small>
      </div>

      <input
        ref={entrada}
        type="file"
        accept="image/*"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={escolher}
      />

      {previa ? (
        <>
          <p className="texto-suave">Assim vai ficar. Salvar?</p>
          <div className="botoes-duplos">
            <button className="btn btn-contorno" onClick={() => setPrevia(null)} disabled={ocupado}>
              Cancelar
            </button>
            <button className="btn btn-primario" onClick={() => executar(() => enviarFoto(previa), 'Foto atualizada.')} disabled={ocupado}>
              {ocupado ? 'Enviando…' : 'Salvar foto'}
            </button>
          </div>
        </>
      ) : (
        <div className={user.foto_url ? 'botoes-duplos' : 'conta-botao-unico'}>
          <button className="btn btn-primario" onClick={() => entrada.current?.click()} disabled={ocupado}>
            {user.foto_url ? 'Trocar foto' : 'Adicionar foto'}
          </button>
          {user.foto_url && (
            <button className="btn btn-contorno" onClick={remover} disabled={ocupado}>
              {ocupado ? 'Removendo…' : 'Remover'}
            </button>
          )}
        </div>
      )}

      {aviso && (
        <p className="aviso" role="status">
          {aviso}
        </p>
      )}
      <Erro erro={erro} />
    </section>
  );
}

function SecaoDados() {
  const { user, atualizarDados } = useAuth();
  const [nome, setNome] = useState(user.nome);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const mudou = nome.trim() !== user.nome && nome.trim() !== '';

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setAviso(null);
    setSalvando(true);
    try {
      const atualizada = await atualizarDados({ nome: nome.trim() });
      setNome(atualizada.nome);
      setAviso('Dados salvos.');
    } catch (err) {
      setErro(err);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form className="cartao form" onSubmit={salvar}>
      <span className="rotulo">Seus dados</span>
      <Campo rotulo="Nome">
        <input
          value={nome}
          onChange={(e) => {
            setNome(e.target.value);
            setAviso(null);
          }}
          autoComplete="name"
          maxLength={120}
          required
        />
      </Campo>
      <Campo rotulo="Email" dica="É com ele que você entra. Não pode ser alterado por aqui.">
        <input value={user.email} readOnly disabled />
      </Campo>
      {aviso && (
        <p className="aviso" role="status">
          {aviso}
        </p>
      )}
      <Erro erro={erro} />
      <button className="btn btn-primario" disabled={!mudou || salvando}>
        {salvando ? 'Salvando…' : 'Salvar'}
      </button>
    </form>
  );
}

function SecaoSenha() {
  const { trocarSenha } = useAuth();
  const vazio = { atual: '', nova: '', confirmacao: '' };
  const [form, setForm] = useState(vazio);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);

  const set = (campo) => (e) => {
    setForm({ ...form, [campo]: e.target.value });
    setErro(null);
    setAviso(null);
  };

  async function salvar(e) {
    e.preventDefault();
    if (!senhaForte(form.nova)) {
      setErro(new Error('A nova senha ainda não atende a todos os requisitos.'));
      return;
    }
    if (form.nova !== form.confirmacao) {
      setErro(new Error('A confirmação não é igual à nova senha.'));
      return;
    }
    setEnviando(true);
    try {
      await trocarSenha(form.atual, form.nova);
      setForm(vazio);
      setAviso('Senha alterada. Esta sessão continua aberta; nos outros aparelhos será preciso entrar de novo.');
    } catch (err) {
      setErro(err);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="cartao form" onSubmit={salvar}>
      <span className="rotulo">Trocar senha</span>
      <Campo rotulo="Senha atual">
        <input type="password" value={form.atual} onChange={set('atual')} autoComplete="current-password" maxLength={72} required />
      </Campo>
      <Campo rotulo="Nova senha">
        <input
          type="password"
          value={form.nova}
          onChange={set('nova')}
          autoComplete="new-password"
          maxLength={72}
          aria-describedby="requisitos-senha"
          required
        />
      </Campo>
      <RequisitosSenha senha={form.nova} />
      <Campo rotulo="Confirme a nova senha">
        <input type="password" value={form.confirmacao} onChange={set('confirmacao')} autoComplete="new-password" maxLength={72} required />
      </Campo>
      {aviso && (
        <p className="aviso" role="status">
          {aviso}
        </p>
      )}
      <Erro erro={erro} />
      <button className="btn btn-primario" disabled={enviando}>
        {enviando ? 'Salvando…' : 'Trocar senha'}
      </button>
    </form>
  );
}
