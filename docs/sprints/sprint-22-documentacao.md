---
sprint: 22
titulo: "Documentação + Handover"
fase: 4
status: concluida
marco: "Produto completo PME-alvo — Sistema pronto para 1.000+ pagantes"
testes_finais: 2200
atualizado: 2026-05-31
---

# Sprint 22 — Documentação + Handover

**Esta é a sprint final do roadmap.** Fecha a Fase 4 (Lapidação) e entrega o produto completo para PMEs brasileiras.

Relacionado: [[roadmap]] · [[onboarding-dev]] · [[decisoes/adr-015-checklist-lp]] · [[decisoes/adr-017-rate-limiting-redis]]

---

## PR1 — Runbooks operacionais + Onboarding + ADRs

O que entrou:
- `docs/runbooks/deploy-producao.md` — checklist pré/pós deploy, zero-downtime rolling, migrations, janelas proibidas.
- `docs/runbooks/on-call-playbook.md` — matriz SEV1-4, diagnóstico por sintoma (latência, 5xx, RLS violation, Celery, LLM, rate limit), comandos de emergência, postmortem.
- `docs/runbooks/backup-recovery.md` — RTO 4h / RPO 1h, RDS PITR, pg_dump, Redis RDB, testes trimestrais, LGPD.
- `docs/onboarding-dev.md` — setup em <60min, estrutura do projeto, 5 conceitos essenciais, 8 passos para nova feature, comandos dia-a-dia, tabela "o que nunca fazer".
- `docs/decisoes/adr-015-checklist-lp.md` — decisão do checklist LP + health score (Sprint 20).
- `docs/decisoes/adr-017-rate-limiting-redis.md` — decisão Fixed Window INCR+EXPIRE (Sprint 21).

---

## PR2 — OpenAPI metadata + testes de contrato + guia

**Testes adicionados:** +13 (total pós-PR2: 2200)

O que entrou:
- `app/main.py` — FastAPI metadata v1.0.0: descrição de autenticação + rate limiting + princípios; contato; tags de domínio documentadas (17 tags).
- `tests/unit/api/__init__.py` + `tests/unit/api/test_openapi_contract.py` — 13 golden tests: versão, título, autenticação, rate limiting na descrição, contato com email, tags críticas, endpoints críticos, healthz funcional.
- `docs/api/openapi-guide.md` — como acessar Swagger/ReDoc/JSON, auth, rate limiting, importar no Postman.

---

## Definition of Done ✅ (Fase 4 completa)

- [x] pytest: 2200 passed, 2 skipped
- [x] mypy strict: 0 erros
- [x] Runbooks operacionais: deploy, on-call, backup/recovery
- [x] Onboarding novo dev documentado
- [x] ADR-015 (checklist LP) e ADR-017 (rate limiting) registrados
- [x] OpenAPI v1.0.0 com metadata completo e security scheme documentado
- [x] Guia `docs/api/openapi-guide.md` publicado
- [x] Log de agente atualizado
- [x] Roadmap marcado ✅ (Sprint 22 + todas as Fases 1-4)

---

## 🎉 Sprints 0–22 concluídas — produto completo PME-alvo

| Fase | Sprints | Marco |
|---|---|---|
| Fase 1 MVP (S0-6) | ✅ | Pipeline NFS-e + DAS + DEFIS + e-CAC |
| Fase 2 Expansão (S7-13) | ✅ | 50 pagantes + MRR R$10k+ |
| Fase 3 SPED+Reforma (S14-20) | ✅ | 200 pagantes + MRR R$40k+ + LP completo |
| Fase 4 Lapidação (S21-22) | ✅ | Pen test sem findings críticos + runbooks + OpenAPI |
