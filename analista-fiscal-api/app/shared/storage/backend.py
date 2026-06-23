"""Backend de storage — interface + 3 adapters (Sprint 19.6 PR3 #2).

Pattern: Protocol + factory + 3 implementações.

  * ``ObjectStorage`` — contrato mínimo.
  * ``LocalDiskStorage`` — escreve em disco local.
  * ``MemoryStorage`` — dict em memória (tests).
  * ``S3Storage`` — boto3 lazy (prod / MinIO compatível).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


class StorageError(Exception):
    """Falha em operação de storage (não exposta como HTTP)."""


class ObjectStorage(Protocol):
    """Contrato mínimo — todo storage do projeto implementa estes 4 métodos.

    ``key`` é determinístico (gerado por módulo) — sempre prefixa
    `tenant/<id>/empresa/<id>/...` para defesa em profundidade contra
    vazamento entre tenants.
    """

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        if_not_exists: bool = False,
    ) -> str:
        """Persiste ``data`` em ``key``. Retorna a key efetiva (útil quando
        adapter resolve prefixo). ``if_not_exists=True`` levanta
        ``StorageError`` se a key já existe (idempotência §8.9).
        """
        ...

    async def get_bytes(self, key: str) -> bytes:
        """Lê o blob de ``key``. Levanta ``StorageError`` se ausente."""
        ...

    async def exists(self, key: str) -> bool:
        """Sem download. True se ``key`` existe."""
        ...

    async def delete(self, key: str) -> None:
        """Remove ``key``. Idempotente — sem-op se já deletada."""
        ...


# ── LocalDiskStorage — dev/CI ───────────────────────────────────────────────


class LocalDiskStorage:
    """Storage em diretório local. Default ``.storage/`` na raiz do projeto.

    Dev/CI/local — sem rede, sem dependência externa. Layout:
        <base_path>/<key>     # `/` no key vira `os.sep` no FS
    """

    def __init__(self, base_path: str = ".storage") -> None:
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        # Normaliza key — dupla camada de proteção contra path traversal:
        # 1. Substituição léxica de ".." (defesa em texto — rápida).
        # 2. Resolução real do path + verificação de confinamento dentro de
        #    _base (defesa simbólica — detecta symlinks e sequências exóticas
        #    que passariam pelo replace léxico).
        safe = key.replace("..", "_").lstrip("/")
        candidate = self._base / safe
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._base.resolve()):
            raise StorageError(
                f"key recusada por path traversal: {key!r} resolve para "
                f"{resolved!r} fora de {self._base!r}"
            )
        return candidate

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        if_not_exists: bool = False,
    ) -> str:
        path = self._path_for(key)
        if if_not_exists and path.exists():
            raise StorageError(f"key já existe: {key!r}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log.info("storage.put", backend="local", key=key, bytes=len(data))
        return key

    async def get_bytes(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.exists():
            raise StorageError(f"key não encontrada: {key!r}")
        return path.read_bytes()

    async def exists(self, key: str) -> bool:
        return self._path_for(key).exists()

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        if path.exists():
            path.unlink()
            log.info("storage.delete", backend="local", key=key)


# ── MemoryStorage — testes unitários ────────────────────────────────────────


class MemoryStorage:
    """Dict in-memory. Reseta a cada instância.

    Não compartilha estado entre instâncias — bom para isolamento de
    testes (cada teste pode usar uma instância nova).
    """

    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        if_not_exists: bool = False,
    ) -> str:
        if if_not_exists and key in self._items:
            raise StorageError(f"key já existe: {key!r}")
        self._items[key] = data
        return key

    async def get_bytes(self, key: str) -> bytes:
        if key not in self._items:
            raise StorageError(f"key não encontrada: {key!r}")
        return self._items[key]

    async def exists(self, key: str) -> bool:
        return key in self._items

    async def delete(self, key: str) -> None:
        self._items.pop(key, None)


# ── S3Storage — produção (boto3 lazy) ───────────────────────────────────────


class S3Storage:
    """Adapter S3-compatível (AWS, MinIO, Cloudflare R2 etc.).

    ``boto3`` import lazy — só importa quando instanciado. Settings:

      * ``STORAGE_BUCKET`` — nome do bucket.
      * ``STORAGE_S3_ENDPOINT_URL`` — None pra AWS S3, URL pra MinIO.
      * ``STORAGE_S3_REGION`` — sa-east-1 default (LGPD §8.7).

    Credenciais vêm da cadeia padrão boto3 (env, IAM role, profile).
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "sa-east-1",
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise StorageError(
                "boto3 não instalado — adicione `poetry add boto3` ou use "
                "STORAGE_BACKEND=local em dev. Sprint 19.6 PR3 deixou o "
                "adapter pronto pra ativação."
            ) from exc

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
        )

    async def put_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        if_not_exists: bool = False,
    ) -> str:
        if if_not_exists and await self.exists(key):
            raise StorageError(f"key já existe: {key!r}")
        # boto3 é sync — usar wrapper se quiser async real (anyio.to_thread).
        # MVP: chamadas síncronas dentro de async — aceitável até load test
        # mostrar contenção. Worker Celery não bloqueia event loop principal.
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        log.info("storage.put", backend="s3", key=key, bytes=len(data))
        return key

    async def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"key não encontrada: {key!r}") from exc
        body: bytes = resp["Body"].read()
        return body

    async def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
        log.info("storage.delete", backend="s3", key=key)


# ── Factory ─────────────────────────────────────────────────────────────────


def build_storage(
    *,
    backend: str = "local",
    base_path: str = ".storage",
    bucket: str | None = None,
    endpoint_url: str | None = None,
    region: str = "sa-east-1",
) -> ObjectStorage:
    """Constrói o adapter conforme settings.

    Backends:

      * ``local``  — ``LocalDiskStorage(base_path)``.
      * ``memory`` — ``MemoryStorage()`` (testes).
      * ``s3``     — ``S3Storage(bucket, endpoint_url, region)``.

    Levanta ``StorageError`` quando backend inválido ou config faltando.
    """
    if backend == "local":
        return LocalDiskStorage(base_path=base_path)
    if backend == "memory":
        return MemoryStorage()
    if backend == "s3":
        if not bucket:
            raise StorageError(
                "STORAGE_BACKEND=s3 exige STORAGE_BUCKET configurado."
            )
        return S3Storage(
            bucket=bucket, endpoint_url=endpoint_url, region=region
        )
    raise StorageError(
        f"STORAGE_BACKEND inválido: {backend!r}. Use 'local'|'memory'|'s3'."
    )


__all__ = [
    "LocalDiskStorage",
    "MemoryStorage",
    "ObjectStorage",
    "S3Storage",
    "StorageError",
    "build_storage",
]
