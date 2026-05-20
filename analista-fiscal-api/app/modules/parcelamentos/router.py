"""Endpoints REST — parcelamentos (Sprint 11 PR3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.parcelamentos.repo import ParcelamentoRepo
from app.modules.parcelamentos.schemas import (
    CancelarParcelamentoIn,
    CriarParcelamentoIn,
    ParcelaOut,
    ParcelamentoOut,
    StatusParcelamentoIn,
)
from app.modules.parcelamentos.service import ParcelamentoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import ParcelamentoNaoEncontrado

router = APIRouter(prefix="/v1/empresas", tags=["parcelamentos"])


@router.post(
    "/{empresa_id}/parcelamentos",
    response_model=ParcelamentoOut,
    status_code=201,
    summary="Cria parcelamento + cronograma de parcelas",
    description=(
        "Gera cronograma do parcelamento ordinário (Lei 10.522/2002). "
        "Parcela mínima R$200 (PJ) / R$100 (PF). Até 60 parcelas. PERT, "
        "PERT2 e demais modalidades ficam para sprint futura — apenas o "
        "tipo é persistido por enquanto."
    ),
)
async def criar_parcelamento(
    empresa_id: UUID,
    payload: CriarParcelamentoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ParcelamentoOut:
    parcelamento = await ParcelamentoService().criar(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ParcelamentoOut.model_validate(parcelamento)


@router.get(
    "/{empresa_id}/parcelamentos",
    response_model=list[ParcelamentoOut],
    summary="Lista parcelamentos da empresa",
)
async def listar_parcelamentos(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    status: StatusParcelamentoIn | None = None,
) -> list[ParcelamentoOut]:
    status_str = status.value if status else None
    rows = await ParcelamentoRepo(session).listar(empresa_id, status=status_str)
    return [ParcelamentoOut.model_validate(r) for r in rows]


@router.get(
    "/{empresa_id}/parcelamentos/{parcelamento_id}/parcelas",
    response_model=list[ParcelaOut],
    summary="Lista parcelas de um parcelamento",
)
async def listar_parcelas(
    empresa_id: UUID,
    parcelamento_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[ParcelaOut]:
    repo = ParcelamentoRepo(session)
    p = await repo.por_id(parcelamento_id)
    if p is None or p.empresa_id != empresa_id:
        raise ParcelamentoNaoEncontrado(
            f"Parcelamento {parcelamento_id} não encontrado nesta empresa"
        )
    rows = await repo.listar_parcelas(parcelamento_id)
    return [ParcelaOut.model_validate(r) for r in rows]


@router.post(
    "/{empresa_id}/parcelamentos/{parcelamento_id}/cancelar",
    response_model=ParcelamentoOut,
    summary="Cancela parcelamento ativo",
)
async def cancelar_parcelamento(
    empresa_id: UUID,
    parcelamento_id: UUID,
    payload: CancelarParcelamentoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ParcelamentoOut:
    parcelamento = await ParcelamentoService().cancelar(
        session, empresa_id, parcelamento_id, payload
    )
    return ParcelamentoOut.model_validate(parcelamento)
