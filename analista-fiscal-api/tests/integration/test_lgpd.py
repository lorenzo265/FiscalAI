"""Integração — LGPD export/portabilidade ponta a ponta (Marco 3).

Fluxo real (router → service → repo → Postgres) sob RLS. O proprio export, ao
gravar em ``lgpd_solicitacao`` sob o role ``fiscal_app``, valida implicitamente
o GRANT + a policy RLS WITH CHECK da migration 0062 (INSERT falharia sem eles).
Requer Postgres + alembic head.
"""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _registrar(client: AsyncClient) -> tuple[str, str]:
    """Registra um tenant novo. Retorna (access_token, email do usuario)."""
    slug = f"t{uuid.uuid4().hex[:10]}"
    email = f"admin@{slug}.com"
    r = await client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant LGPD",
            "tenant_slug": slug,
            "usuario_nome": "Admin LGPD",
            "usuario_email": email,
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["access_token"]), email


async def test_export_estrutura_e_audit(live_client: AsyncClient) -> None:
    token, email = await _registrar(live_client)
    h = {"Authorization": f"Bearer {token}"}

    r = await live_client.get("/v1/lgpd/exportar", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()

    # Envelope.
    assert body["gerado_em"]
    assert body["tenant_id"]
    assert body["resumo"]["usuarios"] == 1
    assert body["resumo"]["empresas"] == 0

    # O usuario do tenant esta no pacote, COM email e SEM senha_hash.
    usuarios = body["dados"]["usuarios"]
    assert len(usuarios) == 1
    assert usuarios[0]["email"] == email
    assert "senha_hash" not in usuarios[0]

    # Export de novo funciona (2a linha de auditoria; INSERT sob fiscal_app
    # comprova o GRANT + RLS WITH CHECK da tabela lgpd_solicitacao).
    r2 = await live_client.get("/v1/lgpd/exportar", headers=h)
    assert r2.status_code == 200, r2.text


async def test_export_isolado_por_rls(live_client: AsyncClient) -> None:
    token_a, _ = await _registrar(live_client)
    _token_b, email_b = await _registrar(live_client)

    r = await live_client.get(
        "/v1/lgpd/exportar", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert r.status_code == 200, r.text

    # O email do tenant B NAO pode aparecer em lugar nenhum do export do A.
    assert email_b not in json.dumps(r.json())
