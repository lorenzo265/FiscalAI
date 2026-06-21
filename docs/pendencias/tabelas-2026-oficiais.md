---
tags: [pendencia, tabelas-tributarias, scd, pessoal]
fonte: "log_agente.md — Pendências conscientes #7"
status: parcial
prioridade: alta
atualizado: 2026-06-21
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
- **IRRF 2026 ✅ PREPARADO (aguarda aprovação — atualizado 2026-06-21):** desbloqueado.
  Migration `0059_irrf_2026_redutor.py` insere a vigência `valid_from=2026-01-01` das
  5 faixas da Lei 15.191/2025 (isento até R$ 2.428,80; deps R$ 189,59; simplificado
  R$ 607,20). O **redutor da Lei 15.270/2025** foi modelado como mecanismo de cálculo
  (constantes legais nomeadas `_REDUTOR_*` em `app/modules/pessoal/calcula_irrf.py`,
  `ALGORITMO_VERSAO` bump `v2`→`v3`), **não** em coluna de schema — o redutor incide
  sobre o rendimento tributável bruto ("o salário, não a base de cálculo" — RFB), após
  o IRRF tradicional, piso 0. Golden `tests/unit/pessoal/test_calcula_irrf_2026.py`
  reproduz os exemplos oficiais da RFB (R$ 6.000 → 382,88; R$ 7.607,20 → 1.016,27).
  Método confirmado na página oficial da RFB (exemplos da Lei 15.270/2025).
  **Pendência de integração SEPARADA:** o redutor só entra em produção quando a cadeia
  `calcula_holerite` → service passar `aplicar_redutor_lei_15270=(competencia>=2026-01-01)`.
  Hoje o flag é opt-in (default `False`, backward-compatible); fiar nos 7 callers (holerite,
  13º, férias, rescisão, pró-labore, distribuição) é PR próprio pós-aprovação da tabela.
- **GAP RETROATIVO mai–dez/2025 (NOVO — pendência separada):** a tabela progressiva
  mudou em **maio/2025** (Lei 15.191/2025) e **nunca foi seedada** — a vigência fev/2024
  ficou aberta o ano inteiro de 2025. A migration 0059 abre só a vigência 2026; o buraco
  histórico 2025-05-01..2025-12-31 exige uma vigência própria (fechada em 2025-12-31).
  Decisão à parte — NÃO corrigida agora.
- **FGTS ✅ sem mudança:** 8% por Lei 8.036/1990 — nenhuma alteração legal em 2026,
  nenhuma vigência nova criada.

## Regra inviolável

Ver [[principios/03-scd-type-2|§8.3 — SCD Type 2]]: `INSERT` de nova vigência, jamais `UPDATE`.

## Relacionado

- [[modulos/pessoal|pessoal]]
- [[principios/03-scd-type-2|03 — Decisões versionadas]]
- [[README|Hub do vault]]
