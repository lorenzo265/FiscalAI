---
sprint: 20
titulo: "Lucro Presumido pronto pra venda"
fase: 3
status: concluida
marco: "200 pagantes + MRR R$40k+"
testes_finais: 2121
atualizado: 2026-05-31
---

# Sprint 20 — Lucro Presumido completo

Objetivo: fechar o módulo LP com tudo pronto pra venda — DARF gerada, checklist de obrigações por trimestre, health score e advisor com 4 regras LP.

Relacionado: [[modulos/lucro-presumido]] · [[roadmap]] · [[principios/04-golden-tests]]

---

## PR1 — DARF LP + algoritmos de apuração

**Testes adicionados:** +29 (total pós-PR1: 2041)

O que entrou:
- Migration `0052_sprint20_darf_guia_pagamento.py` — tabela `guia_pagamento` com `tenant_id` + RLS + índices por empresa/competência.
- `app/modules/lucro_presumido/calcula_irpj.py` — `calcular_irpj_trimestral()`: base presumida, adicional 10%, IRPJ total.
- `app/modules/lucro_presumido/calcula_csll.py` — `calcular_csll_trimestral()`.
- `app/modules/lucro_presumido/calcula_pis_cofins.py` — `calcular_pis_cumulativo_mensal()` e `calcular_cofins_cumulativo_mensal()`.
- `app/modules/lucro_presumido/calcula_darf_lp.py` — `calcular_darf_irpj/csll/pis/cofins()` com códigos de receita e vencimentos corretos.
- Golden tests em `tests/unit/lucro_presumido/`.

---

## PR2 — Checklist + health score + 3 endpoints

**Testes adicionados:** +31 (total pós-PR2: 2072)

O que entrou:
- `app/modules/lucro_presumido/calcula_checklist_lp.py` — `calcular_checklist_trimestre()`: 16 itens por trimestre (IRPJ+CSLL+PIS×3+Cofins×3, cada um com apuração e DARF), status `ok/pendente/atrasado`, `percentual_conclusao`, `completo`.
- `app/modules/lucro_presumido/repo.py` — `listar_trimestre()` em `ApuracaoLpRepo` e `GuiaPagamentoRepo` (batch 2 queries por checklist).
- `app/modules/lucro_presumido/service.py` — `LpChecklistService`: `checklist_trimestre()`, `fechar_trimestre()` (409 se incompleto), `saude_lp()` (N trimestres cronológicos).
- `app/modules/lucro_presumido/schemas.py` — `ItemChecklistOut`, `ChecklistTrimestreOut`, `SaudeLpOut` com `from_checklists()`.
- `app/modules/lucro_presumido/router.py` — 3 novos endpoints:
  - `GET /{empresa_id}/lp/trimestre/{ano}/{trimestre}/checklist`
  - `POST /{empresa_id}/lp/trimestre/{ano}/{trimestre}/fechar`
  - `GET /{empresa_id}/lp/saude?trimestres=4`
- `app/shared/exceptions.py` — `ChecklistLpNaoConcluido` (HTTP 409).

---

## PR3 — E2E piloto + Advisor LP

**Testes adicionados:** +49 (total pós-PR3: 2121)

O que entrou:
- `app/modules/advisor/regras_lp.py` — 4 regras LP puras (Camada 1):
  1. `checar_darf_lp_vencidas()` — DARF em atraso, severidade alta, Lei 9.430/1996.
  2. `checar_irpj_adicional()` — adicional 10% ativado, severidade média, Lei 9.249/1995 art. 3º §1º.
  3. `checar_distribuicao_isenta_potencial()` — margem de distribuição isenta > R$5k, severidade informativa, RIR/2018 art. 238.
  4. `checar_limite_receita_lp()` — receita >90% do teto R$78M, severidade média/alta, RIR/2018 art. 587.
- `tests/unit/advisor/test_regras_lp.py` — 22 golden tests cobrindo as 4 regras.
- `tests/unit/lucro_presumido/test_e2e_piloto_lp.py` — 27 testes E2E sem I/O, 3 perfis:
  - `TestConsultoriaTI` (serviços, 32%, R$500k/trim)
  - `TestComercioVarejista` (comércio, 8%/12%, R$1,2M/trim)
  - `TestServicosPorte` (serviços pequeno porte, 32%, R$150k/trim — sem adicional)

---

## Definition of Done ✅

- [x] pytest: 2121 passed, 2 skipped
- [x] mypy strict: 0 erros
- [x] Golden tests bloqueando merge (§8.4)
- [x] Todos os cálculos com `Decimal`, zero `float` (§8)
- [x] RLS em todas as tabelas de domínio (§8.1)
- [x] LLM não escreve fatos — advisor é Camada 1 determinística (§8.8)
- [x] Log de agente atualizado
- [x] Roadmap marcado ✅
