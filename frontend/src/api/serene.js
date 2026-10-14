/**
 * Um método por endpoint da API. As páginas só falam com a API por aqui,
 * então uma mudança de rota no backend se corrige num lugar só.
 */
import { request } from './client';

export const auth = {
  register: (dados) => request('/auth/register', { method: 'POST', body: dados }),
  // O login usa o formulário OAuth2 padrão: username = email.
  login: (email, senha) =>
    request('/auth/login', { method: 'POST', form: { username: email, password: senha } }),
  me: () => request('/auth/me'),
  // Confirma o email com o código de 4 dígitos; devolve o token de acesso.
  // A senha vai junto: só quem definiu a senha da conta pode confirmá-la.
  verificarEmail: (email, codigo, senha) =>
    request('/auth/verificar-email', { method: 'POST', body: { email, codigo, senha } }),
  reenviarCodigo: (email) => request('/auth/reenviar-codigo', { method: 'POST', body: { email } }),
  // "Esqueci minha senha": envia o código por email (resposta igual exista ou não a conta).
  esqueciSenha: (email) => request('/auth/esqueci-senha', { method: 'POST', body: { email } }),
  redefinirSenha: (email, codigo, novaSenha) =>
    request('/auth/redefinir-senha', {
      method: 'POST',
      body: { email, codigo, nova_senha: novaSenha },
    }),
  // --- conta logada
  atualizarMe: (dados) => request('/auth/me', { method: 'PUT', body: dados }),
  // Devolve um token novo: a sessão atual continua, as de outros aparelhos caem.
  trocarSenha: (senhaAtual, novaSenha) =>
    request('/auth/me/senha', {
      method: 'POST',
      body: { senha_atual: senhaAtual, nova_senha: novaSenha },
    }),
  // `imagem` é um data URI base64 ("data:image/webp;base64,..."); o backend
  // envia ao Cloudinary e guarda a URL.
  enviarFoto: (imagem) => request('/auth/me/foto', { method: 'PUT', body: { imagem } }),
  removerFoto: () => request('/auth/me/foto', { method: 'DELETE' }),
};

export const essencias = {
  listar: () => request('/essencias'),
  obter: (id) => request(`/essencias/${id}`),
  criar: (dados) => request('/essencias', { method: 'POST', body: dados }),
  atualizar: (id, dados) => request(`/essencias/${id}`, { method: 'PUT', body: dados }),
  apagar: (id) => request(`/essencias/${id}`, { method: 'DELETE' }),
  lacunas: () => request('/essencias/lacunas'),
  // Analisa como as essências trabalham juntas, sem gravar acorde.
  compatibilidade: (ids) =>
    request('/essencias/compatibilidade', { method: 'POST', body: { essencia_ids: ids } }),
  sugestoes: (nome) => request('/essencias/sugestao-classificacao', { params: { nome } }),
};

export const referencias = {
  listar: () => request('/referencias'),
  criar: (dados) => request('/referencias', { method: 'POST', body: dados }),
  atualizar: (id, dados) => request(`/referencias/${id}`, { method: 'PUT', body: dados }),
  apagar: (id) => request(`/referencias/${id}`, { method: 'DELETE' }),
  // Direção estimada, famílias que a aluna tem/não tem e essências dela nessa direção.
  caminhos: (id) => request(`/referencias/${id}/caminhos`),
};

export const perfis = {
  listar: () => request('/perfis'),
  obter: (id) => request(`/perfis/${id}`),
  criar: (respostas) => request('/perfis', { method: 'POST', body: { respostas } }),
  apagar: (id) => request(`/perfis/${id}`, { method: 'DELETE' }),
  recomendacoes: (id) => request(`/perfis/${id}/recomendacoes`),
};

export const criacoes = {
  listar: () => request('/criacoes'),
  obter: (id) => request(`/criacoes/${id}`),
  criar: (dados) => request('/criacoes', { method: 'POST', body: dados }),
  atualizar: (id, dados) => request(`/criacoes/${id}`, { method: 'PUT', body: dados }),
  apagar: (id) => request(`/criacoes/${id}`, { method: 'DELETE' }),
  recomendacoes: (id) => request(`/criacoes/${id}/recomendacoes`),
};

export const acordes = {
  listar: (criacaoId) => request(`/criacoes/${criacaoId}/acordes`),
  // `motivo` (opcional): o que mudou nesta versão e por quê.
  criar: (criacaoId, itens, motivo) =>
    request(`/criacoes/${criacaoId}/acordes`, { method: 'POST', body: { itens, motivo: motivo || null } }),
  identidade: (criacaoId, acordeId) => request(`/criacoes/${criacaoId}/acordes/${acordeId}/identidade`),
  ajuste: (criacaoId, acordeId, movimento) =>
    request(`/criacoes/${criacaoId}/acordes/${acordeId}/ajuste`, {
      method: 'POST',
      body: { movimento },
    }),
};

export const testes = {
  listar: (criacaoId) => request(`/criacoes/${criacaoId}/testes`),
  criar: (criacaoId, dados) =>
    request(`/criacoes/${criacaoId}/testes`, { method: 'POST', body: dados }),
};

export const colecoes = {
  listar: () => request('/colecoes'),
  criar: (dados) => request('/colecoes', { method: 'POST', body: dados }),
  atualizar: (id, dados) => request(`/colecoes/${id}`, { method: 'PUT', body: dados }),
  reordenar: (id, criacaoIds) =>
    request(`/colecoes/${id}/ordem`, { method: 'PUT', body: { criacao_ids: criacaoIds } }),
  apagar: (id) => request(`/colecoes/${id}`, { method: 'DELETE' }),
  adicionarCriacao: (id, criacaoId) =>
    request(`/colecoes/${id}/criacoes`, { method: 'POST', body: { criacao_id: criacaoId } }),
  removerCriacao: (id, criacaoId) =>
    request(`/colecoes/${id}/criacoes/${criacaoId}`, { method: 'DELETE' }),
};

export const conhecimento = {
  familias: () => request('/conhecimento/familias'),
  notas: () => request('/conhecimento/notas'),
  relacoes: () => request('/conhecimento/relacoes'),
  descritores: () => request('/conhecimento/descritores'),
  funcoes: () => request('/conhecimento/funcoes'),
  territorios: () => request('/conhecimento/territorios'),
  publicos: () => request('/conhecimento/publicos'),
  regras: (tipo) => request('/conhecimento/regras', { params: { tipo } }),
};

// Mapa Olfativo: pontos da aluna + territórios e caminhos da base, numa chamada só.
export const mapa = {
  obter: () => request('/mapa'),
};
