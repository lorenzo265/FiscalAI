"""Painel admin de tabelas tributárias (Sprint 19.5).

Bounded context que substitui o anti-padrão "criar migration nova toda vez
que sai Portaria" por endpoints REST que aceitam JSON estruturado da norma
publicada.

Decisão arquitetural §8.8 (LLM nunca escreve fato): mesmo a Camada 3 (PR3)
não persiste vigência tributária diretamente — gera sugestão pendente que o
admin humano comita com 1 clique. Esta sprint cobre os 3 PRs:

  * PR1 — Endpoints admin (esta entrega) — POST cria vigência + log audit.
  * PR2 — Worker Celery de alerta proativo (próxima entrega).
  * PR3 — Scraper DOU + LLM extrai → admin aprova (entrega final).

Estrutura:

  schemas.py        — 7 schemas Pydantic v2 (1 por tipo de tabela) + outputs
  salario_minimo.py — dict 2022-2026 (validação da primeira faixa INSS/IRRF)
  validadores.py    — funções puras §8.6 golden-testable
  repo.py           — VigenciaTabelaLogRepo + bridge SCD (chama repos existentes)
  service.py        — TabelaAdminService (idempotência §8.9 + orquestra)
  router.py         — 9 endpoints sob /v1/admin/tabelas/...

Princípios cravados — ver ``docs/sprints/sprint-19-5-tabelas-tributarias.md``
seção "Princípios cravados (gates de merge)".
"""

from __future__ import annotations
