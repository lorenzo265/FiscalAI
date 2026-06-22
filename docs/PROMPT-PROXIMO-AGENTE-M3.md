# Prompt — próximo orquestrador (Marco 3: LGPD & Segurança)

> Cole isto inteiro numa sessão nova do Claude Code na raiz do repo. Você é a continuação da orquestração de produção do Arkan; o agente anterior fez a auditoria fiscal + Marcos 1 e 2. Você NÃO tem memória dele — este documento é todo o seu contexto.

---

## 0. Quem você é
Você é o **orquestrador (engineering manager)** do projeto **Arkan / Analista Fiscal** — um SaaS fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido). Você conduz o trabalho, valida e commita. Hoje a missão é o **Marco 3 — LGPD & Segurança** do caminho de produção.

## 1. O projeto (mapa)
- Raiz: `C:\dev\Apresentação-Ideia` (Windows; caminho TEM acento — cuidado em shell).
- **Backend** (seu foco): `analista-fiscal-api/` — FastAPI + Postgres 16 (RLS) + Redis + Celery. Python 3.12, Poetry, SQLAlchemy 2.0 async, Pydantic v2, Alembic.
- Frontend: `analista-fiscal-web/` (Next 15) — NÃO é o foco do M3.
- Git remote: `github.com/lorenzo265/FiscalAI`. Branch principal: `main` (já PUSHADA, sincronizada).

## 2. LEIA PRIMEIRO (nesta ordem)
1. `CLAUDE.md` (raiz) — constituição: stack cravada, **10 princípios invioláveis** (RLS multi-tenant, fatos imutáveis, SCD Type 2, golden tests, LGPD-first, etc.), convenções de código, o que NUNCA fazer.
2. `docs/HANDOFF-ORQUESTRADOR.md` — **a última entrada (2026-06-22)** resume tudo que o agente anterior fez e as lições operacionais. Append-only: ao terminar, ADICIONE sua entrada.
3. `log_agente.md` (raiz) — histórico de PRs do backend; **as entradas do topo** cobrem a auditoria fiscal + M1 + M2. Atualize ao fechar trabalho.
4. `docs/PLANO_GO_LIVE.md` — o plano de produção (ações PO §A × orquestrador §B). **Marco 3 é o §B "Marco 3"**.
5. `docs/PRODUCTION_READINESS_AUDIT-2026-06-21.md` — a auditoria que originou os marcos (dimensão "Segurança & LGPD" tem os detalhes/evidências dos gaps).
6. `docs/principios/07-lgpd-first.md` — o princípio LGPD (exige endpoints `/lgpd/exportar` e `/lgpd/excluir`, retenção, audit trail).

## 3. Ambiente & toolchain (cole e use)
Shell = **Git Bash** (a ferramenta Bash). Poetry precisa do PATH (Device Guard):
```bash
export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"
cd "/c/dev/Apresentação-Ideia/analista-fiscal-api"
poetry run python -m pytest tests/unit tests/eval      # suite canônica (~35s, deve dar 2700 passed, 3 skipped)
poetry run python -m mypy app/                          # strict, deve dar 0 erros (365 arquivos)
poetry run ruff check app/ tests/                       # lint (ruff --fix aplica os triviais)
poetry run alembic upgrade head                         # aplica migrations no DEV (Docker de pé)
poetry run python -m pytest tests/integration           # integração (precisa Docker postgres+redis)
```
- **Docker** está de pé (`docker ps` → `fiscal_postgres`, `fiscal_redis`). Postgres acessível: `docker exec fiscal_postgres psql -U fiscal -d fiscal -c "..."`.
- Última migration: **0061**. A próxima que você criar = **0062** (down_revision = "0061").

## 4. COMO TRABALHAR (lições caras — siga)
1. **Subagentes andam INSTÁVEIS (erro 529 Overloaded recorrente). Faça SOLO** (você mesmo escreve o código). Se tentar subagente e ele falhar, não insista — assuma. Mesmo quando rodam, subagentes **erram cálculo de cabeça** e fazem fixtures quebradas: **pytest verde só prova consistência interna** — valide os números à mão e rode a **integração**.
2. **Você roda e valida tudo** (poetry/pytest/mypy/git/docker). Subagentes, se usados, são write-only.
3. **Padrão de validação por mudança:** pytest do módulo → mypy → ruff → (se tocou DB) `alembic upgrade head` + query de verificação + `pytest tests/integration` → só então commit.
4. **GRANT a `fiscal_app` deve ser EXPLÍCITO em toda migration que cria tabela** (`op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON <tabela> TO fiscal_app")`). O `ALTER DEFAULT PRIVILEGES` do `infra/postgres/init.sql` NÃO cobre tabelas criadas via alembic.
5. **Padrão de migration RLS:** `_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"` + `op.create_table(...)` + `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY x_tenant ON x USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})` + GRANT. Veja `alembic/versions/0061_billing_assinatura.py` como gabarito.
6. **Sessões/deps:** `app/shared/db/deps.py` — `SessionDep` (autenticado, SET ROLE fiscal_app + RLS por tenant), `WebhookSessionDep` (superuser, bypassa RLS, p/ webhooks externos), `TenantDep` (dá `ctx.tenant_id`). Exceções de domínio: `app/shared/exceptions.py` (herdam `DomainError`, têm `http_status`; mapeadas em `app/main.py`).
7. **Convenções:** `Decimal` nunca `float`; `from __future__ import annotations`; mypy strict (zero `Any` público); imports absolutos `app.`; inputs Pydantic `ConfigDict(extra="forbid")`; structlog (`log.info("evento.acao", chave=valor)`, Decimal→str, PII redigida); datetime aware `America/Sao_Paulo`. Cada cálculo puro tem golden test.
8. **FREIOS (NUNCA sem o PO Lorenzo):** `git push`/merge remoto, **alteração de alíquota/tabela tributária seedada**, deploy, transmissão fiscal real, cobrança real. (Billing usa `_FakeBillingProvider` até o PO setar `STRIPE_*`.) **O PO autorizou push nesta linha de trabalho** — confirme com ele antes de pushar; consolide na `main` por fast-forward local.
9. **Branch/commit:** trabalhe numa branch (`git checkout -b feat/m3-lgpd-seguranca`), commite por entrega, valide, depois consolide na `main` (`git checkout main && git merge --ff-only <branch>`) e **pergunte ao PO** antes de `git push origin main`. Mensagem de commit termina com `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 5. Estado atual (já feito — NÃO refaça)
- **main @ `153ac30`, PUSHADA.** Suite **2700 passed, 3 skipped**; mypy strict 0; ruff ok. Migrations 0059/0060/0061 aplicadas no DEV.
- **Fiscal:** auditoria corrigida (Ondas A/B/C + follow-up) — IRRF 2026 com redutor, dividendos com retenção 10%, Fator R, DRE, lançador, reconciliação NF, etc. Tudo testado.
- **M1 (fundação):** Sentry + Prometheus `/metrics` + `CorrelationIdMiddleware` (em `app/shared/middleware/correlation_id.py` — **use como gabarito de middleware**) + Celery worker/beat reais (`infra/docker/Dockerfile.{worker,beat}` + `docker-compose.prod.yml`).
- **M2 (billing):** módulo `app/modules/billing/` completo (Stripe + fake). Migration 0061.

## 6. SUA MISSÃO — Marco 3 (LGPD & Segurança). Tudo código seu.
Entregue em PRs pequenos, validando cada um. Ordem sugerida:

### 6.1 Security headers middleware (rápido, alto valor)
- Crie `app/shared/middleware/security_headers.py` espelhando `correlation_id.py` (BaseHTTPMiddleware). Adicione na resposta: `Strict-Transport-Security` (HSTS, só em prod/https), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, e um `Content-Security-Policy` conservador (API-only). Plugue em `app/main.py` (cuidado com a ORDEM dos middlewares — comentário no main explica que o último adicionado roda OUTERMOST).
- Golden: `tests/unit/middleware/test_security_headers.py` (Starlette mínimo + TestClient, confere os headers).

### 6.2 Endpoints LGPD — direito do titular (`app/modules/lgpd/`)
- `GET /v1/lgpd/exportar` (SessionDep) — reúne TODOS os dados do tenant (empresa(s), usuários, documentos fiscais, folha, sócios, apurações, etc.) num JSON estruturado (direito de portabilidade, LGPD art. 18). Use os repos existentes; respeite RLS (a SessionDep já isola por tenant).
- `POST /v1/lgpd/excluir` (SessionDep) — direito ao esquecimento, MAS **respeitando a imutabilidade fiscal (princípio §8.2) e a retenção legal de 5 anos**: NÃO delete fatos fiscais; **anonimize a PII** (CPF/CNPJ de PF/email/telefone/nome → tokens/hash) e marque a conta para expurgo após o prazo legal. Documente a decisão (anonimização ≠ deleção física) no docstring. Crie uma tabela de auditoria `lgpd_solicitacao` (migration 0062, RLS + GRANT) registrando exportações/exclusões com timestamp.
- Golden + integração (mirror `tests/integration/test_billing.py` p/ o fluxo via `live_client`).

### 6.3 AES-256 em repouso (PII)
- `app/shared/crypto/__init__.py` tem um TODO de "envelope AES-256-GCM". Implemente os helpers de envelope (chave via `settings` em dev; em prod a chave vem do KMS — deixe a env `PII_ENCRYPTION_KEY` e documente que prod usa KMS). Aplique a colunas PII sensíveis (ex.: CPF de sócio/funcionário) via um SQLAlchemy `TypeDecorator` OU pgcrypto na migration. Comece por 1 coluna de prova (CPF) com migration 2-fases (nova coluna cifrada → backfill → dropar a antiga). NÃO quebre os golden tests existentes.

### 6.4 Refresh token (rotação JWT)
- `app/shared/auth/jwt.py` emite JWT de 60 min sem refresh. Adicione um endpoint `POST /v1/auth/refresh` que troca um refresh token válido por um novo access token (rotação). Modele o refresh token (tabela com hash + revogação) ou use JWT de refresh com `typ='refresh'`. Golden dos invariantes (expiração, revogação, typ).

### 6.5 CI — AgentShield/Semgrep bloqueante (se der tempo)
- `.github/workflows/qa-gates.yml` tem Semgrep/Gitleaks em `continue-on-error: true` (soft). Promova o que for estável a bloqueante. ⚠️ NÃO promova o gate visual Playwright sem antes commitar a baseline de snapshots (hoje ausente → quebraria a CI).

## 7. Definition of Done (a cada PR e ao fim)
- `pytest tests/unit tests/eval` verde + `mypy app/` 0 erros + `ruff check` limpo + (se DB) integração verde + migration aplicada no dev e conferida com query.
- **Write-back (sem pedir confirmação):** atualize `log_agente.md` (contagem de testes + o que entrou) e **ADICIONE entrada em `docs/HANDOFF-ORQUESTRADOR.md`** (data · o que fez · arquivos · pendências · próximo). Se houver memória do Claude Code (`producao-milestones`), atualize o estado.
- Consolide na `main` (fast-forward) e **pergunte ao PO antes de `git push`**.
- Ao fim do M3, escreva o prompt do próximo agente para o **M4** (S3 storage efetivo, Reinf→SERPRO, e-mail transacional, Dockerfile do front) — mesmo formato deste documento.

## 8. Cola de comandos úteis
```bash
export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"; cd "/c/dev/Apresentação-Ideia/analista-fiscal-api"
poetry run python -m pytest tests/unit tests/eval -q | tail -2
poetry run python -m mypy app/ | tail -2
poetry run ruff check --fix app/ tests/
ls alembic/versions | sort | tail -3                 # achar o head (0061) → próxima é 0062
docker exec fiscal_postgres psql -U fiscal -d fiscal -t -c "SELECT has_table_privilege('fiscal_app','<tabela>','SELECT');"
# Gabaritos: middleware → app/shared/middleware/correlation_id.py · migration RLS → alembic/versions/0061_billing_assinatura.py · módulo → app/modules/billing/*
```

**Regra-mãe:** re-vestir o que existe, seguir os padrões, validar de verdade (à mão + integração), parar nos freios, e deixar tudo pronto atrás de env/flag — sem mock em produção.
