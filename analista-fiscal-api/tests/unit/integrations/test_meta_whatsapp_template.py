"""Testes do ``MetaWhatsAppSender.enviar_template`` (Sprint 15.5 PR2).

Mockamos ``httpx.AsyncClient.post`` diretamente; tenacity tem ``wait=wait_none()``
patched para evitar sleeps reais durante o retry path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from tenacity import wait_none

from app.config import Settings
from app.shared.exceptions import EnvioWhatsappFalhou
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender


def _settings() -> Settings:
    return Settings(
        META_WHATSAPP_TOKEN="tk-test",
        META_WHATSAPP_PHONE_ID="phone-id-123",
    )


def _build_sender() -> MetaWhatsAppSender:
    sender = MetaWhatsAppSender(_settings())
    # Evita sleeps reais — retries são instantâneos.
    MetaWhatsAppSender._post_template.retry.wait = wait_none()  # type: ignore[attr-defined]
    return sender


def _resp(status_code: int, body: dict[str, object] | None = None, text: str = "") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.is_success = 200 <= status_code < 300
    r.json = MagicMock(return_value=body or {"messages": [{"id": "wamid.123"}]})
    r.text = text
    return r


# ── Sucesso na primeira tentativa ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_enviar_template_sucesso_payload_correto() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(return_value=_resp(200))  # type: ignore[method-assign]

    result = await sender.enviar_template(
        "5511999990000",
        template_name="weekly_digest_pt_br",
        language_code="pt_BR",
        body_parameters=["ACME", "Resumo da semana"],
    )

    assert result == {"messages": [{"id": "wamid.123"}]}
    sender._http.post.assert_awaited_once()
    url, _ = sender._http.post.call_args.args, sender._http.post.call_args.kwargs
    payload = sender._http.post.call_args.kwargs["json"]
    assert payload["messaging_product"] == "whatsapp"
    assert payload["to"] == "5511999990000"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "weekly_digest_pt_br"
    assert payload["template"]["language"]["code"] == "pt_BR"
    assert payload["template"]["components"][0]["parameters"] == [
        {"type": "text", "text": "ACME"},
        {"type": "text", "text": "Resumo da semana"},
    ]


@pytest.mark.asyncio
async def test_enviar_template_url_usa_phone_id_configurado() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(return_value=_resp(200))  # type: ignore[method-assign]

    await sender.enviar_template(
        "5511999990000",
        template_name="weekly_digest_pt_br",
        language_code="pt_BR",
        body_parameters=["x"],
    )
    url_arg = sender._http.post.call_args.args[0]
    assert url_arg.endswith("/phone-id-123/messages")


# ── 5xx → retry ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_5xx_aciona_retry_e_sucesso_na_segunda_tentativa() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(  # type: ignore[method-assign]
        side_effect=[_resp(503, text="overloaded"), _resp(200)]
    )

    result = await sender.enviar_template(
        "5511999990000",
        template_name="weekly_digest_pt_br",
        language_code="pt_BR",
        body_parameters=["x"],
    )
    assert result == {"messages": [{"id": "wamid.123"}]}
    assert sender._http.post.await_count == 2


@pytest.mark.asyncio
async def test_5xx_esgota_3_tentativas_levanta_envio_falhou() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(return_value=_resp(502, text="bad gateway"))  # type: ignore[method-assign]

    with pytest.raises(EnvioWhatsappFalhou, match="Meta WhatsApp indisponível"):
        await sender.enviar_template(
            "5511999990000",
            template_name="weekly_digest_pt_br",
            language_code="pt_BR",
            body_parameters=["x"],
        )
    assert sender._http.post.await_count == 3


# ── 4xx → sem retry, falha direta ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_4xx_nao_aciona_retry_e_propaga_envio_falhou() -> None:
    """Template não aprovado / fora da janela 24h → 4xx; erro do nosso lado."""
    sender = _build_sender()
    sender._http.post = AsyncMock(  # type: ignore[method-assign]
        return_value=_resp(400, text="template not approved")
    )

    with pytest.raises(EnvioWhatsappFalhou, match="Meta WhatsApp 400"):
        await sender.enviar_template(
            "5511999990000",
            template_name="weekly_digest_pt_br",
            language_code="pt_BR",
            body_parameters=["x"],
        )
    assert sender._http.post.await_count == 1


# ── TransportError (timeout) → retry ────────────────────────────────────────


@pytest.mark.asyncio
async def test_transport_error_aciona_retry() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            httpx.ConnectError("timeout"),
            httpx.ConnectError("timeout"),
            _resp(200),
        ]
    )

    result = await sender.enviar_template(
        "5511999990000",
        template_name="weekly_digest_pt_br",
        language_code="pt_BR",
        body_parameters=["x"],
    )
    assert result == {"messages": [{"id": "wamid.123"}]}
    assert sender._http.post.await_count == 3


# ── Phone ID ausente ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sem_phone_id_levanta_envio_falhou_sem_chamar_http() -> None:
    sender = MetaWhatsAppSender(Settings(META_WHATSAPP_TOKEN="tk", META_WHATSAPP_PHONE_ID=""))
    sender._http.post = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(EnvioWhatsappFalhou, match="META_WHATSAPP_PHONE_ID"):
        await sender.enviar_template(
            "5511999990000",
            template_name="weekly_digest_pt_br",
            language_code="pt_BR",
            body_parameters=["x"],
        )
    sender._http.post.assert_not_awaited()


# ── Componente body vazio (corner case) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_body_parameters_vazio_envia_components_sem_parametros() -> None:
    sender = _build_sender()
    sender._http.post = AsyncMock(return_value=_resp(200))  # type: ignore[method-assign]

    await sender.enviar_template(
        "5511999990000",
        template_name="weekly_digest_pt_br",
        language_code="pt_BR",
        body_parameters=[],
    )
    payload = sender._http.post.call_args.kwargs["json"]
    assert payload["template"]["components"][0]["parameters"] == []
