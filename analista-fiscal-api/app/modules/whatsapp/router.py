from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.shared.db.models import Empresa
from app.shared.db.rls import set_tenant_id
from app.shared.integrations.meta_whatsapp.webhook import (
    extrair_mensagens,
    verificar_assinatura_meta,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/whatsapp", tags=["whatsapp"])


async def _lookup_empresa_por_phone(engine: AsyncEngine, phone: str) -> Empresa | None:
    """Localiza empresa pelo whatsapp_phone — bypassa RLS (rota de sistema).

    Usa a engine diretamente (superuser) apenas para routing. Nenhum dado
    sensível é retornado além de (id, tenant_id) para iniciar a sessão correta.
    """
    async with engine.connect() as conn:
        stmt = select(Empresa).where(Empresa.whatsapp_phone == phone, Empresa.ativa.is_(True))
        result = await conn.execute(stmt)
        row = result.mappings().first()
        if row is None:
            return None
        # Reconstrói objeto mínimo sem ORM (apenas os campos necessários)
        return Empresa(
            id=row["id"],
            tenant_id=row["tenant_id"],
            cnpj=row["cnpj"],
            razao_social=row["razao_social"],
            regime_tributario=row["regime_tributario"],
            perfil_ui=row["perfil_ui"],
        )


@router.get(
    "/webhook",
    response_class=PlainTextResponse,
    summary="Verificação do webhook Meta (GET challenge)",
    include_in_schema=False,
)
async def verificar_webhook(
    request: Request,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    """Responde ao challenge de verificação do Meta WhatsApp Cloud API."""
    from app.config import Settings

    settings: Settings = request.app.state.settings
    if (
        hub_mode == "subscribe"
        and hub_verify_token == settings.META_WHATSAPP_VERIFY_TOKEN
        and hub_challenge
    ):
        log.info("whatsapp.webhook.verificado")
        return hub_challenge

    log.warning("whatsapp.webhook.verificacao_falhou", mode=hub_mode)
    raise HTTPException(status_code=403, detail="Token de verificação inválido")


@router.post(
    "/webhook",
    status_code=200,
    summary="Receber mensagens WhatsApp (POST webhook Meta)",
    include_in_schema=False,
)
async def receber_webhook(request: Request) -> Response:
    """Recebe eventos do Meta WhatsApp Cloud API.

    Fluxo:
    1. Verifica HMAC-SHA256 (§8.9 — obrigatório antes de qualquer processamento)
    2. Extrai mensagens do envelope Meta
    3. Para cada mensagem: localiza empresa pelo phone → processa com RLS correto
    4. Retorna 200 imediatamente (Meta não faz retry se recebe 200)
    """
    from app.config import Settings
    from app.modules.whatsapp.schemas import MensagemRecebidaIn
    from app.modules.whatsapp.service import WhatsAppService

    settings: Settings = request.app.state.settings
    payload_bytes = await request.body()

    # Verificação HMAC — obrigatória se app_secret configurado
    if settings.META_WHATSAPP_APP_SECRET:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verificar_assinatura_meta(
            payload_bytes, signature, settings.META_WHATSAPP_APP_SECRET
        ):
            log.warning("whatsapp.webhook.hmac_invalido")
            raise HTTPException(status_code=401, detail="Assinatura HMAC inválida")

    try:
        payload = await request.json()
    except Exception:
        log.warning("whatsapp.webhook.payload_invalido")
        return Response(status_code=200)

    mensagens_raw = extrair_mensagens(payload)
    if not mensagens_raw:
        return Response(status_code=200)

    engine: AsyncEngine = request.app.state.engine
    session_factory = request.app.state.session_factory
    sender = getattr(request.app.state, "whatsapp_sender", None)
    service = WhatsAppService()

    for msg_raw in mensagens_raw:
        msg = MensagemRecebidaIn(**msg_raw)
        try:
            empresa = await _lookup_empresa_por_phone(engine, msg.phone)
            if empresa is None:
                log.info("whatsapp.phone_nao_vinculado", phone_sufixo=msg.phone[-4:])
                continue

            async with session_factory() as session:
                await session.execute(text("SET LOCAL ROLE fiscal_app"))
                await set_tenant_id(session, empresa.tenant_id)
                await service.processar_mensagem(
                    session,
                    msg,
                    tenant_id=empresa.tenant_id,
                    empresa_id=empresa.id,
                    sender=sender,
                )
        except Exception as exc:
            log.error(
                "whatsapp.webhook.erro_processamento",
                erro=str(exc),
                tipo=type(exc).__name__,
                phone_sufixo=msg.phone[-4:],
            )

    return Response(status_code=200)
