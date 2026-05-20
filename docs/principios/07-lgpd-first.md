---
tags: [principio, lgpd, seguranca, privacidade]
fonte: "[[PlanoBackend]] §8.7"
status: ativo
---

# 07 — LGPD-first

> Princípio inviolável §8.7. Fonte: [[PlanoBackend]].

## Regra

- AES-256 em repouso (pgcrypto + KMS), TLS 1.3 em trânsito.
- Dados em território nacional (`sa-east-1`).
- Logs por titular (audit_log particionado); CNPJ/CPF/email redacted antes de Loki.
- Endpoints `/lgpd/exportar` e `/lgpd/excluir`. Retenção 5 anos.
- Consentimento versionado no onboarding.
- DPO obrigatório ao passar de 100 clientes.
- Compartilhamento com contador parceiro requer **consentimento explícito por consulta**.

## Relacionado

- [[principios/01-rls-multi-tenant|01 — RLS multi-tenant]]
- [[sprints/sprint-13-marketplace|Sprint 13 — Marketplace]] (consentimento por consulta)
- [[principios/10-observabilidade|10 — Observabilidade]]
