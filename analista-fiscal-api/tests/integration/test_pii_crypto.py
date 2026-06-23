"""Integração — PII cifrada em repouso (Marco 3): empresa.whatsapp_phone.

Prova end-to-end que o ORM grava CIPHERTEXT no banco (a coluna crua nao contem
o telefone) e que a leitura via ORM decifra de volta, transparente. Requer
Postgres + alembic head (>= 0063).
"""
from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.main import app
from app.shared.db.models import Empresa

pytestmark = pytest.mark.asyncio


async def test_whatsapp_phone_cifrado_em_repouso(live_client: AsyncClient) -> None:
    slug = f"t{uuid.uuid4().hex[:10]}"
    r = await live_client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant Cripto",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    tenant_id = UUID(r.json()["tenant"]["id"])

    telefone = "11987654321"
    factory = app.state.session_factory

    # Insert via ORM: PiiCifrada cifra no bind. Sessao superuser -> RLS bypass.
    async with factory() as s:
        empresa = Empresa(
            tenant_id=tenant_id,
            cnpj="12345678000199",
            razao_social="Empresa Cripto LTDA",
            regime_tributario="simples_nacional",
            perfil_ui="sn_sem_funcionarios",
            codigo_municipio_ibge="3550308",
            whatsapp_phone=telefone,
        )
        s.add(empresa)
        await s.commit()
        empresa_id = empresa.id

    async with factory() as s:
        # Coluna CRUA (text() ignora o TypeDecorator) -> ciphertext, nao o fone.
        raw = (
            await s.execute(
                text("SELECT whatsapp_phone FROM empresa WHERE id = :i"),
                {"i": empresa_id},
            )
        ).scalar_one()
        assert raw != telefone
        assert raw.startswith("v1:")

        # Via ORM -> PiiCifrada decifra de volta ao telefone original.
        recarregada = await s.get(Empresa, empresa_id)
        assert recarregada is not None
        assert recarregada.whatsapp_phone == telefone
