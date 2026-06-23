"""Tarefa Celery — processar lote SPED grande via storage async.

Sprint 19.6 PR4 (#40). Resolve limite do upload síncrono multipart (50MB)
do importador SPED da Sprint 18 PR2/3.

**Fluxo proposto** (endpoint upload-async fica em sprint dedicada quando
storage S3 estiver wired com presigned URL):

  1. Cliente faz upload do blob diretamente para S3 via presigned URL
     (out-of-scope desta task — exige `boto3 generate_presigned_post`).
  2. Cliente chama `POST /v1/empresas/{eid}/migracao/sped/{tipo}/processar`
     informando `{storage_key}`.
  3. Endpoint persiste lote em `status='processando'` e dispara
     `migracao.processar_lote_async.delay(...)`.
  4. Esta task baixa o blob do storage, chama o service correto baseado
     em `tipo` e marca o lote como `'concluido'` ou `'falhou'`.

**Estado atual da entrega:** apenas a task Celery + função async core.
Endpoint upload-async + presigned S3 ficam como pendência operacional
[risco-deploy] rastreada para sprint dedicada quando primeiro cliente
piloto precisar importar EFD-Contribuições anual cheio (>50MB).

Tipos suportados (espelha métodos do MigracaoService):
  * `ecd` → `MigracaoService.importar_sped_ecd`
  * `ecf` → `MigracaoService.importar_sped_ecf`
  * `efd_contribuicoes` → `importar_sped_efd_contribuicoes`
  * `efd_icms_ipi` → `importar_sped_efd_icms_ipi`
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.config import get_settings
from app.modules.migracao.service import MigracaoService
from app.shared.db.perf import build_async_engine
from app.shared.storage import build_storage
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


_ImportFn = Callable[
    [AsyncSession, UUID, UUID, bytes, str | None],
    Awaitable[object],
]


_DISPATCH: dict[str, str] = {
    "ecd": "importar_sped_ecd",
    "ecf": "importar_sped_ecf",
    "efd_contribuicoes": "importar_sped_efd_contribuicoes",
    "efd_icms_ipi": "importar_sped_efd_icms_ipi",
}


@celery_app.task(
    name="migracao.processar_lote_async",
    acks_late=True,
    max_retries=2,
    queue="default",
)
def processar_lote_async(
    *,
    empresa_id: str,
    tenant_id: str,
    tipo: str,
    storage_key: str,
    nome_arquivo: str | None = None,
) -> JsonObject:
    """Task Celery — processa lote SPED grande via storage.

    Não levanta — wraps exceções em log estruturado + return com
    ``status='erro'``. Celery decide retry baseado em ``acks_late`` +
    ``max_retries=2``.
    """
    if tipo not in _DISPATCH:
        log.error(
            "migracao.lote_async.tipo_desconhecido",
            tipo=tipo,
            storage_key=storage_key,
        )
        return {"status": "erro", "motivo": f"tipo {tipo!r} desconhecido"}

    try:
        resultado = asyncio.run(
            _executar(
                empresa_id=UUID(empresa_id),
                tenant_id=UUID(tenant_id),
                tipo=tipo,
                storage_key=storage_key,
                nome_arquivo=nome_arquivo,
            )
        )
    except Exception:
        log.exception(
            "migracao.lote_async.falhou",
            empresa_id=empresa_id,
            tipo=tipo,
            storage_key=storage_key,
        )
        return {"status": "erro", "storage_key": storage_key}

    return resultado


async def _executar(
    *,
    empresa_id: UUID,
    tenant_id: UUID,
    tipo: str,
    storage_key: str,
    nome_arquivo: str | None,
) -> JsonObject:
    """Pipeline async — exposto pra teste mockando colaboradores."""
    settings = get_settings()
    engine = build_async_engine(settings)
    storage = build_storage(
        backend=settings.STORAGE_BACKEND,
        base_path=settings.STORAGE_BASE_PATH,
        bucket=settings.STORAGE_BUCKET or None,
        endpoint_url=settings.STORAGE_S3_ENDPOINT_URL or None,
        region=settings.STORAGE_S3_REGION,
    )

    try:
        # 1) Baixa blob do storage.
        try:
            conteudo = await storage.get_bytes(storage_key)
        except Exception:
            log.exception(
                "migracao.lote_async.storage_get_falhou",
                storage_key=storage_key,
            )
            return {
                "status": "erro",
                "motivo": "blob_nao_encontrado_no_storage",
                "storage_key": storage_key,
            }

        log.info(
            "migracao.lote_async.iniciado",
            empresa_id=str(empresa_id),
            tipo=tipo,
            bytes=len(conteudo),
        )

        # 2) Chama o método correto do MigracaoService.
        method_name = _DISPATCH[tipo]
        sess_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with sess_factory() as session:
            await session.execute(
                text("SET LOCAL app.tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
            svc = MigracaoService()
            method = getattr(svc, method_name)
            await method(
                session,
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                conteudo=conteudo,
                nome_arquivo=nome_arquivo,
            )

        log.info(
            "migracao.lote_async.concluido",
            empresa_id=str(empresa_id),
            tipo=tipo,
            bytes=len(conteudo),
        )
        return {
            "status": "concluido",
            "tipo": tipo,
            "bytes_processados": len(conteudo),
            "storage_key": storage_key,
        }
    finally:
        await engine.dispose()


__all__ = ["processar_lote_async"]
