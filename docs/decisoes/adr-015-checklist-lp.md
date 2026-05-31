---
id: ADR-015
titulo: "Checklist LP — modelo de obrigações por trimestre"
status: aceito
data: 2026-05-31
autores: [equipe-backend]
tags: [lucro-presumido, checklist, saude-fiscal, sprint-20]
---

# ADR-015 — Checklist LP e health score por trimestre (Sprint 20)

## Contexto

O módulo de Lucro Presumido precisava de um mecanismo para rastrear o cumprimento das obrigações fiscais trimestrais sem depender de I/O em nenhum cálculo. Um trimestre LP tem 16 obrigações:
- 2 apurações trimestrais (IRPJ + CSLL) + 2 DARFs trimestrais
- 6 apurações mensais (PIS×3 + Cofins×3) + 6 DARFs mensais

## Decisão

Implementar `calcular_checklist_trimestre()` como função pura em `calcula_checklist_lp.py`:
- Entrada: `apuracoes_existentes: frozenset[str]` + `darfs_existentes: frozenset[str]` (keys `"tipo:YYYY-MM-DD"`)
- Saída: `ChecklistTrimestre` com `itens: list[ItemChecklist]`, `percentual_conclusao`, `completo`, `status_geral`
- Status por item: `ok | pendente | atrasado` (baseado em `data_referencia` opcional)

**Health score** em `SaudeLpOut`: score 0-100 via `from_checklists()` sobre N trimestres históricos. Status: `saudavel` (≥90%) | `atencao` (≥60%) | `critico` (<60%).

## Alternativas rejeitadas

- **Query direta ao DB por checklist**: acoplaria a lógica fiscal ao banco, impossibilitando testes puros. Princípio §8.4 exige golden test sem I/O.
- **Status calculado no frontend**: o backend precisa expor o `percentual_conclusao` para exibição em múltiplos clientes (web, WhatsApp digest).

## Consequências

- `LpChecklistService` faz exatamente 2 queries (apurações + DARFs do trimestre) e passa os frozensets para a função pura.
- 31 golden tests cobrem todos os casos de status, incluindo T4 (meses out={10,11,12}) e atrasado.
- Endpoints: `GET /checklist`, `POST /fechar` (409 se incompleto), `GET /saude?trimestres=N`.

Relacionado: [[modulos/lucro-presumido]] · [[principios/04-golden-tests]] · [[sprints/sprint-20-lp-piloto]]
