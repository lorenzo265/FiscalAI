"""Tarefa Celery — alerta por e-mail de obrigações fiscais a vencer (Marco 4 PR3 #14).

Beat schedule (ver ``celery_app.py``): diário **06:45 BR**. Varre ``AgendaItem``
*pendentes* cujo vencimento cai dentro da janela (``ALERTA_AGENDA_DIAS``, default
7) e que ainda não foram alertados (``alertado_em IS NULL``), e dispara um e-mail
por item ao **usuário primário** do tenant, marcando ``alertado_em`` em seguida.

Semântica AT-LEAST-ONCE: o enqueue ocorre antes do commit de ``alertado_em``; se
o commit falhar, o próximo run diário re-alerta o item. É a escolha deliberada —
preferimos re-alertar a perder o aviso (não é exactly-once).

Roda como superuser fiscal (bypass RLS — operação cross-tenant de sistema, mesmo
padrão do ``advisor_enviar_digests``). Falha em um item **não aborta** os demais.

Auto-gating: ``enfileirar_email`` é no-op sem Celery e o provider é fake sem
``EMAIL_API_KEY`` — em dev nada sai. Em prod (Celery + key) o alerta de fato vai.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.modules.auth.repo import UsuarioRepo
from app.shared.db.models import AgendaItem, Empresa
from app.shared.db.perf import build_async_engine
from app.shared.integrations.email.templates import renderizar_alerta_fiscal
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app
from app.workers.tasks.email_enviar import enfileirar_email

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="agenda.alertar_vencimentos",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def alertar_vencimentos() -> JsonObject:
    """Alerta por e-mail as obrigações a vencer na janela configurada."""
    import asyncio

    async def _run() -> tuple[int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        enviados = 0
        pulados = 0
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            hoje = datetime.now(tz=_TZ_BR).date()
            limite = hoje + timedelta(days=settings.ALERTA_AGENDA_DIAS)

            async with sess_factory() as session:
                stmt = (
                    select(AgendaItem, Empresa)
                    .join(Empresa, Empresa.id == AgendaItem.empresa_id)
                    .where(AgendaItem.status == "pendente")
                    .where(AgendaItem.alertado_em.is_(None))
                    .where(AgendaItem.data_vencimento >= hoje)
                    .where(AgendaItem.data_vencimento <= limite)
                    .where(Empresa.ativa.is_(True))
                )
                pares = list((await session.execute(stmt)).all())

            for item, _empresa in pares:
                async with sess_factory() as session:
                    try:
                        usuario = await UsuarioRepo(session).primeira_do_tenant(
                            item.tenant_id
                        )
                        if usuario is None:
                            pulados += 1
                            continue
                        msg = renderizar_alerta_fiscal(
                            nome=usuario.nome,
                            titulo=item.titulo,
                            mensagem=item.descricao or item.titulo,
                            link_painel=f"{settings.APP_BASE_URL}/compliance",
                            prazo=item.data_vencimento,
                        )
                        enfileirar_email(msg, to=usuario.email, tags=["alerta_fiscal"])
                        # Marca após o despacho (at-least-once): no caminho feliz
                        # re-execuções não re-alertam; se o commit abaixo falhar,
                        # o próximo run re-alerta (preferível a perder o aviso).
                        atual = await session.get(AgendaItem, item.id)
                        if atual is not None:
                            atual.alertado_em = datetime.now(tz=_TZ_BR)
                        await session.commit()
                        enviados += 1
                    except Exception:
                        await session.rollback()
                        log.exception("agenda.alerta.item_erro", item_id=str(item.id))
                        pulados += 1
        finally:
            await engine.dispose()
        return (enviados, pulados)

    try:
        enviados, pulados = asyncio.run(_run())
    except Exception:
        log.exception("agenda.alerta.batch_falhou")
        raise

    log.info("agenda.alerta.batch_ok", enviados=enviados, pulados=pulados)
    return {"status": "ok", "enviados": enviados, "pulados": pulados}
