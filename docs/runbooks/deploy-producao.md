---
tags: [runbook, deploy, operacional, prod]
atualizado: 2026-05-31
---

# Runbook — Deploy em Produção

> Leia todo o runbook antes de executar qualquer passo. Erros nesta operação afetam clientes reais.

Relacionado: [[runbooks/backup-recovery]] · [[runbooks/on-call-playbook]] · [[decisoes/adr-016-hardening-seguranca]]

---

## Checklist pré-deploy

```
[ ] Tests passando em CI: pytest tests/unit tests/eval (0 failures, ≤2 skipped)
[ ] mypy strict: 0 erros
[ ] Bandit: 0 findings HIGH/MEDIUM sem nosec
[ ] Migration Alembic gerada e revisada manualmente
[ ] CLAUDE.md "O que NUNCA fazer" verificado
[ ] ADR criado para qualquer decisão nova de stack
[ ] log_agente.md atualizado com PR
[ ] Não há migration que faz DROP/ALTER NOT NULL em 1 passo (usar 2 fases)
[ ] Branch atual tem PR aprovado e squashed
[ ] Janela de deploy confirmada com time (evitar seg 7-10h: DAS vence, pico de uso)
```

---

## 1. Deploy da API (zero-downtime rolling)

**Assumindo:** Kubernetes com `kubectl` configurado para o cluster prod (`sa-east-1`).

```bash
# 1. Build e push da imagem
docker build -f infra/docker/Dockerfile.api -t fiscalai-api:$VERSION .
docker push $REGISTRY/fiscalai-api:$VERSION

# 2. Atualizar a imagem no manifesto
kubectl set image deployment/fiscalai-api api=$REGISTRY/fiscalai-api:$VERSION -n prod

# 3. Aguardar rollout
kubectl rollout status deployment/fiscalai-api -n prod --timeout=300s

# 4. Verificar que os pods novos estão healthy
kubectl get pods -n prod -l app=fiscalai-api

# 5. Testar /healthz e /readyz
curl -sf https://api.fiscalai.com.br/healthz | jq .
curl -sf https://api.fiscalai.com.br/readyz | jq .
```

Se `rollout status` falhar → [Rollback imediato](#rollback).

---

## 2. Migrations Alembic

**Execute ANTES do deploy da nova imagem** quando o PR contém migration.

```bash
# Conectar ao pod de migração (job one-shot) ou ao pod de API existente
kubectl exec -it deploy/fiscalai-api -n prod -- \
  alembic upgrade head

# Verificar versão atual
kubectl exec -it deploy/fiscalai-api -n prod -- \
  alembic current
```

**Migrations backward-compatible:** nova coluna nullable → deploy → backfill → NOT NULL.
Nunca rodar migration destrutiva sem janela de manutenção e backup fresco.

---

## 3. Deploy do Worker Celery (quando há mudança em tasks)

```bash
docker build -f infra/docker/Dockerfile.worker -t fiscalai-worker:$VERSION .
docker push $REGISTRY/fiscalai-worker:$VERSION
kubectl set image deployment/fiscalai-worker worker=$REGISTRY/fiscalai-worker:$VERSION -n prod
kubectl rollout status deployment/fiscalai-worker -n prod --timeout=300s
```

Celery Beat usa a mesma imagem:
```bash
kubectl set image deployment/fiscalai-beat beat=$REGISTRY/fiscalai-worker:$VERSION -n prod
```

---

## Rollback

```bash
# API
kubectl rollout undo deployment/fiscalai-api -n prod
kubectl rollout status deployment/fiscalai-api -n prod

# Workers
kubectl rollout undo deployment/fiscalai-worker -n prod

# Migration — apenas se a nova versão for backward-incompatível
# (preferível manter a migration e corrigir o código)
kubectl exec -it deploy/fiscalai-api -n prod -- \
  alembic downgrade -1
```

---

## 4. Checklist pós-deploy (5 minutos após rollout)

```
[ ] /healthz retorna {"status":"ok"}
[ ] /readyz retorna {"status":"ok"} — postgres + redis verdes
[ ] Grafana: p99 latência <500ms (últimos 5 min)
[ ] Grafana: taxa de erros 5xx = 0 (últimos 5 min)
[ ] Sentry: nenhuma exceção nova emergindo
[ ] Langfuse: LLM ainda produzindo traces (se há chamadas LLM no PR)
[ ] Testar manualmente 1 endpoint crítico do PR (smoke test)
```

Se qualquer item vermelhar → rollback imediato, abrir incidente.

---

## 5. Secrets e variáveis de ambiente

Secrets em AWS Secrets Manager (`/fiscalai/prod/*`). Nunca colocar em código ou `.env` commitado. Para atualizar:

```bash
aws secretsmanager update-secret \
  --secret-id /fiscalai/prod/JWT_SECRET \
  --secret-string "$(openssl rand -hex 32)"

# Restart dos pods para pegar o novo secret (se não usar External Secrets Operator)
kubectl rollout restart deployment/fiscalai-api -n prod
```

---

## 6. Janelas proibidas de deploy

| Período | Motivo |
|---|---|
| Dias 1-5 de cada mês (8h-18h) | Pico: DAS, PGDAS-D, DARF LP vencendo |
| Vigília fiscal (DEFIS, ECF, ECD) | Alta criticidade — consultar calendário fiscal |
| Sexta-feira após 16h | Sem time disponível no fim de semana |
| Semana de virada de ano | Alíquotas novas, alto volume de apuração |
