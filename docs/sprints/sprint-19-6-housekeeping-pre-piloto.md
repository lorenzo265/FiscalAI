---
tags: [sprint, housekeeping, pre-piloto, riscos, deploy, fase-3, concluida, extra]
fonte: "Decisão pós-Sprint 19.5 (2026-05-27) — fechar todos riscos antes do piloto pago"
status: concluida
fase: 3
ordem: "executou após [[sprints/sprint-19-5-tabelas-tributarias]], antes de [[sprints/sprint-19-7-backlog-tecnico]]"
estimativa_dias: 14-16
testes_estimados: +80
testes_final: 1885
testes_entregues: 64
pendencias_resolvidas: [1, 2, 4, 11, 14, 16, 17, 18, 31, 33, 34, 37, 40, 41, 42]
pendencias_parcialmente_resolvidas: [3]
concluida_em: 2026-05-28
marco: "16 de 17 pendências [risco-*] fechadas estruturalmente — green light pra Sprint 20 piloto LP"
---

# Sprint 19.6 — Housekeeping pré-piloto

> **Sprint extra**, análoga à [[sprint-15-advisor|15.5]] (envio real WhatsApp)
> e [[sprint-19-5-tabelas-tributarias|19.5]] (painel admin tabelas). Fecha
> os 16 itens com tag `[risco-cliente]` / `[risco-regulatorio]` / `[risco-deploy]`
> do `log_agente.md` antes do piloto pago da Sprint 20.
>
> Primeira de 3 sprints de fechamento ("trilha 100%"):
> - **19.6** — riscos críticos (esta) → green light pra Sprint 20
> - [[sprint-19-7-backlog-tecnico|19.7]] — backlog técnico (scope-cuts prioritários)
> - [[sprint-19-8-cleanup-externos|19.8]] — cleanup + runbook dos externos

## Contexto

A Sprint 19.5 fechou as pendências #9 (INSS/IRRF/FGTS 2026) e #37 (INSS 2024
retroativa) **estruturalmente** via painel admin. Mas o `log_agente.md`
ainda tem 38 pendências ativas; 16 delas são **bloqueadoras** do piloto
pago da Sprint 20 (10 empresas reais, MRR R$40k+) — incluindo riscos diretos
ao cliente (CIAP, vencimento ICMS por UF, S-2400 errado no eSocial) e
riscos de deploy que travam features (Celery não instalado, storage só
em BYTEA, código_municipio_ibge ainda nullable).

**Princípio governante:** §8.6 (re-check determinístico) e §8.12 (transmissão
é ato consciente do cliente). Quando vai cobrar do cliente, não pode ter
bug fiscal latente.

## Objetivo

Fechar todos os 16 itens `[risco-*]` ativos. Marco mensurável:

- ✅ Suite **~1900 testes** (estimativa: +80 vs 1821 da 19.5)
- ✅ mypy strict 0 erros em ~350 arquivos
- ✅ Todas as 4 pendências `[risco-cliente]` ativas fechadas
- ✅ Todas as 2 pendências `[risco-regulatorio]` fechadas
- ✅ Todas as 10 pendências `[risco-deploy]` resolvidas
- ✅ Celery instalado real + worker + beat rodando (gate hard #1 do `DEPLOY.md`)
- ✅ Storage S3/GCS plugado em `app/shared/storage/` (gate soft)

## Marco da sprint

- ⏳ Suite +~80 testes
- ⏳ Princípios §8.1 RLS, §8.6 re-check, §8.9 idempotência, §8.10 observabilidade reforçados em todo PR
- ⏳ `log_agente.md` "Pendências conscientes" — 16 itens marcados como ✅ resolvidos
- ⏳ Próxima: [[sprint-19-7-backlog-tecnico|Sprint 19.7]] (scope-cuts prioritários)

## Estrutura — 4 PRs

### PR1 — Riscos cliente fiscal (~4 dias, +25 testes)

Os 4 itens `[risco-cliente]` ativos (excluindo #25 LR que foi confirmado
como out-of-scope MVP — ver `log_agente.md`):

**#3 — CRF (Caixa) + CNDT (TST) scraping real**
- Sprint 6 PR1 deixou como `processando` skeleton.
- Sem CRF/CNDT real, cliente que precisa de certidão pra licitação/contrato
  com governo não consegue baixar.
- Implementação: scraping HTML + retry tenacity + parse PDF (reuso do pattern
  `app/shared/integrations/serpro/client.py`).
- Endpoints: `POST /v1/empresas/{eid}/certidoes/crf/solicitar` + idem CNDT.
- Esforço: ~3-4 dias (scraping é fundamentalmente frágil).

**#31 — EFD ICMS-IPI CIAP G110+ (crédito ICMS imobilizado)**
- Sprint 17 PR2 deixou bloco G vazio. Empresa com imobilizado relevante
  (~R$500k+) perde crédito legítimo de 1/48 ICMS por mês.
- Implementação: relacionar `imobilizado_bem` (Sprint 8) × NF-e de aquisição
  com ICMS destacado; gerar G110 (saldo) + G125 (movimentos do período).
- Esforço: ~1-2 dias.

**#33 — EFD ICMS-IPI vencimento ICMS por UF**
- Sprint 17 PR2 hardcoded dia 10 do mês seguinte como vencimento E116.
- Implementação: estender `aliquota_icms_uf` com coluna `dia_vencimento_padrao`
  (SCD Type 2 já ativa) + migration aditiva + service usa lookup.
- Esforço: 1 dia.

**#37 — INSS 2024 retroativa**
- Sprint 18 PR2 valida `periodo_inicio >= 2024-01-01`, mas seed atual tem
  só 2025. Cliente importando folha 2024 → cálculo errado.
- Implementação: opção A) seed direto via migration nova; opção B) relaxar
  anti-regressão temporal do `TabelaAdminService` (Sprint 19.5) para aceitar
  seed retroativo com flag explícito + auth admin.
- Decisão: **opção A** (migration `0045_seed_inss_2024.py`) — anti-regressão
  protege contra erro acidental do admin, não vale relaxar.
- Esforço: 0.5 dia.

### PR2 — Riscos regulatórios eSocial + SERPRO (~3 dias, +15 testes)

**#14 — S-2400 uso adaptado**
- Sprint 10 PR3 usa S-2400 (leiaute oficial: "Cadastro Beneficiário Ente
  Público / RPPS") para sócios beneficiários de pró-labore. eSocial pode
  rejeitar como leiaute incorreto em prod.
- Implementação: trocar para S-2300 (TSVE — Trabalhador sem Vínculo de
  Emprego) que é o evento canônico pra sócio recebendo pró-labore.
- Esforço: 1-2 dias (refactor de gerador + golden tests).

**#16 — Manual SERPRO PGDAS-D v1.0 vs v1.4+**
- `app/modules/pgdas/service.py::_ID_ATIVIDADE_POR_ANEXO` mapeia Anexo I→1
  etc. (Manual v1.0). Manual v1.4+ usa códigos por atividade-anexo.
- Implementação: re-validar payload contra Manual SERPRO vigente; atualizar
  mapa por (anexo, codigo_atividade_pgdas) em vez de só anexo.
- Esforço: 1-2 dias (re-leitura do manual + ajuste).

### PR3 — Infraestrutura de runtime (Celery + storage + IBGE) (~5 dias, +25 testes)

**#1 — Celery instalado real**
- Hoje stub dual-mode. Instalar pacote (`poetry add celery[redis]`),
  preencher corpos dos 4 stubs mais críticos (sync e-CAC, sync Pluggy,
  depreciação mensal, provisão mensal).
- Workers usam `build_async_engine` da Sprint 19 PR1 + `SET LOCAL ROLE`
  apropriado por contexto.
- Comando: `celery -A app.workers.celery_app worker -Q default -l info`.
- Esforço: ~2 dias.

**#2 — Storage S3/GCS de PDFs**
- Criar `app/shared/storage/` (novo módulo): `S3StorageClient` (interface)
  + `LocalDiskClient` (dev) + `S3Client` (prod boto3) + `GCSClient`
  (futuro). Setting `STORAGE_BACKEND=local|s3|gcs`.
- Backfill: recibos SERPRO + DANFSE Focus + (Sprint 19.7) holerite PDF.
- Esforço: ~2 dias.

**#17 — `codigo_municipio_ibge` NOT NULL**
- Migration `0046_codigo_municipio_ibge_not_null.py` — fase 2 do 2-fases
  da Fase 2 PR6. Pré-requisito: todas as empresas do banco terem IBGE
  preenchido (verificar em pré-migração).
- Esforço: 0.5 dia.

**#41 — Wiring live worker DOU + LLM (Sprint 19.5 PR3 stub)**
- Hoje `_processar_tipo` em `tabelas_varrer_dou.py` é stub.
- Implementação: pipeline real DouClient → httpx download PDF →
  `extrair_texto_pdf` (pdfplumber lazy) → LLMClient com prompt versionado
  → `recheck_llm` → `persistir_extracao_llm`.
- `poetry add pdfplumber` (já documentado como dep opt-in no DEPLOY.md).
- Esforço: ~1 dia.

**#42 — Hook digest admin plugado no advisor**
- Hoje `AlertaAdminService.alertas_para_digest_admin()` existe mas não é
  chamado pelo `app/modules/advisor/gera_digest_semanal.py`.
- Implementação: quando `settings.ADMIN_WHATSAPP_PHONE` configurado,
  gerar digest extra apenas com bullets de alertas críticos pra esse número.
- Esforço: 0.5 dia.

### PR4 — Validações deploy (~2-3 dias, +15 testes)

**#4 — Webhook Pluggy → sync inline**
- Depende de #1 (Celery real). Implementação: webhook persiste
  `pluggy_webhook_event` E dispara `sync_pluggy_empresa.delay()` com
  `SET LOCAL ROLE` admin (SECURITY DEFINER role).
- Esforço: 1 dia.

**#11 — Holerite PDF**
- Depende de #2 (storage). Implementação: gerar PDF do holerite via
  reportlab + persistir no storage + popular `storage_key`.
- Esforço: 1 dia.

**#34 — EFD beat schedule mensal**
- Tasks `sped.gerar_efd_contribuicoes_mensal` + `sped.gerar_efd_icms_ipi_mensal`
  no beat schedule. Pattern: replica `sped.gerar_ecd_anual` + iterar
  empresas LP/LR (Contribuições) e empresas com IE (ICMS-IPI).
- **Nota**: LR confirmado out-of-scope MVP, então EFD-Contribuições só
  cobre LP (cumulativo). EFD ICMS-IPI continua independente do regime.
- Esforço: 0.5 dia.

**#40 — Importador SPED workers >50MB**
- Depende de #1. Upload assíncrono via Celery + presigned S3 (depende #2).
- Esforço: 1 dia.

**#18 — WhatsApp dedup validação (passivo)**
- Validação Grafana: task `whatsapp.expurgar_processadas` deve aparecer
  no schedule e executar daily 04:00. Sem código — só verificação operacional
  após #1 instalado.
- Esforço: 0 dia (validação durante deploy).

**Pendência operacional #25 (LR) — decidida nesta sprint:**

Confirmar item #25 do `log_agente.md` como **decidido fora de escopo MVP**:
PlanoBackend.md §1.1 (linha 41) e §9.3 (linha 1371) sempre cravaram apenas
SN + LP. Empresas LR continuam caindo em `RegimeIncompativel`. Marketplace
de contadores parceiros (Sprint 13) cobre o encaminhamento. Sem trabalho
técnico — apenas atualização do log.

## Princípios cravados (visão consolidada)

| § | Como aplicado |
|---|---|
| 8.1 RLS | Migration #17 (NOT NULL `codigo_municipio_ibge`) preserva RLS; workers Celery usam `SET LOCAL` por tenant |
| 8.5 Citação | #14 S-2300 (substituindo S-2400) cita leiaute eSocial v2.5+ |
| 8.6 Re-check | #41 DOU+LLM wiring usa `recheck_llm.py` da Sprint 19.5 |
| 8.9 Idempotência | #4 webhook Pluggy + #40 importador SPED via `idempotency_key` UUID5 |
| 8.10 Observabilidade | #1 Celery beat schedule visível em Grafana; #18 dedup validado |
| 8.12 Out-of-scope | #25 LR confirmado como out-of-scope MVP (Plano §1.1 + §9.3) |

## Pendências resolvidas estruturalmente

* **#3** CRF + CNDT scraping real → PR1
* **#14** S-2400 → S-2300 → PR2
* **#16** PGDAS-D Manual v1.4+ → PR2
* **#17** `codigo_municipio_ibge` NOT NULL → PR3
* **#18** WhatsApp dedup validação → PR4 (passivo)
* **#31** EFD ICMS-IPI CIAP G110+ → PR1
* **#33** EFD ICMS-IPI vencimento ICMS por UF → PR1
* **#37** INSS 2024 retroativa → PR1
* **#1** Celery instalado real → PR3
* **#2** Storage S3/GCS → PR3
* **#4** Webhook Pluggy → sync inline → PR4
* **#11** Holerite PDF → PR4
* **#34** EFD beat schedule mensal → PR4
* **#40** Importador SPED workers >50MB → PR4
* **#41** Wiring live worker DOU + LLM → PR3
* **#42** Hook digest admin plugado no advisor → PR3

## Pendência decidida (sem trabalho técnico)

* **#25** Lucro Real EFD-Contribuições não-cumulativo → **decidido out-of-scope MVP**.
  PlanoBackend §1.1 + §9.3 sempre listaram apenas SN + LP. Atualizar item
  do log com nota da decisão (PR4 commit final).

## Out-of-scope explícito

❌ **Scope-cuts** (14 itens — #5, #6, #10, #12, #13, #15, #27, #28, #29, #30, #32, #35, #36, #38, #39) — ficam para [[sprint-19-7-backlog-tecnico|Sprint 19.7]].
❌ **Externos** (6 itens — #19, #20, #21, #22, #23, #24) — viram runbook na [[sprint-19-8-cleanup-externos|Sprint 19.8]].
❌ **eSocial XMLDSig + envio real** — escopo grande (~7-10 dias), fica na Sprint 19.7.

## Estimativa consolidada

| PR | Esforço | Migrations | Endpoints | Testes |
|---|---|---|---|---|
| PR1 — Riscos cliente fiscal | 4d | 0045 (INSS 2024) + 0046 (`dia_vencimento_padrao` ICMS) | +2 (CRF/CNDT) | +25 |
| PR2 — Riscos regulatórios | 3d | (refactor) | (atualiza existentes) | +15 |
| PR3 — Infra runtime | 5d | 0047 (IBGE NOT NULL) | (atualiza existentes) | +25 |
| PR4 — Validações deploy | 3d | — | (atualiza webhook) | +15 |
| **Total** | **14-16 dias** | **3 migrations** | **+2 endpoints** | **+80 testes** |

## Cronograma de execução

```
[ Sprint 19.5 ✅ — Painel admin tabelas tributárias ]
                          ↓
[ Sprint 19.6 — Housekeeping pré-piloto ]    ← esta sprint
                          ↓
[ Sprint 19.7 — Backlog técnico ]
                          ↓
[ Sprint 19.8 — Cleanup + runbook externos ]
                          ↓
[ Sprint 20 — Piloto LP pronto pra venda ]   ← marco Fase 3
```

## Referências

- Pendências: `log_agente.md` §"Pendências conscientes" — 16 itens com tag `[risco-*]`
- Princípios: [[principios/06-recheck-deterministico]], [[principios/09-idempotencia]], [[principios/10-observabilidade]], [[principios/12-transmissao-consciente]]
- Documentação deploy: `analista-fiscal-api/DEPLOY.md` §11
- Sprint anterior: [[sprints/sprint-19-5-tabelas-tributarias]]
- Próxima sprint: [[sprints/sprint-19-7-backlog-tecnico]]
- ADRs candidatos pós-implementação:
  - `decisoes/adr-0019-lucro-real-fora-de-mvp.md` (decisão #25)
  - `decisoes/adr-0020-celery-workers-prod.md` (decisão #1 — corpos das tasks + beat real)
