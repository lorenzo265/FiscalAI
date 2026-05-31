"""Tarefa Celery — backfill CBS/IBS informacional para documentos do ano
corrente (Sprint 14 PR3).

Beat schedule (ver ``celery_app.py``): diário às 04:30.

Itera empresas ativas e chama ``ReformaService.recalcular_historico_documentos``
do ano corrente. Idempotente — só toca documentos com ``valor_cbs IS NULL OR
valor_ibs IS NULL``. Re-execução produz mesmo estado.

Roda como superuser fiscal (bypass RLS — operação cross-tenant de sistema).
"""

from __future__ import annotations

import structlog
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.modules.reforma.service import ReformaService
from app.shared.db.models import Empresa
from app.shared.db.perf import build_async_engine
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="reforma.refresh_cbs_ibs_historico",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def refresh_cbs_ibs_historico() -> JsonObject:
    """Backfill CBS/IBS informacional para documentos do ano corrente.

    Itera empresas ativas e processa cada uma. Falha em uma empresa não
    aborta as demais (resiliência — log estruturado por empresa).
    """
    import asyncio

    async def _run() -> tuple[int, int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        ano = datetime.now(_TZ_BR).year
        empresas_ok = 0
        empresas_erro = 0
        total_atualizados = 0
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                stmt = select(Empresa).where(Empresa.ativa.is_(True))
                empresas = list((await session.execute(stmt)).scalars().all())
            for empresa in empresas:
                async with sess_factory() as session:
                    try:
                        resultado = await ReformaService(
                            session
                        ).recalcular_historico_documentos(
                            empresa.id, ano=ano, forcar=False
                        )
                        await session.commit()
                        empresas_ok += 1
                        total_atualizados += resultado.atualizados
                    except Exception:
                        await session.rollback()
                        log.exception(
                            "reforma.backfill.empresa_falhou",
                            empresa_id=str(empresa.id),
                            ano=ano,
                        )
                        empresas_erro += 1
        finally:
            await engine.dispose()
        return (empresas_ok, empresas_erro, total_atualizados)

    try:
        ok, erro, atualizados = asyncio.run(_run())
    except Exception:
        log.exception("reforma.backfill.falhou")
        raise

    log.info(
        "reforma.backfill.ok",
        empresas_ok=ok,
        empresas_erro=erro,
        documentos_atualizados=atualizados,
    )
    return {
        "status": "ok",
        "empresas_ok": ok,
        "empresas_erro": erro,
        "documentos_atualizados": atualizados,
    }
