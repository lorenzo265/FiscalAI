"""Testes do pagamento stub do marketplace (Sprint 13 PR3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.marketplace.pagamento import (
    ConsultaPagamentoService,
    _FakeProvider,
    idempotency_pagamento,
)
from app.shared.exceptions import (
    CobrancaInvalida,
    CobrancaNaoEncontrada,
    ConsultaNaoEncontrada,
)


def _consulta(
    *,
    status: str = "concluida",
    valor: Decimal = Decimal("80.00"),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        empresa_id=uuid.uuid4(),
        status=status,
        valor_consulta=valor,
        comissao_plataforma=Decimal("24.00"),
        paga_em=None,
    )


def _cobranca(
    *,
    consulta_id: uuid.UUID | None = None,
    status: str = "pendente",
    provider_externo_id: str = "fake-abc123",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        consulta_id=consulta_id or uuid.uuid4(),
        provider="fake",
        provider_externo_id=provider_externo_id,
        idempotency_key=uuid.uuid4(),
        valor=Decimal("80.00"),
        status=status,
        checkout_url="https://fiscalai.local/checkout/x",
        criado_em=datetime(2026, 5, 21, 10, 0, 0),
        paga_em=None,
        cancelada_em=None,
    )


# ── helpers puros ────────────────────────────────────────────────────────────


def test_idempotency_pagamento_estavel_por_consulta() -> None:
    cid = uuid.uuid4()
    assert idempotency_pagamento(cid) == idempotency_pagamento(cid)


def test_idempotency_pagamento_difere_entre_consultas() -> None:
    assert idempotency_pagamento(uuid.uuid4()) != idempotency_pagamento(uuid.uuid4())


@pytest.mark.asyncio
async def test_fake_provider_devolve_url_deterministica() -> None:
    cid = uuid.uuid4()
    out = await _FakeProvider().criar_cobranca(
        consulta_id=cid,
        valor=Decimal("100"),
        idempotency_key=uuid.uuid4(),
    )
    assert out.provider == "fake"
    assert out.checkout_url == f"https://fiscalai.local/checkout/{cid}"
    assert out.provider_externo_id.startswith("fake-")


# ── gerar_cobranca ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gerar_cobranca_consulta_inexistente_levanta() -> None:
    session = AsyncMock()
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.marketplace.pagamento.ConsultaRepo",
        return_value=consulta_repo,
    ):
        with pytest.raises(ConsultaNaoEncontrada):
            await ConsultaPagamentoService().gerar_cobranca(
                session, tenant_id=uuid.uuid4(), consulta_id=uuid.uuid4()
            )


@pytest.mark.asyncio
async def test_gerar_cobranca_consulta_nao_concluida_levanta() -> None:
    session = AsyncMock()
    consulta = _consulta(status="aceita")
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    with patch(
        "app.modules.marketplace.pagamento.ConsultaRepo",
        return_value=consulta_repo,
    ):
        with pytest.raises(CobrancaInvalida, match="concluida"):
            await ConsultaPagamentoService().gerar_cobranca(
                session, tenant_id=consulta.tenant_id, consulta_id=consulta.id
            )


@pytest.mark.asyncio
async def test_gerar_cobranca_sucesso() -> None:
    session = AsyncMock()
    # session.add é sync no AsyncSession real
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    consulta = _consulta(status="concluida")
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)

    with (
        patch(
            "app.modules.marketplace.pagamento.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch.object(
            ConsultaPagamentoService,
            "_buscar_por_consulta",
            new=AsyncMock(return_value=None),
        ),
    ):
        cobranca = await ConsultaPagamentoService().gerar_cobranca(
            session, tenant_id=consulta.tenant_id, consulta_id=consulta.id
        )

    assert cobranca.status == "pendente"
    assert cobranca.valor == Decimal("80.00")
    assert cobranca.provider == "fake"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_gerar_cobranca_idempotente_devolve_existente() -> None:
    session = AsyncMock()
    consulta = _consulta(status="concluida")
    consulta_repo = AsyncMock()
    consulta_repo.por_id = AsyncMock(return_value=consulta)
    existente = _cobranca(consulta_id=consulta.id)

    with (
        patch(
            "app.modules.marketplace.pagamento.ConsultaRepo",
            return_value=consulta_repo,
        ),
        patch.object(
            ConsultaPagamentoService,
            "_buscar_por_consulta",
            new=AsyncMock(return_value=existente),
        ),
    ):
        out = await ConsultaPagamentoService().gerar_cobranca(
            session, tenant_id=consulta.tenant_id, consulta_id=consulta.id
        )
    assert out is existente
    # Idempotente — não chama add/commit
    session.commit.assert_not_called()


# ── processar_webhook ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_status_invalido_levanta() -> None:
    session = AsyncMock()
    with pytest.raises(CobrancaInvalida, match="Status inválido"):
        await ConsultaPagamentoService().processar_webhook(
            session, provider_externo_id="x", status="rebaba"
        )


@pytest.mark.asyncio
async def test_webhook_cobranca_inexistente_levanta() -> None:
    session = AsyncMock()
    with patch.object(
        ConsultaPagamentoService,
        "_buscar_por_externo_id",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(CobrancaNaoEncontrada):
            await ConsultaPagamentoService().processar_webhook(
                session, provider_externo_id="x", status="paga"
            )


@pytest.mark.asyncio
async def test_webhook_paga_propaga_para_consulta() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    cobranca = _cobranca(status="pendente")
    consulta_atrelada = _consulta(status="concluida")
    consulta_atrelada.id = cobranca.consulta_id

    session.get = AsyncMock(return_value=consulta_atrelada)

    with patch.object(
        ConsultaPagamentoService,
        "_buscar_por_externo_id",
        new=AsyncMock(return_value=cobranca),
    ):
        out = await ConsultaPagamentoService().processar_webhook(
            session,
            provider_externo_id=cobranca.provider_externo_id,
            status="paga",
        )

    assert out.status == "paga"
    assert out.paga_em is not None
    # Consulta também recebe paga_em
    assert consulta_atrelada.paga_em is not None


@pytest.mark.asyncio
async def test_webhook_duplicado_eh_noop() -> None:
    session = AsyncMock()
    cobranca = _cobranca(status="paga")
    with patch.object(
        ConsultaPagamentoService,
        "_buscar_por_externo_id",
        new=AsyncMock(return_value=cobranca),
    ):
        out = await ConsultaPagamentoService().processar_webhook(
            session,
            provider_externo_id=cobranca.provider_externo_id,
            status="paga",
        )
    assert out is cobranca
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_estado_terminal_bloqueia_transicao() -> None:
    """Cobrança já paga não pode virar cancelada — estado terminal."""
    session = AsyncMock()
    cobranca = _cobranca(status="paga")
    with patch.object(
        ConsultaPagamentoService,
        "_buscar_por_externo_id",
        new=AsyncMock(return_value=cobranca),
    ):
        with pytest.raises(CobrancaInvalida, match="terminal"):
            await ConsultaPagamentoService().processar_webhook(
                session,
                provider_externo_id=cobranca.provider_externo_id,
                status="cancelada",
            )
