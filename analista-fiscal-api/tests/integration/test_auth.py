"""Testes de integração — fluxo register/login com Postgres real.

Requer: `alembic upgrade head` executado antes dos testes (CI faz isso automaticamente).
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _slug() -> str:
    """Slug único por chamada — evita colisão entre testes."""
    return f"t{uuid.uuid4().hex[:10]}"


def _payload(slug: str) -> dict[str, str]:
    return {
        "tenant_nome": "Tenant Integração",
        "tenant_slug": slug,
        "usuario_nome": "Admin",
        "usuario_email": f"admin@{slug}.com",
        "usuario_senha": "S3nh@Forte!",
    }


async def test_register_retorna_201_com_token(live_client: AsyncClient) -> None:
    resp = await live_client.post("/auth/register", json=_payload(_slug()))
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert "tenant" in data
    assert "usuario" in data


async def test_register_slug_duplicado_retorna_409(live_client: AsyncClient) -> None:
    slug = _slug()
    await live_client.post("/auth/register", json=_payload(slug))
    resp = await live_client.post("/auth/register", json=_payload(slug))
    assert resp.status_code == 409


async def test_register_slug_formato_invalido_retorna_422(live_client: AsyncClient) -> None:
    payload = _payload("slug inválido!")
    resp = await live_client.post("/auth/register", json=payload)
    assert resp.status_code == 422


async def test_register_senha_curta_retorna_422(live_client: AsyncClient) -> None:
    payload = _payload(_slug())
    payload["usuario_senha"] = "curta"
    resp = await live_client.post("/auth/register", json=payload)
    assert resp.status_code == 422


async def test_login_credenciais_corretas_retorna_token(live_client: AsyncClient) -> None:
    payload = _payload(_slug())
    await live_client.post("/auth/register", json=payload)

    resp = await live_client.post(
        "/auth/login",
        json={
            "tenant_slug": payload["tenant_slug"],
            "email": payload["usuario_email"],
            "senha": payload["usuario_senha"],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_senha_errada_retorna_401(live_client: AsyncClient) -> None:
    payload = _payload(_slug())
    await live_client.post("/auth/register", json=payload)

    resp = await live_client.post(
        "/auth/login",
        json={
            "tenant_slug": payload["tenant_slug"],
            "email": payload["usuario_email"],
            "senha": "senha_errada_aqui",
        },
    )
    assert resp.status_code == 401


async def test_login_tenant_inexistente_retorna_404(live_client: AsyncClient) -> None:
    resp = await live_client.post(
        "/auth/login",
        json={"tenant_slug": "nao-existe-0x1a2b", "email": "x@x.com", "senha": "qualquer"},
    )
    assert resp.status_code == 404


async def test_token_autentica_endpoint_empresa(live_client: AsyncClient) -> None:
    """Token do register deve funcionar para criar empresa (fluxo happy path)."""
    payload = _payload(_slug())
    r = await live_client.post("/auth/register", json=payload)
    token = r.json()["access_token"]

    resp = await live_client.post(
        "/v1/empresas",
        json={
            "cnpj": "12345678000195",
            "razao_social": "Empresa Integração Ltda",
            "regime_tributario": "simples_nacional",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["cnpj"] == "12345678000195"
    assert data["regime_tributario"] == "simples_nacional"
