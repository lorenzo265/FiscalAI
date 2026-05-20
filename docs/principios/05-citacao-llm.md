---
tags: [principio, llm, ia, citacao]
fonte: "[[PlanoBackend]] §8.5"
status: ativo
---

# 05 — Citação obrigatória em LLM

> Princípio inviolável §8.5. Fonte: [[PlanoBackend]].

## Regra

Toda resposta de LLM passa por um validador de citação. Sem citação válida → **reject + retry**. Segunda falha → resposta padrão ou encaminhamento ao [[sprints/sprint-13-marketplace|marketplace]].

## Em código

- `app/shared/llm/citacao.py` — validação de citação + detecção out-of-scope.
- Eval suite (`tests/eval/`, 166 casos) é barreira de merge.

## O que nunca fazer

- ❌ Servir resposta LLM sem citação válida.
- ❌ Deixar o LLM "improvisar" sobre tema [[principios/08-llm-nao-escreve-fatos|fora de escopo]].

## Relacionado

- [[principios/06-recheck-deterministico|06 — Re-check determinístico]]
- [[principios/08-llm-nao-escreve-fatos|08 — LLM nunca escreve fatos]]
- [[decisoes/adr-002-llm-citacao|ADR-002 — Citação obrigatória]]
