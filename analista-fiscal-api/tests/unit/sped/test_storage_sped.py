"""Testes do módulo de storage SPED (Marco 4 #10).

Cobre ``chave_storage_sped``, ``mover_blob_sped_para_storage`` (idempotente,
serve de backfill), ``mover_blob_sped_best_effort`` (nunca falha) e
``ler_conteudo_sped`` (storage-first com fallback BYTEA).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.sped.storage import (
    chave_storage_sped,
    ler_conteudo_sped,
    mover_blob_sped_best_effort,
    mover_blob_sped_para_storage,
)
from app.shared.db.models import ArquivoSped
from app.shared.storage import MemoryStorage, StorageError

_TENANT = UUID("11111111-1111-1111-1111-111111111111")
_EMPRESA = UUID("22222222-2222-2222-2222-222222222222")
_ARQ = UUID("33333333-3333-3333-3333-333333333333")
_CONTEUDO = b"|0000|LECD|01012025|31122025|X LTDA|\r\n|9999|2|\r\n"


def _arquivo(
    *,
    conteudo: bytes | None = _CONTEUDO,
    storage_key: str | None = None,
    tipo: str = "ecd",
) -> ArquivoSped:
    return ArquivoSped(
        id=_ARQ,
        tenant_id=_TENANT,
        empresa_id=_EMPRESA,
        tipo=tipo,
        periodo_inicio=date(2025, 1, 1),
        periodo_fim=date(2025, 12, 31),
        conteudo_bytea=conteudo,
        tamanho_bytes=len(conteudo) if conteudo is not None else 0,
        hash_arquivo="a" * 64,
        storage_key=storage_key,
        algoritmo_versao="sped.ecd.v2",
    )


# ── chave_storage_sped ──────────────────────────────────────────────────────


def test_chave_inclui_tenant_empresa_tipo_periodo_e_id() -> None:
    chave = chave_storage_sped(_arquivo())
    assert chave == (
        f"tenant/{_TENANT}/empresa/{_EMPRESA}/sped/ecd/"
        f"2025-01-01_2025-12-31/{_ARQ}.txt"
    )


def test_chave_difere_por_id_para_snapshots_supersededos() -> None:
    """Mesma chave de domínio, ids distintos -> chaves de storage distintas."""
    a = _arquivo()
    b = _arquivo()
    b.id = uuid4()
    assert chave_storage_sped(a) != chave_storage_sped(b)


# ── mover_blob_sped_para_storage ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mover_escreve_no_storage_e_zera_bytea() -> None:
    storage = MemoryStorage()
    session = AsyncMock()
    arquivo = _arquivo()

    moveu = await mover_blob_sped_para_storage(session, arquivo, storage)

    assert moveu is True
    chave = chave_storage_sped(arquivo)
    assert arquivo.storage_key == chave
    assert arquivo.conteudo_bytea is None
    assert await storage.get_bytes(chave) == _CONTEUDO
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_mover_idempotente_quando_ja_tem_storage_key() -> None:
    storage = MemoryStorage()
    session = AsyncMock()
    arquivo = _arquivo(storage_key="ja/existe.txt")

    moveu = await mover_blob_sped_para_storage(session, arquivo, storage)

    assert moveu is False
    assert arquivo.storage_key == "ja/existe.txt"
    assert arquivo.conteudo_bytea == _CONTEUDO  # intacto
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_mover_noop_quando_sem_conteudo() -> None:
    storage = MemoryStorage()
    session = AsyncMock()
    arquivo = _arquivo(conteudo=None)

    moveu = await mover_blob_sped_para_storage(session, arquivo, storage)

    assert moveu is False
    assert arquivo.storage_key is None
    session.commit.assert_not_awaited()


# ── ler_conteudo_sped ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ler_storage_first_quando_ha_storage_key() -> None:
    storage = MemoryStorage()
    await storage.put_bytes("k/arquivo.txt", _CONTEUDO)
    arquivo = _arquivo(conteudo=None, storage_key="k/arquivo.txt")

    assert await ler_conteudo_sped(arquivo, storage) == _CONTEUDO


@pytest.mark.asyncio
async def test_ler_fallback_bytea_quando_linha_legada() -> None:
    storage = MemoryStorage()  # vazio
    arquivo = _arquivo(conteudo=_CONTEUDO, storage_key=None)

    assert await ler_conteudo_sped(arquivo, storage) == _CONTEUDO


@pytest.mark.asyncio
async def test_ler_levanta_quando_sem_conteudo_nem_key() -> None:
    storage = MemoryStorage()
    arquivo = _arquivo(conteudo=None, storage_key=None)

    with pytest.raises(StorageError):
        await ler_conteudo_sped(arquivo, storage)


# ── mover_blob_sped_best_effort ─────────────────────────────────────────────


class _StorageQueExplode:
    """Storage cujo put_bytes sempre falha - simula S3 fora do ar."""

    async def put_bytes(
        self, key: str, data: bytes, *, content_type: str = "", if_not_exists: bool = False
    ) -> str:
        raise StorageError("S3 indisponível")

    async def get_bytes(self, key: str) -> bytes:  # pragma: no cover
        raise StorageError("n/a")

    async def exists(self, key: str) -> bool:  # pragma: no cover
        return False

    async def delete(self, key: str) -> None:  # pragma: no cover
        return None


@pytest.mark.asyncio
async def test_best_effort_nao_propaga_falha_e_preserva_bytea() -> None:
    session = AsyncMock()
    arquivo = _arquivo()

    # Não deve levantar mesmo com o storage explodindo.
    await mover_blob_sped_best_effort(session, arquivo, _StorageQueExplode())

    assert arquivo.storage_key is None  # não migrou
    assert arquivo.conteudo_bytea == _CONTEUDO  # preservado para fallback
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_best_effort_move_no_caminho_feliz() -> None:
    storage = MemoryStorage()
    session = AsyncMock()
    arquivo = _arquivo()

    await mover_blob_sped_best_effort(session, arquivo, storage)

    assert arquivo.storage_key == chave_storage_sped(arquivo)
    assert arquivo.conteudo_bytea is None
