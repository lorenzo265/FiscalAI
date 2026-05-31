---
tags: [runbook, backup, recovery, postgres, redis, operacional]
atualizado: 2026-05-31
rto: "4 horas"
rpo: "1 hora"
---

# Runbook — Backup e Recovery

**RTO (Recovery Time Objective):** 4 horas — tempo máximo para restaurar o serviço.
**RPO (Recovery Point Objective):** 1 hora — perda máxima aceitável de dados.

Relacionado: [[runbooks/deploy-producao]] · [[runbooks/on-call-playbook]]

---

## 1. PostgreSQL — Backup

### Backup automatizado (AWS RDS / Aurora)

Em produção, usar RDS com:
- **Automated backups:** retenção 7 dias, janela 03:00-04:00 BRT (baixo uso).
- **Point-in-Time Recovery (PITR):** até 5 minutos de granularidade.
- **Snapshots manuais:** antes de cada deploy com migration destrutiva.

```bash
# Snapshot manual pré-migration (executar ANTES da migration)
aws rds create-db-snapshot \
  --db-instance-identifier fiscalai-prod \
  --db-snapshot-identifier "pre-deploy-$(date +%Y%m%d-%H%M)"

# Verificar status do snapshot
aws rds describe-db-snapshots \
  --db-snapshot-identifier "pre-deploy-$(date +%Y%m%d-%H%M)" \
  --query 'DBSnapshots[0].Status'
```

### Backup manual (pg_dump — ambiente sem RDS)

```bash
# Dump completo (comprimido) — ~1-2 min para DB de 10GB
pg_dump $DATABASE_URL \
  --format=custom \
  --compress=9 \
  --file="fiscalai-prod-$(date +%Y%m%d-%H%M).pgdump"

# Upload para S3
aws s3 cp "fiscalai-prod-$(date +%Y%m%d-%H%M).pgdump" \
  s3://$BACKUP_BUCKET/postgres/

# Verificar integridade
pg_restore --list "fiscalai-prod-$(date +%Y%m%d-%H%M).pgdump" > /dev/null && echo "OK"
```

### Retenção

| Tipo | Retenção | Destino |
|---|---|---|
| Backup diário automático | 7 dias | RDS (ou S3 glacier) |
| Snapshot pré-deploy | 30 dias | S3 Standard |
| Snapshot mensal | 5 anos | S3 Glacier (obrigação LGPD §16: 5 anos fiscal) |

---

## 2. PostgreSQL — Recovery

### PITR (Point-in-Time Recovery) — dados corrompidos ou deletados acidentalmente

```bash
# Via AWS Console: RDS → Instâncias → Ações → Restaurar para point-in-time
# Escolher timestamp ANTES do incidente (ex.: 30 min antes)
# Nome: fiscalai-prod-recovery-YYYY-MM-DD

# Verificar dados na instância restaurada (não conectar produção ainda)
psql "postgresql://fiscal:fiscal@fiscalai-prod-recovery.xxx.rds.amazonaws.com:5432/fiscal"

# Se OK: trocar o DNS da instância prod para a nova (ou renomear)
```

### Restore completo (pg_restore)

```bash
# 1. Criar DB novo (não sobrescrever prod até validar)
createdb -h $PG_HOST fiscal_recovery

# 2. Restaurar
pg_restore \
  --dbname="postgresql://fiscal:fiscal@$PG_HOST:5432/fiscal_recovery" \
  --format=custom \
  --jobs=4 \  # paralelismo
  "fiscalai-prod-YYYYMMDD-HHMM.pgdump"

# 3. Validar: contar registros críticos
psql "postgresql://...fiscal_recovery" \
  -c "SELECT count(*) FROM empresa; SELECT count(*) FROM apuracao_fiscal; SELECT count(*) FROM audit_log"

# 4. Se validado: trocar DATABASE_URL nos secrets e reiniciar API
```

---

## 3. Redis — Backup e Recovery

Redis contém: sessions JWT (TTL curto), cache SCD, rate limit counters. **Não é fonte de verdade** — perda de Redis = lentidão temporária (cache miss), não perda de dados.

### Backup RDB (snapshot)

```bash
# Forçar snapshot imediato
redis-cli -u $REDIS_URL BGSAVE
redis-cli -u $REDIS_URL LASTSAVE  # timestamp do último save

# O arquivo dump.rdb fica em /var/lib/redis/dump.rdb (auto-configurado via Redis managed)
```

### Recovery (se Redis ficar totalmente vazio)

Após restart do Redis com dados perdidos:
1. **Rate limit:** contadores zerados → todos os tenants começam sem histórico de rate limit (aceitável).
2. **Cache SCD:** miss no primeiro acesso → DB responde normalmente; cache se reconstrói automaticamente.
3. **Sessions JWT:** tokens ainda válidos (assinados pelo JWT_SECRET no Postgres — não dependem do Redis).

**Impacto:** latência aumentada por 5-10 min enquanto o cache aquece. Sem perda de dados.

---

## 4. Testes de Recovery (trimestrais)

Executar a cada trimestre para validar o RPO/RTO:

```
[ ] Simular falha do Redis: kubectl exec redis -- redis-cli FLUSHALL → verificar recuperação automática
[ ] Restaurar snapshot PostgreSQL em ambiente staging → validar RLS e dados
[ ] Medir tempo de restore completo → confirmar RTO ≤ 4h
[ ] Validar que backup mensal existe e é acessível em S3 Glacier
[ ] Testar rollback de migration no staging
```

---

## 5. Dados sensíveis (LGPD)

Conforme §8.7 do Plano e LGPD art. 46:
- Backups em repouso: AES-256 (RDS encryption + S3 SSE-KMS).
- Backups em trânsito: TLS 1.3.
- Acesso ao bucket de backup: apenas role `fiscalai-backup-reader` (princípio do mínimo privilégio).
- Exclusão de dados de titular: após `DELETE /lgpd/dados-do-titular`, confirmar que os backups futuros não conterão os dados (os dados existentes nos backups antigos ficam por 5 anos — política documentada no Termo de Uso).
