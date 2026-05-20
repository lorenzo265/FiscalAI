"""Endpoints REST — ICMS (Sprint 11 PR2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.icms.repo import ApuracaoIcmsRepo
from app.modules.icms.schemas import ApuracaoIcmsOut, ApurarIcmsMensalIn
from app.modules.icms.service import IcmsService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["icms"])


@router.post(
    "/{empresa_id}/icms/apurar",
    response_model=ApuracaoIcmsOut,
    status_code=201,
    summary="Apura ICMS mensal — débito × crédito + ajustes + saldo anterior",
    description=(
        "Aplica alíquota interna da UF da empresa (vinda da SCD "
        "``aliquota_icms_uf``). Saldo positivo é a recolher; saldo negativo "
        "vira credor a transportar para o mês seguinte (LC 87/1996). "
        "Idempotente por (empresa, competência)."
    ),
)
async def apurar_icms(
    empresa_id: UUID,
    payload: ApurarIcmsMensalIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoIcmsOut:
    apuracao = await IcmsService().apurar_mensal(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ApuracaoIcmsOut.from_apuracao(apuracao)


@router.get(
    "/{empresa_id}/icms/apuracoes",
    response_model=list[ApuracaoIcmsOut],
    summary="Lista apurações ICMS da empresa",
)
async def listar_icms(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    limite: int = 24,
) -> list[ApuracaoIcmsOut]:
    rows = await ApuracaoIcmsRepo(session).listar(empresa_id, limite=limite)
    return [ApuracaoIcmsOut.from_apuracao(r) for r in rows]
