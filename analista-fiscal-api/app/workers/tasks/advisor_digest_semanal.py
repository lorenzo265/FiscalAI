"""Tarefa Celery — geração do digest semanal (Sprint 15 PR3).

Beat schedule (ver ``celery_app.py``): segunda-feira 06:00 BR.

Itera empresas ativas + com ``whatsapp_phone`` cadastrado e chama
``AdvisorService.gerar_digest_semanal`` com ``forcar=True`` (sobrescreve
versão anterior da mesma semana, se houver). Resiliente — falha em uma
empresa não aborta as demais.

Envio real via Meta WhatsApp utility template ainda não está implementado
(depende de template aprovado — pendência consciente registrada). Esta
task gera o snapshot com status='preparado'; envio fica para sprint
futura quando o template estiver aprovado.

Roda como superuser fiscal (bypass RLS — operação cross-tenant).
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
from app.shared.exceptions import DigestJaGeradoNaSemana
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="advisor.gerar_digest_semanal",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_digest_semanal() -> JsonObject:
    """Gera digest da semana corrente para todas as empresas com WhatsApp."""
    import asyncio

    async def _run() -> tuple[int, int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        competencia = datetime.now(_TZ_BR).date()
        empresas_ok = 0
        empresas_erro = 0
        empresas_skip = 0
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                stmt = (
                    select(Empresa)
                    .where(Empresa.ativa.is_(True))
                    .where(Empresa.whatsapp_phone.isnot(None))
                )
                empresas = list((await session.execute(stmt)).scalars().all())
            for empresa in empresas:
                async with sess_factory() as session:
                    try:
                        await AdvisorService(session).gerar_digest_semanal(
                            empresa.id, competencia=competencia, forcar=True
                        )
                        await session.commit()
                        empresas_ok += 1
                    except DigestJaGeradoNaSemana:
                        await session.rollback()
                        empresas_skip += 1
                    except Exception:
                        await session.rollback()
                        log.exception(
                            "advisor.digest.empresa_falhou",
                            empresa_id=str(empresa.id),
                            competencia=competencia.isoformat(),
                        )
                        empresas_erro += 1
        finally:
            await engine.dispose()
        return (empresas_ok, empresas_erro, empresas_skip)

    try:
        ok, erro, skip = asyncio.run(_run())
    except Exception:
        log.exception("advisor.digest.falhou")
        raise

    log.info(
        "advisor.digest.batch_ok",
        empresas_ok=ok,
        empresas_erro=erro,
        empresas_skip=skip,
    )
    return {
        "status": "ok",
        "empresas_ok": ok,
        "empresas_erro": erro,
        "empresas_skip": skip,
    }
