---
tags: [deploy, infra, operacional]
fonte: "Inventário pós-Sprint 19.5 (2026-05-27)"
status: ativo
atualizado: 2026-05-27
---

# 🚀 Deploy — Analista Fiscal API

Mapeamento operacional do que precisa estar configurado pra rodar o sistema em produção.

**Fonte de verdade:** `analista-fiscal-api/DEPLOY.md` (raiz do sub-projeto backend). Esta nota é o ponto de entrada no knowledge graph; o documento real, com tabelas detalhadas por setting e decisões por integração, vive lá.

## TL;DR

**5 gates `hard`** sem os quais a API não aceita primeiro request:

1. Celery instalado + `worker` + `beat` rodando.
2. `JWT_SECRET` ≥ 32 bytes (não o placeholder).
3. `FOCUS_NFE_TOKEN` válido + `FOCUS_NFE_SANDBOX=false`.
4. `SERPRO_CONSUMER_KEY` + `SECRET` + `SANDBOX=false`.
5. `DATABASE_URL` real + `alembic upgrade head` rodado.

**6 gates `soft`** (sistema sobe sem, mas feature off): Storage S3, Langfuse, Sentry, template WhatsApp, EFD beat tasks, CRF/CNDT scraping.

## Decisões arquiteturais consolidadas

- **LLM dual** — Ollama+Gemma 3 4B local em dev (zero custo, privacy); Gemini 2.5 Flash em prod. `contem_pii=True` força Ollama mesmo em prod ([[principios/07-lgpd-first]]). Sem `GEMINI_API_KEY` em prod → fallback Ollama (degradação graceful).
- **Fail-closed em segredos vazios** — `MARKETPLACE_ADMIN_TOKEN=""` → endpoints admin retornam 503; `PLUGGY_WEBHOOK_SECRET=""` → webhook rejeita tudo; `WHATSAPP_DIGEST_TEMPLATE_ATIVO=false` → digest preparado mas não enviado.
- **Sandbox em dev por default** — Focus NFe + SERPRO. Prod exige flip explícito.
- **Painel admin substitui migration** — SCD tributárias INSS/IRRF/FGTS atualizam via `POST /v1/admin/tabelas/<tipo>/vigencia` ([[sprints/sprint-19-5-tabelas-tributarias]]), não por nova migration toda vez que sai Portaria.
- **Trigger SCD fecha `valid_to` automaticamente** — `scd_close_previous_valid_to` (migration 0025) em 8 tabelas tributárias.
- **Pool calibrado para 1k empresas** — `DB_POOL_SIZE=20` + `DB_MAX_OVERFLOW=30` (Sprint 19 PR1).
- **Roles Postgres não-superuser** — `fiscal_app` (tenant-scoped), `tax_table_admin` (cross-tenant SCD), `marketplace_partner` (consultas marketplace).

## Pendências `[risco-deploy]`

10 itens (8 acumulados + 2 introduzidos pela Sprint 19.5 PR3):

| # | Pendência | Sprint endereçará |
|---|---|---|
| 1 | Celery instalado real | Sprint 20 PR4 housekeeping |
| 2 | Storage S3/GCS | PR pré-Sprint 20 |
| 4 | Webhook Pluggy → sync inline | Depende #1 |
| 11 | Holerite PDF | Depende #2 |
| 17 | `codigo_municipio_ibge` NOT NULL | PR pré-Sprint 20 |
| 18 | WhatsApp dedup 7d (validação Grafana) | Depende #1 |
| 34 | EFD beat schedule mensal | Depende #1 |
| 40 | Importador SPED workers >50MB | Depende #1 |
| **41** | Wiring live worker DOU + LLM | Sprint 20 PR4 |
| **42** | Hook digest admin plugado no advisor | Sprint 20 PR4 |

**Total: ~10 dias = 1 sprint dedicada de housekeeping pré-piloto.**

Detalhamento completo: `analista-fiscal-api/DEPLOY.md` §11 + `log_agente.md` §"Pendências conscientes".

## Relacionado

- [[PlanoBackend]] §11 — cronograma de sprints
- [[roadmap]] — estado atual (21 sprints concluídas, próxima é Sprint 20 piloto LP)
- [[principios/01-rls-multi-tenant]] — RLS via `SET LOCAL app.tenant_id`
- [[principios/07-lgpd-first]] — AES-256 via pgcrypto + LLM com PII em Ollama
- [[principios/09-idempotencia]] — `idempotency_key` em toda integração externa
- [[sprints/sprint-19-5-tabelas-tributarias]] — painel admin que substituiu migration tributária
