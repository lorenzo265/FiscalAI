---
tags: [principio, llm, ia, arquitetura]
fonte: "[[PlanoBackend]] §8.8"
status: ativo
---

# 08 — LLM nunca escreve fatos

> Princípio inviolável §8.8. Fonte: [[PlanoBackend]].

## Regra

O pipeline determinístico **ingere, calcula e persiste**. O LLM só **lê** o grafo de memória + apurações, sintetiza e cita IDs. Nenhum fato fiscal entra no banco por caminho do LLM.

## Fronteira

```
ingestão → cálculo (calcula_*.py) → persistência   ← determinístico (escreve)
                                          ↓
                         LLM lê + sintetiza + cita   ← nunca escreve
```

## O que nunca fazer

- ❌ LLM gravando fato diretamente.
- ❌ Persistir saída de LLM sem [[principios/06-recheck-deterministico|re-check determinístico]].

## Relacionado

- [[principios/02-fatos-imutaveis|02 — Fatos imutáveis]]
- [[principios/05-citacao-llm|05 — Citação obrigatória]]
- [[principios/11-out-of-scope|11 — Out-of-scope declarado]]
