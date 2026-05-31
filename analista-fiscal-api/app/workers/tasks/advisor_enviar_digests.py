"""Tarefa Celery — envio dos digests preparados via Meta WhatsApp (Sprint 15.5 PR4).

Beat schedule (ver ``celery_app.py``): segunda-feira **06:30 BR** — 30min após
``advisor.gerar_digest_semanal`` (06:00). Separar geração de envio dá
buffer para re-tentativa caso o gerador atrase ou o Meta esteja momentaneamente
fora.

Filtro de candidatos a enviar (todos cumulativos):

  * ``status = 'preparado'`` (status='falhou' é terminal — operador precisa
    investigar; status='enviado' já saiu; status='cancelado' foi desativado).
  * ``superseded_by IS NULL`` (apenas a versão ativa da semana).
  * ``tentativas_envio < 5`` (após 5 ciclos sem sucesso, vira 'falhou').
  * ``empresa.ativa = true``.
  * ``empresa.whatsapp_phone IS NOT NULL``.

Resiliência: falha de envio em um digest **não aborta** os demais. O service
``enviar_digest_via_whatsapp`` já registra ``tentativas_envio +1`` e
``ultimo_erro_envio`` quando o Meta rejeita; o worker apenas propaga.

Roda como superuser fiscal (bypass RLS — operação cross-tenant de sistema).

**Pré-requisito de produção:** ``WHATSAPP_DIGEST_TEMPLATE_ATIVO=True`` em
``Settings`` (default ``False``). Quando a flag está desligada, o service
levanta ``EnvioWhatsappFalhou`` antes de tocar a Meta — o worker conta como
tentativa e segue para o próximo digest. Ver
``docs/runbooks/whatsapp-digest-template.md``.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.modules.advisor.service import AdvisorService
from app.shared.db.models import DigestSemanal, Empresa
from app.shared.db.perf import build_async_engine
from app.shared.exceptions import EnvioWhatsappFalhou
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_LIMITE_TENTATIVAS = 5


@celery_app.task(
    name="advisor.enviar_digests_preparados",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def enviar_digests_preparados() -> JsonObject:
    """Envia os digests preparados da última semana via Meta WhatsApp."""
    import asyncio

    async def _run() -> tuple[int, int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        sender = MetaWhatsAppSender(settings=settings)
        enviados = 0
        falhas = 0
        skip = 0
        try:
            sess_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with sess_factory() as session:
                stmt = (
                    select(DigestSemanal, Empresa)
                    .join(Empresa, Empresa.id == DigestSemanal.empresa_id)
                    .where(DigestSemanal.status == "preparado")
                    .where(DigestSemanal.superseded_by.is_(None))
                    .where(DigestSemanal.tentativas_envio < _LIMITE_TENTATIVAS)
                    .where(Empresa.ativa.is_(True))
                    .where(Empresa.whatsapp_phone.isnot(None))
                )
                pares = list((await session.execute(stmt)).all())

            for digest, empresa in pares:
                async with sess_factory() as session:
                    try:
                        await AdvisorService(session).enviar_digest_via_whatsapp(
                            empresa.id,
                            digest.id,
                            sender=sender,
                            settings=settings,
                        )
                        await session.commit()
                        enviados += 1
                    except EnvioWhatsappFalhou as exc:
                        # Service já registrou a tentativa; commitamos para
                        # persistir tentativas_envio +1 / ultimo_erro_envio.
                        await session.commit()
                        falhas += 1
                        log.info(
                            "advisor.digest.envio_falha_registrada",
                            empresa_id=str(empresa.id),
                            digest_id=str(digest.id),
                            motivo=str(exc)[:200],
                        )
                    except Exception:
                        await session.rollback()
                        log.exception(
                            "advisor.digest.envio_erro_inesperado",
                            empresa_id=str(empresa.id),
                            digest_id=str(digest.id),
                        )
                        skip += 1
        finally:
            await sender.aclose()
            await engine.dispose()
        return (enviados, falhas, skip)

    try:
        ok, falhas, skip = asyncio.run(_run())
    except Exception:
        log.exception("advisor.digest.envio_batch_falhou")
        raise

    log.info(
        "advisor.digest.envio_batch_ok",
        enviados=ok,
        falhas=falhas,
        erros_inesperados=skip,
    )
    return {
        "status": "ok",
        "enviados": ok,
        "falhas": falhas,
        "erros_inesperados": skip,
    }
