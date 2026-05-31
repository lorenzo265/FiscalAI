---
tags: [sprint, performance, escala, cache, onboarding, fase-3, concluida]
fonte: "[[PlanoBackend]] §11 Sprint 19"
status: concluida
fase: 3
marco: "Fase 3 finalizando (S19 = polish para S20 piloto LP)"
testes_baseline: 1671
testes_final: 1756
iniciada_em: 2026-05-26
concluida_em: 2026-05-26
---

# Sprint 19 — Polish + escala

> Penúltima sprint da Fase 3, depois de [[sprints/sprint-18-migracao]]. Tema
> único no Plano (§11, linha 1524): **"Performance tuning, cache layers,
> load testing 1k empresas, bundle onboarding self-service"**. Não há PRs
> detalhados no Plano — escopo refinado durante a sprint.

## Objetivo

A Sprint 20 (piloto Lucro Presumido com **10 empresas reais**) dispara
apurações trimestrais pesadas (IRPJ + CSLL + PIS + Cofins × trimestre ×
empresa) e queries de relatórios (DRE/Balanço/DFC) em produção pela
primeira vez. **Sem polish de performance antes**, esse piloto entra em
risco real de timeout/lock/N+1, e a Fase 3 (200 pagantes, MRR R$40k+)
não tem evidência empírica de que aguenta 1k empresas.

## Marco da sprint

- ⏳ Suite **1671+ testes** + delta — sem regressão de valor
- ⏳ mypy strict 0 erros mantido
- ⏳ Latência p99 balancete trimestral ≤ 200ms (medido em `tests/perf/`)
- ⏳ Princípios §8.1, §8.2, §8.4, §8.9, §8.10 cravados em cada PR
- ⏳ Sprint 20 desbloqueada — apurações LP rodam dentro de budget de
  latência

## Decisões de design (travadas com o usuário)

- **4 PRs, 1 eixo cada** (não os 3 PRs históricos — escopo amplo demais).
- **Ordem:** PR1 (perf DB) → PR3 (load harness) → PR2 (cache) → PR4
  (onboarding). Harness antes do cache para medir baseline real e provar
  ganho com números.
- **Prioridade absoluta:** PR1 = Performance DB — risco direto Sprint 20.
- **`pg_stat_statements`** habilitado via `CREATE EXTENSION` em migration
  0041 (RDS-friendly — assume `shared_preload_libraries` configurado em
  parameter group).
- **Load test em k6** (não Locust) — output Prometheus nativo, integra
  Grafana existente.
- **NÃO** mexer em particionamento declarativo de tabelas grandes
  (`audit_log`, `documento_fiscal`, `lancamento_contabil`) — intrusivo,
  exige revisar RLS policies em partições. Documentar como Sprint 21+.

## PRs

### PR1 — Performance DB (2026-05-26, [[../log_agente#sprint-19-pr1]])
- Migration 0041: `CREATE EXTENSION pg_stat_statements` + 4 índices
  novos via `CREATE INDEX CONCURRENTLY` em `autocommit_block` (ajuda
  balancete/razão, LP trimestral, last-value de saldos).
- `app/shared/db/perf.py` (novo) — `build_async_engine(settings)` aplica
  pool config consistente (size=20, max_overflow=30, timeout=30s,
  recycle=30min); `install_slow_query_listener(engine, threshold_ms)`
  registra event listener que loga `db.slow_query` estruturado.
- `Settings` novos: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`,
  `DB_POOL_RECYCLE`, `SLOW_QUERY_THRESHOLD_MS`.
- `app/main.py` + 17 workers Celery passam a usar `build_async_engine`
  (DRY do pool config).
- `tests/perf/` (novo) — `test_query_counts.py` (guards N+1 via
  `event.listen`) + estrutura para snapshots EXPLAIN futuros.
- **NÃO** refatorou `_upsert_saldos`/ingestão batch — verificação
  mostrou que já estão bulk (comentário existente no
  `EncerramentoService._upsert_saldos`).

### PR3 — Load test harness (k6) — 2026-05-26, [[../log_agente#sprint-19-pr3]]
- `scripts/seed/` (novo módulo): `cardinality.py` (3 presets — SMOKE
  5×2, MODERATE 50×3, FULL 1000×5 = alvo PlanoBackend §11), `seed_helpers.py`
  (CNPJ válido com algoritmo oficial RFB + UUID5 determinístico em
  `SEED_NAMESPACE` estável + receita/RBT12 sintéticos), `seed_1k_tenants.py`
  (orquestrador async — Tenant + Usuario + Empresa via bulk
  `pg_insert.on_conflict_do_nothing`, fail-fast em `ENVIRONMENT=prod`,
  emite `tests/load/.seed/empresas.json` com `{empresa_id, tenant_id,
  jwt, regime, cnpj}` que o k6 consome).
- `tests/load/` (novo): `docker-compose.load.yml` (stack isolada
  Postgres-5435 + Redis-6380 + API-8001 + k6 runner; postgres com
  `shared_preload_libraries=pg_stat_statements` + tuning de perf),
  `run.ps1` (wrapper PowerShell: `up`/`migrate`/`seed`/`k6`/`down`),
  `scenarios/lib.js` (helpers compartilhados — `SharedArray` para fixtures,
  `competenciaRotativa` evita conflito de UNIQUE), `scenarios/healthcheck.js`
  (smoke, sem seed), `scenarios/das_mensal.js` (POST DAS, cenário 1 — exercita
  índice `ix_apuracao_empresa_tipo_comp` da migration 0041), `scenarios/dashboard_trimestral.js`
  (GET relatórios, cenário 3 — exercita `ix_saldo_empresa_comp_desc`),
  `README.md` runbook + `.gitignore` (fixtures não vão pro repo).
- **+31 testes** em `tests/perf/test_seed_helpers.py` validam helpers
  puros (CNPJ válido pelo algoritmo RFB inclusive `11222333000181` da
  Receita; rejeita sequências repetidas; UUID5 determinístico; presets
  com limites superiores defensivos; SMOKE ≤ 50 empresas para CI).
- **Cenário 2 (LP trimestral) e Cenário 4 (onboarding) ficaram out-of-scope** —
  dependem de seed gerar empresas LP com plano de contas + presunção
  SCD (Sprint 20 piloto) e do PR4 (endpoints de bootstrap).
- **Grafana dashboard JSON** fora do escopo — observability stack
  self-hosted ainda não existe (Sprint 21+). k6 já tem saída
  estruturada via thresholds.

### PR2 — Cache Redis (2026-05-26, [[../log_agente#sprint-19-pr2]])
- `app/shared/cache/` (novo módulo): `cache.py` com classe `Cache`
  low-level (get/set/delete/invalidate_pattern/get_or_compute),
  `keys.py` com helpers determinísticos de chave (`aliquota_cbs_ibs_key`,
  `scd_cache_pattern`), `__init__.py` re-exporta API pública.
- **Mitigação thundering herd**: jitter ±10% no TTL + SETNX lock curto
  (15s) na primeira miss; perdedores fazem backoff exponencial e leem
  o valor recém-computado pelo vencedor. Fail-open em erro Redis
  (disponibilidade > performance).
- **Invalidação por SCAN+DEL paginado** (não bloqueia Redis em prod):
  pattern `scd:cbs_ibs:*` limpa toda a tabela CBS/IBS em 1 chamada.
- **Aplicado no `AliquotaCbsIbsRepo`** (1ª camada SCD — alvo Sprint 20
  piloto LP): construtor aceita `Cache | None`, fallback ao DB
  preservado para testes/ambientes sem Redis. Função `_resolver_db`
  extraída como fonte de verdade. Serialização JSON manual com
  `_encode_aliquota`/`_decode_aliquota` preservando Decimal+date+Enum.
  TTL 24h.
- **Exceções NÃO entram no cache** — `AliquotaCbsIbsAusente` e
  `PeriodoReformaNaoMapeado` propagam direto. Cachear erro grudaria o
  defeito por 24h após o seed ser corrigido.
- `app/main.py` instancia `Cache(redis_client)` no lifespan e expõe via
  `app.state.cache`.
- **Out-of-scope (Sprint 20+):** aplicar cache em outros SCD repos
  (`PresuncaoLpRepo`, `FaixaSimplesRepo`, `AliquotaIssRepo`); endpoint
  admin `POST /v1/admin/cache/invalidate`; integração com LLM cache
  (já existe parcialmente em `LLMClient`); thundering herd via
  stale-while-revalidate (SETNX lock já mitiga).
- **Não medimos ganho de p99 com k6 ainda** — depende de rodar o stack
  isolado do PR3 manualmente. PR pronto para essa medição.

### PR4 — Onboarding self-service bundle (2026-05-26, [[../log_agente#sprint-19-pr4]])
- **Achado durante exploração:** `ContabilService.clonar_plano_referencial`
  (Sprint 9 PR1) e endpoint `POST /v1/empresas/{eid}/plano-contas/clonar-padrao`
  **já existem** e são idempotentes. O gap real do PR4 é **orquestração**:
  guard contra conflito com importação SPED (Sprint 18) + checklist
  contextualizada por `perfil_ui`.
- `app/modules/empresa/onboarding_bundle.py` (novo): `OnboardingBundleService.executar`
  pipeline: (1) verifica empresa existe, (2) **guard** `COUNT(lote_importacao
  WHERE status='concluido')` > 0 levanta `OnboardingConflitoComImportacao`
  (HTTP 409 — plano vem do SPED, não pode ser overwritten); (3) delega
  clone ao `ContabilService` (já idempotente); (4) constrói checklist por
  perfil_ui marcando `concluido` por passo refletindo estado real (ISS
  validada, WhatsApp cadastrado).
- Helper defensivo `_perfil_seguro` cai em `SN_SEM_FUNCIONARIOS` se o
  perfil_ui do DB for desconhecido pelo enum.
- **Checklist por perfil_ui:** MEI (3 passos), SN (4 com Pluggy),
  Lucro Presumido/Real (5 com SPED ECF anual). Cada passo: `chave`
  machine-readable, `titulo`/`descricao` humanos, `endpoint` sugerido
  com `{empresa_id}` substituído pelo ID real.
- Exceção nova `OnboardingConflitoComImportacao` (409) em
  `shared/exceptions.py`.
- Endpoint `POST /v1/empresas/{empresa_id}/onboarding/bundle` plugado em
  `empresa/router.py`.
- **15 testes** em `tests/unit/empresa/test_onboarding_bundle.py`:
  guards (empresa inexistente; lote concluído bloqueia 409; lote falhou
  não bloqueia), delegação ao `ContabilService`, propagação de contadores
  em re-execução, checklist por perfil, perfil inválido cai em SN,
  estado por passo (ISS / WhatsApp / endpoint substituído), propagação
  de `welcome_digest_optin`.
- **Out-of-scope (Sprint 21+):** persistência do `welcome_digest_optin`
  como coluna em Empresa (hoje só vai no log); Pluggy/SERPRO connect
  flow proativo (endpoints já existem — UI consome direto).

## Princípios cravados

| § | Como aplicado |
|---|---|
| 8.1 RLS multi-tenant | Índices novos têm `empresa_id`/`tenant_id` no início do compound; índices não bypassam RLS (que é por linha) |
| 8.2 Fatos imutáveis | Zero ALTER em `documento_fiscal`, `lancamento_contabil`, `apuracao_fiscal` — só CREATE INDEX |
| 8.4 Golden tests | Suite existente é regressão de valor; `tests/perf/` checa plano/count, não tempo |
| 8.9 Idempotência | `CREATE INDEX IF NOT EXISTS`/`CREATE EXTENSION IF NOT EXISTS`; PR4 onboarding com guard de "já bootstrapped" |
| 8.10 Observabilidade | Slow query log estruturado em todo engine; `pg_stat_statements` ativo no DB; Prometheus k6 (PR3); Langfuse LLM (PR2) |

## Riscos principais

1. **`CREATE INDEX` sem CONCURRENTLY** trava prod → usar `autocommit_block` sempre.
2. **Pool exhaustion** em workers Celery (engine próprio cada um) → pool size 20 × concurrency baixo no beat.
3. **Snapshot EXPLAIN flaky** (planner muda com `ANALYZE`) → comparar só estrutura, não custos.
4. **Cache poisoning SCD** (PR2) → chave por `(tabela, data_referencia)`, não só ID.
5. **Load test "verde" falso** (PR3) → dataset com cardinalidade realista de NF por empresa.

## Pendências geradas

- **Particionamento de tabelas grandes** — `audit_log`, `documento_fiscal`,
  `lancamento_contabil` candidatos a partitioning declarativo por mês ou
  tenant. Fora do escopo (intrusivo, revisar RLS policies em partições).
  Documentado como Sprint 21+.
- **PgBouncer transaction pooling** — settings preparam o terreno; ativação
  fica como decisão de infra. Exige `statement_cache_size=0` em asyncpg.

## Referências cruzadas

- Plano: [[PlanoBackend]] §11 Sprint 19
- Princípios: [[principios/01-rls-multi-tenant]], [[principios/10-observabilidade]]
- Sprint anterior: [[sprints/sprint-18-migracao]]
- Próxima sprint: [[sprints/sprint-20-piloto-lp]] (a criar quando Sprint 19 fechar)
