---
tags: [principio, seguranca, multi-tenant, postgres]
fonte: "[[PlanoBackend]] §8.1"
status: ativo
---

# 01 — RLS multi-tenant ativo desde o dia 1

> Princípio inviolável §8.1. Fonte: [[PlanoBackend]].

## Regra

Toda tabela de domínio tem `tenant_id NOT NULL` e **Row Level Security** ativo no Postgres. O middleware FastAPI injeta `app.tenant_id` a cada request via `SET LOCAL`.

## Em código

```python
# get_session com SET LOCAL — app/shared/db/deps.py
await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
```

```python
# policy padrão em toda migration que cria tabela
_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"
op.execute("ALTER TABLE x ENABLE ROW LEVEL SECURITY")
op.execute(f"CREATE POLICY x_tenant ON x USING ({_RLS_USING})")
```

## O que nunca fazer

- ❌ Desativar RLS "temporariamente".
- ❌ Sessão SQLAlchemy sem `SET LOCAL app.tenant_id`.
- ❌ Confiar em filtro `WHERE tenant_id = ...` no app em vez da policy.

## Verificação

Testes de integração validam isolamento cross-tenant. Meta Fase 1: **0 violações de RLS detectadas**.

## Relacionado

- [[principios/07-lgpd-first|07 — LGPD-first]]
- [[decisoes/adr-001-postgres-rls|ADR-001 — Postgres + RLS]]
- Aplica-se a todos os [[README|módulos]].
