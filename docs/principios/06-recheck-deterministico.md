---
tags: [principio, llm, ia, validacao]
fonte: "[[PlanoBackend]] §8.6"
status: ativo
---

# 06 — Re-check determinístico pós-LLM

> Princípio inviolável §8.6. Fonte: [[PlanoBackend]].

## Regra

Depois que o LLM responde, valores monetários, datas e CNPJs/CPFs têm sua **literalidade verificada via regex** contra os fatos persistidos. O LLM sintetiza; o código confere.

## Por quê

Mitiga o risco crítico **R1 — alucinação em valor fiscal**. Meta Fase 1: **<2% de taxa de alucinação**.

## O que nunca fazer

- ❌ Exibir número vindo do LLM sem reconferir contra a fonte determinística.

## Relacionado

- [[principios/05-citacao-llm|05 — Citação obrigatória]]
- [[principios/08-llm-nao-escreve-fatos|08 — LLM nunca escreve fatos]]
- [[principios/04-golden-tests|04 — Golden tests]]
