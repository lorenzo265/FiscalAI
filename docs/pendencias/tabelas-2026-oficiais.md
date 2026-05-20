---
tags: [pendencia, tabelas-tributarias, scd, pessoal]
fonte: "log_agente.md — Pendências conscientes #7"
status: aberta
prioridade: alta
---

# Pendência — Tabelas INSS/IRRF/FGTS 2026 oficiais

> Pendência consciente. Fonte: `log_agente.md`.

O seed atual é **2025** (Portaria 6/2025). Quando as tabelas 2026 oficiais saírem, inserir **nova linha SCD** (`valid_from` 2026), nunca sobrescrever a de 2025.

## Regra inviolável

Ver [[principios/03-scd-type-2|§8.3 — SCD Type 2]]: `INSERT` de nova vigência, jamais `UPDATE`.

## Relacionado

- [[modulos/pessoal|pessoal]]
- [[principios/03-scd-type-2|03 — Decisões versionadas]]
- [[README|Hub do vault]]
