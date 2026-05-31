"""Tarefa Celery — re-detecção diária de anomalias fiscais (Sprint 15 PR1).

Beat schedule (ver ``celery_app.py``): diário às 07:30 BR.

Itera empresas ativas e chama ``AdvisorService.redetectar_empresa`` para a
competência corrente. Idempotente (§8.9) — UNIQUE parcial em
``anomalia_fiscal`` evita duplo alerta; re-detecção com mesmo valor é no-op.

Roda como superuser fiscal (bypass RLS — operação cross-tenant de sistema).
Falha em uma empresa não aborta as demais (resiliência — log por empresa).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.modules.advisor.service import AdvisorService
from app.shared.db.models import Empresa
from app.shared.db.perf import build_async_engine
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="advisor.detectar_anomalias_diario",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def detectar_anomalias_diario() -> JsonObject:
    """Roda anomaly detection para todas as empresas ativas (diário 07:30 BR)."""
    import asyncio

    async def _run() -> tuple[int, int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        competencia = datetime.now(_TZ_BR).date()
        empresas_ok = 0
        empresas_erro = 0
        total_registradas = 0
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                stmt = select(Empresa).where(Empresa.ativa.is_(True))
                empresas = list((await session.execute(stmt)).scalars().all())
            for empresa in empresas:
                async with sess_factory() as session:
                    try:
                        resultado = await AdvisorService(session).redetectar_empresa(
                            empresa.id, competencia=competencia
                        )
                        await session.commit()
                        empresas_ok += 1
                        total_registradas += resultado.anomalias_registradas
                    except Exception:
                        await session.rollback()
                        log.exception(
                            "advisor.anomalias.empresa_falhou",
                            empresa_id=str(empresa.id),
                            competencia=competencia.isoformat(),
                        )
                        empresas_erro += 1
        finally:
            await engine.dispose()
        return (empresas_ok, empresas_erro, total_registradas)

    try:
        ok, erro, registradas = asyncio.run(_run())
    except Exception:
        log.exception("advisor.anomalias.falhou")
        raise

    log.info(
        "advisor.anomalias.ok",
        empresas_ok=ok,
        empresas_erro=erro,
        anomalias_registradas=registradas,
    )
    return {
        "status": "ok",
        "empresas_ok": ok,
        "empresas_erro": erro,
        "anomalias_registradas": registradas,
    }
