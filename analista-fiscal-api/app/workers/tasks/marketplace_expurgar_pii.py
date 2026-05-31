"""Tarefa Celery — expurga PII de consultas com consentimento revogado (PR3).

Beat schedule (ver ``celery_app.py``): diário às 03:00.

LGPD (§8.7 do Plano): cliente pode revogar consentimento a qualquer momento;
plataforma tem 30 dias para apagar PII. Aqui:

  * ``consentimento_revogado_em < now() - 30 days AND pii_apagado_em IS NULL``
    → zera ``pergunta`` (NULL), zera ``contexto_empresa_jsonb`` ('{}'), preenche
    ``pii_apagado_em``.

Não deleta linhas — preserva audit + estatística (status, valor, rating).
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
    name="marketplace.expurgar_pii",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def expurgar_pii_marketplace() -> JsonObject:
    """LGPD §8.7 — apaga PII das consultas com consentimento revogado > 30d."""
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
                        UPDATE consulta_marketplace
                        SET pergunta = NULL,
                            contexto_empresa_jsonb = '{}'::jsonb,
                            pii_apagado_em = now()
                        WHERE consentimento_revogado_em IS NOT NULL
                          AND consentimento_revogado_em < now() - INTERVAL '30 days'
                          AND pii_apagado_em IS NULL
                        """
                    )
                )
                await session.commit()
                return int(getattr(result, "rowcount", 0) or 0)
        finally:
            await engine.dispose()

    try:
        apagados = asyncio.run(_run())
    except Exception:
        log.exception("marketplace.expurgar_pii.falhou")
        raise

    log.info("marketplace.expurgar_pii.ok", apagados=apagados)
    return {"status": "ok", "apagados": apagados}
