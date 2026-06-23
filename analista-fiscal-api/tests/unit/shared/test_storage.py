"""Testes do storage de blobs (Sprint 19.6 PR3 #2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.shared.storage import (
    LocalDiskStorage,
    MemoryStorage,
    StorageError,
    build_storage,
)

# ── MemoryStorage ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_put_get_roundtrip() -> None:
    s = MemoryStorage()
    key = await s.put_bytes("tenant/x/empresa/y/file.pdf", b"PDF data")
    assert key == "tenant/x/empresa/y/file.pdf"
    data = await s.get_bytes(key)
    assert data == b"PDF data"


@pytest.mark.asyncio
async def test_memory_get_inexistente_levanta() -> None:
    s = MemoryStorage()
    with pytest.raises(StorageError, match="não encontrada"):
        await s.get_bytes("inexistente")


@pytest.mark.asyncio
async def test_memory_exists() -> None:
    s = MemoryStorage()
    assert await s.exists("k") is False
    await s.put_bytes("k", b"x")
    assert await s.exists("k") is True


@pytest.mark.asyncio
async def test_memory_delete_idempotente() -> None:
    s = MemoryStorage()
    await s.put_bytes("k", b"x")
    await s.delete("k")
    await s.delete("k")  # 2x — não levanta
    assert await s.exists("k") is False


@pytest.mark.asyncio
async def test_memory_if_not_exists_rejeita_overwrite() -> None:
    s = MemoryStorage()
    await s.put_bytes("k", b"v1")
    with pytest.raises(StorageError, match="já existe"):
        await s.put_bytes("k", b"v2", if_not_exists=True)
    # Sem flag, overwrite é permitido.
    await s.put_bytes("k", b"v2")
    assert await s.get_bytes("k") == b"v2"


# ── LocalDiskStorage ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_local_disk_roundtrip(tmp_path: Path) -> None:
    s = LocalDiskStorage(base_path=str(tmp_path))
    key = await s.put_bytes("tenant/abc/sped/2026-03.txt", b"|0000|...")
    assert key == "tenant/abc/sped/2026-03.txt"
    # Arquivo existe no FS
    assert (tmp_path / "tenant" / "abc" / "sped" / "2026-03.txt").exists()
    assert await s.get_bytes(key) == b"|0000|..."


@pytest.mark.asyncio
async def test_local_disk_normaliza_dot_dot(tmp_path: Path) -> None:
    """Path traversal via `..` é mitigado em duas camadas.

    Camada 1 (léxica): `..` vira `_` → `../etc/passwd` → `_/etc/passwd`
    que fica dentro de base_path (nenhuma escrita fora do diretório).
    Camada 2 (resolve): garante confinamento real para sequências que
    escapem do replace léxico (ex.: symlinks, encodings exóticos).
    """
    s = LocalDiskStorage(base_path=str(tmp_path))
    # A camada léxica converte "../etc/passwd" → "_/etc/passwd" (dentro da base)
    # → não lança, mas também não escreve fora do base_path.
    await s.put_bytes("../etc/passwd", b"x")
    # Confirma que não escreveu fora do base_path (era o objetivo).
    assert not (tmp_path.parent / "etc" / "passwd").exists()
    # O arquivo foi criado dentro da base com o nome normalizado.
    assert (tmp_path / "_" / "etc" / "passwd").exists()


@pytest.mark.asyncio
async def test_local_disk_path_traversal_resolve_guard(tmp_path: Path) -> None:
    """O guard resolve()+is_relative_to() bloqueia caminhos que escapem da base
    mesmo após a normalização léxica.

    Este teste usa um symlink para criar um path que resolve para fora da base
    sem conter `..` explícito — exercita a camada 2 de defesa.
    """
    import os

    outside_dir = tmp_path.parent / "outside_dir"
    outside_dir.mkdir(exist_ok=True)
    link_path = tmp_path / "escape_link"

    try:
        os.symlink(str(outside_dir), str(link_path))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks não suportados neste ambiente")

    s = LocalDiskStorage(base_path=str(tmp_path))
    # Key que atravessa o symlink para fora da base
    with pytest.raises(StorageError, match="path traversal"):
        await s.put_bytes("escape_link/secret.txt", b"x")


@pytest.mark.asyncio
async def test_local_disk_path_traversal_symlink_style(tmp_path: Path) -> None:
    """Keys legítimas com underscores e pontos simples passam normalmente."""
    s = LocalDiskStorage(base_path=str(tmp_path))
    key = await s.put_bytes("tenant/abc/._./file.txt", b"data")
    assert key == "tenant/abc/._./file.txt"


@pytest.mark.asyncio
async def test_local_disk_if_not_exists(tmp_path: Path) -> None:
    s = LocalDiskStorage(base_path=str(tmp_path))
    await s.put_bytes("k", b"v1")
    with pytest.raises(StorageError):
        await s.put_bytes("k", b"v2", if_not_exists=True)


# ── Factory ────────────────────────────────────────────────────────────────


def test_factory_local(tmp_path: Path) -> None:
    s = build_storage(backend="local", base_path=str(tmp_path))
    assert isinstance(s, LocalDiskStorage)


def test_factory_memory() -> None:
    s = build_storage(backend="memory")
    assert isinstance(s, MemoryStorage)


def test_factory_invalido() -> None:
    with pytest.raises(StorageError, match="inválido"):
        build_storage(backend="ftp")


def test_factory_s3_sem_bucket_levanta() -> None:
    with pytest.raises(StorageError, match="STORAGE_BUCKET"):
        build_storage(backend="s3")


def test_factory_s3_com_bucket_sem_boto3() -> None:
    """boto3 lazy — quando não instalado, S3Storage levanta StorageError
    com mensagem de instalação. Ambiente CI sem boto3 cai aqui.
    """
    import importlib.util

    if importlib.util.find_spec("boto3") is not None:
        pytest.skip("boto3 instalado — não dá pra testar fallback ausente")
    with pytest.raises(StorageError, match="boto3 não instalado"):
        build_storage(backend="s3", bucket="fiscal-blobs")
