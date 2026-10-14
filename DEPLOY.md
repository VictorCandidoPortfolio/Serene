# Deploy no Vercel

O Sérené vira **dois projetos no Vercel**, a partir do mesmo repositório:

| Projeto | Root Directory | O que é | URL de exemplo |
|---|---|---|---|
| `serene-api` | `backend` | FastAPI (função Python) | `https://serene-api.vercel.app` |
| `serene` | `frontend` | Site estático (Vite + React) | `https://serene.vercel.app` |

O banco **não** fica no Vercel: é preciso um MySQL 8 hospedado.

---

## 1. Banco MySQL hospedado

Qualquer MySQL 8.0.16+ com acesso pela internet e TLS serve, por exemplo:
**TiDB Cloud Serverless**, **Aiven for MySQL** ou **Railway**.

1. Crie o banco e um usuário só para o Sérené.
2. Copie a string de conexão no formato:
   `mysql+pymysql://USUARIO:SENHA@HOST:PORTA/BANCO?charset=utf8mb4`
3. **Sempre** use `DATABASE_SSL=true`. Se o provedor usa uma autoridade
   certificadora própria (o Aiven usa), baixe o `ca.pem`, coloque em
   `backend/certs/ca.pem` e defina `DATABASE_SSL_CA=certs/ca.pem`.

### Criar as tabelas e a base de conhecimento

Rode **do seu computador**, apontando para o banco de produção (PowerShell,
dentro de `backend`, com o `.venv` ativo):

```powershell
$env:DATABASE_URL="mysql+pymysql://USUARIO:SENHA@HOST:PORTA/BANCO?charset=utf8mb4"
$env:DATABASE_SSL="true"
$env:JWT_SECRET_KEY="qualquer-valor-com-32-ou-mais-caracteres-so-para-o-alembic"
$env:EMAIL_BACKEND="console"
alembic upgrade head
python -m app.seed
```

> Por que não rodar as migrations automaticamente em cada deploy: os
> deploys de *preview* (de cada branch/PR) usariam o mesmo banco e poderiam
> migrar a produção com código que ainda não foi aprovado.

Repita o `alembic upgrade head` sempre que um deploy trouxer migrations novas
(arquivos novos em `backend/alembic/versions/`), **antes** de publicar.

---

## 2. Email (código de verificação)

Com Gmail:

1. Ative a verificação em duas etapas na conta Google que vai enviar.
2. Gere uma **senha de app** em <https://myaccount.google.com/apppasswords>.
   A senha normal da conta é recusada pelo Gmail.

---

## 3. Projeto da API (`backend`)

1. No Vercel: **Add New → Project** → importe o repositório.
2. **Root Directory:** `backend`. O Vercel detecta o FastAPI sozinho
   (`app/main.py`, Python da `.python-version`).
3. **Environment Variables** (escopo **Production**):

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | a string do passo 1 |
   | `DATABASE_SSL` | `true` |
   | `DATABASE_SSL_CA` | só se o provedor exigir (ex.: `certs/ca.pem`) |
   | `JWT_SECRET_KEY` | gere com `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `EMAIL_BACKEND` | `smtp` |
   | `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURITY` | `smtp.gmail.com` / `587` / `starttls` |
   | `SMTP_USER` / `SMTP_PASSWORD` | conta e senha de app do passo 2 |
   | `CORS_ORIGINS` | por enquanto `https://example.com`; troque no passo 5 |
   | `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | opcionais: credenciais do Cloudinary para a foto de perfil (Dashboard da conta). Sem elas, o resto funciona e só o envio de foto fica indisponível |

   `APP_ENV` não precisa: no Vercel ela vira `production` sozinha. Em
   produção a API **se recusa a subir** se faltar email SMTP, CORS, ou se o
   `JWT_SECRET_KEY` for o valor de exemplo.
4. **Deploy.** Teste: `https://SUA-API.vercel.app/health/ready` deve responder
   `{"status": "ok", "banco": "ok"}`. Se responder 503, a API não alcança o
   banco: confira `DATABASE_URL`, `DATABASE_SSL` e se o provedor libera
   conexões de fora (alguns pedem lista de IPs; o Vercel não tem IP fixo, então
   libere `0.0.0.0/0` e conte com usuário/senha + TLS).

O `/docs` fica desligado em produção. Para ligar temporariamente, defina
`ENABLE_DOCS=true` e faça redeploy.

---

## 4. Projeto do frontend (`frontend`)

1. **Add New → Project** → o mesmo repositório.
2. **Root Directory:** `frontend`. Framework: Vite (detectado).
3. **Environment Variables:** `VITE_API_URL` = `https://SUA-API.vercel.app`
   (sem barra no final). O build **falha** sem ela, ou se não for `https://`.
4. **Deploy.**

O `frontend/vercel.json` já cuida de: rotas da SPA (recarregar `/criacoes`
não dá 404), cabeçalhos de segurança e cache dos arquivos de `/assets`.

---

## 5. Ligar um ao outro (CORS)

No projeto da API, troque `CORS_ORIGINS` pela URL do frontend
(`https://serene.vercel.app`; se tiver domínio próprio, inclua os dois
separados por vírgula) e faça **Redeploy**.

> Deploys de *preview* do frontend têm outra URL e ficam bloqueados pelo
> CORS da API de produção. Isso é proposital.

---

## 6. Checklist depois do deploy

- [ ] `/health/ready` da API responde `ok`.
- [ ] Cadastro com uma senha fraca é recusado; com senha forte, chega o email
      com o código.
- [ ] Código errado mostra "restam N tentativas"; o certo entra no app.
- [ ] Recarregar a página em `/criacoes` não dá 404.
- [ ] `https://SUA-API.vercel.app/docs` responde 404 (documentação desligada).
- [ ] No painel do Vercel (**Logs** do projeto da API), aparecem linhas
      `[serene.auth]` para cadastro e login.

## Limites que valem em produção

- Login: 10 tentativas por email a cada 15 min e 20 por IP a cada 5 min.
- Cadastro: 10 por IP por hora. Código: 5 tentativas por código, 15 por conta
  por hora, 1 reenvio por minuto e 5 por hora.
- Corpo de requisição até 1 MB; acorde com até 20 essências; até 1.000
  essências por conta.
