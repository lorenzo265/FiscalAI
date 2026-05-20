---
tags: [modulo, conciliacao, open-finance, pluggy]
fonte: "[[PlanoBackend]] §7.3, §11 (Sprint 7)"
sprint_origem: "7"
path: "analista-fiscal-api/app/modules/conciliacao/"
status: concluido
---

# Módulo `conciliacao`

> Bounded context de conciliação bancária via Open Finance. Fonte: [[PlanoBackend]] §7.3 (Sprint 7).

## Responsabilidade

Integração Pluggy (widget), sync de transações e algoritmo de match banco × NF.

## Integração

`app/shared/integrations/pluggy.py`. Toda chamada usa `idempotency_key`.

## Pendências do módulo

- [[pendencias/webhook-pluggy-sync|Webhook Pluggy → sync inline]] (cross-tenant routing exige Celery + role admin).
- [[pendencias/celery-instalacao|Celery instalação]] (sync assíncrono depende disso).

## Princípios aplicados

- [[principios/09-idempotencia|09 — Idempotência]] (POST a Pluggy)
- [[principios/01-rls-multi-tenant|01 — RLS multi-tenant]]

## Relacionado

- [[modulos/relatorios|relatorios]] (DFC usa dados conciliados)
- [[README|Hub do vault]]
