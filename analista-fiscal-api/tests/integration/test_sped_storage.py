"""Integração — SPED blob em object storage (Marco 4 #10).

Prova end-to-end, contra Postgres + o storage do lifespan (LocalDisk em dev),
que ``mover_blob_sped_para_storage`` tira o ``.txt`` da coluna BYTEA, grava no
storage e que ``ler_conteudo_sped`` recupera os bytes. Requer Postgres +
alembic head (>= 0065, que tornou ``conteudo_bytea`` nullable).
"""

from __future__ import annotations

import uuid
from datetime import date
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.main import app
from app.modules.sped.storage import (
    chave_storage_sped,
    ler_conteudo_sped,
    mover_blob_sped_para_storage,
)
from app.shared.db.models import ArquivoSped, Empresa

pytestmark = pytest.mark.asyncio

_CONTEUDO = b"|0000|LECD|01012025|31122025|EMPRESA SPED LTDA|\r\n|9999|2|\r\n"


async def test_blob_sped_migra_para_storage_e_le_de_volta(
    live_client: AsyncClient,
) -> None:
    slug = f"t{uuid.uuid4().hex[:10]}"
    r = await live_client.post(
        "/auth/register",
        json={
            "tenant_nome": "Tenant SPED Storage",
            "tenant_slug": slug,
            "usuario_nome": "Admin",
            "usuario_email": f"admin@{slug}.com",
            "usuario_senha": "S3nh@Forte!",
        },
    )
    assert r.status_code == 201, r.text
    tenant_id = UUID(r.json()["tenant"]["id"])

    factory = app.state.session_factory
    storage = app.state.storage

    # Setup: empresa + arquivo_sped com conteudo_bytea (estado recém-gerado).
    # Sessao superuser -> bypassa RLS para o setup (mesmo padrao do test_pii).
    async with factory() as s:
        empresa = Empresa(
            tenant_id=tenant_id,
            cnpj="12345678000199",
            razao_social="Empresa SPED LTDA",
            regime_tributario="lucro_presumido",
            perfil_ui="sn_sem_funcionarios",
            codigo_municipio_ibge="3550308",
        )
        s.add(empresa)
        await s.commit()
        empresa_id = empresa.id

        arquivo = ArquivoSped(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            tipo="ecd",
            periodo_inicio=date(2025, 1, 1),
            periodo_fim=date(2025, 12, 31),
            conteudo_bytea=_CONTEUDO,
            tamanho_bytes=len(_CONTEUDO),
            hash_arquivo="a" * 64,
            algoritmo_versao="sped.ecd.v2",
        )
        s.add(arquivo)
        await s.commit()
        await s.refresh(arquivo)
        arquivo_id = arquivo.id
        chave = chave_storage_sped(arquivo)

        # Act: move o blob de BYTEA para o object storage.
        moveu = await mover_blob_sped_para_storage(s, arquivo, storage)
        assert moveu is True
        assert arquivo.storage_key == chave
        assert arquivo.conteudo_bytea is None

    try:
        async with factory() as s:
            # Coluna crua no banco: conteudo_bytea NULL, storage_key preenchida.
            row = (
                await s.execute(
                    text(
                        "SELECT conteudo_bytea, storage_key "
                        "FROM arquivo_sped WHERE id = :i"
                    ),
                    {"i": arquivo_id},
                )
            ).one()
            assert row.conteudo_bytea is None
            assert row.storage_key == chave

            # Round-trip via helper de leitura: recupera os bytes do storage.
            recarregado = await s.get(ArquivoSped, arquivo_id)
            assert recarregado is not None
            conteudo = await ler_conteudo_sped(recarregado, storage)
            assert conteudo == _CONTEUDO

        # Idempotência: rodar de novo numa linha ja migrada e no-op.
        async with factory() as s:
            recarregado = await s.get(ArquivoSped, arquivo_id)
            assert recarregado is not None
            moveu_2 = await mover_blob_sped_para_storage(s, recarregado, storage)
            assert moveu_2 is False
    finally:
        await storage.delete(chave)
