# Analista Fiscal — Backend (`analista-fiscal-api`)

Backend do **Analista Fiscal**: sistema fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido), com ingestão automática de NF-e/NFS-e, cálculo determinístico de tributos, apuração mensal, conciliação bancária via Open Finance, departamento pessoal completo e assistente IA com citação obrigatória.

> **Fonte de verdade:** [`../docs/PlanoBackend.md`](../docs/PlanoBackend.md). Stack, arquitetura e princípios são cravados — não substituir, não improvisar.

## Status

**Sprint 0 — Setup** (atual). Veja [`docs/sprints/sprint-00.md`](docs/sprints/sprint-00.md) para o checklist binário.

## Stack (resumo, ver §3 do Plano)

- **Python 3.12** · **FastAPI 0.115** · **SQLAlchemy 2.0 async** · **Alembic** · **Pydantic v2**
- **PostgreSQL 16** + **pgvector 0.7+** · **Redis 7.4** · **Ollama** (Gemma 3 4B local)
- **Celery 5.4** (Sprint 2+) · **Gemini 2.5 Flash/Lite/Pro** (Sprint 3+)
- Integrações: **Focus NFe**, **SERPRO Integra Contador**, **Pluggy**, **Meta WhatsApp Cloud API**

## Quickstart (dev local)

Pré-requisitos: Docker Desktop com Compose v2.

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/healthz
```

Esperado: `{"status":"ok"}`.

Para ver Postgres + Redis + Ollama prontos:

```bash
curl http://localhost:8000/readyz
```

OpenAPI interativo: http://localhost:8000/docs

### Comandos úteis

```bash
docker compose logs -f api          # ver logs do FastAPI
docker compose down                 # parar tudo
docker compose down -v              # parar e apagar volumes (zera dados)
docker compose exec postgres psql -U fiscal fiscal   # abrir psql
```

## Desenvolvimento sem Docker (opcional)

```bash
poetry install --with dev
poetry run uvicorn app.main:app --reload
poetry run pytest
poetry run ruff check .
poetry run mypy app
```

## Estrutura de pastas

Veja §4.2 do Plano. Resumo:

```
app/
├── main.py             # FastAPI entrypoint + lifespan + healthz/readyz
├── config.py           # pydantic-settings
├── modules/            # bounded contexts (auth, empresa, fiscal, notas, ...) — Sprint 1+
├── shared/             # db, llm, auth, crypto, audit, integrations
└── workers/            # Celery (Sprint 2+)

alembic/                # migrations (vazio na Sprint 0)
tests/                  # unit, integration, e2e, golden, eval
infra/docker/           # Dockerfile.api / .worker / .beat
docs/adr/               # 10 ADRs assinados na Sprint 0
docs/sprints/           # checklist por sprint
.github/workflows/ci.yml
```

## Como contribuir (8-step chain)

Toda feature segue:

1. Ler o `PlanoBackend.md` e ADRs aplicáveis
2. Modelar (SQLAlchemy + Alembic com `tenant_id` + RLS policy)
3. Schemas Pydantic (input/output)
4. Lógica determinística pura (golden test **antes** do código)
5. Repositório / data access
6. Service / use case
7. Endpoint FastAPI ou Celery task
8. Testes: unit (golden) → integration → e2e

Pular um passo = furo em produção. PR sem golden test = ❌ no review gate.

## Princípios invioláveis (§8 do Plano)

1. Multi-tenancy via RLS ativa desde dia 1
2. Fatos fiscais imutáveis (cancelamento = nova linha)
3. Decisões versionadas (SCD Type 2)
4. Golden tests como barreira de merge
5. Citação obrigatória em respostas LLM
6. Re-check determinístico pós-LLM
7. LGPD-first (AES-256, TLS 1.3, dados em sa-east-1)
8. **LLM nunca escreve fatos** — pipeline determinístico ingere/calcula/persiste
9. Idempotência em integrações externas (`idempotency_key`)
10. Observabilidade obrigatória (Langfuse, Tempo, Sentry, Grafana)

## ADRs

Todas as decisões arquiteturais ficam em [`docs/adr/`](docs/adr/). Os 10 ADRs da Sprint 0:

- [0001 — FastAPI vs Litestar](docs/adr/0001-fastapi-vs-litestar.md)
- [0002 — pgvector vs Qdrant](docs/adr/0002-pgvector-vs-qdrant.md)
- [0003 — LLM 3-camadas](docs/adr/0003-llm-3-camadas.md)
- [0004 — Multi-tenancy via RLS](docs/adr/0004-multi-tenancy-rls.md)
- [0005 — Fatos imutáveis](docs/adr/0005-fatos-imutaveis.md)
- [0006 — Focus NFe vs PlugNotas](docs/adr/0006-focus-nfe-vs-plugnotas.md)
- [0007 — Pluggy vs Belvo](docs/adr/0007-pluggy-vs-belvo.md)
- [0008 — Citação obrigatória](docs/adr/0008-citacao-obrigatoria.md)
- [0009 — SERPRO Integra Contador](docs/adr/0009-serpro-integra-contador.md)
- [0010 — Meta WhatsApp Cloud API direto](docs/adr/0010-meta-whatsapp-direto.md)

## Roadmap

16 sprints, 32 semanas. Ver §9 do Plano. MVP fechado na Sprint 6 (5 empresas demo emitindo NFS-e e pagando DAS).
