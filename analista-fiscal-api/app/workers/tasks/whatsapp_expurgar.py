"""Tarefa Celery — expurga ``whatsapp_mensagem_processada`` > 7 dias (Fase 2 PR7).

Mantém a tabela enxuta. Meta documenta que retries de webhook não persistem
além de algumas horas — 7 dias é uma janela conservadora com margem de auditoria.

Beat schedule (ver ``celery_app.py``): diário às 04:00 (janela de menor tráfego).
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
    name="whatsapp.expurgar_processadas",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def expurgar_mensagens_processadas() -> JsonObject:
    """Apaga registros com ``processed_at < now() - 7 days``. Idempotente."""
    import asyncio

    async def _run() -> int:
        settings = get_settings()
        engine = build_async_engine(settings)
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                result = await session.execute(
                    text(
                        "DELETE FROM whatsapp_mensagem_processada "
                        "WHERE processed_at < now() - INTERVAL '7 days'"
                    )
                )
                await session.commit()
                return int(getattr(result, "rowcount", 0) or 0)
        finally:
            await engine.dispose()

    try:
        apagados = asyncio.run(_run())
    except Exception:
        log.exception("whatsapp.expurgar_processadas.falhou")
        raise
    log.info("whatsapp.expurgar_processadas.ok", apagados=apagados)
    return {"status": "ok", "apagados": apagados}
