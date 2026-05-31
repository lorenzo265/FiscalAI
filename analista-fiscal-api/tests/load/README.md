# Load Test Harness — Sprint 19 PR3

Harness k6 + docker-compose isolado para medir performance dos hotpaths
do Analista Fiscal API. **Não roda em CI de PR** (caro, ~horas no preset
`full`). Use manualmente para validar baseline + comparativo antes/depois
de mudanças de perf.

## Estrutura

```
tests/load/
├── README.md                    (este arquivo)
├── docker-compose.load.yml      (stack isolado postgres+redis+api+k6)
├── run.ps1                      (wrapper PowerShell — Windows)
├── .seed/                       (fixtures emitidas pelo seed; .gitignore)
│   └── empresas.json
└── scenarios/
    ├── lib.js                   (helpers compartilhados — auth, fixtures)
    ├── healthcheck.js           (smoke — só /healthz e /readyz)
    ├── das_mensal.js            (cenário 1 — DAS Simples paralelo)
    └── dashboard_trimestral.js  (cenário 3 — listagem relatórios)
```

`scripts/seed/seed_1k_tenants.py` (no projeto raiz) gera os fixtures que
o k6 consome.

## Fluxo end-to-end (Windows / PowerShell)

```powershell
# 1. Subir stack isolado (Postgres 5435, API 8001 — não conflita com dev)
.\tests\load\run.ps1 up

# 2. Aplicar migrations (cria schema + roda 0041 com pg_stat_statements)
.\tests\load\run.ps1 migrate

# 3. Seedar dataset sintético
.\tests\load\run.ps1 seed -Scale smoke      # ~10 empresas (CI-friendly, <30s)
.\tests\load\run.ps1 seed -Scale moderate   # ~150 empresas (~5min desktop)
.\tests\load\run.ps1 seed -Scale full       # ~5k empresas (alvo PlanoBackend, ~horas)

# 4. Rodar cenários k6
.\tests\load\run.ps1 k6 -Scenario healthcheck                       # smoke
.\tests\load\run.ps1 k6 -Scenario das_mensal -Duration 1m -Rate 20  # DAS
.\tests\load\run.ps1 k6 -Scenario dashboard_trimestral -Duration 30s

# 5. Investigar slow queries via pg_stat_statements
docker exec -it fiscal_loadtest_postgres psql -U fiscal -d fiscal `
  -c "SELECT mean_exec_time, calls, query FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 6. Tear down + limpa volumes
.\tests\load\run.ps1 down
```

## Fluxo equivalente bash/Linux

```bash
cd analista-fiscal-api
docker compose -f tests/load/docker-compose.load.yml up -d postgres redis api

export DATABASE_URL=postgresql+asyncpg://fiscal:fiscal@localhost:5435/fiscal
poetry run alembic upgrade head
poetry run python -m scripts.seed.seed_1k_tenants --scale smoke

docker compose -f tests/load/docker-compose.load.yml run --rm k6 \
  run /load/scenarios/das_mensal.js

docker compose -f tests/load/docker-compose.load.yml down -v
```

## Cenários

### `healthcheck.js`
Smoke. 5 VUs por 15s. Hit em `/healthz` + `/readyz`. Não precisa de seed.
Use como warm-up antes dos cenários pesados.

**Thresholds:**
- `/healthz` p99 < 100ms
- `/readyz` p99 < 500ms (toca DB+Redis)

### `das_mensal.js`
POST `/v1/empresas/{eid}/apuracoes/das` com competência rotativa. Exercita:
- Lookup na MV `rbt12_mensal`
- SCD lookup em `faixa_simples`
- INSERT em `apuracao_fiscal` (índice `ix_apuracao_empresa_tipo_comp` da
  migration 0041)

**Knobs (env):** `RATE=20`, `DURATION=1m`, `PRE_VUS=50`, `MAX_VUS=200`.

**Thresholds:**
- p99 < 1000ms (target inicial; Sprint 20 quer p99 < 500ms para LP)
- erro 5xx < 0,5%
- checks > 99%

### `dashboard_trimestral.js`
GET `/v1/empresas/{eid}/relatorios?limite=20`. 100 VUs constantes. Exercita
`SaldosPeriodoRepo` last-value (índice `ix_saldo_empresa_comp_desc`).

**Thresholds:**
- p95 < 500ms
- erro 5xx < 1%

## Presets de seed (`scripts/seed/cardinality.py`)

| Preset      | Tenants | Empresas | NF/empresa | Duração seed |
|-------------|---------|----------|------------|--------------|
| `smoke`     | 5       | 10       | 15         | < 30s        |
| `moderate`  | 50      | 150      | 240        | ~5min        |
| `full`      | 1.000   | 5.000    | 600        | ~horas       |

A versão atual do seed cria **tenants/usuários/empresas** apenas (PR3 mínimo).
Documentos fiscais e lançamentos contábeis ficam para iteração futura
(ou mock via worker quando PR4 entrar).

## Determinismo + idempotência

- UUIDs derivam de `uuid5(SEED_NAMESPACE, f"<tipo>|<idx>")` — re-execução
  produz mesmos IDs.
- CNPJs prefixados com `42` (marca visual de sintético) e DV calculado pelo
  algoritmo oficial RFB.
- Emails em `*.invalid` (TLD reservado RFC 2606 — nunca conflita com prod).
- Inserts via `ON CONFLICT DO NOTHING` em `id` — re-rodar é no-op.

## Observabilidade durante o teste

### `pg_stat_statements` (perf-side)

A migration 0041 (Sprint 19 PR1) instala a extension. Use para encontrar
queries lentas durante carga:

```sql
SELECT
  round(mean_exec_time::numeric, 2) AS mean_ms,
  calls,
  round(total_exec_time::numeric / 1000, 1) AS total_s,
  substring(query for 100) AS query
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 20;
```

### Slow query log (app-side)

`app/shared/db/perf.py` (Sprint 19 PR1) loga `db.slow_query` no structlog
sempre que uma query passa de `SLOW_QUERY_THRESHOLD_MS`. Em loadtest a
threshold default é 500ms — ajuste via env se quiser ver mais ruído.

```powershell
.\tests\load\run.ps1 logs | Select-String "slow_query"
```

## Não-objetivos (pendências documentadas)

- **Grafana dashboard `load-test.json`**: o stack k6 expõe métricas em JSON
  (saída padrão). Integração com Prometheus + Grafana fica para quando o
  observability stack existir self-hosted (Sprint 21+).
- **Cenário 2 — Apuração LP trimestral**: depende de seed gerar empresas
  com regime `lucro_presumido` + presunção SCD + plano de contas.
  Stub em [`apuracao_lp.js`] fica para Sprint 20 (piloto LP).
- **Cenário 4 — Onboarding self-service**: depende do PR4 (endpoints
  `/plano-contas/bootstrap` etc).
- **CI integration**: rodar nightly o preset `moderate` num runner dedicado
  com Postgres provisionado por job. Fica para hardening de DevOps.

## Defesa contra dano em prod

`seed_1k_tenants.py` levanta `RuntimeError` se `settings.ENVIRONMENT ==
'prod'`. O docker-compose `docker-compose.load.yml` força
`ENVIRONMENT=local`. **Nunca apontar este script para DB de produção.**
