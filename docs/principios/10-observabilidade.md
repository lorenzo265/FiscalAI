---
tags: [principio, observabilidade, devops]
fonte: "[[PlanoBackend]] §8.10"
status: ativo
---

# 10 — Observabilidade obrigatória

> Princípio inviolável §8.10. Fonte: [[PlanoBackend]].

## Regra

- Cada chamada LLM em **Langfuse** (prompt + resposta + custo + latência).
- Cada chamada SERPRO/Focus/Pluggy em **Tempo** (traces).
- Cada erro em **Sentry** self-hosted.
- Métricas no **Grafana**; logs em **Loki** (PII redacted).

## Logging estruturado

```python
import structlog
log = structlog.get_logger(__name__)
log.info("evento.acao", empresa_id=str(empresa.id), valor=str(decimal))  # Decimal → str
```

## O que nunca fazer

- ❌ `print()` em vez de logger estruturado.
- ❌ CNPJ/CPF/email chegando cru no Loki.

## Relacionado

- [[principios/07-lgpd-first|07 — LGPD-first]]
- [[principios/09-idempotencia|09 — Idempotência]]
