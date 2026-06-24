"""Testes do endpoint genérico ``GET /sped/{tipo}/{sped_id}/download``
(Sprint 19.7 PR3 #35).

Chama o handler diretamente (sem FastAPI TestClient) — mocka o repo
porque o endpoint é fino: 1 lookup + Response com bytes do BYTEA.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.sped.router import TipoSpedFiltro, download_sped_generico
from app.shared.db.models import ArquivoSped


def _arquivo_fake(*, tipo: str = "ecd") -> ArquivoSped:
    return ArquivoSped(
        id=uuid4(),
        tenant_id=uuid4(),
        empresa_id=uuid4(),
        tipo=tipo,
        periodo_inicio=date(2026, 4, 1),
        periodo_fim=date(2026, 4, 30),
        status="gerado",
        conteudo_bytea=b"|0000|fake-sped|conteudo|\r\n",
        tamanho_bytes=27,
        hash_arquivo="a" * 64,
        algoritmo_versao="sped.ecd.v2",
    )


@pytest.mark.asyncio
async def test_download_genericu_serve_bytea_com_headers() -> None:
    arquivo = _arquivo_fake(tipo="efd_contribuicoes")
    import app.modules.sped.router as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)
    mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    session = MagicMock()
    resp = await download_sped_generico(
        empresa_id=arquivo.empresa_id,
        ctx=MagicMock(),
        session=session,
        storage=MagicMock(),
        tipo=TipoSpedFiltro.EFD_CONTRIBUICOES,
        sped_id=arquivo.id,
    )
    assert resp.status_code == 200
    assert resp.headers["X-Sped-Hash"] == "a" * 64
    assert resp.headers["X-Sped-Algoritmo-Versao"] == "sped.ecd.v2"
    assert resp.media_type == "application/octet-stream"
    assert "filename=" in resp.headers["Content-Disposition"]
    assert "efd_contribuicoes" in resp.headers["Content-Disposition"]
    assert resp.body == arquivo.conteudo_bytea


@pytest.mark.asyncio
async def test_download_404_quando_arquivo_inexistente() -> None:
    import app.modules.sped.router as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=None)
    mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    with pytest.raises(HTTPException) as ei:
        await download_sped_generico(
            empresa_id=uuid4(),
            ctx=MagicMock(),
            session=MagicMock(),
            storage=MagicMock(),
            tipo=TipoSpedFiltro.ECF,
            sped_id=uuid4(),
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_download_404_quando_tipo_url_nao_casa_com_arquivo() -> None:
    """Defesa em profundidade: arquivo ECD não baixa via URL `.../ecf/...`."""
    arquivo = _arquivo_fake(tipo="ecd")
    import app.modules.sped.router as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)
    mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    with pytest.raises(HTTPException) as ei:
        await download_sped_generico(
            empresa_id=arquivo.empresa_id,
            ctx=MagicMock(),
            session=MagicMock(),
            storage=MagicMock(),
            tipo=TipoSpedFiltro.ECF,  # arquivo é ECD
            sped_id=arquivo.id,
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_download_404_quando_empresa_url_nao_casa() -> None:
    """RLS-like guard: arquivo de empresa X não baixa via URL empresa Y."""
    arquivo = _arquivo_fake(tipo="ecd")
    import app.modules.sped.router as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)
    mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    with pytest.raises(HTTPException) as ei:
        await download_sped_generico(
            empresa_id=uuid4(),  # ≠ arquivo.empresa_id
            ctx=MagicMock(),
            session=MagicMock(),
            storage=MagicMock(),
            tipo=TipoSpedFiltro.ECD,
            sped_id=arquivo.id,
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_download_filename_inclui_periodo() -> None:
    arquivo = _arquivo_fake(tipo="efd_icms_ipi")
    import app.modules.sped.router as mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)
    mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    resp = await download_sped_generico(
        empresa_id=arquivo.empresa_id,
        ctx=MagicMock(),
        session=MagicMock(),
        storage=MagicMock(),
        tipo=TipoSpedFiltro.EFD_ICMS_IPI,
        sped_id=arquivo.id,
    )
    cd = resp.headers["Content-Disposition"]
    assert "20260401-20260430" in cd
    assert ".txt" in cd


# ── FIX #7 (PR6) — download_ecd legado: guard de tipo ─────────────────────────
#
# O endpoint /sped/ecd/{id}/download legado só checava empresa_id. Com o fix,
# um arquivo de tipo "ecf" não pode ser baixado via rota ECD.


@pytest.mark.asyncio
async def test_download_ecd_legado_rejeita_tipo_errado() -> None:
    """FIX #7: arquivo ECF não deve ser servido pelo endpoint legado ECD."""
    from app.modules.sped.ecd.router import download_ecd

    arquivo = _arquivo_fake(tipo="ecf")  # tipo errado para rota ECD
    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)

    import app.modules.sped.ecd.router as ecd_mod

    ecd_mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    with pytest.raises(HTTPException) as ei:
        await download_ecd(
            empresa_id=arquivo.empresa_id,
            sped_id=arquivo.id,
            ctx=MagicMock(),
            session=MagicMock(),
            storage=MagicMock(),
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_download_ecd_legado_serve_arquivo_correto() -> None:
    """FIX #7: arquivo ECD correto é servido normalmente."""
    arquivo = _arquivo_fake(tipo="ecd")
    arquivo.empresa_id = arquivo.empresa_id

    import app.modules.sped.ecd.router as ecd_mod

    fake_repo = MagicMock()
    fake_repo.por_id = AsyncMock(return_value=arquivo)
    ecd_mod.ArquivoSpedRepo = lambda _s: fake_repo  # type: ignore[assignment, misc]

    from app.modules.sped.ecd.router import download_ecd

    resp = await download_ecd(
        empresa_id=arquivo.empresa_id,
        sped_id=arquivo.id,
        ctx=MagicMock(),
        session=MagicMock(),
        storage=MagicMock(),
    )
    assert resp.status_code == 200
    assert resp.headers["X-Sped-Hash"] == "a" * 64
