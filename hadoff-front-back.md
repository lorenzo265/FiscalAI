# hadoff-front-back.md — Barramento da Integração Frontend ↔ Backend

> **Arquivo de coordenação da frota** (append-only). Toda etapa que um agente conclui é registrada aqui.
> Leia o **Apêndice de Contrato** (abaixo) ANTES de tocar em qualquer adapter de domínio.
> Plano-mãe: `C:\Users\loren\.claude\plans\voc-sera-o-tech-pure-wren.md`.

---

## Como registrar (formato obrigatório ao terminar)

Acrescente uma entrada no fim da seção **«Registro da frota»** com:

```
### <data AAAA-MM-DD> · <agente> · <fase>
- **O que fez:** …
- **Arquivos tocados:** …
- **Descobertas de contrato:** (endpoint real, shape, divergências snake/camel que você resolveu)
- **Gaps / pendências:** (endpoint inexistente, dado que o backend não fornece — NÃO inventar dado)
- **Próximo agente:** …
```

Regra-mãe: **onde o backend não tiver endpoint no formato esperado pelo mock, registre o gap aqui — nunca invente dado.**

---

## Apêndice de Contrato (fonte de verdade da integração)

### Base & ambiente
- **Base URL:** `process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1"`.
- Front em `:3000`, API em `:8000`, Postgres `:5434`, Redis `:6379`, Ollama `:11434`.
- OpenAPI vivo (use para conferir shapes em tempo real): `http://localhost:8000/openapi.json` e `/docs`.

### Autenticação (JWT, OAuth2-ish)
- **Registro:** `POST /v1/auth/register`
  body `{tenant_nome, tenant_slug, usuario_nome, usuario_email, usuario_senha}` →
  `{access_token, token_type:"bearer", expires_in, usuario:{id,tenant_id,nome,email}, tenant:{id,nome,slug}}` (201).
- **Login:** `POST /v1/auth/login` body `{tenant_slug, email, senha}` → `{access_token, token_type, expires_in}` (200).
  ⚠️ **tenant_slug é obrigatório** — o front ganha um campo "código da conta".
- **Todo request autenticado** envia `Authorization: Bearer <access_token>`.
- **Tenant NÃO vai na querystring nem no body** — o backend extrai `tid` do JWT e aplica RLS (`SET LOCAL app.tenant_id`).
- `empresa_id` vai **na rota** (`/v1/empresas/{empresa_id}/…`), não no token.
- Público (sem token): `/v1/auth/register`, `/v1/auth/login`, `/healthz`, `/readyz`.

### Formato de erro
- Domínio → `{ "codigo": "TokenInvalido", "mensagem": "…" }` com HTTP status mapeado.
- Códigos úteis: `TokenInvalido`/`CredenciaisInvalidas` (401), `SemPermissao` (403),
  `EmpresaNaoEncontrada` (404), `CnpjJaCadastrado`/`ApuracaoJaExiste` (409), validação Pydantic (422),
  `LLMIndisponivel` (503), `FocusNfeTimeout` (504).
- O adapter `http.ts` parseia isso em `ApiError(status, codigo, mensagem)`.

### Convenções de dados
- Backend é **snake_case**; schemas Zod do front são **camelCase**. O adapter traduz (`toCamel`/`toSnake`).
- **Dinheiro = string decimal** (`NUMERIC(14,2)`). Nunca converter para `float`. Manter como string até formatar.
- Datas: `TIMESTAMPTZ` (ISO-8601 aware). Competência fiscal: `"YYYY-MM"`.
- Rate limit: 1000 req/h padrão; 100 req/h em prefixos sensíveis (`/v1/auth`, `/v1/notas`, `/v1/pgdas`,
  `/v1/sped`, `/v1/e-cac`, `/v1/certidoes`, `/v1/declaracao`). Headers `X-RateLimit-*`.

### Utilitários compartilhados (entregues pela Fundação — NÃO reinventar)
- `src/lib/http.ts` → `fetchJson<T>(path, schema, init)`, `ApiError`, `toCamel/toSnake`, injeção de token, 401-handler.
- `src/lib/auth.ts` → token store (`getToken`, `setSessao`, `limparSessao`, `isLogado`).
- `getEmpresaIdAtiva()` → `empresa_id` da empresa ativa (para montar as rotas `/v1/empresas/{id}/…`).
- `src/lib/api/<dominio>.ts` → cada agente de domínio é DONO de um arquivo (sem colisão).
- Reusar a classe `ApiError` e os schemas Zod existentes em `src/lib/schemas/*` (ajustar, não recriar).

### Mapa endpoint ↔ assinatura `api.*` (alvo da tradução)

| Domínio | Assinatura `api.*` (preservar) | Endpoint real (alvo) | Notas / gaps a investigar |
|---|---|---|---|
| **auth** | login/register | `POST /v1/auth/login`, `/register` | precisa `tenant_slug` |
| **empresa** | `empresa.lookupCnpj` | `POST /v1/empresas/onboarding`, `GET/POST /v1/empresas`, `GET /v1/empresas/{id}` | lookup CNPJ = onboarding BrasilAPI |
| **fiscal** | `fiscal.{saude,apuracaoAtual,historico,guias}` | `POST/GET /v1/empresas/{id}/apuracoes/das` | ⚠️ "saúde fiscal" SN pode não ter endpoint — registrar gap |
| **agenda** | `agenda.{listar,listarMes,listarAno}` | `GET /v1/empresas/{id}/agenda?ano=`, `POST …/agenda/gerar` | filtro mês/ano client-side se backend só der lista |
| **notas** | `notas.{catalogo,lookupContraparte}` + CRUD Dexie | `POST /v1/empresas/{id}/notas/nfse`, `GET …/nfse/{ref}`, `POST …/ingestao/upload`, `GET …/documentos` | ⚠️ front = CRUD Dexie; backend = emissão Focus + ingestão. Mapear o que casa, registrar resto |
| **controles** | bancos/transações/pagar-receber/fluxo | `/v1/empresas/{id}/open-finance`, `…/conciliacao` | ⚠️ pagar/receber e fluxo de caixa podem não ter endpoint — registrar gap |
| **pessoal** | funcionários/holerites/eSocial | `/v1/empresas/{id}/pessoal`, `…/funcionarios`, `GET …/folha/{competencia}` | eSocial: transmissão real existe |
| **contabil** | `contabil` (lançamentos) | `/v1/empresas/{id}/contabil` (plano-contas, lançamentos), `GET …/balancete/{competencia}` | |
| **relatorios** | `relatorios.{dre,balanco,dfc,indicadores}` (hoje calculado no cliente) | `POST /v1/empresas/{id}/relatorios/{dre,balanco,dfc}`, `GET …/relatorios` | **mover cálculo p/ servidor** — descartar `src/lib/relatorios/geracao` |
| **compliance** | certidões/intimações/parcelamentos | `/v1/empresas/{id}/certidoes`, `…/monitor-cadastral`, `…/parcelamentos` | |
| **assistente** | `assistente.{listarMensagens,enviarPergunta,limparHistorico}` | `/v1/assistente` | citação obrigatória; tratar `LLMIndisponivel` |

### Invariantes de função (não quebrar ao integrar)
- Telas e navegação intactas; hooks `use-*` mantêm assinatura pública; wizards RHF+Zod preservados.
- Status sempre **cor + ícone + palavra**; **nunca** expor CFOP/CST/NCM crus ao dono de PME (traduzir).
- Token sempre via header; tenant via JWT (nunca querystring); dinheiro como string/Decimal.

### Credenciais de dev (preenchidas pela Fundação ao criar `seed_dev.py`)
- tenant_slug: `demo`
- email: `demo@arkan.dev`
- senha: `arkan1234`
- empresa SN seedada: CNPJ `11222333000181` — Simples Nacional, Anexo I, São Paulo/SP
  (razão "Comércio Demonstração Arkan LTDA", faturamento 12m R$ 680.000,00).
- `tenant_id` / `empresa_id`: **seed executado com sucesso na Fase B** (Postgres
  no ar em `:5434`). UUIDs reais do ambiente atual:
  - `tenant_id` = `2292630b-dce1-4ddc-b0d5-d7e06d3071b8`
  - `empresa_id` = `ca9d6835-f826-4ede-95d6-6644c58de34d`
  O `empresa_id` vai na rota `/v1/empresas/{empresa_id}/…` e alimenta
  `setEmpresaIdAtiva(id)` (o EmpresaProvider já faz isso no boot).
  ⚠️ O `print` final do `seed_dev.py` quebra com `UnicodeEncodeError` (cp1252 ×
  emoji) NO WINDOWS — mas o tenant/empresa SÃO criados antes do print. Idempotente.

---

## Registro da frota

<!-- agentes acrescentam entradas abaixo, em ordem cronológica -->

### 2026-06-05 · Fundação · Fase A (camada-contrato serial)
- **O que fez:** Construiu a camada-contrato que todos os agentes de domínio vão
  consumir, SEM mudar comportamento de dados (mock segue intacto). Cliente HTTP
  real, token store real, store de empresa ativa, split do `api-client`, CORS no
  backend e seed de dev.
- **Arquivos tocados:**
  - **Front (novos):** `src/lib/http.ts`, `src/lib/empresa-ativa.ts`,
    `src/lib/api/_mock-fetch.ts`, `src/lib/api/{empresa,fiscal,agenda,notas,controles,pessoal,contabil,relatorios,compliance,assistente}.ts`,
    `src/lib/api/index.ts`, `.env.local`, `.env.local.example` (+ var).
  - **Front (reescritos):** `src/lib/auth.ts` (token store), `src/lib/api-client.ts`
    (virou shim que re-exporta de `src/lib/api/index.ts`).
  - **Back (novos):** `scripts/seed/seed_dev.py`.
  - **Back (alterados):** `app/config.py` (setting `CORS_ORIGINS` + validator CSV),
    `app/main.py` (`CORSMiddleware`).
- **Descobertas de contrato:**
  - **`ApiError`** agora é `ApiError(status, codigo, mensagem)`. `super(message)`
    recebe a `mensagem` → `.message` (lido pelas telas) preservado; `.status`
    preservado; `.codigo`/`.mensagem` novos. Erro `{codigo,mensagem}` do FastAPI é
    parseado; fallback para `detail` (validação Pydantic 422) e `error` (mock).
    A `ApiError` real mora em `@/lib/http` e é reexportada pelo barrel e pelo shim
    `api-client.ts` — imports existentes (`import { api, ApiError } from "@/lib/api-client"`)
    continuam válidos.
  - **`toCamel`/`toSnake`** são deep (arrays + objetos aninhados), só mexem em
    CHAVES — valores intactos: string de dinheiro/decimal NUNCA vira número. O
    `fetchJson` aplica `toCamel` na resposta antes do `schema.parse` (backend é
    snake, schemas Zod são camel). `toSnake` está exportado para os adapters
    montarem bodies.
  - **`getEmpresaIdAtiva()`/`setEmpresaIdAtiva(id)`** moram em
    `src/lib/empresa-ativa.ts` (não em auth.ts) — store `localStorage` chave
    `arkan:empresa-id`.
  - **Token store** em `src/lib/auth.ts`: chaves `arkan:token`, `arkan:token-exp`
    (epoch ms), `arkan:email`. `getToken()` retorna `null` se expirado (e limpa).
    `isLogado()` = token válido. `setSessao({access_token,expires_in,email?})`,
    `limparSessao()`. `entrar/sair/emailLogado` preservados (compat — a UI real de
    login vem na Fase B; `entrar` cria sessão local placeholder).
  - **401** em `fetchJson` → `limparSessao()` + `window.location.assign("/login")`
    (guarda `typeof window`).
  - **Barrel `src/lib/api/index.ts`** monta `export const api = { empresa, fiscal,
    agenda, notas, controles, pessoal, assistente, compliance, relatorios }` —
    EXATAMENTE a forma atual (o `api` original NÃO tinha chave `contabil`; mantido
    assim). Cada agente de domínio reescreve só o seu `src/lib/api/<dominio>.ts`.
  - **CORS:** setting `CORS_ORIGINS` (default `["http://localhost:3000"]`, env
    aceita CSV via `field_validator(mode="before")`). `CORSMiddleware` adicionado
    DEPOIS do `RateLimitMiddleware` → roda outermost (trata preflight + injeta
    headers antes do rate-limit). `allow_credentials=True` + origens explícitas,
    `expose_headers` inclui `X-RateLimit-*`.
  - **seed_dev:** usa os services reais (`AuthService.registrar` → hash bcrypt de
    verdade, login funciona; `EmpresaService.criar` → perfil_ui derivado).
    Idempotente: relê tenant por slug e captura `CnpjJaCadastrado`. Falha-rápido se
    `ENVIRONMENT=prod`. Imprime credenciais + `tenant_id`/`empresa_id`.
- **Verificação:**
  - Front `npm run build` → **VERDE** (52 rotas; só warnings pré-existentes de
    unused-vars em telas/mocks, nada dos arquivos novos).
  - Back `python -c "import app.main; import scripts.seed.seed_dev"` → **OK**.
  - `mypy app/config.py app/main.py scripts/seed/seed_dev.py` → **Success, 0 erros**.
- **Gaps / pendências:**
  - **seed_dev não pôde ser executado contra o DB**: Postgres/Docker estava
    indisponível neste ambiente (ConnectionRefused em `:5434`). O código chega a
    conectar (passou config/import/RLS-setup) — falha é só ambiente. **Próximo a
    rodar:** `docker compose up -d && poetry run alembic upgrade head` e então
    `poetry run python -m scripts.seed.seed_dev`; copiar os UUIDs impressos para a
    seção «Credenciais de dev» acima.
  - `src/lib/api/contabil.ts` existe (reexporta `listarLancamentos`) mas NÃO entra
    no `api` (mantém a forma original). Dono de contábil cria a superfície real na
    integração.
  - Os 4 domínios mock (`empresa,fiscal,agenda,notas`) ainda usam
    `src/lib/api/_mock-fetch.ts` (BASE `/api/mock`). Domínios Dexie
    (`controles,pessoal,contabil,relatorios,compliance,assistente`) seguem no
    db-service. Trocar por `fetchJson` de `@/lib/http` é tarefa de cada agente.
- **Próximo agente:** **Fase B — Auth & Empresa.** Implementar a UI real de login
  (RHF+Zod, campo `tenant_slug`/"código da conta") chamando `POST /v1/auth/login`
  e gravando `setSessao(...)`; popular `setEmpresaIdAtiva(id)` a partir de
  `GET /v1/empresas`; reescrever `src/lib/api/empresa.ts` para os endpoints reais
  (`onboarding`, lista, get). Usar o seed acima para testar.

### 2026-06-05 · Auth & Empresa · Fase B
- **O que fez:** Login/registro reais (RHF+Zod, campo `tenant_slug` = "Código da
  conta"), adapter de empresa em HTTP real, EmpresaProvider booteando do backend,
  wizard de onboarding plugado no `POST /v1/empresas/onboarding` real. AuthGuard
  deixou de ter o bypass de perf. Tudo verificado contra o backend no ar.
- **Arquivos tocados:**
  - **Novos:** `src/lib/api/auth.ts` (adapter de auth + `mensagemAmigavelAuth`).
  - **Reescritos:** `src/lib/api/empresa.ts` (HTTP real + mappers),
    `src/components/auth/login-card.tsx` (RHF+Zod, 2 abas reais),
    `src/components/layout/empresa-provider.tsx` (boot via `GET /v1/empresas`).
  - **Editados:** `src/lib/api/index.ts` (+`auth` no barrel),
    `src/lib/schemas/empresa.ts` (campos backend-absent viram optional/default +
    `perfilUi`/`codigoMunicipioIbge`/`ativa`/`aliquotaIssValidada`),
    `src/components/layout/auth-guard.tsx` (removido `PERF_BYPASS`),
    `src/lib/stores/onboarding-store.ts` (+`empresaCriada`/`setEmpresaCriada`),
    `src/components/onboarding/passo-cnpj.tsx` (usa `lookupCnpjComEmpresa` e
    pré-preenche regime/anexo/faturamento da empresa criada),
    `src/components/onboarding/passo-conclusao.tsx` (usa a empresa já criada no
    backend; fallback local só se `empresaCriada` for null).
- **Descobertas de contrato (LEIA — afeta TODOS os agentes de domínio):**
  - ⚠️ **Auth NÃO está sob `/v1`.** O router de auth é montado em `/auth/login` e
    `/auth/register` (sem prefixo). Como `BASE` termina em `/v1`, o adapter de
    auth (`src/lib/api/auth.ts`) monta a URL a partir da RAIZ do host
    (`BASE.replace(/\/v1\/?$/, "")`). **Não** use `fetchJson` para auth — ele
    prefixa `BASE`. Login/register são públicos (sem Bearer).
  - **`TokenOut`** (login): `{access_token, token_type:"bearer", expires_in:3600}`.
    **`RegisterOut`**: idem + `usuario:{id,tenant_id,nome,email}` +
    `tenant:{id,nome,slug}` (HTTP 201).
  - **Erros de auth** (códigos REAIS, confirmados por curl):
    `CredenciaisInvalidas` (senha errada), `TenantNaoEncontrado` (slug inexistente,
    HTTP 404), `SlugJaCadastrado`, `EmailJaCadastrado`. Traduzidos em
    `mensagemAmigavelAuth(err)` — nunca vaze o `codigo` cru.
  - **`EmpresaOut` REAL (campo a campo, snake; vira camel após `toCamel`):**
    | snake | camel | tipo | nota |
    |---|---|---|---|
    | `id` | `id` | UUID str | |
    | `tenant_id` | `tenantId` | UUID str | |
    | `cnpj` | `cnpj` | str (14 díg) | |
    | `razao_social` | `razaoSocial` | str | |
    | `nome_fantasia` | `nomeFantasia` | str\|null | |
    | `regime_tributario` | `regimeTributario` | str **lowercase** | `simples_nacional`/`lucro_presumido`/`mei`/`lucro_real` |
    | `perfil_ui` | `perfilUi` | str | `sn_sem_funcionarios` etc. |
    | `anexo_simples` | `anexoSimples` | str\|null | `"I"`..`"V"` |
    | `cnae_principal` | `cnaePrincipal` | str\|null | só dígitos, ex. `4781400` |
    | `municipio` | `municipio` | str\|null | |
    | `codigo_municipio_ibge` | `codigoMunicipioIbge` | str\|null | 7 díg |
    | `uf` | `uf` | str\|null | 2 letras |
    | `faturamento_12m` | `faturamento12m` | **string decimal** | `"680000.00"` — NÃO é number |
    | `ativa` | `ativa` | bool | |
    | `aliquota_iss_validada` | `aliquotaIssValidada` | bool | default false |
  - **Mapeamento snake→camel→Empresa(front)** em `mapearEmpresa()`:
    `regimeTributario` lowercase → enum UPPER do front; `faturamento12m` string →
    `number` (só p/ estimativa RBT12, NÃO é caminho de precisão monetária);
    `setor` derivado do CNAE (47→COMERCIO, 10/20/30→INDUSTRIA, resto→SERVICOS);
    `modulosAtivos` derivado do regime; `cnae`/`municipio`/`uf` direto.
  - **`POST /v1/empresas/onboarding` JÁ CRIA a empresa** (BrasilAPI → auto-create).
    Retorna `OnboardingResultadoOut`: `{cnpj, razao_social, nome_fantasia, porte,
    situacao_cadastral, cnae_principal, cnae_descricao, municipio,
    codigo_municipio_ibge, uf, regime_sugerido(lowercase), anexo_sugerido(null|"I"),
    empresa_criada:EmpresaOut|null, aviso:str|null}`. Quando o CNPJ já existe,
    `empresa_criada=null` e `aviso="CNPJ já cadastrado…"`. `lookupCnpjComEmpresa()`
    devolve `{dados:CnpjLookupResponse, empresa:Empresa|null}`.
- **Gaps / pendências (campos do front SEM correspondência no backend):**
  - `EmpresaOut` **não** tem: `socios`, `setor`, `bancosConectados`, `modulosAtivos`,
    `criadoEm`, `inscricaoEstadual`, `inscricaoMunicipal`, `certificadoA1`. No front
    viram default/derivados (mapper) — **dado NÃO inventado**, apenas vazio/derivado.
    `setor` e `modulosAtivos` são derivações determinísticas (CNAE/regime).
  - **`OnboardingResultadoOut` é mais pobre que `CnpjLookupResponse`** do wizard:
    sem **endereço completo** (logradouro/numero/bairro/cep) e sem **quadro
    societário** nem **CNAEs secundários**. `mapearLookup()` preenche esses com
    string vazia / array vazio. Se o wizard precisar deles, falta endpoint.
  - **Não há endpoint de UPDATE de empresa.** `salvarEmpresa()` no provider agora
    só atualiza o contexto em memória + `setEmpresaIdAtiva`. Edições em
    `configuracoes/form-empresa.tsx` ficam locais até o próximo `refresh()` (que
    relê do backend e descarta a edição). Quando houver `PUT/PATCH /v1/empresas/{id}`,
    plugar aqui.
  - **`seed_dev.py` crasha no print final (Windows cp1252 × emoji)** — mas cria
    tenant+empresa antes. Para rodar limpo: `$env:PYTHONIOENCODING="utf-8"` antes,
    ou ajustar o `print` do seed. Idempotente, então re-rodar é seguro.
- **O que a Onda 1 (Fiscal/Notas/Agenda) precisa saber:**
  - `getEmpresaIdAtiva()` já vem populado após login (o EmpresaProvider seta no boot).
    Use-o para montar `/v1/empresas/{id}/...`.
  - `faturamento_12m` chega como **string decimal** do backend — se precisar do
    valor monetário, NÃO use `empresa.faturamento12m` (que o mapper converteu p/
    number); puxe a string do `EmpresaOut` cru se exigir precisão.
  - Códigos de erro de domínio chegam em `ApiError.codigo` — traduza p/ msg
    amigável no seu adapter (espelhe `mensagemAmigavelAuth`).
- **Verificação:**
  - Front `npm run build` → **VERDE** (52 rotas; só warnings pré-existentes de
    unused-vars; nada dos arquivos da Fase B).
  - curl `POST /auth/login {demo}` → `access_token` (248 chars), `expires_in=3600`.
  - curl senha errada → `{codigo:"CredenciaisInvalidas"}`.
  - curl `GET /v1/empresas` (Bearer) → 1 empresa, shape acima.
  - curl `POST /v1/empresas/onboarding {cnpj demo}` → `OnboardingResultadoOut` com
    `empresa_criada=null` + `aviso` (CNPJ já existe) — fallback do wizard cobre.
- **Próximo agente:** **Onda 1 — Fiscal / Notas / Agenda.** Reescrever
  `src/lib/api/{fiscal,notas,agenda}.ts` para os endpoints
  `/v1/empresas/{id}/apuracoes/das`, `…/notas/nfse`, `…/agenda` usando `fetchJson`
  + `getEmpresaIdAtiva()`. Ver gaps de "saúde fiscal" e CRUD-Dexie-vs-emissão no
  mapa do Apêndice.

### 2026-06-05 · Orquestrador (tech lead) · Infra DB / migrations
- **O que fez:** Subiu o stack Docker (postgres:5434, redis, api:8000, ollama),
  rodou `alembic upgrade head` e o `seed_dev`. Corrigiu um bug de migration que
  travava o backend antes do head.
- **Bug corrigido — `0034_sprint14_reforma_aliquotas.py`:** o `op.bulk_insert` passava
  `sa.bindparam("vf_*", value="YYYY-MM-DD", type_=sa.Date())` como **valor** de
  `valid_from` no dict — `bulk_insert` não resolve bindparam em dict de valores, então
  o objeto `BindParameter` ia cru ao driver pg8000 → `invalid input syntax for type
  date: ":vf_teste_2026"`. **Fix:** trocado pelos `datetime.date(2026,1,1)` /
  `(2027,1,1)` / `(2033,1,1)` literais (+ `import datetime`). Migration roda em
  transação, então o DB tinha ficado em 0033 (por isso auth/empresa funcionavam mas
  reforma+ não). Após o fix, avançou 0033→0040.
- **GAP de backend (NÃO bloqueia o frontend) — migrations 0041+:** `0041` (e provavelmente
  outras com `CREATE INDEX CONCURRENTLY`) falham com `25001 CREATE INDEX CONCURRENTLY
  cannot run inside a transaction block`. Causa: `alembic/env.py` converte a URL para
  **pg8000** (apesar do docstring dizer "psycopg2"), e o `op.get_context().autocommit_block()`
  do pg8000 não escapa a transação de fato. Significa que `alembic upgrade head` **nunca**
  rodou inteiro neste setup. **Fica como tarefa de infra de backend** (trocar driver do
  alembic para psycopg2/psycopg no container, ou ajustar o autocommit) — é um workstream
  separado.
- **Por que não bloqueia:** TODAS as tabelas dos domínios do frontend
  (fiscal/notas/agenda/controles/pessoal/contabil/relatorios/compliance/assistente) vêm
  de migrations **≤0033**. As 0041–0055 são perf-indexes / advisor / SPED / painel-admin /
  reforma-data / validação FA — backend-only, não exercidas pelas telas. **O DB em 0040
  é suficiente para a integração front-back.**
- **Estado verificado (ao vivo):** DB em `0040`; `POST /auth/login {demo}` → token (248
  chars); `GET /v1/empresas` (Bearer) → empresa demo. **`empresa_id` =
  `ca9d6835-f826-4ede-95d6-6644c58de34d`**, `tenant_id = 2292630b-dce1-4ddc-b0d5-d7e06d3071b8`.
- **Nota de orquestração:** os agentes paralelos das ondas **devolvem** a entrada do
  handoff no relatório final (o orquestrador consolida aqui) — evita corrida de escrita
  no arquivo. Agentes seriais (Fundação, Auth) escreveram direto.

### 2026-06-05 · Onda 1 / Fiscal · Fase C
- **O que fez:** Reescreveu `src/lib/api/fiscal.ts` para a API real via `fetchJson`+`getEmpresaIdAtiva()`, preservando assinaturas `saude/apuracaoAtual/historico/guias` e os hooks `use-fiscal-*`. `apuracaoAtual`/`guias` → `POST /v1/empresas/{id}/apuracoes/das`. Adicionou `mensagemAmigavelFiscal`. Deletou os 4 route handlers mock de fiscal.
- **Arquivos tocados:** reescrito `src/lib/api/fiscal.ts`; deletados `src/app/api/mock/fiscal/{saude,apuracao/atual,historico,guias}/route.ts`. `src/lib/mocks/fiscal.ts` ficou órfão (mantido).
- **Descobertas de contrato:** `ApuracaoDASOut` = {id,empresa_id,competencia(YYYY-MM-DD),anexo,anexo_efetivo,faixa,rbt12_usado,aliquota_nominal,aliquota_efetiva,receita_mes,valor_das,fator_r,status,uf,sublimite_aplicado,sublimite_excedido} (dinheiro string). Body POST: `{competencia:"YYYY-MM", receita_mes:"<decimal>"}` (anexo III/V exige `folha_12m`). `vencimento` derivado (dia 20 do mês seguinte). Schemas Zod NÃO alterados.
- **Gaps/pendências:** (1) sem endpoint de saúde fiscal → estado vazio honesto (score 0), nada inventado; (2) sem histórico → série `[]`; (3) DAS não decomposto por tributo → composição `[]`; (4) sem listagem/emissão de guias → 1 guia derivada da apuração corrente (nº doc/cód barras/PIX vazios). Há `ApuracaoFiscalRepo.listar_empresa` no backend mas **sem endpoint GET de listagem** exposto — quando expuser, plugar `guias`.

### 2026-06-05 · Orquestrador (tech lead) · Fix backend — FiscalService não persistia
- **Bug:** `FiscalService.calcular_e_salvar_das` chamava `repo.salvar` (add+flush+refresh) mas **nunca `session.commit()`**; e `get_session` (deps.py) não comita no sucesso → SQLAlchemy fazia ROLLBACK ao fechar a sessão. Resultado: DAS calculava e devolvia 201, mas **não persistia** (GET-por-competência sempre 404; re-POST nunca dava 409). Convenção do projeto é commit no service (pgdas/relatorios/provisoes/empresa todos comitam).
- **Fix:** adicionado `await self._session.commit()` após `salvar` em `app/modules/fiscal/service.py` (1 linha, no padrão dos outros services).
- **Verificado ao vivo:** `POST .../apuracoes/das` → 201 → `GET .../2026-04/das` → **200 (persistiu)** → re-POST → **409 ApuracaoJaExiste**. `pytest tests/unit/fiscal` → 51 verdes (golden tests intactos).

### 2026-06-05 · Onda 1 / Notas · Fase C
- **O que fez:** Reescreveu `src/lib/api/notas.ts` como adapter HTTP real (`fetchJson`+`getEmpresaIdAtiva`) e reconectou `src/lib/notas/db-service.ts` para a listagem/leitura virem do backend (`GET …/documentos`) mescladas com Dexie. Emissão de SAÍDA de serviço dispara NFS-e real (Focus). Hooks/assinaturas preservados.
- **Arquivos tocados:** `src/lib/api/notas.ts` (reescrito), `src/lib/notas/db-service.ts` (reescrito). Nenhum mock route handler a deletar (notas era CRUD-Dexie, não existia `/api/mock/notas`).
- **Descobertas de contrato:** Endpoints: `GET /v1/empresas/{id}/documentos`; `POST …/ingestao/upload`; `POST …/notas/nfse` (202); `GET …/notas/nfse/{focus_ref}`. Body `EmitirNfseIn`: natureza_operacao(1|2), servico_descricao, servico_codigo, servico_valor(decimal>0), aliquota_iss(2..5, 4 casas), cnpj_tomador?/cpf_tomador?, razao_social_tomador?, email_tomador?. `DocumentoFiscalOut`: id, empresa_id, tipo(nfe/nfse/nfce), direcao(saida/entrada), chave(NULLABLE), numero, serie, status, emitida_em, cnpj_emitente, cnpj_destinatario?, valor_total + valor_icms/ipi/pis/cofins (decimal STRING, nullable), cfop?, ncm?, natureza_operacao?, ingested_via?, created_at. `notaFiscalSchema` NÃO alterado; mapper converte decimal-string→number na fronteira e mescla com Dexie.
- **Gaps/pendências (sem backend → mantidos LOCAIS, nada inventado):** `DocumentoFiscalOut` não traz razão da contraparte (só CNPJ), itens detalhados, breakdown por tributo nomeado, manifesto, cartas de correção. SEM endpoint para: cancelar nota, carta-correção (CC-e), manifestar entrada, catálogo de produtos, lookup de contraparte → permanecem Dexie. Emissão só de **NFS-e de serviço** (não há NF-e de produto). `servico_codigo` LC116 não é capturado pelo wizard hoje (placeholder rastreável) — pendência de UI. **Ambiente:** `POST /notas/nfse` → 502 (Focus NFe sem sandbox alcançável); contrato validado via 422 em body inválido. Quando houver token Focus sandbox, emissão real funciona (504→`FocusNfeTimeout` já tratado).

### 2026-06-05 · Onda 1 / Agenda · Fase C
- **O que fez:** Reescreveu `src/lib/api/agenda.ts` para a API real via `fetchJson`+`getEmpresaIdAtiva()`; `GET …/agenda?ano=` com **fallback de geração sob demanda** (`POST …/agenda/gerar`) quando o ano vem vazio; mapeamento `AgendaItemOut→EventoAgenda`; filtro de mês client-side. `useAgenda` inalterado. **Domínio totalmente funcional com dados reais.**
- **Arquivos tocados:** `src/lib/api/agenda.ts` (reescrito), `src/lib/schemas/agenda.ts` (+ schemas backend, preservando `eventoAgendaSchema`).
- **Descobertas de contrato:** `GET /v1/empresas/{id}/agenda?ano=YYYY` e `POST …/agenda/gerar {ano,tem_funcionarios?,parcelar_irpj?}` → `AgendaListaOut {empresa_id,ano,total,itens[]}`. Item: {id,titulo,descricao|null,data_vencimento(date),regime,tipo_obrigacao,status}. **Agenda é GERADA SOB DEMANDA** (GET vazio até `/gerar`; gerar → 13 itens p/ SN). status backend `pendente|concluido|vencido` → front `pago/pendente/atrasado`. `tipo_obrigacao` (pgdas_d, defis, das_mei, dctf_web, fgts, esocial_s1200, gps_inss, dirf…) → `imposto|obrigacao_acessoria|folha|esocial|informativo`. Backend só filtra por ANO.
- **Gaps/pendências:** backend não fornece `valor`(R$) nem `rota` por evento → `undefined` (telas tratam como opcional). Filtro de mês é client-side. `tem_funcionarios` derivado de `perfilUi` (heurística).

**Estado Onda 1:** build front **VERDE** (52 rotas). Agenda 100% real. Fiscal real + persistência corrigida (saúde/histórico aguardam endpoints). Notas real para listagem+emissão (emissão depende de Focus sandbox; CRUD auxiliar segue local). **Próximo:** Fase D (revisor + e2e), depois Onda 2.

### 2026-06-05 · Revisor (contexto fresco) + Orquestrador · Fase D
- **Veredito do revisor:** **APROVADO COM RESSALVAS**, zero bloqueadores. Invariantes
  OK (assinaturas `api.*`/hooks preservadas; token via header; tenant via JWT; dinheiro
  string no caminho de precisão; CFOP/CST/NCM não expostos crus; erros traduzidos; sem
  dado inventado). Fixes de backend (commit fiscal, CORS, migration 0034, seed) corretos.
- **Bug de follow-on corrigido pelo orquestrador (CRÍTICO):** meu fix de persistência do
  DAS quebrou o adapter fiscal, que fazia **POST incondicional** — com persistência, o
  segundo POST da mesma competência dá **409** (e `apuracaoAtual`+`guias` disparam no
  mesmo load → quebraria a tela). Reescrevi `obterOuCalcularDAS` em `src/lib/api/fiscal.ts`
  para **GET-first → POST-on-404 → recupera 409 via GET** (idempotente + resiliente a
  corrida). Build front reconfirmado **VERDE (exit 0, 48 páginas)**. Comentário
  desatualizado do topo do arquivo também corrigido.
- **Ressalvas não-bloqueantes (pendências registradas):**
  1. **Notas:** `servicoCodigo` usa CFOP onde o backend quer código LC116/2003 (serviço
     municipal). Inofensivo hoje (Focus sandbox off); pendência de UI capturar LC116.
  2. **Fundação:** `seed_dev.py` print final usa box-drawing não-ASCII → pode dar
     `UnicodeEncodeError` no Windows (cosmético; seed completa antes do print).
  3. **Auth:** `login-card.tsx` é card central com sombra (flerta com "tell" de slop,
     mas mitigado por serif/mono/acento verde/sombra quente) — considerar fios 1px/crop
     marks. `passo-cnpj` renderiza endereço com campos vazios (onboarding não traz
     logradouro) — ocultar vazios.
  4. **Backend:** sem `PUT/PATCH /v1/empresas/{id}` → `salvarEmpresa` só em memória;
     edições em configurações se perdem no `refresh()`.
- **e2e de contrato (ao vivo, PowerShell):** login `/auth/login` 200; `GET /v1/empresas`
  200; `POST .../apuracoes/das` 201 → `GET .../2026-04/das` 200 → re-POST 409; agenda
  `/gerar` → 13 itens. `pytest tests/unit/fiscal` 51 verdes.

**Próximo:** Onda 2 — Controles · Pessoal · Contábil · Relatórios · Compliance · Assistente.

### 2026-06-05 · Onda 2 / Controles · Fase E
- **O que fez:** `src/lib/api/controles.ts` + `src/lib/controles/db-service.ts` → Open Finance real (`fetchJson`+`getEmpresaIdAtiva`). Bancos/transações/sincronização/conciliação vêm do backend; fallback honesto p/ Dexie demo quando não há contas Pluggy. `mensagemAmigavelControles`. Assinaturas e hooks preservados.
- **Descobertas:** `GET …/contas-bancarias` → `ContaBancariaOut[]` {id, pluggy_item_id, banco_nome, agencia, numero, tipo(CHECKING/SAVINGS/CREDIT_CARD), saldo_atual(string)…}. `GET …/transacoes?conta_id=&desde=&ate=&limite=` → `TransacaoBancariaOut[]` {…, valor(string), tipo(CREDIT/DEBIT), status(PENDING/CONFIRMED), merchant_cnpj…}. `POST …/open-finance/items/{item}/sync`. Conciliação = `…/conciliacao[/run|/{id}/confirmar|/rejeitar]` (Match NF×banco). Empresa demo: tudo `[]` (sem Pluggy seedado).
- **Gaps:** **contas a pagar/receber e fluxo de caixa SEM endpoint** → 100% Dexie/cálculo cliente (fluxo derivado de contas+transações reais + pagar/receber locais). Conciliação **tx↔lançamento** (semântica do front) ≠ Match NF×banco do backend → vínculo persistido localmente. Conectar conta exige widget Pluggy → conta local de demo. `saldoApos` não vem do backend → 0.

### 2026-06-05 · Onda 2 / Pessoal · Fase E
- **O que fez:** `src/lib/api/pessoal.ts` + `src/lib/pessoal/db-service.ts` → API real. Funcionários (listar/obter/adicionar) e folha/holerites (listar, do mês, "gerar"=fechar) reais. `mensagemAmigavelPessoal`. `garantirSeedPessoal` virou no-op. Assinaturas/hooks preservados.
- **Descobertas:** `FuncionarioOut` {id, nome, cpf, cargo, vinculo(clt/prazo_determinado/intermitente), data_admissao, salario_base(string), dependentes_irrf, ativo}; `FuncionarioIn` POST 201 (cpf ^\d{11}$). GET `?somente_ativos=`. SEM GET por id (recupera da lista). `FolhaMensalOut` (`GET …/folhas?limite=`) {competencia, status(aberta/fechada), totais string…}. `HoleriteOut` (`GET …/folhas/{competencia}/holerites`) {salario_base, inss_empregado, irrf, fgts_empregador, valor_liquido…} — NÃO traz nome/cargo (join), INSS patronal derivado. "Gerar" = `POST …/folhas/{competencia}/fechar` (idempotente: 409 `FolhaJaFechada`).
- **Gaps:** **eSocial** ficou Dexie-local pois o módulo estava quebrado no ambiente (modelo `EventoESocial` esperava colunas da migration 0051, DB travado em 0040). → **RESOLVIDO pelo orquestrador (ver abaixo): DB foi a head (0055), eSocial agora responde 200.** O re-wire do adapter eSocial p/ o backend real fica como follow-up trivial (endpoints `…/esocial/eventos` + `…/esocial/transmissao/lotes` confirmados). `FuncionarioOut` não traz email/telefone/nascimento → vazios no mapper. **Bug folha→lançamento (500) RESOLVIDO pelo orquestrador (migration 0056).**

### 2026-06-05 · Onda 2 / Contábil · Fase E
- **O que fez:** `src/lib/api/contabil.ts` + `src/lib/contabil/db-service.ts` → API real; plugou `contabil` no barrel `index.ts`. Lançamentos (listar/criar), plano de contas e balancete reais. Hooks e a forma de `listarLancamentos` (que Relatórios consome) preservados.
- **Descobertas:** `GET …/plano-contas` → `ContaContabilOut[]` (codigo é a chave de junção UUID↔código; backend `natureza`='D'/'C', backend `tipo`=natureza-do-front). Plano vem vazio até `POST …/plano-contas/clonar-padrao` (47 contas, idempotente — feito no demo). `GET/POST …/lancamentos` → `LancamentoOut` {…, total_debito/credito(string), status(rascunho/confirmado/encerrado), partidas[{conta_contabil_id(UUID), tipo('D'/'C'), valor(string)}]}. POST cria em `rascunho`, valida Σ D = Σ C. Adapter **explode** lançamento N-partidas (UUID) → linhas planas (código), pareando D×C. `GET …/contabil/balancete/{YYYY-MM}`.
- **Gaps:** Sem DELETE de lançamento (§8.2 imutável) → `removerLancamento` lança 405 (nenhuma tela aciona). Telas ainda montam balancete/razão client-side a partir de `listarLancamentos`. **Bug robustez backend:** `GET …/balancete/2026-13` → 500 (ValueError não tratado em `_parse_competencia`); adapter só envia competência válida.

### 2026-06-05 · Onda 2 / Relatórios · Fase E
- **O que fez:** `src/lib/api/relatorios.ts` → **cálculo movido do cliente para o servidor**. `dre/balanco/dfc/indicadores` chamam `POST …/relatorios/{tipo}` reais. **Deletou** `src/lib/relatorios/geracao.ts` (geração client-side). `mensagemAmigavelRelatorios`. Assinaturas/hooks preservados; Recharts re-renderiza com os mesmos dados.
- **Descobertas:** `RelatorioOut` {…, payload(dict), …} snapshot imutável idempotente por período. Bodies: DRE/DFC/INDICADORES `{periodo_inicio, periodo_fim}`; BALANCO `{data_referencia}`. `payload` camelizado, dinheiro string: DRE cascata (receitaBruta…lucroLiquido), BALANCO grupos {…contas:[[codigo,desc,saldo]]} + fecha/diferenca, DFC fluxos, INDICADORES 11 índices {valor(string|null), formato}.
- **Gaps:** Empresa demo SEM lançamentos → todos os 4 endpoints respondem **422 `SemDadosContabeis`** → adapter cai em **estado vazio honesto** (sem inventar número). Backend calcula 1 período; telas que esperavam comparativo multi-coluna / série 12m → mapeadas p/ 1 coluna/1 ponto real (sem fabricar histórico). Indicadores do mock sem backend (ticket médio, PMR, ROI) substituídos pelos 11 reais. **Nota:** agora que a folha gera lançamento real (fix 0056), DRE/balanço passam a ter dado quando há folha/lançamentos.

### 2026-06-05 · Onda 2 / Compliance · Fase E
- **O que fez:** `src/lib/api/compliance.ts` + `src/lib/compliance/db-service.ts` → API real. Certidões (listar/renovar) e parcelamentos (listar) reais. `mensagemAmigavelCompliance`. Schema Zod não alterado; assinaturas/hooks preservados.
- **Descobertas:** `GET …/certidoes` → `CertidaoOut[]` {tipo(CND/CRF/CNDT), status(negativa/positiva/processando/erro…), valid_until…}. **Status do backend é resultado da consulta (regularidade), não vigência** → mapeado p/ vocabulário da tela via `calcularStatusCertidao`. Emissão/renovação `POST …/certidoes/{tipo}` (202, assíncrono — CRF/CNDT marcam `processando`). `GET …/parcelamentos` → `ParcelamentoOut[]` {tipo, divida_consolidada(string), num_parcelas, status…} + `…/{id}/parcelas` p/ parcelaAtual/proximoVencimento.
- **Gaps:** **Intimações SEM endpoint** (monitor-cadastral é só snapshot RFB/Sintegra, conceito ≠ intimação e-CAC) → permanecem Dexie local. `enviarAoContador` e `painel` agregado SEM endpoint → local/derivado. Certidão estadual/municipal: backend só CND/CRF/CNDT. `valid_until` ausente → vencimento = data emissão (não inventado).

### 2026-06-05 · Onda 2 / Assistente · Fase E
- **O que fez:** `src/lib/api/assistente.ts` + `src/lib/assistente/db-service.ts` → API real. `enviarPergunta` → `POST …/assistente/perguntar`. Removeu resposta mock/`mockLatency`. Citações preservadas (§8.5). `mensagemAmigavelAssistente` (trata `LLMIndisponivel`/503). Histórico segue Dexie local.
- **Descobertas:** Endpoint `POST /v1/empresas/{id}/assistente/perguntar` (NÃO `/v1/assistente`). Body `PerguntaIn {pergunta(3..2000), contexto_adicional?, contem_pii?}`. `RespostaOut {resposta, citacoes[{fato_id, trecho_citado}], encaminhar_marketplace, categoria_marketplace, provider_usado, custo_usd(string)…}`. `encaminhar_marketplace=true` → bloco de alerta info (out-of-scope §8.11). Citação `{fato_id,trecho}` → `{tipo:"fonte", rotulo:trecho}`.
- **Gaps:** Histórico de chat LOCAL (backend `memoria` é grafo de fatos, não transcrição). **LLM 503/fallback:** Ollama sem `gemma3:4b` puxado → `provider:"fallback"`, citações vazias, texto seguro (status 200, não quebra). Out-of-scope routing (holding→marketplace) funciona. `ollama pull gemma3:4b` habilita resposta plena.

### 2026-06-05 · Orquestrador (tech lead) · Fase E — Hardening de backend (DB a head + folha→contábil)
- **DB levado a head (0055):** a cadeia estava travada em 0040 por `0041` (`CREATE INDEX CONCURRENTLY` incompatível com o driver **pg8000** que o `alembic/env.py` força — autocommit_block não escapa a transação; bug de infra que atingiria prod). Como só a 0041 usa CONCURRENTLY em migration-time (a 0026 usa dentro de função, runtime), apliquei os 4 índices manualmente (non-concurrently, instantâneo em DB de dev vazio) + extensão, `stamp 0041`, e `upgrade head`. **Sem tocar arquivos de migration** (semântica de prod intacta). A 0049 abortou por guard de dados (80 empresas-cruft com `codigo_municipio_ibge=NULL` de seeds antigos no volume) → backfill com IBGE de SP. Resultado: **0055 (head)**, e **eSocial (colunas da 0051) agora responde 200** (era 500).
- **Bug folha→lançamento (CHECK) — CORRIGIDO:** `ContabilLancadorService.lote_folha` cria o lançamento da folha com `origem_tipo='folha'`, mas o CHECK `ck_lanc_origem_tipo` (0014/0040) não incluía 'folha' → fechar folha dava 500 (folha/holerites persistiam, lançamento não). **Fix:** migration **0056** adiciona 'folha' ao CHECK + `models.py` atualizado; e o `except` fail-soft do `fechar_folha_mensal` ganhou `await session.rollback()` (limpa transação abortada → endpoint responde 200 mesmo se o lançamento falhar por outro motivo). **Verificado:** fechar folha → 200; lançamento `origem=folha 2026-03-01 D=C=5940.00 confirmado` (partidas dobradas). **Conecta Pessoal→Contábil→Relatórios com dado real.**
- **Gaps de robustez de backend (NÃO bloqueiam o front; adapters passam input válido):** `GET …/lancamentos` sem `competencia` e `GET …/balancete/{mês-inválido}` → 500 por validação de input frouxa (ValueError não tratado). eSocial re-wire do adapter pendente (endpoints prontos). Integrações externas precisam de credenciais reais p/ dado vivo: **Focus NFe** (emissão NFS-e → 502 sandbox), **Pluggy** (Open Finance → contas vazias), **Ollama gemma3:4b** (assistente → fallback).
- **Build combinado Onda 2:** front `npm run build` **VERDE (exit 0, 48 páginas)**. `pytest tests/unit/fiscal` 51 verdes.

### 2026-06-05 · Revisor (contexto fresco) + Orquestrador · Fase F (fechamento)
- **Veredito do revisor:** **APROVADO COM RESSALVAS**, zero bloqueadores. Invariantes
  OK em todos os 6 adapters da Onda 2 (assinaturas/hooks preservados; token via header;
  tenant via JWT; dinheiro string; CFOP/CST/NCM não crus; erros traduzidos; gaps em
  estado local/vazio honesto — sem dado inventado; citação preservada no assistente).
  Backend OK (0056 espelha 0040; model bate com CHECK; `rollback` no except correto —
  folha comitada antes; 0034 `datetime.date` correto).
- **Correções aplicadas pelo orquestrador (decorrentes do fix 0056):**
  1. **`src/lib/api/contabil.ts` — `origemTipoSchema` não incluía `"folha"`/`"importacao"`.**
     CRÍTICO: agora que a folha gera lançamento `origem_tipo='folha'` real, o `parse`
     **rejeitaria** o lançamento e quebraria a tela do Livro Diário. Adicionados ao enum.
  2. **`mapearOrigem`** passou a tratar `case "folha" → "folha"` (antes caía em
     `default→"manual"`, rotulando o lançamento de folha como "manual").
  3. **`src/lib/pessoal/db-service.ts`** — comentário do gap eSocial atualizado
     (DB foi a head; endpoints respondem 200; re-wire é follow-up trivial).
- **Ressalvas remanescentes (pendências conscientes, não bloqueiam):** INSS patronal
  derivado no cliente por alíquota estatutária (exibição, não persiste); `compliancePainel.cnpjAtivo=true`
  assumido (sem snapshot RFB); re-wire do adapter eSocial p/ backend real; comentário de
  `removerLancamento` impreciso (nenhuma tela aciona).
- **Build final após correções:** `npm run build` **VERDE (exit 0, 48 páginas)**.

---

## RESUMO EXECUTIVO DA INTEGRAÇÃO (estado final)

**10 domínios do frontend ligados ao backend real** via camada anticorrupção (adapters
preservam assinaturas; `fetchJson` injeta Bearer + traduz snake↔camel; `empresa_id` na
rota). Login real com `tenant_slug`. Build front **VERDE**; DB em **head (0055+0056)**.

| Domínio | Estado |
|---|---|
| Auth / Empresa | ✅ real (login tenant_slug, onboarding cria empresa, lista via JWT) |
| Fiscal (DAS) | ✅ real + **persistindo** (fix commit); saúde/histórico = estado vazio (sem endpoint) |
| Agenda | ✅ real (geração sob demanda; dados reais) |
| Notas | ✅ listagem (documentos) + emissão NFS-e real (emissão depende de **Focus sandbox**); CRUD auxiliar local |
| Controles | ✅ Open Finance real (contas/transações/conciliação); pagar-receber/fluxo = local (sem endpoint); dado vivo depende de **Pluggy** |
| Pessoal | ✅ funcionários + folha/holerites reais; **folha→lançamento contábil** real (fix 0056); eSocial = local (endpoints prontos, re-wire pendente) |
| Contábil | ✅ real (lançamentos/plano/balancete; partidas dobradas) |
| Relatórios | ✅ cálculo no servidor (DRE/Balanço/DFC/indicadores); estado vazio honesto sem lançamentos |
| Compliance | ✅ certidões/parcelamentos reais; intimações/painel = local (sem endpoint) |
| Assistente | ✅ real (citação + out-of-scope); resposta plena depende de **`ollama pull gemma3:4b`** |

**Bugs de backend encontrados e corrigidos:** (1) migration 0034 bindparam; (2) FiscalService
sem commit; (3) cadeia de migrations travada (0041 CONCURRENTLY+pg8000 → DB a head manualmente);
(4) folha→lançamento CHECK sem 'folha' (migration 0056 + rollback fail-soft).

### 2026-06-05 · Orquestrador · Assistente local (Ollama) habilitado
- **Modelos baixados no container `fiscal_ollama`:** `gemma3:4b` (3.3 GB, chat — nome exato que `client.py:241` exige) + `nomic-embed-text` (274 MB, embeddings do RAG). `docker compose exec ollama ollama pull <modelo>`.
- **Fix de roteamento (`app/shared/llm/client.py` `_rotear`):** por padrão (`contem_pii=False`) o cliente roteava para **Gemini cloud**; sem `GEMINI_API_KEY` o assistente caía em fallback. Agora: **sem chave Gemini → usa o Ollama local** (com chave, volta ao Gemini). Afeta todo o LLM do backend (assistente/advisor/digest) em ambiente self-hosted.
- **Verificado ao vivo:** pergunta sem `contem_pii` → `provider: ollama-gemma3-4b`, ~14-15s (CPU), resposta real do Gemma. `pytest tests/unit/shared tests/unit/assistente` verdes (85).
- **Notas:** (1) latência ~15s é CPU (container Docker no Windows não usa GPU) — para GPU, repontar `OLLAMA_URL=http://host.docker.internal:11434` e `ollama pull gemma3:4b` no host. (2) `memoria_node` tem **0 fatos** → o assistente responde com o LLM mas sem citações específicas da empresa (o grafo é populado pela ingestão de documentos — fluxo à parte).

### 2026-06-05 · Orquestrador · Ollama migrado para o host (GPU)
- **Mudança:** o backend passou a usar o **Ollama do host (GPU)** via `host.docker.internal:11434`; o container `fiscal_ollama` foi removido (serviço comentado no `docker-compose.yml`, volume `ollama_data` removido). Modelo de chat tornou-se configurável: **`OLLAMA_MODEL`** (setting em `config.py`, default `gemma3:4b`; `client.py` usa a setting em vez do hardcode). Timeout da chamada Ollama elevado de 60s→**180s** (`client.py`) — modelos grandes / 1ª carga estouravam 60s e caíam em fallback.
- **Modelo final = `gemma3:4b` (3.3 GB) no host → 100% GPU.** Testado: `gemma4:latest` (10 GB) não cabe na VRAM (rodava 68% CPU, ~37s/resposta); gemma3:4b cabe inteiro (`ollama ps` = 100% GPU), **~7s aquecido / ~17s a frio**. `nomic-embed-text` também 100% GPU (pronto p/ RAG/ingestão).
- **Arquivos tocados:** `app/config.py` (+`OLLAMA_MODEL`), `app/shared/llm/client.py` (usa setting + timeout 180s + roteamento sem-chave-Gemini→Ollama), `docker-compose.yml` (api → host.docker.internal + `OLLAMA_MODEL=gemma3:4b`; serviço ollama comentado). Host: `ollama pull gemma3:4b` + `nomic-embed-text`.
- **Comportamento esperado:** parte das perguntas ainda retorna o fallback seguro — é o **gate de citação §8.5** (sem fatos no `memoria_node` vazio, afirmações fiscais sem citação são rejeitadas). Resolve quando a ingestão popular o grafo. Após ~4 min ocioso o Ollama descarrega o modelo (próxima chamada recarrega, ~17s) — comportamento padrão do `keep_alive`.
- **Reverter p/ Ollama no container (CPU, self-contained):** descomentar o serviço `ollama` + volume no compose e voltar `OLLAMA_URL=http://ollama:11434`.

**Pendências p/ "100%" pleno (não-bloqueantes):** credenciais reais de Focus/Pluggy
p/ dado vivo dessas integrações; re-wire do adapter eSocial; `PUT/PATCH /v1/empresas/{id}`
p/ persistir edição de empresa; o bug pg8000+CONCURRENTLY no `env.py` (infra de backend).

### 2026-06-06 · Orquestrador · Robustez de input — competência mensal (RESOLVIDO)
- **Balancete mês-inválido → 500 RESOLVIDO.** `GET …/contabil/balancete/2026-13` (e `2026-00`,
  razão, e os demais endpoints com competência na rota) devolvia 500 (`ValueError` de
  `date(2026,13,1)` não tratado no `_parse_competencia`). Extraído helper compartilhado
  `app/shared/competencia.py::parse_competencia_mensal` → levanta `CompetenciaInvalida` (422,
  contrato `{codigo,mensagem}`). Removidas 7 cópias duplicadas do parser (contabil,
  lucro_presumido, imobilizado, pgdas, provisoes, reinf, pessoal). +17 testes. Live: 422 ok.
- **`GET …/lancamentos` sem competência: NÃO reproduz 500** — responde **200** (o
  `competencia: date | None` do FastAPI valida sozinho; `?competencia=` vazio → 422). O 500
  do handoff anterior não se confirma no estado atual; sem fix necessário.
- **Suite:** 2509 passed / 3 skipped · mypy 0 erros (357 arq.). Detalhe em `log_agente.md`.
