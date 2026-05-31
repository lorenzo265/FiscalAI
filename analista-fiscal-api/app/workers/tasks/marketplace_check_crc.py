"""Tarefa Celery — relata parceiros com CRC desatualizado > 30d (Sprint 13 PR3).

Beat schedule (ver ``celery_app.py``): dia 5 às 06:00.

**Out-of-scope:** scraping real do portal do CFC para validar CRC (pendência
``crc-cndt-scraping`` do mesmo bucket que CRF/CNDT da Sprint 6). Esta task
**só loga** parceiros com ``crc_status_atualizado_em < now() - 30 days`` para
que o admin entre em contato manualmente. Quando o scraping entrar (sprint
futura), a task atualiza ``crc_status`` direto.
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
    name="marketplace.check_crc_mensal",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def check_crc_mensal() -> JsonObject:
    """Conta + loga parceiros com CRC desatualizado. Não faz scraping ainda."""
    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = build_async_engine(settings)
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM contador_parceiro
                        WHERE ativo = TRUE
                          AND (
                            crc_status_atualizado_em IS NULL
                            OR crc_status_atualizado_em < now() - INTERVAL '30 days'
                          )
                        """
                    )
                )
                return int(result.scalar_one() or 0)
        finally:
            await engine.dispose()

    try:
        pendentes = asyncio.run(_run())
    except Exception:
        log.exception("marketplace.check_crc_mensal.falhou")
        raise

    log.warning(
        "marketplace.check_crc_mensal.pendencia",
        parceiros_para_verificar=pendentes,
    )
    return {"status": "ok", "parceiros_para_verificar": pendentes}
