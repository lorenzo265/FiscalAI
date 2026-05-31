"""Task Celery — verificação diária de vigências SCD tributárias (Sprint 19.5 PR2).

Beat schedule (ver ``celery_app.py``): diário 06:15 BR — 15 minutos depois do
sync e-CAC (06:00) para não competir por conexão Postgres no horário de pico.

Pipeline:
  1. Consulta ``valid_from`` ativo de cada uma das 7 tabelas SCD (+ por UF
     para ICMS).
  2. Aplica os avaliadores puros ``avaliacao_vigencias.avaliar_*`` que
     decidem se gera alerta + severidade + contexto.
  3. INSERT ON CONFLICT DO NOTHING em ``alerta_admin`` via
     ``AlertaAdminRepo.upsert_idempotente`` — 1 alerta por
     ``(tipo, tipo_tabela, ano)``.

Roda como role ``tax_table_admin`` (não superuser). Sessão dedicada via
``async_sessionmaker(engine)`` + ``SET LOCAL ROLE``.

Princípios cravados:
  * §8.9 — idempotência via UUID5 + UNIQUE.
  * §8.10 — log estruturado ``tabelas.verificacao.iniciada/concluida/falhou``.
  * §8.7 — sem PII em logs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.modules.tabelas_admin.alertas_repo import AlertaAdminRepo
from app.modules.tabelas_admin.alertas_service import AlertaAdminService
from app.modules.tabelas_admin.repo import SCDTabelasRepo
from app.shared.db.perf import build_async_engine
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="tabelas.verificar_vigencias",
    acks_late=True,
    max_retries=2,
    queue="default",
)
def verificar_vigencias() -> JsonObject:
    """Varre as 7 tabelas SCD e cria alertas idempotentes onde necessário."""

    async def _run() -> tuple[int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        hoje = datetime.now(_TZ_BR).date()
        log.info("tabelas.verificacao.iniciada", hoje=hoje.isoformat())
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                # Worker assume role tax_table_admin — espelha o pattern
                # do PR1 (session admin via deps), mas aqui não tem HTTP
                # request, então SET LOCAL ROLE diretamente.
                await session.execute(text("SET LOCAL ROLE tax_table_admin"))
                svc = AlertaAdminService(
                    alerta_repo=AlertaAdminRepo(session),
                    scd_repo=SCDTabelasRepo(session),
                )
                criados, ja_existiam = await svc.verificar_e_alertar(
                    session, hoje
                )
        finally:
            await engine.dispose()
        return criados, ja_existiam

    try:
        criados, ja_existiam = asyncio.run(_run())
    except Exception:
        log.exception("tabelas.verificacao.falhou")
        raise

    return {
        "criados": criados,
        "ja_existiam": ja_existiam,
    }
