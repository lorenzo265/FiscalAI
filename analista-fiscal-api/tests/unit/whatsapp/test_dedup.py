"""Testes unitários — dedup de mensagens do webhook Meta WhatsApp (Fase 2 PR7).

Cobre o fix M1 da auditoria: ``mensagem_id`` é único do Meta e dedup precisa
acontecer ANTES de qualquer side-effect (incremento de sessão, envio via sender).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.whatsapp.schemas import MensagemRecebidaIn
from app.modules.whatsapp.service import WhatsAppService


def _msg(mensagem_id: str = "wamid.ABC123") -> MensagemRecebidaIn:
    return MensagemRecebidaIn(
        phone="5511999998888",
        mensagem_id=mensagem_id,
        texto="qual é o meu DAS?",
        tipo="text",
    )


def _empresa(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=empresa_id, cnpj="12345678000195")


def _sessao() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        mensagens_na_sessao=0,
    )


@pytest.mark.asyncio
async def test_primeira_mensagem_e_processada_normalmente() -> None:
    """1ª chamada com mensagem_id novo: marcar_processada=True, processa fluxo."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    sender = AsyncMock()
    sender.enviar_texto = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa(empresa_id))

    dedup_repo = AsyncMock()
    dedup_repo.marcar_processada = AsyncMock(return_value=True)

    sessao_repo = AsyncMock()
    sessao_repo.obter_ou_criar = AsyncMock(return_value=_sessao())
    sessao_repo.incrementar_mensagens = AsyncMock()

    with (
        patch("app.modules.whatsapp.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.whatsapp.service.MensagemProcessadaRepo",
            return_value=dedup_repo,
        ),
        patch(
            "app.modules.whatsapp.service.SessaoWhatsAppRepo",
            return_value=sessao_repo,
        ),
    ):
        out = await WhatsAppService().processar_mensagem(
            session,
            _msg(),
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            sender=sender,
        )

    assert out is not None
    dedup_repo.marcar_processada.assert_awaited_once()
    sessao_repo.incrementar_mensagens.assert_awaited_once()
    sender.enviar_texto.assert_awaited_once()


@pytest.mark.asyncio
async def test_mensagem_duplicada_retorna_none_sem_side_effects() -> None:
    """2ª chamada com mesmo mensagem_id: marcar_processada=False, early-return."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()
    sender = AsyncMock()
    sender.enviar_texto = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa(empresa_id))

    dedup_repo = AsyncMock()
    dedup_repo.marcar_processada = AsyncMock(return_value=False)  # já existia

    sessao_repo = AsyncMock()
    sessao_repo.obter_ou_criar = AsyncMock()
    sessao_repo.incrementar_mensagens = AsyncMock()

    with (
        patch("app.modules.whatsapp.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.whatsapp.service.MensagemProcessadaRepo",
            return_value=dedup_repo,
        ),
        patch(
            "app.modules.whatsapp.service.SessaoWhatsAppRepo",
            return_value=sessao_repo,
        ),
    ):
        out = await WhatsAppService().processar_mensagem(
            session,
            _msg(),
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            sender=sender,
        )

    # Early-return: nenhum side-effect
    assert out is None
    dedup_repo.marcar_processada.assert_awaited_once()
    sessao_repo.obter_ou_criar.assert_not_awaited()
    sessao_repo.incrementar_mensagens.assert_not_awaited()
    sender.enviar_texto.assert_not_awaited()


@pytest.mark.asyncio
async def test_dedup_chamado_com_campos_corretos() -> None:
    """marcar_processada deve receber mensagem_id, tenant_id, empresa_id e phone."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa(empresa_id))

    dedup_repo = AsyncMock()
    dedup_repo.marcar_processada = AsyncMock(return_value=True)

    sessao_repo = AsyncMock()
    sessao_repo.obter_ou_criar = AsyncMock(return_value=_sessao())
    sessao_repo.incrementar_mensagens = AsyncMock()

    with (
        patch("app.modules.whatsapp.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.whatsapp.service.MensagemProcessadaRepo",
            return_value=dedup_repo,
        ),
        patch(
            "app.modules.whatsapp.service.SessaoWhatsAppRepo",
            return_value=sessao_repo,
        ),
    ):
        await WhatsAppService().processar_mensagem(
            session,
            _msg(mensagem_id="wamid.XYZ789"),
            tenant_id=tenant_id,
            empresa_id=empresa_id,
        )

    chamada = dedup_repo.marcar_processada.await_args
    assert chamada.kwargs["mensagem_id"] == "wamid.XYZ789"
    assert chamada.kwargs["tenant_id"] == tenant_id
    assert chamada.kwargs["empresa_id"] == empresa_id
    assert chamada.kwargs["phone"] == "5511999998888"


@pytest.mark.asyncio
async def test_mensagem_sem_id_pula_dedup() -> None:
    """Mensagem sem mensagem_id (cenário defensivo) processa sem dedup."""
    empresa_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=_empresa(empresa_id))

    dedup_repo = AsyncMock()
    dedup_repo.marcar_processada = AsyncMock(return_value=True)

    sessao_repo = AsyncMock()
    sessao_repo.obter_ou_criar = AsyncMock(return_value=_sessao())
    sessao_repo.incrementar_mensagens = AsyncMock()

    with (
        patch("app.modules.whatsapp.service.EmpresaRepo", return_value=empresa_repo),
        patch(
            "app.modules.whatsapp.service.MensagemProcessadaRepo",
            return_value=dedup_repo,
        ),
        patch(
            "app.modules.whatsapp.service.SessaoWhatsAppRepo",
            return_value=sessao_repo,
        ),
    ):
        out = await WhatsAppService().processar_mensagem(
            session,
            _msg(mensagem_id=""),
            tenant_id=tenant_id,
            empresa_id=empresa_id,
        )

    assert out is not None
    dedup_repo.marcar_processada.assert_not_awaited()
    sessao_repo.incrementar_mensagens.assert_awaited_once()
