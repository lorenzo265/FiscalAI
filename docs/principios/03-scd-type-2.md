---
tags: [principio, dados, scd, tabelas-tributarias]
fonte: "[[PlanoBackend]] §8.3"
status: ativo
---

# 03 — Decisões versionadas (SCD Type 2)

> Princípio inviolável §8.3. Fonte: [[PlanoBackend]].

## Regra

Toda alíquota tem `valid_from` / `valid_to`. Cálculos históricos usam a tabela vigente **na data do fato**. Migração de tabela tributária gera **nova versão** — nunca substitui a linha existente.

## Em código

- Seed de tabela tributária = `INSERT` de nova vigência (ver [[pendencias/tabelas-2026-oficiais]]).
- Calculadora recebe a data de competência e seleciona a vigência correta.

## O que nunca fazer

- ❌ Hardcode de alíquota.
- ❌ `UPDATE` em linha de tabela tributária seedada.
- ❌ Usar a tabela "mais recente" para apurar mês passado.

## Relacionado

- [[principios/02-fatos-imutaveis|02 — Fatos imutáveis]]
- [[principios/04-golden-tests|04 — Golden tests]]
- [[pendencias/tabelas-2026-oficiais|Pendência: tabelas 2026]]
- [[modulos/pessoal|módulo pessoal]] · [[modulos/fiscal|módulo fiscal]]
