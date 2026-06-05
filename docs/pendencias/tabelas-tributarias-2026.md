---
titulo: Tabelas tributárias 2026 ausentes (INSS + IRRF) — seed SCD pendente
status: aberta
severidade: MAJOR (risco-cliente — folha calculada com vigência defasada)
origem: AUDITORIA_FISCAL_BACKEND.md · issue M2
data: 2026-06-04
decisao: adiar — não seedar sem norma oficial (decisão do usuário)
---

# M2 — Tabelas tributárias 2026 ausentes (INSS + IRRF)

## Problema

A última vigência SCD seedada de **INSS** é `valid_from=2025-01-01, valid_to=NULL`
(`alembic/versions/0016_...`, `0045_...`); a de **IRRF** é fev/2024. Em jun/2026 toda folha de
competência 2026 usa faixas defasadas (mínimo R$1.518 de 2025; IRRF sem a ampliação de isenção de
2026). Os valores 2024/2025 estão corretos faixa a faixa — falta apenas a **vigência 2026**.

> Era a pendência consciente #7 do `log_agente.md`, mas deixou de ser teórica: **calcula folha
> errada em produção agora.**

## Por que está adiada (e não corrigida no sprint de hardening fiscal de 2026-06-04)

Seedar tabela tributária com valor **não-confirmado** viola o §3 (SCD Type 2 — alíquota sempre de
norma vigente) e geraria folha **errada com aparência de correta** (pior que a defasagem, que ao
menos é auditável). O agente **não deve fabricar alíquotas**. Decisão registrada do usuário: manter
como pendência ativa até a norma oficial estar em mãos.

## O que falta para fechar (gatilho)

1. **Salário mínimo 2026** — Decreto/Portaria oficial.
2. **Faixas INSS 2026** — Portaria Interministerial MPS/MF (faixas + alíquotas + teto + contribuinte
   individual), reajustadas pelo mínimo + INPC.
3. **Tabela IRRF 2026** — RFB, considerando a reforma do IRPF (Lei 15.270/2025, se aplicável à
   competência: nova faixa de isenção, dedução simplificada).

## Como aplicar quando a norma sair (≈ meia hora)

`INSERT` de novas linhas SCD com `valid_from='2026-01-01'` e `UPDATE` fechando `valid_to='2025-12-31'`
das vigências 2025 — **sem alterar histórico** (§8.3). Padrão idêntico ao seed retroativo INSS 2024
(`0045_sprint19_6_pr1_seed_inss_2024.py`). Seed via migration direto (não via painel admin, que
rejeita `valid_from ≤ max` por anti-regressão). Acrescentar golden tests da competência 2026.

Relacionado: [[03-scd-type-2]] · interage com `pessoal/calcula_inss.py`, `calcula_irrf.py`.
