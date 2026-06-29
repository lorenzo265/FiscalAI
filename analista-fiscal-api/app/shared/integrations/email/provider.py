"""Provider de e-mail transacional — Resend real (atrás de env) + fake.

Marco 4 PR3 (#14). Camada 4 (integrações externas). Espelha o padrão do
billing (Protocol + provider real + ``_Fake`` + factory): sem ``EMAIL_API_KEY``
a factory cai no ``_FakeEmailProvider`` (não envia). Nunca há mock em
produção — a credencial liga o envio real.

Resend é chamado via httpx puro (sem SDK novo): ``POST /emails`` com
``Authorization: Bearer``. Retry só em 5xx/transporte (mesmo padrão do
``MetaWhatsAppSender``); 4xx é erro nosso → ``EmailEnvioFalhou`` sem retry.
"""

from __future__ import annotations

from typing import Final, Protocol

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings
from app.shared.exceptions import EmailEnvioFalhou
from app.shared.integrations.email.types import EmailEnviado, EmailMessage
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_RESEND_URL: Final = "https://api.resend.com/emails"


def _redact(email: str) -> str:
    """E-mail redigido para log (LGPD): ``ana@x.com`` → ``a***@x.com``."""
    nome, _, dominio = email.partition("@")
    if not dominio or not nome:
        return "***"
    return f"{nome[0]}***@{dominio}"


class _EmailTemporaryError(Exception):
    """Erro temporário (5xx/TransportError) — aciona retry interno."""


class EmailProvider(Protocol):
    """Contrato mínimo de um provedor de e-mail transacional."""

    nome: str

    async def enviar(self, msg: EmailMessage) -> EmailEnviado:
        """Envia a mensagem já renderizada. Levanta ``EmailEnvioFalhou``."""
        ...

    async def aclose(self) -> None:
        """Fecha recursos de transporte."""
        ...


class ResendProvider:
    """Provedor real Resend. httpx + retry em 5xx/transporte."""

    nome: str = "resend"

    def __init__(
        self,
        settings: Settings,
        *,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._remetente_padrao = settings.EMAIL_FROM
        self._http = http or httpx.AsyncClient(
            base_url="",
            headers={
                "Authorization": f"Bearer {settings.EMAIL_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def enviar(self, msg: EmailMessage) -> EmailEnviado:
        if not msg.to:
            raise EmailEnvioFalhou("Destinatário (to) vazio — envio bloqueado.")
        payload: JsonObject = {
            "from": msg.remetente or self._remetente_padrao,
            "to": [msg.to],
            "subject": msg.assunto,
            "html": msg.html,
            "text": msg.texto,
        }
        try:
            return await self._post(payload, to=msg.to)
        except _EmailTemporaryError as exc:
            log.warning(
                "email.envio.tentativas_esgotadas",
                to=_redact(msg.to),
                erro=str(exc)[:200],
            )
            raise EmailEnvioFalhou(
                f"Resend indisponível após retries: {exc}"
            ) from exc

    @retry(
        wait=wait_exponential_jitter(initial=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(_EmailTemporaryError),
        reraise=True,
    )
    async def _post(self, payload: JsonObject, *, to: str) -> EmailEnviado:
        try:
            resp = await self._http.post(_RESEND_URL, json=payload)
        except httpx.TransportError as exc:
            raise _EmailTemporaryError(f"transport: {exc}") from exc

        if 500 <= resp.status_code < 600:
            raise _EmailTemporaryError(f"http_{resp.status_code}: {resp.text[:200]}")
        if not resp.is_success:
            # 4xx — erro nosso (domínio não verificado, payload inválido). Sem retry.
            raise EmailEnvioFalhou(f"Resend {resp.status_code}: {resp.text[:200]}")

        dados: JsonObject = resp.json()
        message_id = str(dados.get("id", ""))
        log.info("email.enviado", to=_redact(to), provider=self.nome, message_id=message_id)
        return EmailEnviado(provider=self.nome, message_id=message_id)


class _FakeEmailProvider:
    """Provedor de mentira (dev/teste sem credencial). Não envia nada."""

    nome: str = "fake"

    async def enviar(self, msg: EmailMessage) -> EmailEnviado:
        if not msg.to:
            raise EmailEnvioFalhou("Destinatário (to) vazio — envio bloqueado.")
        # Não logar o assunto: pode conter PII (ex.: nome no onboarding).
        log.info(
            "email.fake.nao_enviado",
            to=_redact(msg.to),
            tags=list(msg.tags),
        )
        return EmailEnviado(provider=self.nome, message_id=f"fake_{abs(hash(msg.to)) % 10**12:012d}")

    async def aclose(self) -> None:
        return None


def build_email_provider(settings: Settings) -> EmailProvider:
    """Resend real se ``EMAIL_API_KEY`` setado E provider 'resend'; senão fake."""
    if settings.EMAIL_API_KEY and settings.EMAIL_PROVIDER == "resend":
        return ResendProvider(settings)
    if settings.EMAIL_API_KEY and settings.EMAIL_PROVIDER != "resend":
        log.warning(
            "email.provider_nao_suportado_usando_fake",
            provider=settings.EMAIL_PROVIDER,
        )
    return _FakeEmailProvider()
