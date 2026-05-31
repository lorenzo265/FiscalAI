"""Storage de blobs (PDFs, XMLs, recibos) — Sprint 19.6 PR3 #2.

Substitui o anti-pattern atual de armazenar blobs em coluna BYTEA do
Postgres. Hoje SERPRO audit + DANFSE Focus + holerite PDF + SPED ECD/ECF/
EFD usam `bytea` ou `storage_key=NULL` (placeholder). Stack pronta:

  * Interface ``ObjectStorage`` — contrato mínimo (put_bytes/get_bytes/exists/delete).
  * ``LocalDiskStorage`` — dev/CI: escreve em diretório local
    (default `.storage/`). Útil para inspeção manual e testes integração.
  * ``MemoryStorage`` — testes unitários: dict in-memory, zero I/O.
  * ``S3Storage`` — produção: boto3 import lazy. Suporta MinIO via
    endpoint_url customizado.

Factory ``build_storage(settings)`` lê ``STORAGE_BACKEND`` e devolve o
adapter apropriado. Plugado no lifespan de `app/main.py` → `app.state.storage`.

**Princípios cravados:**

  * §8.7 LGPD — chaves geradas por módulo prefixam tenant e empresa
    (ex.: `tenant/<uuid>/empresa/<uuid>/sped/<arquivo>.txt`); RLS no
    Postgres + IAM no S3 = defesa em profundidade.
  * §8.9 idempotência — `put_bytes` aceita `if_not_exists=True` para
    rejeitar overwrite acidental de fato fiscal imutável.
  * §8.10 observabilidade — todos os adapters logam structlog
    `storage.put/get/delete` com tenant_id quando disponível na key.
"""

from __future__ import annotations

from app.shared.storage.backend import (
    LocalDiskStorage,
    MemoryStorage,
    ObjectStorage,
    StorageError,
    build_storage,
)

__all__ = [
    "LocalDiskStorage",
    "MemoryStorage",
    "ObjectStorage",
    "StorageError",
    "build_storage",
]
