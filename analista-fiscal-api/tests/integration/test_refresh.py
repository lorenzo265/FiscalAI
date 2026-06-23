"""Integração — refresh token: rotação + detecção de reuso (Marco 3).

Fluxo real sob Postgres. Cobre a rotação (cada uso emite novo par e invalida o
anterior), a detecção de reuso (token já rotacionado => família revogada) e a
revogação na exclusão LGPD. Requer Postgres + alembic head (>= 0064).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _registrar(client: AsyncClient) -> dict[str, str]:
    slug = f"t{uuid.uuid4().hex[:10]}"
    r = await client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Refresh",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


async def test_register_e_rotacao_emitem_novos_tokens(live_client: AsyncClient) -> None:
    body = await _registrar(live_client)
    assert body["refresh_token"]

    r = await live_client.post(
        "/auth/refresh", json={"refresh_token": body["refresh_token"]}
    )
    assert r.status_code == 200, r.text
    novo = r.json()
    assert novo["access_token"]
    assert novo["refresh_token"]
    # Rotação: o refresh token muda a cada uso.
    assert novo["refresh_token"] != body["refresh_token"]


async def test_reuso_de_token_rotacionado_revoga_a_familia(
    live_client: AsyncClient,
) -> None:
    body = await _registrar(live_client)
    rt1 = body["refresh_token"]

    # Usa rt1 -> emite rt2 (rt1 fica revogado).
    r = await live_client.post("/auth/refresh", json={"refresh_token": rt1})
    assert r.status_code == 200
    rt2 = r.json()["refresh_token"]

    # Reusa rt1 (já rotacionado) -> 401 E revoga a família inteira.
    r = await live_client.post("/auth/refresh", json={"refresh_token": rt1})
    assert r.status_code == 401

    # rt2 também foi revogado (mesma família) -> 401.
    r = await live_client.post("/auth/refresh", json={"refresh_token": rt2})
    assert r.status_code == 401


async def test_refresh_invalido_retorna_401(live_client: AsyncClient) -> None:
    r = await live_client.post(
        "/auth/refresh", json={"refresh_token": "token-que-nao-existe"}
    )
    assert r.status_code == 401


async def test_login_emite_refresh_token(live_client: AsyncClient) -> None:
    slug = f"t{uuid.uuid4().hex[:10]}"
    email = f"admin@{slug}.com"
    senha = "S3nh@Forte!"
    await live_client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Login Refresh",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": email,
            "usuario_senha": senha,
        },
    )
    r = await live_client.post(
        "/auth/login",
        json={"tenant_slug": slug, "email": email, "senha": senha},
    )
    assert r.status_code == 200, r.text
    assert r.json()["refresh_token"]


async def test_exclusao_lgpd_revoga_refresh(live_client: AsyncClient) -> None:
    body = await _registrar(live_client)
    h = {"Authorization": f"Bearer {body['access_token']}"}
    rt = body["refresh_token"]

    # Esquecimento LGPD revoga os refresh tokens vivos do titular.
    r = await live_client.post("/v1/lgpd/excluir", json={"confirmar": True}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["resumo"]["refresh_tokens_revogados"] >= 1

    # O refresh token não renova mais (titular esquecido).
    r = await live_client.post("/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 401
