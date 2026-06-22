"""Testes do AdvisorService.enviar_digest_via_whatsapp (Sprint 15.5 PR3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.modules.advisor.service import AdvisorService
from app.shared.exceptions import (
    DigestJaEnviado,
    EmpresaNaoEncontrada,
    EmpresaSemWhatsapp,
    EnvioWhatsappFalhou,
)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


def _empresa(
    *,
    whatsapp_phone: str | None = "5511999990000",
    nome_fantasia: str | None = "ACME",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        whatsapp_phone=whatsapp_phone,
        nome_fantasia=nome_fantasia,
        razao_social="ACME COMERCIO LTDA",
    )


def _digest_preparado(
    empresa_id: uuid.UUID,
    *,
    status: str = "preparado",
    superseded_by: uuid.UUID | None = None,
    tentativas: int = 0,
) -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.empresa_id = empresa_id
    m.status = status
    m.superseded_by = superseded_by
    m.tentativas_envio = tentativas
    m.ultimo_erro_envio = None
    m.enviado_via_whatsapp_em = None
    m.enviado_template_name = None
    m.texto_redigido = "Olá ACME — resumo da semana."
    m.conteudo_estruturado = {"empresa_apelido_curto": "ACME"}
    return m


def _settings(ativo: bool = True) -> Settings:
    return Settings(
        META_WHATSAPP_TOKEN="tk",
        META_WHATSAPP_PHONE_ID="phone-id",
        WHATSAPP_DIGEST_TEMPLATE_NAME="weekly_digest_pt_br",
        WHATSAPP_DIGEST_LANG_CODE="pt_BR",
        WHATSAPP_DIGEST_TEMPLATE_ATIVO=ativo,
    )


# ── Caminho feliz ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_envio_caminho_feliz_marca_enviado() -> None:
    empresa = _empresa()
    digest = _digest_preparado(empresa.id)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    digest_repo.marcar_enviado = AsyncMock()
    sender = AsyncMock()
    sender.enviar_template = AsyncMock(return_value={"messages": [{"id": "wamid.1"}]})

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        result = await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )

    assert result is digest
    sender.enviar_template.assert_awaited_once()
    digest_repo.marcar_enviado.assert_awaited_once()
    # body_parameters: apelido + texto truncado
    kwargs = sender.enviar_template.call_args.kwargs
    assert kwargs["template_name"] == "weekly_digest_pt_br"
    assert kwargs["language_code"] == "pt_BR"
    assert kwargs["body_parameters"][0] == "ACME"
    assert "ACME" in kwargs["body_parameters"][1]


@pytest.mark.asyncio
async def test_envio_trunca_texto_a_1024_chars() -> None:
    empresa = _empresa()
    digest = _digest_preparado(empresa.id)
    digest.texto_redigido = "x" * 2000  # excede limite Meta
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    sender.enviar_template = AsyncMock(return_value={"messages": [{"id": "wamid.1"}]})

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )

    corpo = sender.enviar_template.call_args.kwargs["body_parameters"][1]
    assert len(corpo) == 1024


# ── Falhas pré-envio (sem chegar a tocar a Meta) ────────────────────────────


@pytest.mark.asyncio
async def test_flag_desativada_levanta_envio_falhou_sem_chamar_sender() -> None:
    session = AsyncMock()
    sender = AsyncMock()
    with pytest.raises(EnvioWhatsappFalhou, match="WHATSAPP_DIGEST_TEMPLATE_ATIVO"):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            uuid.uuid4(),
            uuid.uuid4(),
            sender=sender,
            settings=_settings(ativo=False),
        )
    sender.enviar_template.assert_not_awaited()


@pytest.mark.asyncio
async def test_digest_inexistente_levanta_404() -> None:
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=None)
    sender = AsyncMock()
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo), pytest.raises(EmpresaNaoEncontrada):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            uuid.uuid4(), uuid.uuid4(), sender=sender, settings=_settings(),
        )


@pytest.mark.asyncio
async def test_digest_de_outra_empresa_levanta_404() -> None:
    """Defesa em profundidade — além do RLS."""
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest = _digest_preparado(uuid.uuid4())  # outra empresa
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo), pytest.raises(EmpresaNaoEncontrada):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            uuid.uuid4(), digest.id, sender=sender, settings=_settings(),
        )


@pytest.mark.asyncio
async def test_digest_superseded_levanta_404() -> None:
    empresa = _empresa()
    digest = _digest_preparado(empresa.id, superseded_by=uuid.uuid4())
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo), pytest.raises(EmpresaNaoEncontrada):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )


@pytest.mark.asyncio
async def test_digest_ja_enviado_levanta_409() -> None:
    empresa = _empresa()
    digest = _digest_preparado(empresa.id, status="enviado")
    digest.enviado_via_whatsapp_em = datetime.now(_TZ_BR)
    session = AsyncMock()
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    with patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo), pytest.raises(DigestJaEnviado):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )


@pytest.mark.asyncio
async def test_empresa_sem_whatsapp_levanta_422() -> None:
    empresa = _empresa(whatsapp_phone=None)
    digest = _digest_preparado(empresa.id)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
        pytest.raises(EmpresaSemWhatsapp),
    ):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )
    sender.enviar_template.assert_not_awaited()


# ── Falhas pós-Meta ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_falha_meta_registra_tentativa_e_propaga_excecao() -> None:
    empresa = _empresa()
    digest = _digest_preparado(empresa.id, tentativas=0)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    digest_repo.registrar_falha_envio = AsyncMock()
    sender = AsyncMock()
    sender.enviar_template = AsyncMock(
        side_effect=EnvioWhatsappFalhou("Meta WhatsApp 500: down")
    )

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
        pytest.raises(EnvioWhatsappFalhou),
    ):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )

    digest_repo.registrar_falha_envio.assert_awaited_once()
    digest_repo.marcar_enviado.assert_not_awaited()


@pytest.mark.asyncio
async def test_envio_usa_apelido_do_conteudo_estruturado() -> None:
    """Apelido vem do snapshot persistido, não do nome corrente da empresa."""
    empresa = _empresa(nome_fantasia="NOVO NOME")
    digest = _digest_preparado(empresa.id)
    digest.conteudo_estruturado = {"empresa_apelido_curto": "APELIDO_NO_SNAPSHOT"}
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    sender.enviar_template = AsyncMock(return_value={})

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )

    body = sender.enviar_template.call_args.kwargs["body_parameters"]
    assert body[0] == "APELIDO_NO_SNAPSHOT"


@pytest.mark.asyncio
async def test_envio_fallback_para_nome_empresa_quando_snapshot_corrupto() -> None:
    """Snapshot sem 'empresa_apelido_curto' → cai no nome_fantasia/razao."""
    empresa = _empresa(nome_fantasia="FALLBACK CO")
    digest = _digest_preparado(empresa.id)
    digest.conteudo_estruturado = {}  # vazio — snapshot legado/corrompido
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    digest_repo = AsyncMock()
    digest_repo.por_id = AsyncMock(return_value=digest)
    sender = AsyncMock()
    sender.enviar_template = AsyncMock(return_value={})

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.DigestRepo", return_value=digest_repo),
    ):
        await AdvisorService(session).enviar_digest_via_whatsapp(
            empresa.id, digest.id, sender=sender, settings=_settings(),
        )

    body = sender.enviar_template.call_args.kwargs["body_parameters"]
    assert body[0] == "FALLBACK CO"


# ── Repo helpers — transições idempotentes ──────────────────────────────────


@pytest.mark.asyncio
async def test_registrar_falha_envio_promove_para_falhou_no_limite() -> None:
    """Após 5 tentativas, status muda para 'falhou'."""
    from app.modules.advisor.repo import DigestRepo

    digest = _digest_preparado(uuid.uuid4(), tentativas=4)
    session = AsyncMock()
    repo = DigestRepo(session)
    await repo.registrar_falha_envio(digest, erro="Meta indisponível", limite_tentativas=5)
    assert digest.tentativas_envio == 5
    assert digest.status == "falhou"


@pytest.mark.asyncio
async def test_registrar_falha_envio_mantem_status_se_abaixo_do_limite() -> None:
    from app.modules.advisor.repo import DigestRepo

    digest = _digest_preparado(uuid.uuid4(), tentativas=2)
    session = AsyncMock()
    repo = DigestRepo(session)
    await repo.registrar_falha_envio(digest, erro="x", limite_tentativas=5)
    assert digest.tentativas_envio == 3
    assert digest.status == "preparado"


@pytest.mark.asyncio
async def test_registrar_falha_envio_trunca_erro_a_500_chars() -> None:
    from app.modules.advisor.repo import DigestRepo

    digest = _digest_preparado(uuid.uuid4(), tentativas=0)
    session = AsyncMock()
    repo = DigestRepo(session)
    erro_grande = "x" * 1000
    await repo.registrar_falha_envio(digest, erro=erro_grande)
    assert digest.ultimo_erro_envio is not None
    assert len(digest.ultimo_erro_envio) == 500
