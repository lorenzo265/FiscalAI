---
tags: [pendencia, sped, storage, infra]
status: aberta
sprint_origem: "16"
prazo_sugerido: "Sprint 18 (importação SPED histórico)"
---

# SPED — storage do `.txt` em S3/GCS

## Estado atual

Conteúdo do arquivo SPED ECD persiste em `arquivo_sped.conteudo_bytea BYTEA`. Limite prático Postgres é ~1GB por valor; PME alvo fica em 5-50MB, então não bloqueia o MVP.

`arquivo_sped.storage_key VARCHAR(500)` está nullable no schema — preparado para migração futura.

## Gatilhos para migrar

Qualquer um dos abaixo:

1. >1.000 empresas ativas (cada uma com 1 ECD + 1 ECF/ano = 2k linhas BYTEA/ano).
2. Sprint 18 entra (importação de SPED histórico de escritórios — média 12 meses × N tipos, carga muito maior).
3. Arquivo médio passar de 100MB (operação maior, vertical industrial/comércio grande).

## Plano de migração

1. Provisionar bucket S3 (sa-east-1) ou GCS (southamerica-east1) — LGPD §8.7.
2. Cliente em `app/shared/integrations/storage/` com `put_object`/`get_object`/`presign_url`.
3. Migration sem coluna nova (storage_key já existe).
4. Backfill: para cada `arquivo_sped` com `conteudo_bytea NOT NULL`, fazer upload → preencher `storage_key` → zerar `conteudo_bytea` em deploy v2.
5. Endpoint `GET .../download` passa a fazer presign + 302 redirect (ou stream do S3 se preferir hide).

## Risco se ficar como está

Tamanho de tabela Postgres cresce em ~100MB/ano por empresa ativa LP. Tolerável até 1k empresas. Acima, custo de storage Postgres (gp3) vira competitivo com S3 standard e backup/restore fica lento.

## Relacionados

[[modulos/sped]] · [[sprints/sprint-18-migracao-escritorio]]
