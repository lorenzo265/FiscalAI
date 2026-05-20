"""Service — monitor cadastral RFB + Sintegra (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.empresa.repo import EmpresaRepo
from app.modules.monitor_cadastral.repo import (
    StatusRfbRepo,
    StatusSintegraRepo,
)
from app.modules.monitor_cadastral.schemas import (
    RegistrarStatusRfbIn,
    RegistrarStatusSintegraIn,
)
from app.shared.db.models import StatusCadastralRfb, StatusSintegra
from app.shared.exceptions import EmpresaNaoEncontrada

log = structlog.get_logger(__name__)


class MonitorCadastralService:
    async def registrar_rfb(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: RegistrarStatusRfbIn,
    ) -> StatusCadastralRfb:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        status = StatusCadastralRfb(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            consultado_em=payload.consultado_em,
            situacao_cadastral=payload.situacao_cadastral.value,
            data_situacao=payload.data_situacao,
            motivo_situacao=payload.motivo_situacao,
            restricoes=payload.restricoes,
            regime_apuracao=payload.regime_apuracao,
            snapshot=payload.snapshot,
        )
        await StatusRfbRepo(session).criar(status)
        await session.commit()
        await session.refresh(status)
        log.info(
            "monitor.rfb.snapshot",
            empresa_id=str(empresa_id),
            situacao=payload.situacao_cadastral.value,
        )
        return status

    async def registrar_sintegra(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: RegistrarStatusSintegraIn,
    ) -> StatusSintegra:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        status = StatusSintegra(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            uf=payload.uf,
            inscricao_estadual=payload.inscricao_estadual,
            consultado_em=payload.consultado_em,
            situacao=payload.situacao.value,
            data_situacao=payload.data_situacao,
            regime_apuracao_ie=payload.regime_apuracao_ie,
            snapshot=payload.snapshot,
        )
        await StatusSintegraRepo(session).criar(status)
        await session.commit()
        await session.refresh(status)
        log.info(
            "monitor.sintegra.snapshot",
            empresa_id=str(empresa_id),
            uf=payload.uf,
            situacao=payload.situacao.value,
        )
        return status
