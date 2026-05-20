"""Smoke test da Sprint 0.

Garante que:
1. O app FastAPI sobe (lifespan executa sem crash).
2. /healthz responde 200 sem tocar dependências externas.

Note: /readyz precisa de Postgres/Redis reais, então não está coberto aqui.
Cobertura de /readyz vira integration test na Sprint 1, com Postgres em
service container do CI.
"""

from __future__ import annotations

from httpx import AsyncClient


async def test_healthz_responde_200(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_openapi_disponivel(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "Analista Fiscal API"
    assert spec["info"]["version"] == "0.1.0"
