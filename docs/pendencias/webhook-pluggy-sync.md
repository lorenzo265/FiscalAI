---
tags: [pendencia, pluggy, webhook, conciliacao]
fonte: "log_agente.md — Pendências conscientes #4"
status: aberta
prioridade: media
---

# Pendência — Webhook Pluggy → sync inline

> Pendência consciente. Fonte: `log_agente.md`.

O webhook do Pluggy hoje só **persiste o evento**. O cross-tenant routing (rotear o evento para o tenant certo) exige Celery + role admin. Sync ainda é inline.

## Bloqueado por

- [[pendencias/celery-instalacao|Celery instalação]]

## Relacionado

- [[modulos/conciliacao|conciliacao]]
- [[principios/09-idempotencia|09 — Idempotência]]
- [[README|Hub do vault]]
