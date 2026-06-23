"""Testes do SyncService + helpers puros (Sprint 7 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.open_finance.sync_service import (
    SyncService,
    _account_para_dto,
    _decimal_ou_none,
    _parse_iso_date,
    _transacao_para_dto,
)
from app.shared.exceptions import ItemNaoEncontrado, PluggyErro

# ── helpers puros ────────────────────────────────────────────────────────────


class TestAccountDto:
    def test_account_basico(self) -> None:
        dto = _account_para_dto(
            {
                "id": "acc-1",
                "name": "Itaú Conta Corrente",
                "type": "CHECKING",
                "balance": "1250.50",
                "bankData": {
                    "agencyNumber": "0001",
                    "accountNumber": "12345-6",
                },
            }
        )
        assert dto is not None
        assert dto["pluggy_account_id"] == "acc-1"
        assert dto["tipo"] == "CHECKING"
        assert dto["saldo_atual"] == Decimal("1250.50")
        assert dto["agencia"] == "0001"
        assert dto["numero"] == "12345-6"

    def test_account_sem_id_retorna_none(self) -> None:
        assert _account_para_dto({}) is None

    def test_account_tipo_invalido_cai_em_checking(self) -> None:
        dto = _account_para_dto({"id": "x", "type": "EXOTIC"})
        assert dto is not None and dto["tipo"] == "CHECKING"

    def test_account_credit_card_mantido(self) -> None:
        dto = _account_para_dto({"id": "x", "type": "credit_card", "balance": "0"})
        assert dto is not None and dto["tipo"] == "CREDIT_CARD"


class TestTransacaoDto:
    def test_credit_positivo(self) -> None:
        dto = _transacao_para_dto(
            {
                "id": "tx-1",
                "type": "CREDIT",
                "amount": "500.00",
                "date": "2026-04-15",
                "description": "PIX recebido",
                "status": "CONFIRMED",
            }
        )
        assert dto is not None
        assert dto["valor"] == Decimal("500.00")
        assert dto["tipo"] == "CREDIT"
        assert dto["data_transacao"] == date(2026, 4, 15)

    def test_debit_sempre_negativo(self) -> None:
        """Mesmo se Pluggy enviar amount positivo em DEBIT, armazenamos signed."""
        dto = _transacao_para_dto(
            {
                "id": "tx-2",
                "type": "DEBIT",
                "amount": "300.00",
                "date": "2026-04-15",
                "description": "Pagamento",
            }
        )
        assert dto is not None
        assert dto["valor"] == Decimal("-300.00")
        assert dto["tipo"] == "DEBIT"

    def test_tipo_ausente_infere_do_sinal(self) -> None:
        dto = _transacao_para_dto(
            {"id": "tx-3", "amount": "-150.00", "date": "2026-04-15"}
        )
        assert dto is not None
        assert dto["tipo"] == "DEBIT"
        assert dto["valor"] == Decimal("-150.00")

    def test_data_iso_datetime_extrai_date(self) -> None:
        dto = _transacao_para_dto(
            {
                "id": "tx",
                "type": "CREDIT",
                "amount": "10",
                "date": "2026-04-15T10:30:00Z",
            }
        )
        assert dto is not None
        assert dto["data_transacao"] == date(2026, 4, 15)

    def test_sem_data_retorna_none(self) -> None:
        assert (
            _transacao_para_dto(
                {"id": "x", "amount": "10", "type": "CREDIT", "date": "lixo"}
            )
            is None
        )

    def test_merchant_cnpj_valido_capturado(self) -> None:
        dto = _transacao_para_dto(
            {
                "id": "x",
                "type": "DEBIT",
                "amount": "50",
                "date": "2026-04-15",
                "merchant": {"cnpj": "12.345.678/0001-95", "name": "Loja"},
            }
        )
        assert dto is not None
        assert dto["merchant_cnpj"] == "12345678000195"
        assert dto["merchant_nome"] == "Loja"

    def test_merchant_cnpj_curto_ignorado(self) -> None:
        dto = _transacao_para_dto(
            {
                "id": "x",
                "type": "DEBIT",
                "amount": "50",
                "date": "2026-04-15",
                "merchant": {"cnpj": "111"},
            }
        )
        assert dto is not None and dto["merchant_cnpj"] is None

    def test_status_invalido_cai_em_confirmed(self) -> None:
        dto = _transacao_para_dto(
            {
                "id": "x",
                "type": "CREDIT",
                "amount": "1",
                "date": "2026-04-15",
                "status": "WHATEVER",
            }
        )
        assert dto is not None and dto["status"] == "CONFIRMED"


class TestParseDate:
    def test_iso_date(self) -> None:
        assert _parse_iso_date("2026-04-15") == date(2026, 4, 15)

    def test_iso_datetime(self) -> None:
        assert _parse_iso_date("2026-04-15T08:00:00Z") == date(2026, 4, 15)

    def test_invalido(self) -> None:
        assert _parse_iso_date("xx") is None
        assert _parse_iso_date(None) is None


class TestDecimal:
    def test_string(self) -> None:
        assert _decimal_ou_none("1.50") == Decimal("1.50")

    def test_invalido(self) -> None:
        assert _decimal_ou_none("abc") is None


# ── service.sincronizar_item ─────────────────────────────────────────────────


def _item(empresa_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa_id,
        pluggy_item_id="pluggy-x",
        status="LOGIN_SUCCEEDED",
    )


@pytest.mark.asyncio
async def test_sync_item_inexistente_levanta() -> None:
    session = AsyncMock()
    repo_item = AsyncMock()
    repo_item.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.open_finance.sync_service.PluggyItemRepo", return_value=repo_item
    ), pytest.raises(ItemNaoEncontrado):
        await SyncService().sincronizar_item(
            session, uuid.uuid4(), uuid.uuid4(), pluggy_client=AsyncMock()
        )


@pytest.mark.asyncio
async def test_sync_sem_pluggy_marca_indisponivel() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_id = uuid.uuid4()
    item = _item(empresa_id)
    repo_item = AsyncMock()
    repo_item.por_id = AsyncMock(return_value=item)
    repo_item.atualizar_status = AsyncMock()

    with patch(
        "app.modules.open_finance.sync_service.PluggyItemRepo", return_value=repo_item
    ):
        result = await SyncService().sincronizar_item(
            session, uuid.uuid4(), item.id, pluggy_client=None
        )

    assert result.contas_processadas == 0
    chamada = repo_item.atualizar_status.await_args
    assert chamada.kwargs["erro_codigo"] == "PluggyIndisponivel"


@pytest.mark.asyncio
async def test_sync_accounts_falha_marca_login_error() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    item = _item(uuid.uuid4())
    repo_item = AsyncMock()
    repo_item.por_id = AsyncMock(return_value=item)
    repo_item.atualizar_status = AsyncMock()

    pluggy = AsyncMock()
    pluggy.list_accounts = AsyncMock(side_effect=PluggyErro("422 invalid"))

    with patch(
        "app.modules.open_finance.sync_service.PluggyItemRepo", return_value=repo_item
    ):
        result = await SyncService().sincronizar_item(
            session, uuid.uuid4(), item.id, pluggy_client=pluggy
        )

    assert result.contas_processadas == 0
    chamada = repo_item.atualizar_status.await_args
    assert chamada.kwargs["status"] == "LOGIN_ERROR"


@pytest.mark.asyncio
async def test_sync_processa_contas_e_transacoes() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    empresa_id = uuid.uuid4()
    item = _item(empresa_id)
    repo_item = AsyncMock()
    repo_item.por_id = AsyncMock(return_value=item)
    repo_item.atualizar_status = AsyncMock()

    repo_conta = AsyncMock()
    conta_uuid = uuid.uuid4()
    conta_obj = SimpleNamespace(id=conta_uuid)
    repo_conta.upsert = AsyncMock(return_value=(conta_obj, True))

    repo_tx = AsyncMock()
    repo_tx.upsert_lote = AsyncMock(return_value=2)

    pluggy = AsyncMock()
    pluggy.list_accounts = AsyncMock(
        return_value={
            "results": [
                {
                    "id": "acc-1",
                    "name": "Itaú",
                    "type": "CHECKING",
                    "balance": "1000.00",
                }
            ]
        }
    )
    # Primeira página com 2 transações; segunda página vazia → para.
    pluggy.list_transactions = AsyncMock(
        side_effect=[
            {
                "results": [
                    {
                        "id": "tx-1",
                        "type": "CREDIT",
                        "amount": "500",
                        "date": "2026-04-15",
                    },
                    {
                        "id": "tx-2",
                        "type": "DEBIT",
                        "amount": "100",
                        "date": "2026-04-16",
                    },
                ]
            },
        ]
    )

    with (
        patch(
            "app.modules.open_finance.sync_service.PluggyItemRepo",
            return_value=repo_item,
        ),
        patch(
            "app.modules.open_finance.sync_service.ContaBancariaRepo",
            return_value=repo_conta,
        ),
        patch(
            "app.modules.open_finance.sync_service.TransacoesRepo",
            return_value=repo_tx,
        ),
    ):
        result = await SyncService().sincronizar_item(
            session, uuid.uuid4(), item.id, pluggy_client=pluggy
        )

    assert result.contas_processadas == 1
    assert result.contas_novas == 1
    assert result.transacoes_processadas == 2

    upsert_call = repo_conta.upsert.await_args
    assert upsert_call.kwargs["pluggy_account_id"] == "acc-1"
    assert upsert_call.kwargs["saldo_atual"] == Decimal("1000.00")

    lote_call = repo_tx.upsert_lote.await_args
    assert lote_call.kwargs["conta_bancaria_id"] == conta_uuid
    lote = lote_call.kwargs["transacoes"]
    assert len(lote) == 2
    assert lote[1]["valor"] == Decimal("-100")  # DEBIT virou negativo

    # Status final = LOGIN_SUCCEEDED + last_sync_at preenchido
    status_call = repo_item.atualizar_status.await_args
    assert status_call.kwargs["status"] == "LOGIN_SUCCEEDED"
    assert status_call.kwargs["last_sync_at"] is not None


@pytest.mark.asyncio
async def test_sync_para_quando_pagina_volta_curta() -> None:
    """Se uma página vier com menos itens que o page_size, o sync deve parar."""
    session = AsyncMock()
    session.commit = AsyncMock()

    item = _item(uuid.uuid4())
    repo_item = AsyncMock()
    repo_item.por_id = AsyncMock(return_value=item)
    repo_item.atualizar_status = AsyncMock()

    repo_conta = AsyncMock()
    repo_conta.upsert = AsyncMock(
        return_value=(SimpleNamespace(id=uuid.uuid4()), False)
    )
    repo_tx = AsyncMock()
    repo_tx.upsert_lote = AsyncMock(return_value=1)

    pluggy = AsyncMock()
    pluggy.list_accounts = AsyncMock(
        return_value={"results": [{"id": "acc-1", "type": "CHECKING", "balance": "0"}]}
    )
    pluggy.list_transactions = AsyncMock(
        return_value={
            "results": [
                {
                    "id": "tx-1",
                    "type": "CREDIT",
                    "amount": "10",
                    "date": "2026-04-15",
                }
            ]
        }
    )

    with (
        patch(
            "app.modules.open_finance.sync_service.PluggyItemRepo",
            return_value=repo_item,
        ),
        patch(
            "app.modules.open_finance.sync_service.ContaBancariaRepo",
            return_value=repo_conta,
        ),
        patch(
            "app.modules.open_finance.sync_service.TransacoesRepo",
            return_value=repo_tx,
        ),
    ):
        await SyncService().sincronizar_item(
            session, uuid.uuid4(), item.id, pluggy_client=pluggy
        )

    # Só uma chamada a list_transactions porque a primeira página já veio curta
    assert pluggy.list_transactions.await_count == 1
