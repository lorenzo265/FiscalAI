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
``build_storage_from_settings`` é o atalho que recebe o objeto de settings
inteiro (usado no lifespan e nos workers Celery, evitando duplicar o mapa
de campos STORAGE_*).

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

from typing import TYPE_CHECKING

from app.shared.storage.backend import (
    LocalDiskStorage,
    MemoryStorage,
    ObjectStorage,
    S3Storage,
    StorageError,
    build_storage,
)

if TYPE_CHECKING:
    from app.config import Settings


def build_storage_from_settings(settings: Settings) -> ObjectStorage:
    """Constrói o adapter de storage a partir do objeto de settings.

    Atalho usado pelo lifespan de ``app/main.py`` e pelos workers Celery —
    centraliza o mapeamento dos campos ``STORAGE_*`` num único lugar para
    não duplicar a chamada a ``build_storage`` por call-site.
    """
    return build_storage(
        backend=settings.STORAGE_BACKEND,
        base_path=settings.STORAGE_BASE_PATH,
        bucket=settings.STORAGE_BUCKET or None,
        endpoint_url=settings.STORAGE_S3_ENDPOINT_URL or None,
        region=settings.STORAGE_S3_REGION,
    )


__all__ = [
    "LocalDiskStorage",
    "MemoryStorage",
    "ObjectStorage",
    "S3Storage",
    "StorageError",
    "build_storage",
    "build_storage_from_settings",
]
