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


async def test_excluir_anonimiza_sem_deletar(live_client: AsyncClient) -> None:
    slug = f"t{uuid.uuid4().hex[:10]}"
    email = f"admin@{slug}.com"
    senha = "S3nh@Forte!"
    r = await live_client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Esquecer",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": email,
            "usuario_senha": senha,
        },
    )
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Sem confirmacao explicita -> 422 (guarda contra exclusao acidental).
    r = await live_client.post(
        "/v1/lgpd/excluir", json={"confirmar": False}, headers=h
    )
    assert r.status_code == 422

    # Confirmada -> 200, status 'agendada', expurgo ~5 anos a frente.
    r = await live_client.post(
        "/v1/lgpd/excluir", json={"confirmar": True}, headers=h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "agendada"
    assert body["resumo"]["usuarios"] == 1
    assert int(body["expurgo_apos"][:4]) == int(body["anonimizado_em"][:4]) + 5

    # A linha do usuario PERMANECE (anonimizada, NAO deletada): export ainda
    # traz 1 usuario, mas com email .invalid e nome [ANONIMIZADO]; a PII
    # original sumiu por completo.
    r = await live_client.get("/v1/lgpd/exportar", headers=h)
    assert r.status_code == 200, r.text
    usuarios = r.json()["dados"]["usuarios"]
    assert len(usuarios) == 1
    assert usuarios[0]["email"].endswith("@anonimizado.invalid")
    assert usuarios[0]["nome"] == "[ANONIMIZADO]"
    assert email not in json.dumps(r.json())

    # Login com as credenciais ORIGINAIS agora e BLOQUEADO: a conta foi
    # desativada (por_slug filtra ativos -> 404) e o email foi anonimizado
    # (nao casaria -> 401). Qualquer um prova o esquecimento efetivo.
    r = await live_client.post(
        "/auth/login",
        json={"tenant_slug": slug, "email": email, "senha": senha},
    )
    assert r.status_code in (401, 404)
