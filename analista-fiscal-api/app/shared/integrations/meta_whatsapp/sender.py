from __future__ import annotations

import httpx
import structlog

from app.config import Settings
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_GRAPH_URL = "https://graph.facebook.com/v18.0"


class MetaWhatsAppSender:
    """Envia mensagens via Meta WhatsApp Cloud API.

    Tipos suportados no MVP:
    - texto simples (service message — grátis em 24h após msg do cliente)

    Regra UX: máximo 3 mensagens por interação antes de redirecionar para
    o dashboard web (§UX do PlanoBackend.md).
    """

    def __init__(self, settings: Settings) -> None:
        self._phone_id = settings.META_WHATSAPP_PHONE_ID
        self._http = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def enviar_texto(self, phone: str, texto: str) -> JsonObject:
        """Envia mensagem de texto simples para o número E.164 informado."""
        if not self._phone_id:
            log.warning("whatsapp.sender.sem_phone_id", phone_sufixo=phone[-4:])
            return {"status": "skip_sem_configuracao"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": texto},
        }
        url = f"{_GRAPH_URL}/{self._phone_id}/messages"
        resp = await self._http.post(url, json=payload)

        if not resp.is_success:
            from app.shared.exceptions import WhatsAppErro

            raise WhatsAppErro(
                f"Falha ao enviar mensagem WhatsApp: {resp.status_code} {resp.text[:200]}"
            )

        result: JsonObject = resp.json()
        log.info("whatsapp.mensagem.enviada", phone_sufixo=phone[-4:])
        return result
