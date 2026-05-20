# ADR 0005 — Fatos fiscais imutáveis

## Status

accepted (2026-05-10)

## Contexto

Documentos fiscais (NF-e, NFS-e, NFC-e) e apurações fiscais são por natureza eventos com consequências legais. Cancelar uma NF-e não apaga o fato — é um novo evento que se sobrepõe ao anterior. A própria SEFAZ trata cancelamento como evento separado.

Mutar registros existentes destrói o rastro de auditoria, complica replicação, e é incompatível com legislação (Ajuste SINIEF 2/2025 exige guarda por 11 anos).

## Decisão

Modelagem **append-only** para todo fato fiscal:

- Cancelamento de NF-e → nova linha em `documento_fiscal` com `evento='cancelou'`, `supersedes` apontando para o registro original e `versao = original.versao + 1`.
- Carta de correção (CC-e) → nova linha com `evento='cce'`.
- Apurações reabertas → nova linha em `apuracao_fiscal` com novo `algoritmo_versao`.
- Tabelas tributárias (alíquotas) → SCD Type 2 com `valid_from`/`valid_to`; nunca `UPDATE`.
- `audit_log` em particionamento mensal por range, append-only.

Alterações administrativas (correção de typo no nome fantasia da empresa) podem usar UPDATE — não são fato fiscal.

## Consequências

**Positivas:**
- Auditoria total — qualquer fact pode ser reconstituído na ordem cronológica.
- LGPD/legal — guarda dos 11 anos garantida; exclusão LGPD remove apenas dados pessoais (PII redacted).
- Replicação e CDC simples — sem updates retroativos.
- Suporta natural-language queries sobre histórico ("o que mudou no DAS de janeiro?").

**Negativas:**
- Volume cresce mais rápido — particionamento mensal obrigatório em tabelas de fato.
- Queries por "estado atual" exigem `WHERE supersedes IS NULL` ou views helper.
- Espaço em disco maior — mitigação: S3 Glacier para XMLs antigos, particionamento + compressão.

## Alternativas consideradas

- **UPDATE in-place** — rejeitado: viola princípio fiscal e legal, destrói auditoria.
- **Soft delete (`deleted_at`)** — não cobre cancelamento (que é evento, não delete) nem versionamento.
- **Event sourcing puro (Kafka)** — overkill para esse volume; complica consultas síncronas.

## Referências

- `PlanoBackend.md` §5.2, §8.2
- Ajuste SINIEF nº 2/2025 (guarda XMLs)
