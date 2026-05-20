"""Endpoints REST — monitor cadastral (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.monitor_cadastral.repo import (
    StatusRfbRepo,
    StatusSintegraRepo,
)
from app.modules.monitor_cadastral.schemas import (
    RegistrarStatusRfbIn,
    RegistrarStatusSintegraIn,
    StatusRfbOut,
    StatusSintegraOut,
)
from app.modules.monitor_cadastral.service import MonitorCadastralService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["monitor_cadastral"])


# ── RFB ─────────────────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/monitor/rfb",
    response_model=StatusRfbOut,
    status_code=201,
    summary="Registra snapshot da situação cadastral CNPJ (RFB)",
)
async def registrar_rfb(
    empresa_id: UUID,
    payload: RegistrarStatusRfbIn,
    ctx: TenantDep,
    session: SessionDep,
) -> StatusRfbOut:
    status = await MonitorCadastralService().registrar_rfb(
        session, ctx.tenant_id, empresa_id, payload
    )
    return StatusRfbOut.model_validate(status)


@router.get(
    "/{empresa_id}/monitor/rfb/atual",
    response_model=StatusRfbOut,
    summary="Snapshot RFB mais recente",
)
async def rfb_atual(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> StatusRfbOut:
    status = await StatusRfbRepo(session).mais_recente(empresa_id)
    if status is None:
        raise HTTPException(
            status_code=404, detail="Sem snapshot RFB para a empresa"
        )
    return StatusRfbOut.model_validate(status)


@router.get(
    "/{empresa_id}/monitor/rfb/historico",
    response_model=list[StatusRfbOut],
    summary="Histórico de snapshots RFB (mais novo primeiro)",
)
async def rfb_historico(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    limite: int = 50,
) -> list[StatusRfbOut]:
    rows = await StatusRfbRepo(session).historico(empresa_id, limite=limite)
    return [StatusRfbOut.model_validate(r) for r in rows]


# ── Sintegra ────────────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/monitor/sintegra",
    response_model=StatusSintegraOut,
    status_code=201,
    summary="Registra snapshot Sintegra (IE estadual)",
)
async def registrar_sintegra(
    empresa_id: UUID,
    payload: RegistrarStatusSintegraIn,
    ctx: TenantDep,
    session: SessionDep,
) -> StatusSintegraOut:
    status = await MonitorCadastralService().registrar_sintegra(
        session, ctx.tenant_id, empresa_id, payload
    )
    return StatusSintegraOut.model_validate(status)


@router.get(
    "/{empresa_id}/monitor/sintegra/{uf}/atual",
    response_model=StatusSintegraOut,
    summary="Snapshot Sintegra mais recente da UF",
)
async def sintegra_atual(
    empresa_id: UUID,
    uf: str,
    ctx: TenantDep,
    session: SessionDep,
) -> StatusSintegraOut:
    status = await StatusSintegraRepo(session).mais_recente_por_uf(
        empresa_id, uf.upper()
    )
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sem snapshot Sintegra para {uf} nesta empresa",
        )
    return StatusSintegraOut.model_validate(status)


@router.get(
    "/{empresa_id}/monitor/sintegra/historico",
    response_model=list[StatusSintegraOut],
    summary="Histórico Sintegra (todas as UFs ou filtrada)",
)
async def sintegra_historico(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    uf: str | None = None,
    limite: int = 50,
) -> list[StatusSintegraOut]:
    rows = await StatusSintegraRepo(session).historico(
        empresa_id, uf=uf.upper() if uf else None, limite=limite,
    )
    return [StatusSintegraOut.model_validate(r) for r in rows]
