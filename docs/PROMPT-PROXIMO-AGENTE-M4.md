# Prompt — próximo orquestrador (Marco 4: Conectar o resto à produção real)

> Cole isto inteiro numa sessão nova do Claude Code na raiz do repo. Você é a continuação da orquestração de produção do Arkan; os agentes anteriores fizeram a auditoria fiscal + Marcos 1, 2 e 3. Você NÃO tem memória deles — este documento é todo o seu contexto.

---

## 0. Quem você é
Você é o **orquestrador (engineering manager)** do projeto **Arkan / Analista Fiscal** — um SaaS fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido). Você conduz o trabalho, valida e commita. Hoje a missão é o **Marco 4 — remover os últimos mocks**: ligar storage S3, EFD-Reinf→SERPRO, e-mail transacional e o Dockerfile do front. Tudo "pronto atrás de env/flag, sem mock".

## 1. O projeto (mapa)
- Raiz: `C:\dev\Apresentação-Ideia` (Windows; caminho TEM acento — cuidado em shell).
- **Backend** (seu foco): `analista-fiscal-api/` — FastAPI + Postgres 16 (RLS) + Redis + Celery. Python 3.12, Poetry, SQLAlchemy 2.0 async, Pydantic v2, Alembic.
- Frontend: `analista-fiscal-web/` (Next 15) — só o item do Dockerfile (15) toca aqui.
- Git remote: `github.com/lorenzo265/FiscalAI`. Branch principal: `main`.

## 2. LEIA PRIMEIRO (nesta ordem)
1. `CLAUDE.md` (raiz) — constituição: stack cravada, **10 princípios invioláveis** (RLS, fatos imutáveis, SCD Type 2, golden tests, LGPD-first, idempotência em integrações externas, etc.), convenções, o que NUNCA fazer.
2. `docs/HANDOFF-ORQUESTRADOR.md` — **as últimas entradas (2026-06-22)** cobrem o Marco 3 inteiro (6.1→6.5) e as lições operacionais caras desta máquina. Append-only: ao terminar, ADICIONE sua entrada.
3. `log_agente.md` (raiz) — histórico de PRs do backend; o topo cobre M1+M2+M3. Atualize ao fechar trabalho.
4. `docs/PLANO_GO_LIVE.md` — o plano de produção. **Marco 4 é o §B "Marco 4" (itens 10, 11, 13, 14, 15, 16)**. As ações do PO (credenciais/infra) estão no §A.
5. `docs/PRODUCTION_READINESS_AUDIT-2026-06-21.md` — a auditoria que originou os marcos.

## 3. Ambiente & toolchain (cole e use)
Shell = **Git Bash** (a ferramenta Bash). Poetry precisa do PATH (Device Guard):
```bash
export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"
cd "/c/dev/Apresentação-Ideia/analista-fiscal-api"
poetry run python -m pytest tests/unit tests/eval      # suite canônica (deve dar ~2728 passed, 3 skipped)
poetry run python -m mypy app/                          # strict, 0 erros (~375 arquivos)
poetry run ruff check app/ tests/                       # ver a nota sobre ruff abaixo
poetry run alembic upgrade head                         # aplica migrations no DEV (Docker de pé)
poetry run python -m pytest tests/integration           # integração (precisa Docker postgres+redis)
```
- **Docker:** `docker ps` deve mostrar `fiscal_postgres` + `fiscal_redis` (healthy). **NESTA MÁQUINA OS CONTAINERS CAÍRAM 2× sozinhos** (parados externamente) — se `psql`/integração falhar com "container not running" ou auth, rode `docker start fiscal_postgres fiscal_redis` e espere o healthcheck. Postgres acessível em **:5434** (NÃO 5432); senha no `.env` (não no default do `config.py`). Query direta: `docker exec fiscal_postgres psql -U fiscal -d fiscal -c "..."`.
- **Última migration: `0064`**. A próxima que você criar = **`0065`** (down_revision = "0064").
- **mypy:** `poetry run mypy app/` (não os tests).

### ⚠️ Nota sobre ruff e a faxina de lint (estado pode variar)
O gate `ruff check .` do `ci.yml` acusava ~1607 findings **pré-existentes** (1101 = RUF001/002/003, ruído de tipografia portuguesa — em-dash/aspas curvas/`×`). Foi **delegado a uma sessão separada** (branch `chore/ruff-lint-cleanup`). Cheque se já foi mergeado (`git log --oneline --all | grep ruff`). Se ainda não: **cada arquivo novo/tocado SEU deve sair `ruff check`-limpo** (zero findings — escreva comentários sem os glyphs ambíguos `—`/`→`/`×`/aspas curvas; acentos normais `ã/ç/é` NÃO são flagados). Rode `poetry run ruff check <seus-arquivos>` para confirmar.

## 4. COMO TRABALHAR (lições caras — siga à risca)
1. **Subagentes andam INSTÁVEIS (529 Overloaded) e erram cálculo/fixtures. Faça SOLO** (você escreve o código). pytest verde só prova consistência interna — **valide os números/comportamento à mão + rode a INTEGRAÇÃO**.
2. **`spawn_task` NÃO garante worktree isolada** — uma faxina delegada rodou no MESMO checkout e trocou a branch debaixo do orquestrador. Para trabalho concorrente, **VOCÊ cria a worktree isolada** (`git worktree add /c/dev/<nome> <branch>`) e trabalha lá.
3. **Worktree isolada precisa de setup** (gitignored não vem): `cp <tree-principal>/analista-fiscal-api/.env <worktree>/analista-fiscal-api/.env` + `poetry install --with dev` (cria `.venv` próprio). O Postgres/Redis (Docker :5434) é compartilhado entre worktrees.
4. **GRANT a `fiscal_app` deve ser EXPLÍCITO em toda migration que cria tabela** (`op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON <tabela> TO fiscal_app")`). O `ALTER DEFAULT PRIVILEGES` do `init.sql` NÃO cobre tabelas do alembic. **No M3 descobri que `guia_pagamento` tinha ACL VAZIA** — se um endpoint seu der "permission denied", é grant faltando: verifique `has_table_privilege('fiscal_app','<t>','SELECT/INSERT/UPDATE')` e conceda na sua migration.
5. **Padrão de migration RLS:** `_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"` + `op.create_table(...)` + `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY x_tenant ON x USING ({_RLS_USING}) WITH CHECK ({_RLS_USING})` + GRANT. Gabaritos: `alembic/versions/0064_refresh_token.py`, `0062_lgpd_solicitacao.py`, `0061_billing_assinatura.py`.
6. **Sessões/deps** (`app/shared/db/deps.py`): `SessionDep` (autenticado, SET ROLE fiscal_app + RLS por tenant), `WebhookSessionDep`/`SystemSessionDep` (superuser, bypassa RLS — webhooks externos / fluxos pré-auth como o refresh), `AnonSessionDep` (auth register/login), `TaxTableAdminSessionDep`. Exceções de domínio em `app/shared/exceptions.py` (herdam `DomainError`, têm `http_status`; mapeadas em `app/main.py`).
7. **Convenções:** `Decimal` nunca `float`; `from __future__ import annotations`; mypy strict (zero `Any` público — `JsonObject`/`JsonValue` em `app/shared/types.py` são os escapes legítimos); imports absolutos `app.`; inputs Pydantic `ConfigDict(extra="forbid")`; structlog (`log.info("evento.acao", chave=valor)`, Decimal→str, PII redigida); datetime aware `America/Sao_Paulo`. Cada cálculo puro tem golden test.
8. **Padrão de integração externa (idempotência §8.9):** todo POST a Focus/SERPRO/Pluggy leva `idempotency_key`. Gabarito de cliente HTTP: `app/shared/integrations/serpro/client.py` (+ `oauth.py`). Gabarito de transmissão: `app/modules/pessoal/transmissao_esocial_service.py` (espelhe-o para o Reinf). Flags opt-in: o serviço fica em `status='preparado'`/stub até a env/credencial existir (ex.: `ESOCIAL_TRANSMISSAO_ATIVA`).
9. **FREIOS (NUNCA sem o PO Lorenzo):** `git push`/merge remoto, **alteração de alíquota/tabela tributária seedada**, deploy, transmissão fiscal real, cobrança real. **Trabalhe numa branch** (worktree isolada), valide tudo, consolide na `main` por fast-forward local e **PERGUNTE ao PO antes de `git push`**. Mensagem de commit termina com `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## 5. Estado atual (já feito — NÃO refaça)
- **Marco 3 COMPLETO** na branch `feat/m3-lgpd-seguranca` (6 commits a partir de `0a076f2`; worktree isolada `C:/dev/m3-pr61-wt`). **PERGUNTE AO PO se já foi consolidado na `main` + pushado** antes de partir — se não, o primeiro passo é: tratar a contaminação do PR 6.1 no tree principal (ver HANDOFF), consolidar `feat/m3-lgpd-seguranca`→`main` por ff, e o PO decide o push.
- **M3 entregou:** security headers (`app/shared/middleware/security_headers.py`); LGPD `GET /v1/lgpd/exportar` + `POST /v1/lgpd/excluir` (anonimização respeitando imutabilidade §8.2 + retenção 5a + audit `lgpd_solicitacao`); AES-256-GCM em repouso (`app/shared/crypto/envelope.py` + `PiiCifrada` TypeDecorator em `empresa.whatsapp_phone`); refresh token DB-backed com rotação + detecção de reuso (`POST /auth/refresh`, tabela `refresh_token`); gate de segredos Gitleaks bloqueante no `ci.yml`. Migrations 0062/0063/0064. `cryptography` virou dep CORE.
- **Suite:** ~2728 unit + 3 skipped; integração ~35; mypy strict 0 (~375 arq).
- **M1 (fundação):** Sentry + Prometheus `/metrics` + correlation-id + Celery worker/beat reais. **M2 (billing):** módulo `app/modules/billing/` (Stripe + fake).

## 6. SUA MISSÃO — Marco 4 (remover os últimos mocks). Tudo código seu, atrás de env/flag.
Entregue em PRs pequenos, validando cada um (pytest+mypy+ruff+integração). Itens (de `docs/PLANO_GO_LIVE.md §B`):

### 6.1 Storage S3 efetivo (item 10) — *começa sem depender do PO*
- Hoje blobs (SPED/DANFSE/holerite PDF/XML) vão pra BYTEA no Postgres ou só calculam `storage_key`. Existe `app/shared/storage/` com `build_storage(backend=...)` — `local`/`memory`/`s3` (boto3, grupo opt-in `storage`). **Ligue o caminho S3**: nos módulos que geram blob (`sped`, `notas`, `pessoal`), persista via `request.app.state.storage` (já injetado no lifespan) usando o `storage_key`, em vez de BYTEA. Migração de dados se preciso (2-fases). `STORAGE_BACKEND=s3` + `STORAGE_BUCKET` ligam o real (o PO cria o bucket sa-east-1 — A2). Golden + integração com o backend `memory`/`local`.

### 6.2 EFD-Reinf → SERPRO (item 11)
- Hoje o Reinf fica em `status='preparado'` permanente. Escreva o **serviço de transmissão** espelhando `app/modules/pessoal/transmissao_esocial_service.py` (assinatura XMLDSig já existe em `app/shared/crypto/xmldsig.py`; cliente SERPRO em `app/shared/integrations/serpro/`). Flag opt-in `REINF_TRANSMISSAO_ATIVA` (default False = fica preparado). Idempotência. Golden + integração. *(Liga com A1: cert A1 + SERPRO do PO.)*

### 6.3 E-mail transacional (item 14)
- Não há cliente de e-mail. Crie `app/shared/integrations/email/` (provider Resend OU Postmark OU SES, atrás de Protocol + `_FakeEmailProvider`, espelhando o `BillingProvider` do billing). Templates: onboarding, fatura/cobrança, alerta fiscal. Env `EMAIL_PROVIDER`/`EMAIL_API_KEY`/`EMAIL_FROM`. Sem credencial → fake (não envia). Task Celery para o envio assíncrono. Golden. *(Liga com A1: provedor + domínio verificado do PO.)*

### 6.4 Dockerfile do frontend (item 15) — *toca o front*
- `analista-fiscal-web` não tem Dockerfile de produção. Crie um multi-stage (Next standalone — exige `output: 'standalone'` no `next.config`), `NEXT_PUBLIC_API_BASE_URL` por build-arg, user não-root. Some `error.tsx`/retry/timeout no fetch (robustez apontada na auditoria). *(Liga com A2: deploy do PO.)*

### 6.5 (se sobrar) Onboarding CNPJ-first backend (item 16) + IaC (item 17)
- Persistência de draft do onboarding no backend + ligar o `BrasilApiClient` ao wizard. IaC (Helm/Terraform sa-east-1) é co-construído com o A2 do PO.

## 7. Definition of Done (a cada PR e ao fim)
- `pytest tests/unit tests/eval` verde + `mypy app/` 0 erros + `ruff check` limpo nos seus arquivos + (se DB) integração verde + migration aplicada no dev e conferida com query (`has_table_privilege` para GRANT).
- **Write-back (sem pedir confirmação):** `log_agente.md` (contagem + o que entrou) + entrada em `docs/HANDOFF-ORQUESTRADOR.md` (data · o que fez · arquivos · pendências · próximo). Atualize a memória `producao-milestones` se existir.
- Consolide na `main` por fast-forward e **pergunte ao PO antes de `git push`**.
- Ao fim do M4, escreva o prompt do próximo agente para o **M5** (deploy real / IaC / observabilidade ligada), no mesmo formato deste.

## 8. Cola de comandos úteis
```bash
export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"; cd "/c/dev/Apresentação-Ideia/analista-fiscal-api"
poetry run python -m pytest tests/unit tests/eval -q --junit-xml=_j.xml >/dev/null 2>&1; echo exit=$?   # contagem exata via junit (o resumo do terminal é suprimido por um hook do conftest)
poetry run python -c "import xml.etree.ElementTree as ET; t=ET.parse('_j.xml').getroot(); s=t if t.tag=='testsuite' else t.find('testsuite'); print(s.get('tests'),s.get('failures'),s.get('skipped'))"; rm _j.xml
poetry run python -m mypy app/ | tail -1
docker ps --format '{{.Names}} {{.Status}}' | grep fiscal   # se vazio: docker start fiscal_postgres fiscal_redis
docker exec fiscal_postgres psql -U fiscal -d fiscal -t -c "SELECT has_table_privilege('fiscal_app','<t>','SELECT');"
ls alembic/versions | sort | tail -3   # head = 0064 → próxima é 0065
```

**Regra-mãe:** re-vestir o que existe, seguir os padrões/gabaritos, validar de verdade (à mão + integração), parar nos freios, e deixar cada integração pronta atrás de env/flag — sem mock em produção. No dia em que a credencial entra no `.env`, a capacidade liga sozinha.
