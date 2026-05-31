---
tags: [pendencia, reforma-tributaria, ibs, scd, sprint-14]
fonte: "Sprint 14 PR1 — limite do seed atual"
status: aberta
prioridade: media
---

# Pendência — Alíquotas IBS por UF (e por município)

> Pendência consciente da Sprint 14 PR1. Fonte: `log_agente.md`.

A tabela `aliquota_cbs_ibs` (migration 0034) hoje tem **alíquota IBS única nacional** por fase. Isso é uma simplificação:

- A LC 214/2025 prevê **IBS estadual + IBS municipal** com somas calibradas pelo Comitê Gestor IBS para preservar a carga média.
- Estados podem variar dentro de um pequeno range em torno da alíquota de referência (~17,7% no pleno) — semelhante ao ICMS atual.
- Municípios herdam parte da carga do ISS via IBS municipal.

## Quando atacar

Critérios para expandir:

1. Comitê Gestor IBS publica tabela oficial com percentuais por UF (e/ou município).
2. PLP 68/2024 sancionado.
3. Pelo menos 1 cliente PME com operações multi-UF demanda diferenciação.

## Implementação esperada

Migration aditiva (não-breaking — `uf` nullable):

```sql
ALTER TABLE aliquota_cbs_ibs ADD COLUMN uf CHAR(2);
ALTER TABLE aliquota_cbs_ibs ADD COLUMN municipio_ibge VARCHAR(7);
```

- O repo `AliquotaCbsIbsRepo._especificidade` já está preparado para receber mais um nível de scoring; basta adicionar `uf` ao tupla de score.
- O service `ReformaService.aliquota_vigente` precisa passar `uf=empresa.uf` (e eventualmente `municipio_ibge`) para o repo.
- Trigger SCD (`scd_close_previous_valid_to`) continua funcionando — basta incluir `uf` no `TG_ARGV`.

Cuidado: se o IBS virar por município (5.570 valores possíveis para 5 fases), avaliar particionamento da tabela por `(fase, uf)` ou MV agregada para o lookup.

## Relacionado

- [[modulos/reforma|módulo reforma]]
- [[decisoes/adr-0016-reforma-tributaria-informacional-2026|ADR 0016]]
- [[sprints/sprint-14-reforma|Sprint 14]]
