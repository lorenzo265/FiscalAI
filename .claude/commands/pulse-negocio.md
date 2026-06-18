---
description: Conselho de negócio — roda market-research + pricing-cac-forecast + compliance-legal-watch e consolida um digest
argument-hint: "[opcional: foco, ex: pricing]"
---

# Pulse de negócio — $ARGUMENTS

Acione os subagentes de business para um **digest consolidado**. Execute sem confirmar a cada passo.

## O que roda (em paralelo quando possível)
1. **market-research** → o que mudou no mercado/concorrência (com fonte).
2. **pricing-cac-forecast** → onde estamos vs metas (MRR, break-even) + recomendação de pricing.
3. **compliance-legal-watch** → mudanças de legislação que afetam produto/alíquota (e tarefas p/ aliquota-smith).
4. `$ARGUMENTS` foca o pulse (ex.: `pricing`, `concorrência`, `legislação`).

## Saída
Digest único: 3 seções (mercado · finanças · compliance) + ações recomendadas. Write-back de cada parte em `docs/negocio/` e no `HANDOFF_NEGOCIO.md`.

> A frota de business **propõe**. Decisões de preço/produto/legislação são suas.
