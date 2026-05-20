---
tags: [adr, arquitetura, postgres, multi-tenant]
adr: "0004"
fonte: "[[PlanoBackend]] §18.1, §8.1"
status: aceito
---

# ADR-001 — Multi-tenancy via Postgres RLS

> Corresponde ao ADR 0004 do Plano (§18.1). Fonte: [[PlanoBackend]].

## Contexto

Sistema multi-tenant para PMEs. Precisa de isolamento forte de dados fiscais entre escritórios, com baixo custo operacional e sem explosão de schemas.

## Decisão

Um único schema com `tenant_id` em toda tabela de domínio + **Row Level Security** do Postgres. Sessão injeta `SET LOCAL app.tenant_id` por request.

## Alternativas descartadas

- Schema por tenant — complexidade de migration linear no nº de tenants.
- Banco por tenant — custo e operação inviáveis na escala-alvo.

## Consequências

- ✅ Isolamento garantido no nível do banco, não do app.
- ✅ Migrations únicas.
- ⚠️ Toda sessão **precisa** do `SET LOCAL` — ver [[principios/01-rls-multi-tenant|princípio §8.1]].

## Relacionado

- [[principios/01-rls-multi-tenant|01 — RLS multi-tenant]]
- [[principios/07-lgpd-first|07 — LGPD-first]]
- ADR-0011 (Marketplace) → [[sprints/sprint-13-marketplace|Sprint 13]]
