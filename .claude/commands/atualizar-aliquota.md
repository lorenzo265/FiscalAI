---
description: Propõe nova vigência de alíquota (SCD) — migration + golden + gate, e PARA para sua aprovação
argument-hint: "[tributo] [ano], ex: inss 2026"
---

# Atualizar alíquota — $ARGUMENTS

Acione o subagente **aliquota-smith** no fluxo **propor + gate**. Execute sem confirmar a cada passo, mas **PARE antes de qualquer merge/push** — a aprovação é humana.

## Tributo/ano
`$ARGUMENTS` (ex.: `inss 2026`, `irrf 2026`, `simples 2026`, `fecp rj`, `cbs-ibs 2027`).

## Fluxo que o aliquota-smith executa
1. Localiza a tabela SCD e a vigência aberta (`valid_to IS NULL`).
2. Gera a migration Alembic com **INSERT de nova vigência** (nunca UPDATE) — o trigger fecha a anterior.
3. Gera/atualiza o golden test com os valores oficiais, citando a fonte legal.
4. `poetry run alembic upgrade head` (local) + invoca o **fiscal-validator**.
5. **PARA:** abre branch + PR e te notifica. Não faz merge nem push.

## Saída
Resumo: tabela, vigência nova (`valid_from`), fonte legal citada, veredito do fiscal-validator (VERDE/VERMELHO) e o estado do PR aguardando sua aprovação.

> Freio (§8.3/§8.8): alíquota nunca é aplicada cega. Você dá o OK final.
