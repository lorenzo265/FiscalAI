"""Tarefa Celery — recalcula rating + auto-suspende parceiros ruins (Sprint 13 PR3).

Beat schedule (ver ``celery_app.py``): diário às 02:00.

Critérios §10.4 do Plano:

  * ``rating_medio < 3.5`` em parceiros com ≥10 consultas → auto-suspende
    (``ativo=False`` + ``crc_status='suspenso'``).
  * Atualiza ``taxa_resposta_horas`` como média entre ``aceita_em -
    aberta_em`` das últimas 10 consultas aceitas.

Idempotente — re-execução produz o mesmo estado dado o mesmo input.
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
    name="marketplace.recalcular_rating",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def recalcular_rating_marketplace() -> JsonObject:
    """Recalcula taxa_resposta_horas + auto-suspende parceiros abaixo do mínimo."""
    import asyncio

    async def _run() -> tuple[int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                # taxa_resposta_horas = avg(EXTRACT(EPOCH FROM (aceita_em -
                # aberta_em)) / 3600) das últimas 10 consultas aceitas.
                #
                # CTE pega últimas 10 por parceiro; UPDATE aplica média.
                await session.execute(
                    text(
                        """
                        WITH recentes AS (
                            SELECT
                                contador_id,
                                EXTRACT(EPOCH FROM (aceita_em - aberta_em)) / 3600.0
                                    AS horas,
                                ROW_NUMBER() OVER (
                                    PARTITION BY contador_id
                                    ORDER BY aceita_em DESC
                                ) AS rn
                            FROM consulta_marketplace
                            WHERE aceita_em IS NOT NULL
                        ),
                        medias AS (
                            SELECT contador_id,
                                   ROUND(AVG(horas))::int AS taxa
                            FROM recentes
                            WHERE rn <= 10
                            GROUP BY contador_id
                        )
                        UPDATE contador_parceiro p
                        SET taxa_resposta_horas = m.taxa
                        FROM medias m
                        WHERE p.id = m.contador_id
                          AND (p.taxa_resposta_horas IS NULL
                               OR p.taxa_resposta_horas <> m.taxa)
                        """
                    )
                )

                # Auto-suspende: rating < 3.5 com ≥10 consultas.
                r_susp = await session.execute(
                    text(
                        """
                        UPDATE contador_parceiro
                        SET ativo = FALSE, crc_status = 'suspenso'
                        WHERE ativo = TRUE
                          AND total_consultas >= 10
                          AND rating_medio IS NOT NULL
                          AND rating_medio < 3.5
                        """
                    )
                )
                await session.commit()
                # rowcount do UPDATE de taxa não é interessante (zero ou um
                # bocado). Loggar só a suspensão importa.
                return (0, int(getattr(r_susp, "rowcount", 0) or 0))
        finally:
            await engine.dispose()

    try:
        _, suspensos = asyncio.run(_run())
    except Exception:
        log.exception("marketplace.recalcular_rating.falhou")
        raise

    log.info("marketplace.recalcular_rating.ok", suspensos=suspensos)
    return {"status": "ok", "suspensos": suspensos}
