"""Testes do OpenFinanceService (Sprint 7 PR1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.open_finance.schemas import RegistrarItemIn, StatusItem
from app.modules.open_finance.service import OpenFinanceService, _parse_iso
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    ItemJaRegistrado,
    PluggyErro,
)


def _empresa() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), cnpj="12345678000195")


# ── helpers ──────────────────────────────────────────────────────────────────


class TestParseIso:
    def test_iso_valido(self) -> None:
        d = _parse_iso("2026-05-17T10:30:00+00:00")
        assert d is not None and d.year == 2026

    def test_iso_com_z(self) -> None:
        d = _parse_iso("2026-05-17T10:30:00Z")
        assert d is not None

    def test_invalido_retorna_none(self) -> None:
        assert _parse_iso("xx") is None
        assert _parse_iso(None) is None
        assert _parse_iso(12345) is None


# ── connect_token ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_token_empresa_inexistente() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)

    with patch(
        "app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(EmpresaNaoEncontrada):
            await OpenFinanceService().emitir_connect_token(
                session, uuid.uuid4(), pluggy_client=AsyncMock()
            )


@pytest.mark.asyncio
async def test_connect_token_sem_pluggy_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    with patch(
        "app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(PluggyErro, match="não disponível"):
            await OpenFinanceService().emitir_connect_token(
                session, empresa.id, pluggy_client=None
            )


@pytest.mark.asyncio
async def test_connect_token_retorna_payload_e_passa_empresa_id() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    pluggy = AsyncMock()
    pluggy.create_connect_token = AsyncMock(
        return_value={
            "accessToken": "tk-abc",
            "expiresAt": "2026-05-17T15:00:00+00:00",
        }
    )

    with patch(
        "app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo
    ):
        out = await OpenFinanceService().emitir_connect_token(
            session, empresa.id, pluggy_client=pluggy
        )

    assert out.connect_token == "tk-abc"
    chamada = pluggy.create_connect_token.await_args
    assert chamada.kwargs["client_user_id"] == str(empresa.id)


@pytest.mark.asyncio
async def test_connect_token_sem_expires_at_usa_default() -> None:
    """Pluggy não devolve expiresAt — service calcula via TTL configurado."""
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    pluggy = AsyncMock()
    pluggy.create_connect_token = AsyncMock(return_value={"accessToken": "tk"})

    with patch(
        "app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo
    ):
        out = await OpenFinanceService().emitir_connect_token(
            session, empresa.id, pluggy_client=pluggy, ttl_minutos=15
        )

    assert out.expires_at is not None
    delta = out.expires_at - datetime.now(out.expires_at.tzinfo)
    # ~15 min, com margem de 1 min para o teste
    assert 13 * 60 <= delta.total_seconds() <= 16 * 60


@pytest.mark.asyncio
async def test_connect_token_sem_access_token_levanta() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    pluggy = AsyncMock()
    pluggy.create_connect_token = AsyncMock(return_value={})

    with patch(
        "app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo
    ):
        with pytest.raises(PluggyErro, match="accessToken"):
            await OpenFinanceService().emitir_connect_token(
                session, empresa.id, pluggy_client=pluggy
            )


# ── registrar_item ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_registrar_item_idempotente_levanta_se_existe() -> None:
    session = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo = AsyncMock()
    repo.por_pluggy_id = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

    with (
        patch("app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.open_finance.service.PluggyItemRepo", return_value=repo),
    ):
        with pytest.raises(ItemJaRegistrado):
            await OpenFinanceService().registrar_item(
                session,
                uuid.uuid4(),
                empresa.id,
                RegistrarItemIn(pluggy_item_id="abcd1234"),
                pluggy_client=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_registrar_item_consulta_pluggy_e_extrai_connector() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    new_id = uuid.uuid4()
    item_persistido = SimpleNamespace(
        id=new_id,
        empresa_id=empresa.id,
        pluggy_item_id="pluggy-xyz",
        connector_id=201,
        connector_nome="Itaú PF",
        status="LOGIN_SUCCEEDED",
        last_sync_at=None,
        ativo=True,
        criado_em=datetime.now(),
    )
    repo = AsyncMock()
    repo.por_pluggy_id = AsyncMock(return_value=None)
    repo.criar = AsyncMock(return_value=item_persistido)

    pluggy = AsyncMock()
    pluggy.get_item = AsyncMock(
        return_value={
            "id": "pluggy-xyz",
            "status": "LOGIN_SUCCEEDED",
            "connector": {"id": 201, "name": "Itaú PF"},
        }
    )

    with (
        patch("app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.open_finance.service.PluggyItemRepo", return_value=repo),
    ):
        out = await OpenFinanceService().registrar_item(
            session,
            uuid.uuid4(),
            empresa.id,
            RegistrarItemIn(pluggy_item_id="pluggy-xyz"),
            pluggy_client=pluggy,
        )

    assert out.status == StatusItem.LOGIN_SUCCEEDED
    chamada = repo.criar.await_args
    assert chamada.kwargs["connector_id"] == 201
    assert chamada.kwargs["connector_nome"] == "Itaú PF"
    assert chamada.kwargs["status"] == "LOGIN_SUCCEEDED"


@pytest.mark.asyncio
async def test_registrar_item_pluggy_indisponivel_persiste_creating() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    item_persistido = SimpleNamespace(
        id=uuid.uuid4(),
        empresa_id=empresa.id,
        pluggy_item_id="x",
        connector_id=None,
        connector_nome=None,
        status="CREATING",
        last_sync_at=None,
        ativo=True,
        criado_em=datetime.now(),
    )
    repo = AsyncMock()
    repo.por_pluggy_id = AsyncMock(return_value=None)
    repo.criar = AsyncMock(return_value=item_persistido)

    pluggy = AsyncMock()
    pluggy.get_item = AsyncMock(side_effect=PluggyErro("503 down"))

    with (
        patch("app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.open_finance.service.PluggyItemRepo", return_value=repo),
    ):
        out = await OpenFinanceService().registrar_item(
            session,
            uuid.uuid4(),
            empresa.id,
            RegistrarItemIn(pluggy_item_id="pluggy-x1"),
            pluggy_client=pluggy,
        )

    assert out.status == StatusItem.CREATING
    chamada = repo.criar.await_args
    assert chamada.kwargs["connector_id"] is None


@pytest.mark.asyncio
async def test_registrar_item_status_desconhecido_fica_creating_com_detalhe() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    empresa = _empresa()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)

    repo = AsyncMock()
    repo.por_pluggy_id = AsyncMock(return_value=None)
    repo.criar = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            empresa_id=empresa.id,
            pluggy_item_id="x",
            connector_id=None,
            connector_nome=None,
            status="CREATING",
            last_sync_at=None,
            ativo=True,
            criado_em=datetime.now(),
        )
    )

    pluggy = AsyncMock()
    pluggy.get_item = AsyncMock(
        return_value={"status": "FUTURO_STATUS_DESCONHECIDO", "connector": {}}
    )

    with (
        patch("app.modules.open_finance.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.open_finance.service.PluggyItemRepo", return_value=repo),
    ):
        await OpenFinanceService().registrar_item(
            session,
            uuid.uuid4(),
            empresa.id,
            RegistrarItemIn(pluggy_item_id="pluggy-x1"),
            pluggy_client=pluggy,
        )

    chamada = repo.criar.await_args
    assert chamada.kwargs["status"] == "CREATING"
    assert "FUTURO_STATUS_DESCONHECIDO" in (chamada.kwargs["status_detalhe"] or "")
