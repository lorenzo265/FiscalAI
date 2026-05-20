---
tags: [principio, integracoes, idempotencia]
fonte: "[[PlanoBackend]] §8.9"
status: ativo
---

# 09 — Idempotência em integrações externas

> Princípio inviolável §8.9. Fonte: [[PlanoBackend]].

## Regra

Toda chamada a Focus NFe / SERPRO / Pluggy usa `idempotency_key`. Em retry: mesma key → mesmo resultado. Todo `POST` a integração externa carrega a key.

## Padrão de referência

`app/modules/provisoes/service.py` (service + idempotência). Ex. de derivação de key: `uuid5(NAMESPACE, "empresa|categoria|hash|dia")`.

## O que nunca fazer

- ❌ `POST` a integração externa sem `idempotency_key`.
- ❌ Gerar nova key num retry da mesma operação.

## Relacionado

- [[modulos/conciliacao|conciliacao]] (Pluggy)
- [[sprints/sprint-13-marketplace|Sprint 13]] (idempotency_key em consulta_marketplace)
- [[pendencias/webhook-pluggy-sync|Pendência: webhook Pluggy]]
