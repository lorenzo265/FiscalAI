---
tags: [pendencia, infra, celery, worker]
fonte: "log_agente.md — Pendências conscientes #1"
status: aberta
prioridade: media
---

# Pendência — Instalação do Celery

> Pendência consciente. Fonte: `log_agente.md`.

Os workers já têm **beat schedule configurado**, mas o pacote é opt-in: `poetry add celery[redis]`. Sem isso, tarefas agendadas não rodam.

## Bloqueia

- [[pendencias/webhook-pluggy-sync|Webhook Pluggy → sync inline]]
- [[pendencias/sintegra-scraping|Sintegra/RFB scraping]]
- [[pendencias/crf-cndt-scraping|CRF/CNDT scraping]]

## Relacionado

- [[modulos/conciliacao|conciliacao]]
- [[README|Hub do vault]]
