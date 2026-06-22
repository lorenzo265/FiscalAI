"""Service de connect_token + registro de items Pluggy (Sprint 7 PR1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.open_finance.repo import PluggyItemRepo
from app.modules.open_finance.schemas import (
    ConnectTokenOut,
    PluggyItemOut,
    RegistrarItemIn,
    StatusItem,
)
from app.shared.exceptions import (
    EmpresaNaoEncontrada,
    ItemJaRegistrado,
    PluggyErro,
    PluggyTimeout,
)
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


class _ClientePluggy(Protocol):
    async def create_connect_token(
        self,
        *,
        client_user_id: str,
        webhook_url: str | None = None,
    ) -> JsonObject: ...

    async def get_item(self, item_id: str) -> JsonObject: ...


class OpenFinanceService:
    async def emitir_connect_token(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        *,
        pluggy_client: _ClientePluggy | None,
        webhook_url: str | None = None,
        ttl_minutos: int = 30,
    ) -> ConnectTokenOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        if pluggy_client is None:
            raise PluggyErro("PluggyClient não disponível em runtime")

        resposta = await pluggy_client.create_connect_token(
            client_user_id=str(empresa_id),
            webhook_url=webhook_url,
        )
        token = str(resposta.get("accessToken") or resposta.get("connectToken") or "")
        if not token:
            raise PluggyErro("Pluggy não retornou accessToken no connect_token")

        # Pluggy retorna `expiresAt` ISO; se ausente, calculamos pelo TTL configurado.
        expires_at_raw = resposta.get("expiresAt")
        expires_at = _parse_iso(expires_at_raw) or (
            datetime.now(_TZ_BR) + timedelta(minutes=ttl_minutos)
        )

        log.info(
            "open_finance.connect_token.emitido",
            empresa_id=str(empresa_id),
            expires_at=expires_at.isoformat(),
        )
        return ConnectTokenOut(connect_token=token, expires_at=expires_at)

    async def registrar_item(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: RegistrarItemIn,
        *,
        pluggy_client: _ClientePluggy | None,
    ) -> PluggyItemOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = PluggyItemRepo(session)
        existente = await repo.por_pluggy_id(payload.pluggy_item_id)
        if existente is not None:
            raise ItemJaRegistrado(
                f"Item Pluggy {payload.pluggy_item_id} já registrado"
            )

        # Consulta o item na Pluggy para captar connector + status reais.
        connector_id: int | None = None
        connector_nome: str | None = None
        status = StatusItem.CREATING.value
        status_detalhe: str | None = None

        if pluggy_client is not None:
            try:
                info = await pluggy_client.get_item(payload.pluggy_item_id)
            except (PluggyErro, PluggyTimeout) as exc:
                log.warning(
                    "open_finance.item.get_falhou",
                    pluggy_item_id=payload.pluggy_item_id,
                    erro=exc.codigo,
                )
            else:
                connector = info.get("connector") or {}
                connector_id = (
                    int(connector["id"]) if isinstance(connector.get("id"), int) else None
                )
                connector_nome = (
                    str(connector.get("name")) if connector.get("name") else None
                )
                status_raw = str(info.get("status") or status)
                # Normaliza para valor do enum, fallback para CREATING.
                try:
                    status = StatusItem(status_raw).value
                except ValueError:
                    status_detalhe = f"Status Pluggy desconhecido: {status_raw}"

        item = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            pluggy_item_id=payload.pluggy_item_id,
            connector_id=connector_id,
            connector_nome=connector_nome,
            status=status,
            status_detalhe=status_detalhe,
        )
        await session.commit()

        log.info(
            "open_finance.item.registrado",
            empresa_id=str(empresa_id),
            pluggy_item_id=payload.pluggy_item_id,
            connector_id=connector_id,
            status=status,
        )

        return PluggyItemOut(
            id=item.id,
            empresa_id=item.empresa_id,
            pluggy_item_id=item.pluggy_item_id,
            connector_id=item.connector_id,
            connector_nome=item.connector_nome,
            status=StatusItem(item.status),
            last_sync_at=item.last_sync_at,
            ativo=item.ativo,
            criado_em=item.criado_em,
        )


# ── helpers puros ────────────────────────────────────────────────────────────


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
