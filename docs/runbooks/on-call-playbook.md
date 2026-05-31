---
tags: [runbook, on-call, incidente, alertas, operacional]
atualizado: 2026-05-31
---

# Runbook — On-Call Playbook

> Guia de resposta a incidentes em produção. Seguir os passos na ordem; não pular etapas.

Relacionado: [[runbooks/deploy-producao]] · [[runbooks/backup-recovery]] · [[decisoes/adr-016-hardening-seguranca]]

---

## Matriz de escalação

| Severidade | Definição | Tempo de resposta | Quem aciona |
|---|---|---|---|
| **SEV1** | Sistema fora; 0% transações; dados corrompidos | 15 min | On-call → Lead imediato |
| **SEV2** | Degradação severa; >5% erros 5xx; p99 >2s | 30 min | On-call |
| **SEV3** | Degradação parcial; funcionalidade específica fora | 2h | On-call (horário comercial) |
| **SEV4** | Anomalia monitorada; sem impacto direto ao usuário | Próximo dia útil | Backlog |

---

## Alertas Grafana — diagnóstico por sintoma

### 🔴 `api.latency.p99 > 500ms`

```bash
# 1. Verificar se é query lenta
# Grafana → Postgres → pg_stat_statements → top queries por total_time

# 2. Verificar connection pool
kubectl exec -it deploy/fiscalai-api -n prod -- \
  python -c "from app.shared.db.perf import *; print('pool ok')"

# 3. Verificar Redis (cache miss storm)
kubectl exec -it deploy/fiscalai-api -n prod -- \
  redis-cli -u $REDIS_URL info stats | grep keyspace
```

Causa mais comum: N+1 em endpoint novo (sem `selectinload`) ou índice ausente após migration.

### 🔴 `api.error_rate.5xx > 1%`

```bash
# 1. Sentry → filtrar por ambiente=prod, últimas 15 min
# 2. Logs Loki
kubectl logs -l app=fiscalai-api -n prod --since=15m | grep '"level":"error"' | head -50

# 3. Verificar se é RLS violation (mais grave — vazamento entre tenants)
kubectl logs ... | grep "RLS\|tenant_id\|policy"
```

Se RLS violation confirmada → **SEV1 imediato**, isolar o tenant afetado.

### 🔴 `rls.violation.detected > 0`

**Este é o alerta mais crítico do sistema.** Princípio §8.1.

```bash
# 1. Identificar o tenant_id nos logs
# 2. Revogar tokens do tenant afetado (impede acesso temporário)
# 3. Auditar quais dados foram expostos via audit_log
kubectl exec -it deploy/fiscalai-api -n prod -- psql $DATABASE_URL \
  -c "SELECT * FROM audit_log WHERE created_at > NOW() - INTERVAL '1 hour' AND tenant_id = '<tenant_afetado>' ORDER BY created_at DESC LIMIT 50"

# 4. Notificar DPO (LGPD — art. 48: 72h para comunicar à ANPD se necessário)
```

### 🔴 `celery.task.failed > 0`

```bash
# 1. Verificar dead-letter
redis-cli -u $REDIS_URL llen celery.dead

# 2. Logs do worker
kubectl logs -l app=fiscalai-worker -n prod --since=30m | grep "ERROR\|FAILURE"

# 3. Re-executar tarefa falha (apenas se idempotente)
kubectl exec -it deploy/fiscalai-worker -n prod -- \
  celery -A app.workers.celery_app inspect reserved
```

### 🟡 `llm.citacao_valida < 100%`

```bash
# Langfuse → filtrar traces com citacao_valida=false
# 1. Verificar se o modelo mudou (Gemini version drift)
# 2. Verificar se o contexto RAG está sendo carregado
# 3. Verificar se o prompt sofreu alteração acidental
```

### 🟡 `rate_limit.blocked.count aumentando`

```bash
# Pode ser ataque ou tenant legítimo em pico de uso
redis-cli -u $REDIS_URL keys "rl:*" | head -20
# Ver qual tenant está consumindo mais
redis-cli -u $REDIS_URL scan 0 match "rl:*" count 100
```

---

## Procedimento geral de incidente

### SEV1/SEV2

```
1. Abrir canal #incidente-YYYY-MM-DD no Slack
2. Designar Incident Commander (IC)
3. Diagnóstico: logs Loki + Sentry + Grafana (5 min)
4. Rollback se o incidente começou com deploy (ver runbook deploy)
5. Comunicar status no canal + status page (se SEV1 > 30 min)
6. Fix/workaround: mínimo para restaurar serviço
7. Pós-incidente: postmortem em até 48h
```

### Postmortem (obrigatório para SEV1/SEV2)

Criar `docs/postmortems/YYYY-MM-DD-<titulo>.md` com:
- Timeline de eventos
- Root cause (não sintoma)
- Impact assessment (quantos tenants, quanto tempo)
- Action items com dono e prazo

---

## Comandos úteis de emergência

```bash
# Ver pods com problema
kubectl get pods -n prod | grep -v Running

# Reiniciar pods problemáticos (cuidado: downtime breve se réplicas=1)
kubectl rollout restart deployment/fiscalai-api -n prod

# Escalar rapidamente em pico
kubectl scale deployment/fiscalai-api --replicas=5 -n prod

# Conexões ativas no Postgres
kubectl exec -it deploy/fiscalai-api -n prod -- psql $DATABASE_URL \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state"

# Queries lentas em execução agora
kubectl exec -it deploy/fiscalai-api -n prod -- psql $DATABASE_URL \
  -c "SELECT pid, now()-query_start AS duracao, query FROM pg_stat_activity WHERE state='active' AND now()-query_start > interval '5 seconds'"

# Terminar query travada
kubectl exec -it deploy/fiscalai-api -n prod -- psql $DATABASE_URL \
  -c "SELECT pg_terminate_backend(<pid>)"
```
