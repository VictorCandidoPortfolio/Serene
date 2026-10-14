import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { auth } from '../api/serene';
import { getToken, setToken, setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Enquanto valida um token salvo, não sabemos se a usuária está logada.
  const [carregando, setCarregando] = useState(Boolean(getToken()));

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (!getToken()) return;
    auth
      .me()
      .then(setUser)
      .catch(logout)
      .finally(() => setCarregando(false));
  }, [logout]);

  /** Guarda o token e carrega a usuária; desfaz tudo se /me falhar. */
  const entrarComToken = useCallback(async (accessToken) => {
    setToken(accessToken);
    try {
      setUser(await auth.me());
    } catch (e) {
      setToken(null);
      throw e;
    }
  }, []);

  // Uma conta com email não confirmado faz o login falhar com
  // ApiError.codigo === 'email_nao_verificado': a tela de login trata isso.
  const login = useCallback(
    async (email, senha) => {
      const { access_token } = await auth.login(email, senha);
      await entrarComToken(access_token);
    },
    [entrarComToken],
  );

  /**
   * Cria a conta. NÃO loga: a conta só entra depois de confirmar o código
   * enviado por email. Devolve os prazos do código (validade e reenvio).
   */
  const register = useCallback((dados) => auth.register(dados), []);

  /** Confirma o email (código + senha); a API já devolve o token, então a usuária entra direto. */
  const verificarEmail = useCallback(
    async (email, codigo, senha) => {
      const { access_token } = await auth.verificarEmail(email, codigo, senha);
      await entrarComToken(access_token);
    },
    [entrarComToken],
  );

  const reenviarCodigo = useCallback((email) => auth.reenviarCodigo(email), []);

  // --- conta logada: cada uma devolve/atualiza a usuária no contexto, para o
  // nome e a foto mudarem na hora em todo o app (barra lateral, início...).
  const atualizarDados = useCallback(async (dados) => {
    const atualizada = await auth.atualizarMe(dados);
    setUser(atualizada);
    return atualizada;
  }, []);

  /**
   * Troca a senha SEM deslogar: a API devolve um token novo (o antigo deixa
   * de valer junto com as sessões dos outros aparelhos) e ele substitui o salvo.
   */
  const trocarSenha = useCallback(async (senhaAtual, novaSenha) => {
    const { access_token } = await auth.trocarSenha(senhaAtual, novaSenha);
    setToken(access_token);
  }, []);

  const enviarFoto = useCallback(async (imagem) => {
    const atualizada = await auth.enviarFoto(imagem);
    setUser(atualizada);
  }, []);

  const removerFoto = useCallback(async () => {
    setUser(await auth.removerFoto());
  }, []);

  const value = useMemo(
    () => ({
      user, carregando, login, register, verificarEmail, reenviarCodigo, logout,
      atualizarDados, trocarSenha, enviarFoto, removerFoto,
    }),
    [user, carregando, login, register, verificarEmail, reenviarCodigo, logout,
      atualizarDados, trocarSenha, enviarFoto, removerFoto],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
