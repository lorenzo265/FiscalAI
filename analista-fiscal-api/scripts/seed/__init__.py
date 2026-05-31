"""Gerador de dataset sintético para load testing (Sprint 19 PR3).

Estrutura:
  * ``cardinality``  — escala configurável (smoke/moderate/full).
  * ``seed_helpers`` — funções puras (CNPJ válido, UUID5 determinístico, etc).
  * ``seed_1k_tenants`` — orquestrador async com SQLAlchemy + JWT mint.

O seed é **determinístico**: re-execução com mesma escala produz mesmas
linhas (mesmos UUIDs, CNPJs, valores). Idempotente via ``ON CONFLICT DO
NOTHING`` em todas as inserts.

Reuso: ``tests/perf/conftest.py`` deve usar este módulo via fixture
``seeded_db_smoke`` (lazy, não duplicar com k6).
"""
