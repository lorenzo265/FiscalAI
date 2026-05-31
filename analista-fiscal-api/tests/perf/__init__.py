"""Tests de performance (Sprint 19 PR1).

Estes testes NÃO medem tempo (flaky em CI). Eles validam:

  * Comportamento do ``build_async_engine`` (Sprint 19 PR1 — pool config).
  * Comportamento do ``install_slow_query_listener`` (slow query log).
  * Em PRs futuros: snapshots EXPLAIN (compara plano, não custo) e
    contagem de queries por hotpath (guards de N+1).
"""
