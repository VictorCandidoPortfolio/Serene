# SÉRENÉ — frontend

Interface em **React 19 + Vite** para a API do SÉRENÉ. Fala com o backend só por
`fetch`, sem biblioteca de HTTP.

## Rodando

Requisitos: Node 20+ e o backend rodando (veja [../backend/README.md](../backend/README.md)).

```bash
cd frontend
npm install
cp .env.example .env      # ajuste VITE_API_URL se a API não estiver em http://127.0.0.1:8000
npm run dev               # http://localhost:5173
```

`npm run build` exige `VITE_API_URL` com `https://` (fora do localhost) e
injeta no `index.html` uma Content-Security-Policy que só deixa a página
falar com ela mesma e com a API. Deploy no Vercel: [../DEPLOY.md](../DEPLOY.md).

O backend precisa liberar a origem do front no CORS. No `backend/.env`:

```
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

A porta 5173 é fixa (`strictPort`): se estiver ocupada, o Vite falha em vez de
trocar de porta e cair num CORS bloqueado.

## Estrutura

```
src/
  api/client.js      fetch + JWT + tradução de erros do FastAPI (inclusive 422 do Pydantic)
  api/serene.js      um método por endpoint; as telas só falam com a API por aqui
  auth/              contexto de login (token no localStorage, logout automático em 401)
  lib/               useApi (carregar/recarregar), vocabulário dos eixos, formatação e regra de senha forte
  components/        Layout (abas no celular, barra lateral no desktop), Gauge, Keypad, Sheet, Confirmar, ErrorBoundary, Illustration, ui
  pages/             Login, VerificarEmail, Home, Essencias, Criacoes, CriacaoDetalhe, RegistrarTeste, Perfis, Colecoes
```

## Celular e desktop

O mesmo código serve os dois; quem decide o layout é só o CSS ([src/styles.css](src/styles.css)):

| Largura | Layout |
|---|---|
| até 519px | celular: tela cheia, abas embaixo |
| 520–1023px | a tela de celular centralizada numa moldura |
| 1024px ou mais | desktop: barra lateral, conteúdo em colunas, listas em grade; login, código e teste divididos em ilustração e formulário |

As telas usam alguns wrappers só para montar as colunas do desktop
(`home-grade`, `detalhe-grade`, `perfil-grade`...). Abaixo de 1024px eles têm
`display: contents`, ou seja, somem do layout e a versão de celular continua
idêntica.

## Telas e endpoints

| Tela | O que faz | Endpoints |
|---|---|---|
| Login | entrar ou criar conta; checklist ao vivo da senha forte | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Confirmar email | digitar o código de 4 dígitos (envia sozinho no 4º dígito) e reenviar com contagem regressiva | `POST /auth/verificar-email`, `POST /auth/reenviar-codigo` |
| Início | total de essências, cobertura de famílias, últimas criações | `GET /essencias`, `/criacoes`, `/conhecimento/familias` |
| Essências | repertório; cadastro e **classificação completa** (família, subfamília, 6 eixos com "não sei", papel, descritores, tags); sugere referência enquanto você digita; aba **Combinar** (compatibilidade sem gravar); lacunas; referências com **caminhos** e criação inspirada | `/essencias`, `PUT /essencias/{id}`, `/essencias/sugestao-classificacao`, `POST /essencias/compatibilidade`, `/essencias/lacunas`, `/referencias`, `/referencias/{id}/caminhos` |
| Criações | direção por **território**, perfil ou referência; **essências sugeridas** para a direção; versões com **motivo** e **comparação**; prévia de compatibilidade; **identidade** (territórios que a versão transmite); ajuste pelo motor; testes com detalhe | `/criacoes`, `/criacoes/{id}/recomendacoes`, `/criacoes/{id}/acordes`, `.../identidade`, `.../ajuste`, `/criacoes/{id}/testes` |
| Registrar teste | nota 0–10, intensidade, persistência, o que senti, o que ficou bom, o que mudar, próximo ajuste | `POST /criacoes/{id}/testes` |
| Perfis | questionário (emoções, territórios, preferências, público, intensidade, idade, perfume de referência), vetor-alvo e ranking do repertório | `/perfis`, `/perfis/{id}/recomendacoes`, `/conhecimento/regras`, `/territorios`, `/publicos` |
| Coleções | agrupar criações aprovadas, renomear, **reordenar** e ver a **identidade geral** da linha | `/colecoes`, `/colecoes/{id}/criacoes`, `PUT /colecoes/{id}/ordem` |
| Mapa | essências e criações posicionadas entre os **territórios** (eixos escolhidos pela aluna) e o grafo de **caminhos entre famílias** | `GET /mapa` |
| Conhecimento | consulta da base: famílias, notas (com busca), relações, territórios, públicos, pirâmide e descritores | `/conhecimento/*` |
| Minha conta | foto de perfil, nome, trocar senha sem deslogar, sair (com confirmação) | `PUT /auth/me`, `POST /auth/me/senha`, `PUT`/`DELETE /auth/me/foto` |

**Minha conta** abre pela foto/iniciais no Início (celular) ou pelo seu nome
no rodapé da barra lateral (desktop). A foto escolhida é cortada em quadrado
e reduzida para 512px no próprio navegador ([src/lib/imagem.js](src/lib/imagem.js)),
e vai para a API como base64 (WebP, ou JPEG onde não há WebP). A API envia
ao Cloudinary e guarda a URL. Por isso a CSP do build libera
`https://res.cloudinary.com` em `img-src`. Todo botão "Sair" passa por
[src/auth/useSair.js](src/auth/useSair.js), que pede confirmação.

Depois do cadastro, a tela de confirmar email abre sozinha. Se uma conta ainda
não confirmada tenta entrar, o login também leva para ela.

Aplicar uma sugestão de ajuste grava uma **nova versão** do acorde. Assim como no
backend, nenhuma versão é sobrescrita.
