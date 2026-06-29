"""Testes do provider de e-mail (Marco 4 PR3 #14).

Factory (fake vs Resend), fake não envia, e Resend via httpx.MockTransport
(sucesso + 4xx sem retry). Sem rede real.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.shared.exceptions import EmailEnvioFalhou
from app.shared.integrations.email.provider import (
    ResendProvider,
    _FakeEmailProvider,
    build_email_provider,
)
from app.shared.integrations.email.types import EmailMessage


def _settings(**over: object) -> Settings:
    defaults: dict[str, object] = {"EMAIL_PROVIDER": "resend", "EMAIL_API_KEY": ""}
    defaults.update(over)
    return Settings(**defaults)  # type: ignore[arg-type]


def _msg(to: str = "ana@cliente.com.br") -> EmailMessage:
    return EmailMessage(
        to=to, assunto="Olá", html="<p>oi</p>", texto="oi", tags=("onboarding",)
    )


# ── Factory ────────────────────────────────────────────────────────────────


def test_factory_fake_sem_key() -> None:
    p = build_email_provider(_settings(EMAIL_API_KEY=""))
    assert p.nome == "fake"


def test_factory_resend_com_key() -> None:
    p = build_email_provider(_settings(EMAIL_API_KEY="re_x", EMAIL_PROVIDER="resend"))
    assert p.nome == "resend"


def test_factory_provider_desconhecido_cai_no_fake() -> None:
    p = build_email_provider(_settings(EMAIL_API_KEY="x", EMAIL_PROVIDER="postmark"))
    assert p.nome == "fake"


# ── Fake provider ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fake_nao_envia_mas_devolve_id() -> None:
    p = _FakeEmailProvider()
    out = await p.enviar(_msg())
    assert out.provider == "fake"
    assert out.message_id.startswith("fake_")
    await p.aclose()


@pytest.mark.asyncio
async def test_fake_to_vazio_levanta() -> None:
    p = _FakeEmailProvider()
    with pytest.raises(EmailEnvioFalhou):
        await p.enviar(_msg(to=""))


# ── Resend (httpx mockado) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_sucesso_retorna_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer re_test"
        return httpx.Response(200, json={"id": "msg_123"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer re_test"},
    )
    p = ResendProvider(_settings(EMAIL_API_KEY="re_test"), http=client)
    out = await p.enviar(_msg())
    assert out.provider == "resend"
    assert out.message_id == "msg_123"
    await p.aclose()


@pytest.mark.asyncio
async def test_resend_4xx_levanta_sem_retry() -> None:
    chamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(422, text="domínio não verificado")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    p = ResendProvider(_settings(EMAIL_API_KEY="re_test"), http=client)
    with pytest.raises(EmailEnvioFalhou):
        await p.enviar(_msg())
    assert chamadas["n"] == 1  # 4xx não faz retry
    await p.aclose()


@pytest.mark.asyncio
async def test_resend_to_vazio_levanta() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    p = ResendProvider(_settings(EMAIL_API_KEY="re_test"), http=client)
    with pytest.raises(EmailEnvioFalhou):
        await p.enviar(_msg(to=""))
    await p.aclose()
