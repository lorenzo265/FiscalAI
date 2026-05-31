from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_GRAPH_URL = "https://graph.facebook.com/v18.0"


class _MetaTemporaryError(Exception):
    """Erro temporário do Meta (5xx ou TransportError) — aciona retry interno.

    Convertido em ``EnvioWhatsappFalhou`` (502) após esgotar tentativas.
    Erros 4xx (payload inválido, número não existe, template não aprovado)
    são levantados como ``EnvioWhatsappFalhou`` direto, sem retry.
    """


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

    # ── Sprint 15.5 — Envio de template (digest semanal) ────────────────────

    async def enviar_template(
        self,
        phone: str,
        *,
        template_name: str,
        language_code: str,
        body_parameters: list[str],
    ) -> JsonObject:
        """Envia mensagem via template Meta (categoria UTILITY ou MARKETING).

        Args:
            phone: número E.164 do destinatário.
            template_name: nome cadastrado e aprovado no Meta Business Manager.
            language_code: BCP-47 com underscore (ex.: ``pt_BR``).
            body_parameters: valores ordenados para ``${1}``, ``${2}``, ...
                Cada parâmetro é truncado pelo caller se necessário; o Meta
                rejeita componentes > 1024 chars com 400.

        Returns:
            Payload JSON da resposta Meta (``messages[0].id`` é o message id).

        Raises:
            EnvioWhatsappFalhou: 4xx (sem retry — erro do nosso lado) ou
                esgotamento de tentativas em 5xx/TransportError.
        """
        from app.shared.exceptions import EnvioWhatsappFalhou

        if not self._phone_id:
            log.warning(
                "whatsapp.template.sem_phone_id",
                phone_sufixo=phone[-4:],
                template_name=template_name,
            )
            raise EnvioWhatsappFalhou(
                "META_WHATSAPP_PHONE_ID não configurado — envio bloqueado."
            )

        payload: JsonObject = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": p} for p in body_parameters
                        ],
                    }
                ],
            },
        }
        url = f"{_GRAPH_URL}/{self._phone_id}/messages"

        try:
            return await self._post_template(url, payload, phone, template_name)
        except _MetaTemporaryError as exc:
            log.warning(
                "whatsapp.template.tentativas_esgotadas",
                phone_sufixo=phone[-4:],
                template_name=template_name,
                erro=str(exc)[:200],
            )
            raise EnvioWhatsappFalhou(
                f"Meta WhatsApp indisponível após retries: {exc}"
            ) from exc

    @retry(
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(_MetaTemporaryError),
        reraise=True,
    )
    async def _post_template(
        self,
        url: str,
        payload: JsonObject,
        phone: str,
        template_name: str,
    ) -> JsonObject:
        """POST com retry — 5xx/TransportError viram ``_MetaTemporaryError``."""
        from app.shared.exceptions import EnvioWhatsappFalhou

        try:
            resp = await self._http.post(url, json=payload)
        except httpx.TransportError as exc:
            raise _MetaTemporaryError(f"transport: {exc}") from exc

        if 500 <= resp.status_code < 600:
            raise _MetaTemporaryError(
                f"http_{resp.status_code}: {resp.text[:200]}"
            )
        if not resp.is_success:
            # 4xx — erro do nosso lado (template não aprovado, payload inválido,
            # número fora da janela 24h, etc.). Sem retry — caller decide.
            raise EnvioWhatsappFalhou(
                f"Meta WhatsApp {resp.status_code}: {resp.text[:200]}"
            )

        result: JsonObject = resp.json()
        log.info(
            "whatsapp.template.enviado",
            phone_sufixo=phone[-4:],
            template_name=template_name,
        )
        return result
