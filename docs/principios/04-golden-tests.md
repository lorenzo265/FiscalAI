---
tags: [principio, testes, ci, fiscal]
fonte: "[[PlanoBackend]] §8.4"
status: ativo
---

# 04 — Golden tests como barreira de merge

> Princípio inviolável §8.4. Fonte: [[PlanoBackend]].

## Regra

Todo cálculo fiscal tem golden tests que **bloqueiam o merge** se falharem. O CI roda a suite a cada PR.

## Suites golden

- `tests/golden/simples_nacional/` — 30+ casos
- `tests/golden/lucro_presumido/` — IRPJ + CSLL + PIS + Cofins + ICMS + ISS
- `tests/golden/folha/` — INSS + IRRF + FGTS + 13º + férias + rescisão
- `tests/golden/sped_ecd/` e `sped_ecf/` — validação contra ReceitaNet

## Padrão canônico

`tests/unit/fiscal/test_calcula_das.py` (referência) ou `tests/unit/pessoal/*` (mais recente). Todo `calcula_*.py` carrega `ALGORITMO_VERSAO`.

## O que nunca fazer

- ❌ Endpoint sem golden test cobrindo o cálculo.
- ❌ Commit sem rodar `pytest` + `mypy`.

## Relacionado

- [[principios/03-scd-type-2|03 — Decisões versionadas]]
- [[principios/06-recheck-deterministico|06 — Re-check determinístico]]
- [[modulos/fiscal|fiscal]] · [[modulos/lucro-presumido|lucro_presumido]] · [[modulos/pessoal|pessoal]]
