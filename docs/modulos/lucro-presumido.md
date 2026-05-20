---
tags: [modulo, lucro-presumido, irpj, csll]
fonte: "[[PlanoBackend]] §11 (Sprint 11)"
sprint_origem: "11"
path: "analista-fiscal-api/app/modules/lucro_presumido/"
status: concluido
---

# Módulo `lucro_presumido`

> Bounded context de apuração do Lucro Presumido. Fonte: [[PlanoBackend]] (Sprint 11).

## Responsabilidade

Calculadora LP: IRPJ + CSLL + PIS + Cofins (apuração trimestral). Acompanha ICMS apurado mensal, EFD-Reinf, DET, monitor cadastral e parcelamentos no mesmo sprint.

## Arquivos-chave

- `calcula_irpj.py` — algoritmo puro (referência de padrão).
- `calcula_csll.py`, PIS/Cofins.

## Padrão de teste

`tests/golden/lucro_presumido/` — IRPJ + CSLL + PIS + Cofins + ICMS + ISS.

## Princípios aplicados

- [[principios/03-scd-type-2|03 — SCD Type 2]]
- [[principios/04-golden-tests|04 — Golden tests]]

## Relacionado

- [[modulos/fiscal|fiscal]] (Simples Nacional, regime alternativo)
- [[modulos/relatorios|relatorios]] (DRE auxiliar trimestral LP)
- [[README|Hub do vault]]
