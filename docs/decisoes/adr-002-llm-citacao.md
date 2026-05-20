---
tags: [adr, llm, ia, citacao]
adr: "0008"
fonte: "[[PlanoBackend]] §18.1, §8.5"
status: aceito
---

# ADR-002 — Citação obrigatória em respostas LLM

> Corresponde ao ADR 0008 do Plano (§18.1). Fonte: [[PlanoBackend]].

## Contexto

LLM em domínio fiscal tem risco crítico de alucinação (R1). Resposta errada sobre valor/prazo fiscal gera dano real ao cliente.

## Decisão

Toda resposta LLM passa por validador de citação. Sem citação válida → reject + retry; segunda falha → resposta padrão ou encaminhamento ao [[sprints/sprint-13-marketplace|marketplace]]. Soma-se o [[principios/06-recheck-deterministico|re-check determinístico]] de valores/datas/CNPJ via regex.

## Consequências

- ✅ Rastreabilidade: toda afirmação aponta para um ID de fato.
- ✅ Taxa de alucinação alvo <2%.
- ⚠️ Eval suite (166 casos) vira barreira de merge.

## Relacionado

- [[principios/05-citacao-llm|05 — Citação obrigatória]]
- [[principios/06-recheck-deterministico|06 — Re-check determinístico]]
- [[principios/08-llm-nao-escreve-fatos|08 — LLM nunca escreve fatos]]
