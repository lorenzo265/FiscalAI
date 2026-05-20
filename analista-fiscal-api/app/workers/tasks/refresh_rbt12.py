"""Tarefa Celery — refresh mensal da MV ``rbt12_mensal`` (Fase 2 PR3).

Chama a função PL/pgSQL ``refresh_rbt12_mensal()`` (criada em
``alembic/versions/0026_fase2_rbt12_materializada.py``), que executa
``REFRESH MATERIALIZED VIEW CONCURRENTLY rbt12_mensal``.

A função é ``SECURITY DEFINER`` — bypass de RLS em ``documento_fiscal``.

Beat schedule (ver ``celery_app.py``): dia 2 às 06:00 (depois do
encerramento contábil do mês anterior). Idempotente — múltiplos refreshes
no mesmo dia produzem o mesmo resultado.

Quando ainda não houver Celery instalado, o stub no ``celery_app`` aceita
``.task(...)`` e devolve a função intocada — chamável diretamente em testes.
"""

from __future__ import annotations

import structlog

from app.shared.types import JsonObject
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    name="rbt12.refresh_mensal",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def refresh_rbt12_mensal() -> JsonObject:
    """Dispara ``refresh_rbt12_mensal()`` no banco — global, sem tenant scope."""
    import asyncio

    async def _run() -> None:
        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                await session.execute(text("SELECT refresh_rbt12_mensal()"))
                await session.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception:
        log.exception("rbt12.refresh_mensal.falhou")
        raise
    log.info("rbt12.refresh_mensal.ok")
    return {"status": "ok"}
