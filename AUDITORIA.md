# AUDITORIA — SÉRENÉ / Mapa Olfativo Inteligente

> Fase 0. Nenhuma linha de código foi alterada. Tudo abaixo vem da leitura dos arquivos
> e de duas execuções: `pytest` no backend e `vite build` no frontend (saída em pasta temporária).

## 1. Resumo

O projeto **já está bem adiantado** e a base é sólida: arquitetura em camadas, isolamento por
usuária imposto na camada de dados e 181 testes passando. O problema é de **modelo**, não de
qualidade: o motor foi construído sobre **6 eixos numéricos (v1–v6, escala 0–10)**, e a
especificação pede **família + subfamília + características sensoriais + intensidade de doçura
baixa/média/alta**. Os dois modelos convivem, mas hoje só o numérico alimenta o motor.

| Verificação | Resultado |
|---|---|
| Backend `pytest` | **181 passaram, 2 puladas, 0 falhas** (145 s, SQLite em memória) |
| As 2 puladas | `tests/test_seguranca.py:129,154`: testes de concorrência que só rodam em MySQL real. **Não rodei.** |
| Frontend `vite build` | **OK** (379 kB JS, 26 kB CSS) |
| Testes de frontend | **Não existem** |
| `alembic check` / MySQL real | **Não verificado.** O `.env` aponta para `127.0.0.1:3307`; não me conectei ao banco |
| Git | Branch `main` **sem nenhum commit**; tudo está não rastreado |

## 2. Stack real (confirmada nos arquivos)

| Camada | O que existe | Confere com a intenção da cliente? |
|---|---|---|
| Backend | FastAPI 0.141, SQLAlchemy 2.0, Alembic (8 migrations), PyMySQL, PyJWT, bcrypt, Python 3.14 | Sim: FastAPI + MySQL |
| Banco | MySQL 8.0.16+ (CHECKs ativos); JSON nativo | Sim |
| Frontend | React 19, react-router 7, Vite 8, **JavaScript** (sem TypeScript), CSS próprio | Sim: React |
| Auth | Cadastro com código de 4 dígitos por e-mail, login JWT, redefinição de senha, troca de senha, foto (Cloudinary) | Existe e está testada; fora do escopo da especificação |
| Deploy | Vercel (2 projetos) + MySQL hospedado, ver `DEPLOY.md` | Documentado |

### Estrutura do backend (`backend/app`)

`core/` config, segurança, e-mail, rate limit · `db/` · `models/` (`knowledge.py` compartilhado,
`repertorio.py` pessoal, `conta.py`) · `schemas/` Pydantic · `repositories/` (**único lugar com SQL**) ·
`services/` regras de negócio · `engine/` motor com **funções puras** · `routers/` HTTP fino ·
`seed/` base de conhecimento.

Esta separação já cumpre a regra 8 (camadas) e boa parte da regra 1.

### Telas do frontend

| Rota | Tela | O que faz de verdade |
|---|---|---|
| `/` | Home | Contagem de essências, "cobertura de famílias", últimas criações |
| `/essencias` | Essências (abas: repertório, combinar, lacunas, referências) | CRUD do repertório, sugestão de classificação por nome, compatibilidade avulsa, lacunas, perfumes de referência |
| `/criacoes`, `/criacoes/:id` | Criações | Criar com direção (perfil, intenção ou referência), montar acorde com pesos, ver identidade, ajustar por movimento, comparar versões, ver testes |
| `/criacoes/:id/teste` | Registrar teste | Formulário do teste |
| `/perfis` | Perfis olfativos | **Questionário** (emoções, territórios, público) que gera um vetor-alvo |
| `/colecoes` | Coleções | Agrupa criações aprovadas |
| `/mapa` | Mapa | Pontos da aluna sobre territórios e famílias da base |
| `/conhecimento` | Conhecimento (Famílias, Notas, Relações, Territórios, Pirâmide) | Leitura da base |
| `/conta` | Conta | Nome, senha, foto |

## 3. Tabela de classificação

Esforço: **B**aixo (horas) · **M**édio (1–2 dias) · **A**lto (vários dias ou depende de conteúdo da cliente).

### 3.1 Infraestrutura e fundação

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Arquitetura em camadas | models / repositories / services / engine / routers separados; regra de negócio fora de componentes | **Manter** | Cumpre a regra 8 | — |
| Isolamento por usuária | `OwnedRepository` e `CriacaoChildRepository` só constroem com `user_id`; toda query parte de `_select()` já filtrado; filhos filtram por JOIN em `criacoes.user_id`; id alheio responde 404; `user_id` no corpo é rejeitado com 422 | **Manter** | Cumpre a regra 2 na camada de dados, não só na interface | — |
| Testes de isolamento | `test_isolamento.py`: B tenta ler, editar, apagar e usar como insumo registros de A, em essências, criações, acordes, testes, referências, perfis e coleções. Há teste no nível do repositório | **Manter** + **Completar** | Comprova o critério de aceite. Faltam rotas derivadas na bateria: `/mapa`, `/identidade`, `/caminhos`, `/criacoes/{id}/recomendacoes` | B |
| Autenticação e conta | Fluxo completo, com testes de segurança e limites de requisição | **Manter** | Fora do escopo; não tocar | — |
| Motor com funções puras | `engine/*` não conhece SQLAlchemy; parâmetros vêm de `knowledge_engine_rules` | **Manter** | Já atende "motor em módulo próprio, regras em dados" (Fase 4) | — |
| Migrations | 0001–0008, todas aditivas | **Manter** | Novas mudanças devem seguir aditivas (nada destrutivo) | — |
| Repositório Git | Sem commits | **Corrigir** | Sem baseline não há "um commit por fase" nem como reverter | B |

### 3.2 Fase 1 — Conhecimento olfativo

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Famílias | **6 de 14**: Cítrico, Aromático, Floral, Floral Branco, Amadeirado, Ambarado | **Completar** | Faltam Frutado, Verde, Aquático/Marinho, Gourmand, Especiado, Chipre, Almiscarado, Fougère, Couro | B |
| Hierarquia família → subfamília | `knowledge_families.parent_id`; "Floral Branco" já é subfamília de Floral | **Manter** + **Completar** | Modelo suporta; só há 1 subfamília. A organização das demais depende de conteúdo da cliente | M |
| Características sensoriais | `knowledge_descriptors` (3 itens: cremoso, luminoso, resinoso; `categoria` mistura "textura"/"temperatura") e `essencias.descritores` (lista JSON de **texto livre**) | **Completar** | Já é entidade separada das famílias. Faltam as 9 características da especificação como vocabulário controlado e uma validação que ligue o texto livre ao vocabulário | M |
| Intensidade da doçura (baixa/média/alta) | Só existe `v3` numérico 0–10 | **Desenvolver** | Falta o campo categórico (ver Dúvida 1) | B |
| Notas de referência | **5** notas, todas com `fonte = "ILUSTRATIVO — substituir pela base oficial SÉRENÉ"` | **Corrigir** | Regra 4. Ver Riscos 1 e 2 | M |
| Relações entre famílias | 5 relações no nível **família × família**; tipos `classico / complementar / atencao / contraste` | **Corrigir** + **Completar** | A especificação pede 4 classes diferentes (harmonia, complementaridade, contraste, combinação desafiadora) e relação por **matéria-prima**, não só por família | A |
| Territórios | 9 territórios no seed (acolhimento, delicadeza, frescor, alegria, amor, encanto, renovação, elegância, magnetismo) | **Corrigir** | A especificação cita 6 objetivos; **sensualidade não existe** e há 4 que ela não cita (ver Dúvida 3) | B |
| Pirâmide | `knowledge_composition_functions` (saída/coração/fundo) e `papel_tipico {saida, coracao, fundo}` em 0..1; `essencias.papel` pode ser nulo | **Manter** | Já é descritivo, com valores parciais, e aceita "sem papel definido". Revisar só os textos para não soarem como regra | B |
| Mapas de estudo | 3 mapas (conteúdo JSON) | **Manter**, **Corrigir** marcação | Conteúdo é ilustrativo e sem marca | B |
| Regras do motor em dados | 38 regras (`correlacao_territorio`, `vetor_movimento`, `peso_score`...) | **Manter** | Boa decisão; mas os **valores** são calibração ilustrativa sem marca (Risco 2) | — |
| Seed | `python -m app.seed`, idempotente, nunca escreve em tabelas pessoais | **Manter** | Cumpre a regra 1 | — |

### 3.3 Fase 2 — Cadastro individual de essências

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| CRUD do próprio repertório | `POST/GET/PUT/DELETE /essencias`, tela completa com confirmação de exclusão, cota de 1.000 por conta | **Manter** | Funciona e está testado | — |
| Campos de classificação | `familia` e `subfamilia` como **texto livre**, ligados à base por nome normalizado; **sem família secundária**; `descritores` múltiplos; `observacoes` | **Completar** | Falta família secundária. Texto livre com erro de digitação faz a família não ser reconhecida (Risco 6) | M |
| "Não sei ainda" | Campos nulos são aceitos em toda a API; a tela tem "Não sei ainda" na família, "Não sei" no tipo e por eixo; o motor trata `None` como desconhecido e não bloqueia | **Manter** | Cumpre o requisito. Revisar se os novos campos herdam o comportamento | B |
| Validação | Nome obrigatório (1–160), demais campos opcionais | **Manter** | Confere | — |
| Sugestão de classificação por nome | Devolve `sugestoes_referencia`; nada é aplicado sozinho | **Manter** na lógica, **Corrigir** o efeito | Ao aplicar, grava `origem="tecnico"` (rótulo "Ficha técnica") mesmo com fonte ilustrativa. Risco 1 | B |

### 3.4 Fase 3 — Perfil olfativo individual

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Perfil calculado **do repertório** (predominâncias, contagens, lacunas) | **Não existe.** `/perfis` é um **questionário** (emoções, territórios, público) que gera um vetor-alvo; não olha o repertório | **Desenvolver** | É uma funcionalidade nova. O questionário vira "direção de criação" e continua útil | M |
| Peças parciais | Gauge de "cobertura de famílias" na Home; `GET /essencias/lacunas` | **Manter** | Reaproveitáveis, mas sem contagem/proporção por família e característica | — |
| Lacunas | `engine/gaps.py`: família ausente, camada fraca, pouca amplitude | **Manter**, **Corrigir** conteúdo | Com 6 famílias, "família ausente" é pouco informativo; passa a valer com as 14 | B |

### 3.5 Fase 4 — Relações

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Motor de compatibilidade | `engine/compatibility.py`, módulo próprio, puro, pesos em dados; par sem família reconhecida → `score=None` ("não avaliada"); nunca declara incompatibilidade, só "atenção" | **Manter** | Boa base e já testada isoladamente | — |
| Classes e justificativa | Devolve score 0–100, tipo da relação e `explicacao` | **Completar** | Falta **"o que observar nos testes"**; falta a classificação nas 4 classes da especificação | M |
| Linguagem de hipótese | Alertas dizem "Atenção: …"; **não há aviso de que é hipótese de experimentação** | **Completar** | Regra 6; o score 0–100 passa impressão de medida (Risco 2) | B |
| Relação por matéria-prima | Só por família (com herança da família-mãe) | **Desenvolver** | A especificação pede considerar a matéria-prima específica | A |

### 3.6 Fase 5 — Construtor de acordes e fragrâncias

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Criação com direção | Origem: perfil, intenção (território/emoção/público) ou perfume de referência | **Manter** | Funciona e está testada | — |
| Recomendação de essências | Ranqueia **só** o repertório da aluna pela proximidade com o vetor-alvo | **Manter** | Cumpre "usar apenas as essências dela" | — |
| Montagem do acorde | **Manual**: a aluna escolhe 2–20 essências e pesos relativos (pouco/médio/bastante). Nunca porcentagem | **Manter** | Evita inventar concentração | — |
| Ajuste por movimento | "mais fresco / mais quente / mais doce…" sugere trocas só com o repertório; se não alcança, nomeia a **lacuna** (família), nunca uma essência que ela não tem | **Manter** | Bem alinhado | — |
| Tipo de produto | **Não existe** (nem na criação nem em outro lugar) | **Desenvolver** | Perfume, body splash, home spray, sabonete, vela... (Dúvida 4) | B |
| Objetivo olfativo | `criacoes.objetivo` é texto livre; "território" é outra lista | **Desenvolver** | A especificação lista doce, fresco, elegante, sensual, limpo, aconchegante, sofisticado (Dúvida 3) | B |
| Geração de propostas | **Não existe geração automática de combinações.** Há ranking e ajuste, mas não "gere propostas de acorde" | **Desenvolver** | Inclui regerar, trocar uma essência e comparar alternativas | A |
| Sugestão × fórmula técnica | Não há concentrações em lugar nenhum (bom). Mas a interface usa o termo **"Fórmula testada"** e `origem="tecnico"` | **Corrigir** | Regra 5. Entidade separada de fórmula com limites **de dado cadastrado** só se a cliente fornecer os dados | M |

### 3.7 Fase 6 — Criações, testes e versões

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Criação | nome, objetivo, status (rascunho/em_ajuste/aprovada/arquivada), data | **Manter** | — | — |
| Versionamento | `acordes` sem PUT nem DELETE; `unique(criacao_id, versao)`; snapshot do nome das essências; campo `motivo` | **Manter** | Já é imutável. A ligação com a versão anterior é implícita (sequência por criação) | — |
| Testes | `resultado_percebido`, persistência, intensidade, o que ficou bom, o que mudar, **nota 0–10**, próximo ajuste. Também versionados | **Manter** + **Completar** | Falta o feedback **gostei / precisa ajustar / não gostei** e separar **impressão inicial** de **evolução** | M |
| Comparar versões | Existe **só no frontend** (`ComparacaoVersoes`): itens, pesos, deltas de eixos e de compatibilidade, com o motivo | **Manter** + **Completar** | Falta ligar "qual foi o resultado" (o teste de cada versão) | B |
| Coleções | Agrupam criações aprovadas, com identidade geral | **Manter** | Fora da especificação; não reconstruir | — |
| Perfumes de referência | Bússola de direção; nunca estoque (tabela sem vetores) | **Manter** | — | — |

### 3.8 Fase 7 — Integração e testes

| Área / Item | Estado atual | Classificação | Justificativa | Esforço |
|---|---|---|---|---|
| Fluxo ponta a ponta | `test_fluxo.py`: essência → perfil (questionário) → criação → acorde → ajuste → teste → coleção, com usuária criada no teste | **Manter** + **Completar** | Não passa por "perfil do repertório → relações → construtor". Também depende de ids fixos de notas ilustrativas (`knowledge_note_id` 1, 3, 4), o que quebra quando a base oficial entrar | M |
| Testes do frontend | Inexistentes; só `vite build` | **Completar** | Mínimo: verificar a integração por API; teste de interface fica para depois | M |

## 4. Plano proposto por fase (se a auditoria for aprovada)

| Fase | O que entra | O que NÃO muda |
|---|---|---|
| 1 | Migration aditiva: 14 famílias, vocabulário de 9 características, campo de doçura, marca `exemplo` nas linhas do seed; separar exemplo de dado validado na UI e na API; revisar territórios | Os 6 eixos, o motor, o isolamento |
| 2 | Família secundária e características controladas no cadastro; teste de isolamento ampliado | CRUD, "Não sei ainda" |
| 3 | Novo módulo `engine/perfil_repertorio.py` + endpoint `GET /perfil-repertorio` + painel | Questionário em `/perfis` (vira "direção") |
| 4 | 4 classes, motivo e "o que observar", aviso de hipótese; dados das relações | `engine/compatibility.py` (estende, não reescreve) |
| 5 | Tipo de produto, objetivo, geração de propostas, regerar/trocar/comparar; trocar "Fórmula" por "Versão em teste" | Acorde com pesos relativos |
| 6 | Feedback categórico, impressão inicial × evolução, ligar teste ↔ comparação | Versionamento imutável |
| 7 | Teste ponta a ponta novo com a aluna fictícia | `test_fluxo.py` atual (mantido) |

Nenhum módulo precisa ser reescrito. Se algo mudar isso, paro e pergunto (protocolo).

---

## 5. Riscos encontrados

**Prioridade alta**

1. **Dado ilustrativo vira "ficha técnica" dentro do repertório da aluna.** Em
   `services/essencias_service.py` (`_aplicar_referencia`), ao confirmar uma sugestão, a essência
   recebe os vetores da nota e `origem="tecnico"`, `confianca` copiada da nota ("media"). A nota é
   ilustrativa. Resultado: um número inventado para o teste do motor aparece na essência dela como
   "Ficha técnica". Viola as regras 1 e 4.
2. **A marca "ilustrativo" é parcial.** Só as 5 notas têm `fonte = ILUSTRATIVO…`. Relações,
   territórios, mapas, descritores, as 38 regras e os pesos de compatibilidade **não têm marca**,
   e a tela de Conhecimento só exibe a de notas, no rodapé de cada cartão. As saídas do motor
   (score de compatibilidade 0–100, "proximidade 82%", "cobertura") dependem desses números e
   são apresentadas como medida. O próprio `tests/test_engine.py` admite "calibração ilustrativa atual".
3. **Vocabulário que contradiz a regra 5:** "Fórmula testada" (`CriacaoDetalhe.jsx:596`), "Ficha técnica"
   (`ClassificacaoEssencia.jsx`, origem), status "Aprovada" (sugere validação técnica).

**Prioridade média**

4. **Isolamento: sólido, com ressalvas.** Vive no código, não no banco (MySQL não tem RLS), mas está
   concentrado num único ponto e coberto por testes. Ressalvas: a bateria não cobre as rotas derivadas
   citadas em 3.1; qualquer consulta nova que use `select(Model)` direto num model pessoal quebraria a
   garantia (o `README` já avisa). Recomendo um teste que falhe se um repositório/serviço fizer isso.
5. **`backend/.env` tem credenciais reais (senha de app do Gmail) dentro de uma pasta sincronizada pelo
   OneDrive.** Está no `.gitignore` e não há commits, então não vazou pelo Git, mas está na nuvem da
   Microsoft. Não copiei nenhum valor secreto para este relatório.
6. **Família é texto livre.** "Citrico", "cítrico" e "Cítrico" casam (normalização), mas "Cítricos" ou um
   erro de digitação deixa `familia_chave = None`, e a compatibilidade vira "não avaliada" sem avisar
   a aluna do motivo. Piora quando houver 14 famílias.
7. **Testes só em SQLite.** Os CHECKs e o `FOR UPDATE` do MySQL real não foram exercitados nesta auditoria.
8. **Git sem commits.** Não há ponto de retorno.

**Prioridade baixa**

9. A maior parte do frontend (`Essencias.jsx` 864 linhas, `CriacaoDetalhe.jsx` 613) é grande; se crescer
   na Fase 5, precisa ser dividida em módulos (regra 7), mas sem reescrever.
10. `test_fluxo.py` usa ids fixos de notas do seed.

## 6. Divergências entre o código e a especificação

| # | Especificação | Código atual |
|---|---|---|
| 1 | Essência = família principal, secundária, subfamília, características, doçura baixa/média/alta | Essência = família e subfamília (texto livre) + **6 eixos numéricos** + tipo + papel + descritores. Sem secundária, sem doçura categórica |
| 2 | 14 famílias | 6 |
| 3 | Perfil calculado **do repertório** | "Perfil" é questionário que gera vetor-alvo; nenhum perfil olha as essências |
| 4 | Relações em 4 classes, por matéria-prima, com "o que observar" | 4 tipos diferentes, só por família, sem "o que observar" |
| 5 | Territórios: acolhimento, alegria, delicadeza, elegância, frescor, sensualidade | 9 territórios; sem sensualidade |
| 6 | Construtor: tipo de produto + objetivo olfativo + propostas geradas | Sem tipo de produto; objetivo é texto livre; sem geração |
| 7 | Feedback gostei / precisa ajustar / não gostei | Nota 0–10 |
| 8 | Impressão inicial e evolução da fragrância | Campo único `resultado_percebido` |
| 9 | Comparar versões: o que mudou **e qual foi o resultado** | Compara o que mudou; não liga ao resultado dos testes |
| 10 | Nada ilustrativo como validado | Marcação parcial e cópia como "ficha técnica" (Riscos 1–2) |
| 11 | Sem catálogo fechado obrigatório | **Conforme**: a aluna cadastra o que tem; a base só sugere |
| 12 | Repertório sempre começa vazio | **Conforme**: o seed nunca escreve em tabelas pessoais, e o teste de isolamento confirma que B vê `[]` |
| 13 | Código sem `TODO`/placeholder | **Conforme**: busca por TODO/FIXME/lorem sem ocorrências |

## 7. Dúvidas que precisam de decisão da cliente

1. **Modelo da essência.** Os 6 eixos numéricos (frio↔quente, profundidade, doçura 0–10, intensidade,
   complexidade, floralidade) são o que o motor usa hoje para recomendar, ajustar e calcular
   identidade. **Posso manter os eixos como camada interna e acrescentar por cima** família secundária,
   características controladas e doçura baixa/média/alta (derivada do eixo ou informada)? É o caminho
   que preserva tudo o que funciona. A alternativa, trocar o modelo, exigiria reescrever o motor.
   *Minha recomendação: manter e acrescentar.*
2. **Conteúdo oficial da base.** Vocês têm a base oficial (14 famílias com subfamílias, notas,
   relações, territórios, características)? As **estruturas** (14 famílias, 9 características) eu
   crio a partir da especificação. Já **notas e relações específicas** precisam de fonte de vocês;
   sem ela, ficam marcadas como "exemplo" e separadas do conteúdo validado, ou a base fica menor e
   honesta. Qual das duas?
3. **Territórios × objetivos.** A especificação cita 6 objetivos sensoriais, o construtor outros 7
   (doce, fresco, elegante, sensual, limpo, aconchegante, sofisticado), e o seed tem 9 territórios.
   Qual é a lista final e como se relacionam? Proposta: manter os 9, adicionar **sensualidade** e
   tratar os 7 do construtor como "objetivo olfativo" que aponta para um ou mais territórios.
4. **Tipos de produto e limites técnicos.** Quais são todos os "tipos previstos no projeto" além de
   perfume, body splash, home spray, sabonete e vela aromática? E haverá limites de concentração /
   segurança? Se sim, **quem fornece e valida** esses números? (Sem isso, o sistema não terá nenhum.)
5. **Baseline do Git.** O repositório não tem commits. Posso criar um **commit inicial com o estado
   atual (sem `.env`)** antes da Fase 1, para que cada fase seguinte seja um commit comparável?

*Não é bloqueante, decido por padrão se não houver objeção:* o feedback categórico (gostei / precisa
ajustar / não gostei) será **somado** à nota 0–10, não a substituirá.
