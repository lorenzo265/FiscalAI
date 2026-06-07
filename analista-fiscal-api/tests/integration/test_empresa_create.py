"""Testes de integração — POST /v1/empresas e o guard de código IBGE.

`codigo_municipio_ibge` é NOT NULL no banco (migration 0049). Criar sem ele deve
devolver 422 `MunicipioIbgeAusente` (erro de domínio limpo), nunca 500.
Requer Postgres real + `alembic upgrade head`.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _slug() -> str:
    return f"t{uuid.uuid4().hex[:10]}"


async def _registrar(client: AsyncClient) -> str:
    slug = _slug()
    r = await client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Create",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    token: str = r.json()["access_token"]
    return token


async def test_criar_sem_ibge_retorna_422_municipio_ausente(
    live_client: AsyncClient,
) -> None:
    token = await _registrar(live_client)
    r = await live_client.post(
        "/v1/empresas",
        json={
            "cnpj": "11222333000181",
            "razao_social": "Sem IBGE Ltda",
            "regime_tributario": "simples_nacional",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["codigo"] == "MunicipioIbgeAusente"


async def test_criar_com_ibge_retorna_201(live_client: AsyncClient) -> None:
    token = await _registrar(live_client)
    r = await live_client.post(
        "/v1/empresas",
        json={
            "cnpj": "11222333000181",
            "razao_social": "Com IBGE Ltda",
            "regime_tributario": "simples_nacional",
            "municipio": "São Paulo",
            "codigo_municipio_ibge": "3550308",
            "uf": "SP",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["codigo_municipio_ibge"] == "3550308"
