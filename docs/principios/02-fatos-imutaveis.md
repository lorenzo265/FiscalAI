---
tags: [principio, dados, auditoria, fiscal]
fonte: "[[PlanoBackend]] §8.2"
status: ativo
---

# 02 — Fatos fiscais imutáveis

> Princípio inviolável §8.2. Fonte: [[PlanoBackend]].

## Regra

Documentos fiscais nunca são deletados. Cancelamento gera **nova linha** com `evento='cancelou'` (ou `supersedes` / `superseded_by`). Apurações antigas não recalculam quando a fórmula muda. O audit log particionado é append-only.

## Por quê

Rastreabilidade fiscal e defesa em auditoria da Receita. O estado em qualquer data passada precisa ser reconstruível exatamente como foi.

## O que nunca fazer

- ❌ `DELETE` ou `UPDATE` destrutivo em fato fiscal.
- ❌ Recalcular apuração histórica com alíquota nova (ver [[principios/03-scd-type-2|SCD Type 2]]).

## Relacionado

- [[principios/03-scd-type-2|03 — Decisões versionadas]]
- [[principios/08-llm-nao-escreve-fatos|08 — LLM nunca escreve fatos]]
- [[modulos/fiscal|módulo fiscal]]
