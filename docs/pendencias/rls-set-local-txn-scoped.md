---
tags: [pendencia, seguranca, rls, multi-tenant, banco]
fonte: "Auditoria backend 2026-06-04 — Lote E (risco estrutural latente)"
status: aberta
prioridade: media
---

# Pendência — RLS SET LOCAL é escopo de transação

> Pendência consciente. Fonte: auditoria de plataforma multi-tenant (2026-06-04).

## Descrição

`app/shared/db/deps.py` usa `SET LOCAL app.tenant_id = '...'` (ou equivalente
`set_config('app.tenant_id', ..., is_local := true)`) para injetar o tenant na
sessão antes de qualquer query. O modificador `LOCAL` (ou `is_local = true`) faz
o setting ser **desfeito automaticamente ao fim da transação atual**.

Hoje isso é seguro porque o padrão de uso é:
```
BEGIN → SET LOCAL → queries → COMMIT (ou ROLLBACK) → conexão devolvida ao pool
```
O `SET LOCAL` nunca sobrevive ao `COMMIT` — o pool recebe a conexão de volta
com o contexto limpo.

## Risco latente

Se um `service.py` futuro realizar **mais de um `session.commit()` dentro do
mesmo ciclo de request** (ex.: two-phase commit, batch com flush parcial, ou
uso incorreto de `savepoint`), o segundo bloco de queries rodará **sem o
`app.tenant_id` ativo** — a política RLS enxergará `NULL` e poderá:

- Rejeitar todas as linhas (se a policy usa `USING ... IS NOT DISTINCT FROM ...`),
  causando erro silencioso de "sem dados"; ou
- Retornar dados de outro tenant (se a policy tiver lógica `OR NULL`) —
  **vazamento cross-tenant**.

## Situação atual

- Nenhum service existente faz múltiplos commits por request (confirmado em
  auditoria de código em 2026-06-04).
- O risco é **potencial**, não explorado — mas basta um commit extra inadvertido
  para abrir a brecha.

## Mitigações recomendadas

### Opção A — Proibir múltiplos commits por request (preferida)
Adicionar guard em `deps.py` ou num middleware de sessão que detecta segundo
`session.commit()` e levanta `RuntimeError`. Combinar com um lint/test de
regressão que verifica ausência do padrão `commit(); ... commit()` no mesmo
contexto de request.

### Opção B — Re-aplicar SET LOCAL em `after_commit` hook
Registrar um listener SQLAlchemy `event.listen(session, "after_commit", ...)` que
reaplica `SET LOCAL app.tenant_id` após cada commit. Cuidado: o after_commit roda
**fora da transação fechada** — precisa de um novo `BEGIN` implícito, o que acontece
automaticamente no próximo statement SQLAlchemy.

### Opção C — Usar `SET SESSION` (não recomendado)
Trocaria `is_local := true` por `is_local := false`, fazendo o setting sobreviver
à transação. Problema: exige limpeza explícita (`SET app.tenant_id = ''`) antes de
devolver a conexão ao pool — qualquer exception não tratada vazaria o tenant para
o próximo request que receber a mesma conexão.

## Relacionado

- [[principios/01-rls-multi-tenant|Princípio §8.1 — RLS multi-tenant]]
- [[decisoes/adr-001-postgres-rls|ADR 001 — Postgres RLS]]
- `app/shared/db/deps.py` — `get_session` (linha onde `SET LOCAL` é emitido)
