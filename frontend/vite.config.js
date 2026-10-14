import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Valida o endereço da API no build de produção.
 *
 * Sem `VITE_API_URL`, o app publicado tentava falar com http://127.0.0.1:8000
 * — a máquina de quem abre o site — e quebrava sem explicação. Também exige
 * HTTPS fora do localhost: o token de acesso não pode trafegar em texto puro.
 */
function origemDaApi(url) {
  if (!url) {
    throw new Error(
      'VITE_API_URL não definida. Configure-a (ex.: https://serene-api.vercel.app) ' +
        'nas variáveis de ambiente do projeto no Vercel ou no frontend/.env.',
    );
  }
  let origem;
  try {
    origem = new URL(url);
  } catch {
    throw new Error(`VITE_API_URL inválida: "${url}".`);
  }
  const local = ['localhost', '127.0.0.1'].includes(origem.hostname);
  if (origem.protocol !== 'https:' && !local) {
    throw new Error(`VITE_API_URL precisa usar https:// (recebido: ${url}).`);
  }
  return origem.origin;
}

/**
 * Content-Security-Policy injetada no index.html do build.
 *
 * Mesmo que um dia algum texto com <script> passe pela interface, o navegador
 * só executa scripts do próprio site e só conversa com a API — isso protege
 * o token guardado no localStorage. Vai como <meta> porque o endereço da API
 * só é conhecido no build; `frame-ancestors` (que não funciona em <meta>) está
 * no vercel.json. Só no build: o servidor de desenvolvimento do Vite precisa
 * de scripts inline e websocket.
 */
function cspPlugin(apiOrigin) {
  const politica = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    // data: = prévia da foto antes de enviar; Cloudinary = fotos de perfil salvas.
    "img-src 'self' data: https://res.cloudinary.com",
    `connect-src 'self' ${apiOrigin}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ');
  return {
    name: 'serene-csp',
    apply: 'build',
    transformIndexHtml() {
      return [{ tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: politica }, injectTo: 'head-prepend' }];
    },
  };
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const plugins = [react()];
  if (command === 'build') plugins.push(cspPlugin(origemDaApi(env.VITE_API_URL)));
  return {
    plugins,
    build: {
      // Fontes sempre como arquivo, nunca embutidas como data:. Um subconjunto
      // pequeno embutido era bloqueado pela CSP (font-src 'self').
      assetsInlineLimit: (arquivo) => (/\.(woff2?|ttf|otf)$/.test(arquivo) ? false : undefined),
    },
    // Porta fixa: o backend libera http://localhost:5173 em CORS_ORIGINS.
    server: { port: 5173, strictPort: true },
  };
});
