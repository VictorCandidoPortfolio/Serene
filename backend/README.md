# SÉRENÉ — Mapa Olfativo Inteligente (backend)

API em **FastAPI + MySQL 8 + SQLAlchemy 2.0 + Alembic + JWT** que ajuda alunas
de perfumaria a organizar o próprio repertório de essências e criar acordes
orientados por conhecimento.

## Arquitetura em 1 minuto

O domínio tem **duas camadas**, e a separação entre elas é a decisão mais
importante do sistema:

| Camada | Tabelas | Quem escreve | Quem lê |
|---|---|---|---|
| **Conhecimento** (compartilhada) | `knowledge_*` | só o seed (`python -m app.seed`) | todas as usuárias, só leitura (`/conhecimento/*`) |
| **Repertório pessoal** | `essencias`, `criacoes`, `acordes`, `testes`, `referencias`, `perfis_olfativos`, `colecoes`, `colecao_criacoes` | a dona | só a dona |

Uma usuária nova começa com o repertório **100% vazio**. Nenhuma nota de
conhecimento vira "essência disponível". Elas servem só para *sugerir*
classificação e para *nomear lacunas*.

**Isolamento sem RLS.** O MySQL não tem Row Level Security, então o
isolamento é imposto em [app/repositories/base.py](app/repositories/base.py):
um repositório pessoal só pode ser construído com o `user_id` da usuária
autenticada, e toda consulta parte de um `SELECT` já filtrado pela dona (ou
por posse transitiva: `acordes`/`testes` → `criacoes.user_id`). Um registro de
outra usuária responde **404**, nunca 403. A prova está em
[tests/test_isolamento.py](tests/test_isolamento.py).

```
app/
  core/          config (.env), security (bcrypt/JWT), dependencies (get_current_user), exceptions, text
  db/            Base declarativa + engine/sessão
  models/        knowledge.py (camada compartilhada) · repertorio.py (camada pessoal)
  schemas/       Pydantic v2 (entrada rejeita campos extras como user_id)
  repositories/  ÚNICO lugar com SQL; base.py impõe o filtro por dona
  services/      regras de negócio; motor.py liga a base de conhecimento ao motor
  engine/        motor olfativo — funções PURAS (vectors, compatibility, movement, gaps, recommendation, reconhecimento)
  routers/       HTTP fino: valida → service → resposta
  seed/          base de conhecimento: estrutura da cliente + conteúdo de EXEMPLO marcado (idempotente)
alembic/versions/  0001–0009 (conhecimento, repertório, coleções, conta, marca de exemplo)
tests/           test_auth · test_isolamento · test_engine · test_fluxo
```

## Rodando localmente

Requisitos: Python 3.11+ e MySQL 8.0.16+ (os CHECKs só são aplicados a partir
do 8.0.16).

### 1. Banco

Com um MySQL local:

```sql
CREATE DATABASE serene CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'serene'@'%' IDENTIFIED BY 'serene';
GRANT ALL ON serene.* TO 'serene'@'%';
```

Ou com Docker (aqui na porta 3307, para não brigar com um MySQL local na 3306):

```bash
docker run -d --name serene-mysql-3307 -p 3307:3306 \
  -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=serene \
  -e MYSQL_USER=serene -e MYSQL_PASSWORD=serene mysql:8.0
```

### 2. Ambiente

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt   # produção + pytest (o Vercel usa só requirements.txt)
cp .env.example .env            # ajuste DATABASE_URL e gere um JWT_SECRET_KEY
```

Gere a chave com `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

#### Email (código de verificação do cadastro)

Toda conta nova recebe por email um código de 4 dígitos e só consegue entrar
depois de digitá-lo. Preencha no `.env` (cada variável está explicada no
[.env.example](.env.example)):

```ini
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app      # no Gmail: senha de app, não a senha da conta
```

**Gmail:** ative a verificação em duas etapas e gere uma *senha de app* em
<https://myaccount.google.com/apppasswords>. A senha normal da conta é recusada.

**Sem email configurado ainda?** Use `EMAIL_BACKEND=console`: o código aparece
no terminal do `uvicorn`. Só para desenvolvimento.

Com `EMAIL_BACKEND=smtp` e `SMTP_HOST` vazio, a API nem sobe e explica o que
falta. Isso é de propósito, para não descobrir a configuração errada só no
primeiro cadastro.

### 3. Migrations e seed

```bash
alembic upgrade head      # cria as tabelas e aplica as 9 migrations
alembic check             # confirma que models e migrations estão em sincronia
python -m app.seed        # popula knowledge_* (pode rodar de novo, é idempotente)
```

O seed mistura dois tipos de conteúdo, e a diferença fica gravada no banco (coluna `ilustrativo`) e aparece na interface:

- **Estrutura da cliente** (`ilustrativo = false`): as 14 famílias, "Floral Branco" como subfamília de Floral, as 9 características sensoriais, os 3 níveis da pirâmide e os nomes dos 10 territórios.
- **Exemplo** (`ilustrativo = true`): 5 notas, 5 relações, 3 mapas e os números do motor (vetores, pesos, limites, públicos). Existem só para exercitar o motor. **Nunca são apresentados como validados**, e os números de uma nota de exemplo não são copiados para a essência da aluna (só a classificação é sugerida).

A base oficial vai substituir essas linhas em [app/seed/data.py](app/seed/data.py); a marca some junto com o exemplo.

### 4. API

```bash
uvicorn app.main:app --reload
```

Abra **http://127.0.0.1:8000/docs**.

## Testando pelo Swagger (`/docs`)

1. `POST /auth/register`: `{"email": "ana@exemplo.com", "senha": "Senha-forte-123", "nome": "Ana"}`. A senha precisa de 8+ caracteres, uma maiúscula e um número ou caractere especial.
2. Pegue o código de 4 dígitos no email (ou no terminal, com `EMAIL_BACKEND=console`) e envie em `POST /auth/verificar-email`: `{"email": "ana@exemplo.com", "codigo": "1234", "senha": "Senha-forte-123"}`. A senha vai junto de propósito (ver "Segurança"). Antes disso, o login responde 403.
3. Clique em **Authorize**, use o email como *username* mais a senha. O Swagger chama `/auth/login` e guarda o token.
4. `GET /essencias` → `[]` (repertório vazio).
5. `POST /essencias` com `{"nome": "bergamot"}`. A resposta traz `sugestoes_referencia` e **nada é aplicado sozinho**.
6. Confirme a sugestão: `{"nome": "Bergamota", "knowledge_note_id": 1, "aplicar_referencia": true}`. Faça o mesmo com Jasmim (nota 3) e Cedro (nota 4).
7. `POST /perfis` com `{"respostas": {"emocoes": ["amor"], "territorios": ["acolhimento"], "publico": "teen"}}`
8. `POST /criacoes` com `{"nome": "Primeira", "perfil_id": 1}`
9. `POST /criacoes/1/acordes` com `{"itens": [{"essencia_id": 3, "peso": "bastante"}, {"essencia_id": 4, "peso": "medio"}]}`. A resposta traz o vetor, o papel, a família resultante e a compatibilidade.
10. `POST /criacoes/1/acordes/1/ajuste` com `{"movimento": "mais_fresco"}`. Vêm sugestões só com essências suas ou, se não houver nenhuma, a **lacuna** (a família que falta).
11. `GET /essencias/lacunas`, `GET /perfis/1/recomendacoes`, `GET /conhecimento/territorios`.

## Testes

```bash
pytest                    # SQLite em memória (rápido, sem dependências)
```

Para rodar contra um **MySQL descartável** (as tabelas são apagadas a cada teste):

```bash
# PowerShell
$env:TEST_DATABASE_URL="mysql+pymysql://serene:serene@127.0.0.1:3307/serene_test?charset=utf8mb4"; pytest
```

## Regras de negócio e onde vivem

| Regra | Onde é garantida |
|---|---|
| Peso é relativo (pouco/medio/bastante), nunca % de produto | `schemas/criacoes.py` (aceita só 1–3), `engine/axes.py` |
| Nunca inventar dado técnico | `engine/*` trata `None` como "não sabemos" e informa cobertura e avisos |
| Nunca sugerir essência fora do repertório | candidatas vêm só de `EssenciaRepository` (filtrado pela dona) |
| Nomear a lacuna, não inventar a solução | `engine/gaps.py` (família, camada ou eixo, nunca uma nota) |
| Referência não vira estoque | `referencias` não tem vetores e nenhum service do motor a lê |
| Versionar, nunca sobrescrever | acordes/testes sem PUT/DELETE; unique `(criacao_id, versao)` |
| Gênero é insumo flexível | `engine/recommendation.py`: contribuição opcional, nunca filtra |
| Nada de regra hardcoded | pesos, movimentos, territórios e públicos em `knowledge_engine_rules` |
| Senha forte (8+, maiúscula, número ou especial) | `core/security.py::problemas_da_senha`, validada em `schemas/auth.py` |
| Conta só entra com email confirmado | `services/auth_service.py` (login 403) e `core/dependencies.py` (token de conta pendente → 403) |

### Verificação de email: decisões

- **Código de 4 dígitos** gerado com `secrets` (criptograficamente aleatório) e guardado só como HMAC-SHA256, nunca em texto puro.
- **Só 10.000 combinações**, por isso há limites: o código expira (10 min), aceita 5 tentativas erradas, só pode ser reenviado a cada 60 s e no máximo 5 vezes por hora. Todos esses valores são configuráveis no `.env`.
- **Se o envio do email falhar**, o cadastro é desfeito (503) e a pessoa pode tentar de novo, em vez de ficar com uma conta presa sem código.
- **`/auth/reenviar-codigo` responde igual** exista ou não a conta, para não servir de consulta de emails cadastrados.
- **Contas criadas antes da migration 0004** foram marcadas como verificadas.

### Redefinição de senha ("esqueci minha senha")

- `POST /auth/esqueci-senha` `{"email"}` → 202. Envia um código de 4 dígitos por email. A resposta é igual exista ou não a conta (e conta ainda não confirmada não recebe código).
- `POST /auth/redefinir-senha` `{"email", "codigo", "nova_senha"}` → 200. Confere o código, troca a senha (que precisa ser forte) e apaga o código. Não devolve token: a pessoa entra depois, em `/auth/login`. **Todos os tokens emitidos antes deixam de valer** (401): o JWT leva a claim `tv` e `users.token_version` sobe a cada redefinição (migration `0006`).
- Reaproveita o fluxo da verificação de email: mesma tabela (`verificacoes_email`), mesmo HMAC, mesma expiração, limite de tentativas e de reenvios. Não há migration nova. Limites extras por IP e por email em `core/rate_limit.py`.

### Conta logada: dados, senha e foto de perfil

Tudo exige o token; a lógica fica em [app/services/conta_service.py](app/services/conta_service.py) e os testes em [tests/test_conta.py](tests/test_conta.py).

- `PUT /auth/me` `{"nome"}` → a conta atualizada. O **email não muda por aqui**: trocá-lo exigiria confirmar o endereço novo por código (senão um token roubado bastaria para tomar a conta).
- `POST /auth/me/senha` `{"senha_atual", "nova_senha"}` → `{"access_token"}`. Confere a senha atual, exige senha forte e diferente da atual. A `token_version` sobe: **as sessões de outros aparelhos caem**, e esta continua com o token devolvido (sem precisar entrar de novo). Senha atual errada é **400, não 401**, para o frontend não confundir com sessão expirada. Limite de 10 tentativas a cada 15 min por conta.
- `PUT /auth/me/foto` `{"imagem": "data:image/webp;base64,..."}` → a conta com `foto_url`. Aceita JPEG, PNG ou WebP de até 2 MB; o conteúdo é conferido pelos primeiros bytes (um SVG dizendo ser PNG é recusado). O upload vai para o **Cloudinary** (upload assinado, [app/core/cloudinary.py](app/core/cloudinary.py), só biblioteca padrão), com nome de arquivo aleatório. O banco guarda `foto_url` e `foto_public_id` (migration `0007`); a foto antiga é apagada do Cloudinary depois que a nova é salva. Esta rota aceita corpo de até 3 MB (as outras, 1 MB). Limite de 20 envios por hora por conta.
- `DELETE /auth/me/foto` → a conta sem foto (e o arquivo apagado no Cloudinary, em melhor esforço).
- Sem `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` no `.env`, a API sobe normalmente e o envio de foto responde **503** "ainda não foi configurado".

## Funcionalidades e onde vivem

| Funcionalidade | API | Motor / service |
|---|---|---|
| Cadastro e classificação (6 eixos, incl. floralidade) | `POST/PUT /essencias` | `services/essencias_service.py` |
| Mapa Olfativo | `GET /mapa` | `services/mapa_service.py` |
| Perfil olfativo (com intensidade, idade e referência) | `/perfis` | `engine/recommendation.py::calcular_vetor_alvo` |
| Identidade de um acorde (territórios que transmite) | `GET /criacoes/{id}/acordes/{aid}/identidade` | `engine/recommendation.py::identificar_territorios` |
| Criador de fragrâncias (direção por perfil, território ou referência + sugestões) | `POST /criacoes` (`perfil_id` \| `intencao` \| `referencia_id`), `GET /criacoes/{id}/recomendacoes` | `services/criacoes_service.py` |
| **Motor de criação** ("O que você quer criar?": pedido → identidade + acorde sugerido) | `POST /criacoes/sugerir` (prévia, não grava), `GET /criacoes/sugerir/opcoes`, `POST /criacoes` com `sugestao` | `engine/criacao.py`, `services/sugestao_service.py` |
| Compatibilidade sem gravar acorde | `POST /essencias/compatibilidade` | `engine/compatibility.py` |
| Caminhos de uma referência | `GET /referencias/{id}/caminhos` | `engine/referencias.py` |
| Evolução (motivo de cada versão) | `POST /criacoes/{id}/acordes` (`motivo`) | `models/repertorio.py::Acorde.motivo` |
| Identidade geral da coleção | `GET /colecoes` (`identidade_geral`) | `services/outros_service.py::ColecoesService.identidade` |
| 10 territórios, 3 públicos | `GET /conhecimento/territorios`, `/publicos` | `seed/data.py` (nomes da cliente; vetores de exemplo) |

### Motor de criação: o algoritmo em 1 minuto

Determinístico (sem `random`, sem modelo de linguagem): o mesmo pedido gera sempre a mesma resposta.
Textos explicativos saem de **templates**. Todos os números ficam em `knowledge_engine_rules`
(tipos `criacao_emocao`, `criacao_preferencia`, `criacao_idade`, `criacao_territorio`,
`criacao_vocabulario` e `peso_score/criacao_score`, `peso_score/criacao_padrao_pesos`), populados por
`app/seed/data_criacao.py`; a professora calibra editando linhas, sem mexer em código.

1. **Vetor-alvo**: parte do neutro (`v1=v2=v3=5`, `v5=4`) e de `v4 = intensidade pedida`; soma os
   deslocamentos de cada emoção/preferência e da idade (clamp 0–10). O `v4` das regras de emoção é
   ignorado aqui: a presença vem só da intensidade (e do teto de idade, ex.: bebê ≤ 3).
2. **Territórios**: cada emoção/preferência soma pontos a famílias de gosto (Floral, Fresco...). Vale o
   primeiro; o segundo entra se tiver ≥ 50 % dos pontos do primeiro.
3. **Ranking** das essências **da aluna**: `score = bônus_território × 2 + proximidade` (v1–v4).
4. **Montagem gulosa**: começa pela melhor e só acrescenta a essência que aproxima o acorde do alvo e
   combina com as já escolhidas; para quando adicionar não ajuda. Máximo 4 essências (3 para bebê).
5. **Pesos relativos** fixos por tamanho (`[2,2]`, `[3,2,1]`, `[3,2,2,1]` = Pouco/Médio/Bastante).
   Nunca são porcentagem nem quantidade de produto.
6. **Lacunas**: se o repertório não alcança a direção, o motor **nomeia a categoria** que falta
   (território/família), nunca uma essência.

`POST /criacoes` com `sugestao` recalcula tudo no servidor (nada vindo do cliente é confiado), grava o
perfil (`perfis_olfativos.respostas`), a criação (`direcao`) e a versão 1 do acorde.

**Limitações conhecidas** (heurística pedagógica, não ciência exata):

- Os números (deslocamentos por emoção, limiares, pesos de score, curva de coerência) são **valores
  iniciais** e precisam ser calibrados com o repertório real e testes olfativos reais.
- A sugestão é tão boa quanto a classificação das essências (eixos, papel, família). Essência mal
  classificada gera sugestão ruim; sem dados, o motor diz que não tem informação suficiente.
- A montagem é **gulosa**: previsível e explicável, mas não garante o melhor acorde possível.
- Pesos fixos por posição (`[3,2,1]`) são simplificação pedagógica; a proporção real depende da
  intensidade e da persistência de cada essência e deve ser validada em bancada.
- O motor orienta a criação; **não prevê** como a mistura vai cheirar na pele.

Testes: [tests/test_funcionalidades.py](tests/test_funcionalidades.py), que também varre o OpenAPI e
falha se alguma rota nova ficar sem exigir login.

## Segurança

Auditoria de outubro/2026 (JWT, proteção de rotas, isolamento, fluxos de
conta, entradas e dependências). Cada falha encontrada virou um teste de
regressão em [tests/test_seguranca.py](tests/test_seguranca.py).

| Proteção | Onde |
|---|---|
| JWT: só HS256/384/512, `exp` e `sub` obrigatórios, segredo de exemplo recusado | `core/security.py`, `core/config.py` |
| Isolamento entre usuárias (todas as rotas com id testadas) | `repositories/base.py`, `tests/test_isolamento.py` |
| Confirmar o email exige código **e** senha; recadastro de conta pendente troca a senha | `services/auth_service.py` (impede sequestro de conta pré-cadastrada) |
| `SELECT … FOR UPDATE` na verificação e nos reenvios | `repositories/conta.py` (impede burlar os limites em paralelo) |
| Limite de tentativas por IP e por email, guardado no banco | `core/rate_limit.py` |
| Limites de tamanho (textos, listas, acordes, corpo de 1 MB) e cotas por conta | `schemas/`, `core/middlewares.py`, `repositories/` |
| Cabeçalhos de segurança, `/docs` desligado em produção, erros sem detalhes internos | `main.py`, `core/middlewares.py` |
| TLS verificado na conexão com o banco | `db/session.py` |
| Logs sem senha, código, token nem email completo | `core/logging_config.py` |

## Deploy

Passo a passo no Vercel: [../DEPLOY.md](../DEPLOY.md).

## Fora do escopo desta fase

Troca de senha (com a usuária logada) e logout no servidor (revogação de
um token isolado; só a redefinição de senha invalida os tokens, todos de uma vez), paginação e filtros avançados, base de
conhecimento completa, cálculo de `identidade_geral` das coleções e endpoint
de escrita administrativa da base de conhecimento.
