---
tags: [modulo, fiscal, simples-nacional, das]
fonte: "[[PlanoBackend]] §5.2"
sprint_origem: "2-4"
path: "analista-fiscal-api/app/modules/fiscal/"
status: concluido
---

# Módulo `fiscal`

> Bounded context de apuração do Simples Nacional. Fonte: [[PlanoBackend]] §5.2.

## Responsabilidade

Cálculo do DAS (Documento de Arrecadação do Simples) com os 5 anexos, Fator R e RBT12. Núcleo fiscal do MVP (Fase 1).

## Arquivos-chave

- `calcula_das.py` — algoritmo puro Decimal-safe, golden-tested, com `ALGORITMO_VERSAO`.
- `repo.py` / `service.py` / `router.py` / `schemas.py` — padrão de módulo.

## Padrão de teste

`tests/unit/fiscal/test_calcula_das.py` é o **golden test canônico** do projeto.

## Princípios aplicados

- [[principios/02-fatos-imutaveis|02 — Fatos imutáveis]]
- [[principios/03-scd-type-2|03 — SCD Type 2]] (alíquotas dos anexos)
- [[principios/04-golden-tests|04 — Golden tests]]

## Relacionado

- [[modulos/lucro-presumido|lucro_presumido]] (regime alternativo)
- [[modulos/relatorios|relatorios]]
- [[README|Hub do vault]]
