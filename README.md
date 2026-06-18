# Arkan — Plataforma Fiscal-Contábil para PMEs (ex-FiscalAI)

> *"Você sabe o que está acontecendo no seu fiscal — sem precisar ser contador."*

SaaS fiscal-contábil **multi-tenant** que substitui boa parte do serviço contábil tradicional para **PMEs brasileiras** (Simples Nacional + Lucro Presumido, faturamento R$200k–R$50M/ano). Ingestão automática de notas, cálculo determinístico de impostos, apuração mensal, SPED, folha de pagamento, Open Finance, compliance e um assistente de IA que **lê e cita fatos, mas nunca os inventa**.

A persona é o **dono da PME** — não um contador. Pode ser o dono de um restaurante que estudou até o ensino médio. Toda a UX é desenhada para isso (status sobre números; código fiscal nunca exposto; uma ação por alerta).

O app está em **rebrand → "Arkan"** (Arkan Fiscal Technologies), com uma re-engenharia de design da pele do frontend ("Instrumento" — uma ferramenta de precisão). A arquitetura e as funções ficam; muda a aparência.

---

## Estado atual (2026-06)

| Workstream | Estado |
|---|---|
| **Backend** (`analista-fiscal-api`) | **Sprints 0–22 concluídas (roadmap completo)** · 2520 testes passando · mypy strict 0 erros em 357 arquivos · bandit 0 issues · 57 migrations Alembic com RLS · 35 módulos |
| **Frontend** (`analista-fiscal-web`) | ~45 rotas / ~100 componentes implementados (Next 15) · 10 domínios ligados ao backend real · **re-engenharia de design "Arkan" em andamento** (Fases 0–4) |
| **Negócio** | Frota de 6 agentes de business montada (market research, pricing, compliance-watch, conteúdo, customer-success, analytics); primeiras análises sob demanda via `/pulse-negocio` |

**Branch ativo:** `hardening-fiscal-2026-06`. **Único item aberto e acionável:** atualização das tabelas INSS/IRRF/FGTS para 2026 (aguarda valores oficiais da Portaria MPS/MF 2026 — ver [Planejamento](#planejamento--o-que-vem-a-seguir)).

---

## Estrutura do monorepo

```
.
├── analista-fiscal-api/      ← Backend — FastAPI + Postgres + Redis (fonte de verdade do produto)
│   ├── alembic/versions/     ← 57 migrations (RLS multi-tenant em toda tabela de domínio)
│   ├── app/
│   │   ├── modules/          ← 35 bounded contexts (calcula_*.py puro → repo → service → router)
│   │   ├── shared/           ← db/models, llm/, integrations/, exceptions, logging
│   │   └── workers/          ← Celery (beat schedule pronto; instalação opt-in)
│   └── tests/                ← unit (golden por módulo) + eval (LLM) + integration (Docker)
│
├── analista-fiscal-web/      ← Frontend — Next.js 15 + React 19 + Tailwind v4 + shadcn
│   └── src/
│       ├── app/              ← App Router: (auth) + (dashboard) — ~45 rotas
│       ├── components/       ← ui / shared / layout / blueprint / por-domínio
│       ├── hooks/ lib/       ← TanStack Query · Dexie · Zod · cálculo fiscal mockado
│       └── ...
│
├── docs/                     ← Vault Obsidian: planos, princípios, sprints, ADRs, pendências, runbooks
├── .claude/                  ← Constituição de agentes: agents/ · commands/ · settings
├── CLAUDE.md                 ← Instruções para agentes (ler primeiro em sessão nova)
└── log_agente.md             ← Livro de passagem do backend (histórico de PRs)
```

---

## O que o produto faz

**Ingestão e operação fiscal**
- Ingestão automática de NF-e / NFS-e / NFC-e (SEFAZ + ADN + IMAP + Manifesto Destinatário)
- Cálculo **determinístico** de DAS, IRPJ, CSLL, PIS, Cofins, ISS, ICMS (golden tests obrigatórios)
- Apuração mensal + transmissão de PGDAS-D / DCTFWeb / DCTF / EFD-Reinf via SERPRO
- Geração **SPED**: ECD anual, ECF anual, EFD-Contribuições mensal, EFD ICMS-IPI mensal
- DEFIS (SN) + DASN-SIMEI (MEI); multa/juros por denúncia espontânea (SELIC acumulada)

**Calendário, alertas e compliance**
- Calendário fiscal por regime + alertas multi-canal (WhatsApp + email + in-app)
- Monitores: e-CAC / DTE / DET trabalhista · cadastral RFB · Sintegra / IE estadual
- Certidões automáticas (CND federal + CRF + CNDT) · parcelamentos (simulador + monitor)

**Contábil e patrimonial**
- Plano de contas hierárquico + código ECD · motor de lançamentos automáticos (NF/banco/folha → razão)
- Imobilizado + depreciação (IN SRF 162/1998) · provisões trabalhistas mensais
- Balancete, DRE, Balanço, DFC, indicadores · encerramento mensal e anual

**Folha e departamento pessoal**
- Folha completa (INSS, IRRF, FGTS) · 13º · férias + 1/3 · rescisão completa · pró-labore
- Distribuição de lucros com limites de presunção · eSocial S-1xxx/S-2xxx/S-3xxx · EFD-Reinf · FGTS Digital

**Tesouraria, Open Finance e IA**
- Pluggy (Belvo backup) · conciliação bancária automática · contas a pagar/receber · fluxo de caixa
- Assistente WhatsApp + in-app com memória por empresa; **3 camadas**: determinística (70%) + LLM local Gemma 3 (20%) + LLM cloud Gemini Flash (10%)

**Reforma Tributária + Marketplace**
- Cálculo informacional CBS/IBS, campos IBSCBS em DFe, pronto para split payment 2027
- Marketplace de contadores parceiros para os 15–25% out-of-scope (contencioso, holding/sucessão)

> **Cobertura ponderada: ~80% do trabalho do contador da PME-alvo.** Os 20% restantes **não devem entrar no produto** — viram receita via marketplace.

---

## Stack

### Backend (`analista-fiscal-api`)
Python 3.12 · FastAPI 0.115+ · SQLAlchemy 2.0 async (asyncpg) · Alembic · Pydantic v2 · **PostgreSQL 16** (RLS, JSONB, pgcrypto, pgvector) · Redis 7.4 · Celery 5.4 · **Gemini 2.5** (cloud) + **Ollama/Gemma 3 4B** (local) · `nomic-embed-text` (embeddings 768-dim) · pytest + golden suite + eval suite · Langfuse/Sentry/Grafana/Tempo/Loki.

### Frontend (`analista-fiscal-web`)
Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind v4 (CSS-first) · shadcn/ui · TanStack Query/Table · Zustand · React Hook Form + Zod · Recharts · Dexie (mock local) · Framer Motion · jsPDF/qrcode/jsbarcode (DANFE/holerite). Identidade alvo: **Fraunces + Hanken Grotesk + Spline Sans Mono** + paleta papel/tinta/verde (Arkan).

### Anti-stack (banido — não substituir)
❌ LangChain · ❌ Litestar · ❌ MongoDB · ❌ Claude/GPT em produção · ❌ `float` em dinheiro · ❌ `Any` em contrato público · ❌ hardcode de tabela tributária · ❌ dark/neon do tema antigo.

---

## Como rodar

### Backend
```powershell
# PATH (Device Guard bloqueia poetry.exe direto)
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd analista-fiscal-api

poetry install
docker compose up -d            # Postgres + Redis
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload   # http://localhost:8000

# Testes
poetry run python -m pytest tests/unit tests/eval   # rápido (~7s)
poetry run python -m mypy app/                       # strict
poetry run python -m pytest tests/integration        # requer Docker
```

### Frontend
```bash
cd analista-fiscal-web
pnpm install
pnpm dev                        # http://localhost:3000
```

---

## Princípios invioláveis (§8 do PlanoBackend)

1. **RLS multi-tenant** ativo em toda tabela de domínio (`SET LOCAL app.tenant_id`).
2. **Fatos fiscais imutáveis** — cancelamento gera nova linha (`supersedes`/`superseded_by`).
3. **Decisões versionadas (SCD Type 2)** — toda alíquota com `valid_from`/`valid_to`.
4. **Golden tests** bloqueando merge em todo cálculo fiscal.
5. **Citação obrigatória em LLM** — resposta sem citação válida é rejeitada.
6. **Re-check determinístico pós-LLM** — valores/datas/CNPJs conferidos por regex.
7. **LGPD-first** — AES-256 em repouso, TLS 1.3, dados em sa-east-1.
8. **LLM nunca escreve fatos** — pipeline determinístico ingere/calcula/persiste.
9. **Idempotência** em toda integração externa (`idempotency_key`).
10. **Observabilidade obrigatória** (Langfuse, Tempo, Sentry, Grafana).
11. **Out-of-scope é declarado**, não improvisado.
12. **Transmissão ao Fisco é ato consciente do cliente** (cert. dele).

Detalhe atômico de cada um em [`docs/principios/`](docs/principios/). Rubrica de PR em [`docs/review-checklist.md`](docs/review-checklist.md).

---

## Documentação (vault `docs/`)

| Quero entender… | Leia |
|---|---|
| Plano completo do backend (arquitetura, 22 sprints, custos) | [docs/PlanoBackend.md](docs/PlanoBackend.md) |
| Plano completo do frontend (escopo de produto, 13 fases) | [docs/Plano.md](docs/Plano.md) |
| Re-engenharia de design "Arkan" | [docs/restructure-frontend/PLANO_REENGENHARIA_FRONTEND_ARKAN.md](docs/restructure-frontend/PLANO_REENGENHARIA_FRONTEND_ARKAN.md) |
| Onde estamos (status de cada sprint) | [docs/roadmap.md](docs/roadmap.md) |
| Hub do knowledge graph (navegação) | [docs/README.md](docs/README.md) |
| Princípios / módulos / ADRs / pendências | [docs/principios/](docs/principios/) · [docs/modulos/](docs/modulos/) · [docs/decisoes/](docs/decisoes/) · [docs/pendencias/](docs/pendencias/) |
| Operação (deploy, on-call, backup) | [docs/runbooks/](docs/runbooks/) · [docs/deploy.md](docs/deploy.md) |
| Frota de agentes (devs + business) | [docs/time_arkan.md](docs/time_arkan.md) · [.claude/agents/](.claude/agents/) |
| O que falta na camada contábil | [docs/ROADMAP_CONTABIL_COMPLETO.md](docs/ROADMAP_CONTABIL_COMPLETO.md) |

---

## Frota de agentes (Claude Code)

O **repositório é o barramento**: subagentes coordenam por arquivos (`CLAUDE.md`, `docs/HANDOFF.md`, `log_agente.md`, `docs/negocio/HANDOFF_NEGOCIO.md`), não por chat. Política de autonomia: **alta no reversível, freio + OK humano no irreversível** (push, deploy, transmitir NF-e/eSocial/SPED real, mexer em tabela tributária seedada).

- **Dev/gate:** `backend-scout`, `backend-dev`, `backend-reviewer`, `migration-smith`, `aliquota-smith`, `fiscal-validator`, `qa-integration`, `security-auditor`, `ci-engineer`.
- **Frontend/design:** `explorer`, `foundation`, `design-system`, `shell`, `screen-implementer`, `motion-polish`, `reviewer`, `frontend-verifier`.
- **Negócio:** `market-research`, `pricing-cac-forecast`, `compliance-legal-watch`, `content-fiscal`, `customer-success`, `product-analytics`.

Comandos: `/atualizar-aliquota` · `/validar-fiscal` · `/revisar-pr` · `/verificar-front` · `/fechar-sprint` · `/pulse-negocio` · `/ci`.

---

## Planejamento — o que vem a seguir

### 1. Atualização fiscal temporal (acionável agora — `[risco-cliente]`)
- **Tabelas INSS / IRRF / FGTS 2026.** O seed vigente é 2025 (Portaria 6/2025); em 2026 a folha calcula errado. É um `INSERT` de nova vigência SCD (`valid_from='2026-01-01'`) — **não pode ser hardcodado sem fonte oficial**. Aguarda os valores da Portaria Interministerial MPS/MF 2026 + tabela IRRF 2026. Fluxo: `/atualizar-aliquota` (gera migration + golden test, roda a suite e **para para aprovação humana**).

### 2. Frontend — re-engenharia "Arkan" (em andamento)
Fases seriais → paralelas: **0** tokens/fontes → **1** design-system (primitivas + `blueprint/` + `lib/motion`) → **2** shell (sidebar/topbar/Lenis) → **3** telas A–E (paralelo, 1 worktree por domínio) → **4** polish (motion premium, perf, a11y, dark mode). Gates anti-AI-slop + invariantes de função em todo PR. Tela **Notas** = gabarito de ouro. Contrato em [docs/restructure-frontend/](docs/restructure-frontend/) + [docs/HANDOFF.md](docs/HANDOFF.md).

### 3. Reforma Tributária — Fase 5 (deferida, aguarda terceiros — `[externo-runbook]`)
Alíquotas IBS por UF, Imposto Seletivo, **split payment 2027**, Bloco K, ajustes NFC-e/CT-e — dependem de RFB / Comitê Gestor publicarem regulamentação e leiautes. Rastreado em [docs/pendencias/runbook-ativacao-externos.md](docs/pendencias/runbook-ativacao-externos.md).

### 4. Ativações de deploy (operacionais — decisões de produção)
- **Celery** worker/beat (pacote opt-in: `poetry add celery[redis]`)
- **Storage S3/GCS** real para recibos SERPRO, DANFSE, holerite PDF, arquivos SPED
- **Scrapers** CRF/CNDT e Sintegra/RFB (hoje aceitam snapshot manual / placeholder)
- Credenciais reais Focus/Pluggy + certificado **A1** do eSocial (ativação consciente, §8.11–8.12)

### 5. Lapidação contábil (nice-to-have)
Registros SPED restantes (J800/J900, 0930/Y600, M400/M800, 0200/H010) e classificação inteligente de NF de entrada por CFOP/NCM via LLM. Detalhe em [docs/ROADMAP_CONTABIL_COMPLETO.md](docs/ROADMAP_CONTABIL_COMPLETO.md).

### 6. Negócio (sob demanda)
Pulse de mercado/pricing/legislação via `/pulse-negocio`; marcos comerciais do plano: **Fase 2** 50 pagantes / MRR R$10k → **Fase 3** 200 pagantes / MRR R$40k → 1.000+ pagantes.

---

## Métricas de qualidade (gates de merge)

- **pytest** — 2520 testes verdes (golden + eval) é critério de merge.
- **mypy strict** — 0 erros em 357 arquivos.
- **bandit** — 0 issues.
- **Frontend** — build de produção passa; Lighthouse desktop 96–99 Performance nas rotas autenticadas.
- Violação de qualquer princípio inviolável bloqueia merge tanto quanto teste vermelho.

> Para agentes: comece sempre por [`CLAUDE.md`](CLAUDE.md), depois [`log_agente.md`](log_agente.md) (backend) ou [`docs/HANDOFF.md`](docs/HANDOFF.md) (frontend), e trate [`docs/PlanoBackend.md`](docs/PlanoBackend.md) / [`docs/Plano.md`](docs/Plano.md) como fonte de verdade.
