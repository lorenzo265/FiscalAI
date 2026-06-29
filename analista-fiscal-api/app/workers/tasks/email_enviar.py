"""Tarefa Celery — envio assíncrono de e-mail transacional (Marco 4 PR3 #14).

On-demand (não tem beat schedule): callers disparam via ``enqueue`` quando
querem enviar onboarding/fatura/alerta sem bloquear o request. O corpo já
chega renderizado (assunto/html/texto) — a task só monta o ``EmailMessage`` e
delega ao provider escolhido pela env (``EMAIL_API_KEY`` vazio = fake, não
envia). Mesmo padrão do ``advisor_enviar_digests`` (asyncio.run + aclose).
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.shared.exceptions import EmailEnvioFalhou
from app.shared.integrations.email.provider import build_email_provider
from app.shared.integrations.email.types import EmailMessage
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app, enqueue

log = structlog.get_logger(__name__)


@celery_app.task(
    name="email.enviar",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def enviar_email(
    *,
    to: str,
    assunto: str,
    html: str,
    texto: str,
    remetente: str | None = None,
    tags: list[str] | None = None,
) -> JsonObject:
    """Envia um e-mail já renderizado via o provider configurado."""
    import asyncio

    async def _run() -> str:
        settings = get_settings()
        provider = build_email_provider(settings)
        try:
            enviado = await provider.enviar(
                EmailMessage(
                    to=to,
                    assunto=assunto,
                    html=html,
                    texto=texto,
                    remetente=remetente,
                    tags=tuple(tags or ()),
                )
            )
            return enviado.message_id
        finally:
            await provider.aclose()

    # Não logar o assunto: pode conter PII (ex.: nome no onboarding). Logamos
    # apenas as tags (tipo do e-mail), que não carregam dado pessoal.
    tags_log = tags or []
    try:
        message_id = asyncio.run(_run())
    except EmailEnvioFalhou:
        log.warning("email.task.envio_falhou", tags=tags_log)
        raise
    except Exception:
        log.exception("email.task.erro_inesperado", tags=tags_log)
        raise

    log.info("email.task.ok", tags=tags_log, message_id=message_id)
    return {"status": "ok", "message_id": message_id}


def enfileirar_email(msg: EmailMessage, *, to: str, tags: list[str]) -> None:
    """Despacha (fail-soft) um ``EmailMessage`` já renderizado para a task.

    Ponto único usado pelos fluxos (onboarding/fatura/alerta). O ``to`` real é
    passado aqui — os templates renderizam com ``to`` vazio. ``enqueue`` é no-op
    sem Celery e NUNCA levanta, então chamar isto não quebra o fluxo que invoca.
    """
    enqueue(
        enviar_email,
        to=to,
        assunto=msg.assunto,
        html=msg.html,
        texto=msg.texto,
        remetente=msg.remetente,
        tags=tags,
    )
