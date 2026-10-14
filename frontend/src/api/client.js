/**
 * Cliente HTTP da API do Sérené, construído sobre `fetch`.
 *
 * Responsabilidades:
 * - prefixar a URL base (VITE_API_URL);
 * - anexar o JWT no header Authorization;
 * - serializar JSON (ou formulário, no login OAuth2);
 * - transformar respostas de erro do FastAPI em `ApiError` com mensagem legível.
 */

// Em produção VITE_API_URL é obrigatória (o build falha sem ela, ver
// vite.config.js). O endereço local só vale no `npm run dev`.
const BASE_URL = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')).replace(/\/$/, '');
const TOKEN_KEY = 'serene.token';

export class ApiError extends Error {
  /**
   * @param {number} status   HTTP status (0 = sem conexão)
   * @param {string} message  texto legível para a usuária
   * @param {any}    detail   `detail` bruto do FastAPI
   * @param {object} [extra]
   * @param {string} [extra.codigo]      identificador estável do erro (ex.: "email_nao_verificado")
   * @param {number} [extra.retryAfter]  segundos até poder tentar de novo (respostas 429)
   */
  constructor(status, message, detail, { codigo, retryAfter } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.codigo = codigo;
    this.retryAfter = retryAfter;
  }
}

// O localStorage pode lançar (aba anônima, dados bloqueados): nunca deixe isso derrubar a app.
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sem persistência: o login dura só esta aba */
  }
}

let onUnauthorized = () => {};

/** Registra o que fazer quando a API responde 401 (token expirado/inválido). */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

const CAMPOS = {
  email: 'Email',
  senha: 'Senha',
  nova_senha: 'Senha',
  nome: 'Nome',
  itens: 'Essências',
  nota: 'Nota',
  movimento: 'Movimento',
  codigo: 'Código',
};

const MENSAGENS_422 = {
  missing: () => 'é obrigatório',
  string_too_short: (ctx) =>
    ctx?.min_length === 1 ? 'não pode ficar vazio' : `precisa de pelo menos ${ctx?.min_length} caracteres`,
  string_too_long: (ctx) => `aceita no máximo ${ctx?.max_length} caracteres`,
  too_short: (ctx) => `precisa de pelo menos ${ctx?.min_length} itens`,
  less_than_equal: (ctx) => `deve ser no máximo ${ctx?.le}`,
  greater_than_equal: (ctx) => `deve ser no mínimo ${ctx?.ge}`,
  extra_forbidden: () => 'não é aceito',
  string_pattern_mismatch: () => 'está em formato inválido',
};

/** Converte o `detail` do FastAPI (string ou lista de erros do Pydantic) em texto. */
function mensagemDeErro(data, status) {
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((e) => {
        const campo = [...(e.loc || [])].reverse().find((p) => typeof p === 'string' && p !== 'body');
        const rotulo = CAMPOS[campo] || campo || 'Dados';
        if (e.type === 'value_error' && campo === 'email') return 'Email inválido.';
        const traduzir = MENSAGENS_422[e.type];
        const texto = traduzir ? traduzir(e.ctx) : (e.msg || '').replace(/^Value error, /, '');
        return `${rotulo} ${texto}.`;
      })
      .join(' ');
  }
  if (status >= 500) return 'O servidor encontrou um erro. Tente de novo em instantes.';
  return `Erro ${status}.`;
}

/**
 * Faz uma requisição à API.
 *
 * @param {string} path      caminho a partir da raiz da API (ex.: "/essencias")
 * @param {object} [opts]
 * @param {string} [opts.method]  GET, POST, PUT, DELETE
 * @param {any}    [opts.body]    enviado como JSON
 * @param {object} [opts.form]    enviado como application/x-www-form-urlencoded
 * @param {object} [opts.params]  query string (valores nulos são ignorados)
 * @returns {Promise<any>} JSON da resposta, ou null em 204
 */
export async function request(path, { method = 'GET', body, form, params } = {}) {
  const url = new URL(BASE_URL + path);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  });

  const headers = { Accept: 'application/json' };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, `Não foi possível falar com a API em ${BASE_URL}. O backend está rodando?`);
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    // 401 = token inválido/expirado; 403 email_nao_verificado com token = conta
    // que perdeu a verificação. Nos dois casos o token salvo não serve mais.
    if (token && (res.status === 401 || (res.status === 403 && data?.codigo === 'email_nao_verificado'))) {
      onUnauthorized();
    }
    throw new ApiError(res.status, mensagemDeErro(data, res.status), data?.detail, {
      codigo: data?.codigo,
      // O backend repete o Retry-After no corpo: o navegador não deixa ler
      // esse header de outra origem sem configuração extra de CORS.
      retryAfter: data?.retry_after,
    });
  }
  return data;
}
