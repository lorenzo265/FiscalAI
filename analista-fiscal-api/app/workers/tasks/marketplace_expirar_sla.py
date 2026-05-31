"""Tarefa Celery — expira SLAs vencidos no marketplace (Sprint 13 PR3).

Beat schedule (ver ``celery_app.py``): horária.

  * ``sla_aceitar_ate`` vencido + status ``atribuida`` → ``expirada``.
  * ``sla_responder_ate`` vencido + status ∈ {aceita, em_andamento} → ``expirada``.

Idempotente — múltiplas execuções produzem o mesmo resultado (linhas já
expiradas não rematch). Roda como superuser (sem ``SET LOCAL ROLE``) para
ignorar RLS — operação de sistema cross-tenant.
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.shared.db.perf import build_async_engine
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="marketplace.expirar_sla",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def expirar_sla_marketplace() -> JsonObject:
    """Marca consultas com SLA vencido como ``expirada``."""
    import asyncio

    async def _run() -> tuple[int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                r1 = await session.execute(
                    text(
                        "UPDATE consulta_marketplace "
                        "SET status = 'expirada' "
                        "WHERE status = 'atribuida' "
                        "AND sla_aceitar_ate < now()"
                    )
                )
                r2 = await session.execute(
                    text(
                        "UPDATE consulta_marketplace "
                        "SET status = 'expirada' "
                        "WHERE status IN ('aceita','em_andamento') "
                        "AND sla_responder_ate < now()"
                    )
                )
                await session.commit()
                return (
                    int(getattr(r1, "rowcount", 0) or 0),
                    int(getattr(r2, "rowcount", 0) or 0),
                )
        finally:
            await engine.dispose()

    try:
        expirado_aceitar, expirado_responder = asyncio.run(_run())
    except Exception:
        log.exception("marketplace.expirar_sla.falhou")
        raise

    log.info(
        "marketplace.expirar_sla.ok",
        expirado_aceitar=expirado_aceitar,
        expirado_responder=expirado_responder,
    )
    return {
        "status": "ok",
        "expirado_aceitar": expirado_aceitar,
        "expirado_responder": expirado_responder,
    }
