import { useCallback } from 'react';
import { useConfirmar } from '../components/Confirmar';
import { useAuth } from './AuthContext';

/**
 * Botão "Sair" com confirmação. Todo botão de sair do app usa isto, para
 * ninguém perder a sessão por um clique sem querer.
 * (O logout automático por token expirado não pergunta nada: ver AuthContext.)
 */
export function useSair() {
  const { logout } = useAuth();
  const confirmar = useConfirmar();
  return useCallback(async () => {
    const ok = await confirmar('Para voltar, você vai precisar entrar de novo com seu email e senha.', {
      titulo: 'Sair da conta?',
      botao: 'Sair',
    });
    if (ok) logout();
  }, [confirmar, logout]);
}
