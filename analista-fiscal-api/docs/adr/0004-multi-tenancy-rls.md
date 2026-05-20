# ADR 0004 — Multi-tenancy via RLS Postgres

## Status

accepted (2026-05-10)

## Contexto

O produto é multi-tenant desde o dia 1 — escritórios contábeis com múltiplas empresas e empresas direto. Vazamento de dados entre tenants é risco existencial (LGPD + reputacional + responsabilidade civil). Precisamos de um mecanismo de isolamento que seja: (a) ativo por padrão, (b) impossível de esquecer, (c) auditável.

Opções principais: Row-Level Security do Postgres, schema-per-tenant, banco-per-tenant, filtro Python em todo repositório.

## Decisão

Usar **Row-Level Security (RLS)** nativo do PostgreSQL 16, com:

- `tenant_id UUID NOT NULL` em **toda** tabela de domínio.
- Policy `tenant_isolation` em toda tabela: `USING (tenant_id = current_setting('app.tenant_id')::UUID)`.
- Toda `AsyncSession` entregue a um endpoint ou worker faz `SET LOCAL app.tenant_id = :tid` no início da transação, via dependency `get_session`.
- Workers Celery propagam `tenant_id` em headers da task.

## Consequências

**Positivas:**
- Defesa em profundidade — mesmo se o desenvolvedor esquecer o `WHERE tenant_id = ...`, RLS bloqueia.
- Auditável — `pg_policies` lista as políticas; um teste automático por tabela pode validar presença.
- Backup único, índices únicos, escalabilidade simples.
- Postgres planner combina RLS com índices compostos (`tenant_id, ...`) eficientemente.

**Negativas:**
- Esquecer de chamar `SET LOCAL` deixa a sessão sem tenant — todas as queries retornam vazio (em vez de vazar). Mitigação: dependency obrigatória + teste de smoke por endpoint.
- Migrations precisam criar a policy junto com a tabela — gate explícito no review.
- Connection pool não pode reusar conexões entre tenants sem `RESET` explícito. Mitigação: usar `SET LOCAL` (escopo de transação).

## Alternativas consideradas

- **Schema-per-tenant** — explode em milhares de schemas; backup, migration e monitoramento viram pesadelo.
- **Banco-per-tenant** — só faz sentido para enterprise único; inviável para PMEs com pricing R$149–R$349/mês.
- **Filtro Python no repositório** — frágil; um `select()` esquecido vaza. Sem defesa em profundidade.

## Referências

- `PlanoBackend.md` §5.1, §8.1
- Postgres docs: https://www.postgresql.org/docs/16/ddl-rowsecurity.html
