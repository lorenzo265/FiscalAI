---
tags: [pendencia, tabelas-tributarias, scd, pessoal]
fonte: "log_agente.md — Pendências conscientes #7"
status: parcial
prioridade: alta
atualizado: 2026-06-10
---

# Pendência — Tabelas INSS/IRRF/FGTS 2026 oficiais

> Pendência consciente. Fonte: `log_agente.md`.

O seed atual é **2025** (Portaria 6/2025). Quando as tabelas 2026 oficiais saírem, inserir **nova linha SCD** (`valid_from` 2026), nunca sobrescrever a de 2025.

## Status (2026-06-10) — proposta parcial, aguardando aprovação humana

- **INSS 2026 ✅ PREPARADO (aguarda aprovação):** migration `0058_inss_2026_nova_vigencia.py`
  insere a vigência `valid_from=2026-01-01` (Portaria Interministerial MPS/MF
  nº 13 de 09/01/2026 — SM R$ 1.621,00, teto R$ 8.475,55). Golden
  `tests/unit/pessoal/test_calcula_inss_2026.py`. SM oficial 2026 fixado em
  `app/modules/tabelas_admin/salario_minimo.py` (era placeholder 1620 → 1621).
- **IRRF 2026 ⛔ BLOQUEADO (FREIO — decisão de escopo humana):** a Lei 15.270/2025
  (26/11/2025) instituiu **redutor mensal na retenção na fonte** para rendimentos
  R$ 5.000–7.350 (isenção efetiva até R$ 5.000), além das 5 faixas da Lei 15.191/2025.
  O schema `tabela_irrf_faixa` + `app/modules/pessoal/calcula_irrf.py` **não modelam**
  esse redutor. Inserir só as 5 faixas reteria IRRF **a maior** na faixa 5.000–7.350.
  Não é INSERT cego de alíquota — exige novo mecanismo (schema + algoritmo). NÃO escrito.
- **FGTS ✅ sem mudança:** 8% por Lei 8.036/1990 — nenhuma alteração legal em 2026,
  nenhuma vigência nova criada.

## Regra inviolável

Ver [[principios/03-scd-type-2|§8.3 — SCD Type 2]]: `INSERT` de nova vigência, jamais `UPDATE`.

## Relacionado

- [[modulos/pessoal|pessoal]]
- [[principios/03-scd-type-2|03 — Decisões versionadas]]
- [[README|Hub do vault]]
