---
tags: [modulo, relatorios, dre, balanco]
fonte: "[[PlanoBackend]] §11 (Sprint 12)"
sprint_origem: "12"
path: "analista-fiscal-api/app/modules/relatorios/"
status: concluido
---

# Módulo `relatorios`

> Bounded context de demonstrações contábeis. Fonte: [[PlanoBackend]] (Sprint 12). **Última sprint concluída.**

## Responsabilidade

DRE, Balanço Patrimonial, DFC, Indicadores e DRE auxiliar trimestral para Lucro Presumido.

## Depende de

- [[modulos/lucro-presumido|lucro_presumido]] (DRE auxiliar trimestral LP)
- [[modulos/conciliacao|conciliacao]] (DFC)
- [[modulos/pessoal|pessoal]] (despesas de folha)

## Princípios aplicados

- [[principios/02-fatos-imutaveis|02 — Fatos imutáveis]] (relatório de período fechado não muda)
- [[principios/04-golden-tests|04 — Golden tests]]

## Relacionado

- Próxima sprint: [[sprints/sprint-13-marketplace|Sprint 13 — Marketplace]]
- [[README|Hub do vault]]
