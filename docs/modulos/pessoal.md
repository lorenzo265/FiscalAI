---
tags: [modulo, pessoal, folha, esocial]
fonte: "[[PlanoBackend]] §11 (Sprint 10)"
sprint_origem: "10"
path: "analista-fiscal-api/app/modules/pessoal/"
status: concluido
---

# Módulo `pessoal`

> Bounded context de folha de pagamento e obrigações trabalhistas. Fonte: [[PlanoBackend]] (Sprint 10).

## Responsabilidade

Folha com tabelas 2026, holerite PDF, rescisão completa (verbas + aviso + FGTS + GRRF), 13º (1ª/2ª) + férias + 1/3, pró-labore (INSS 11% + IRRF), eSocial S-1xxx/2xxx/3xxx.

## Arquivos-chave

- `calcula_inss.py` — algoritmo puro (referência recente de padrão).
- `calcula_irrf.py`, `calcula_fgts.py`, rescisão, férias, 13º.

## Pendências do módulo

- [[pendencias/tabelas-2026-oficiais|Tabelas INSS/IRRF/FGTS 2026 oficiais]] (seed atual é 2025).
- [[pendencias/folha-lancamento-contabil|Lançamento contábil automático da folha]].
- [[pendencias/esocial-transmissao|eSocial transmissão real]].

## Princípios aplicados

- [[principios/03-scd-type-2|03 — SCD Type 2]] (tabelas INSS/IRRF/FGTS versionadas)
- [[principios/04-golden-tests|04 — Golden tests]] (`tests/golden/folha/`)

## Relacionado

- [[modulos/relatorios|relatorios]]
- [[README|Hub do vault]]
