"""Endpoints REST — EFD-Reinf (Sprint 11 PR2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.reinf.repo import EfdReinfRepo
from app.modules.reinf.schemas import (
    EventoReinfOut,
    RegistrarRetencaoIn,
    TipoEventoReinfIn,
)
from app.modules.reinf.service import ReinfService
from app.shared.competencia import parse_competencia_mensal
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["efd_reinf"])


@router.post(
    "/{empresa_id}/reinf/retencoes-pj",
    response_model=EventoReinfOut,
    status_code=201,
    summary="Registra retenção PJ→PJ (R-4020) com cálculo IR + CSRF",
    description=(
        "Calcula IRRF 1,5% (Lei 7.713/1988) + CSRF 4,65% (Lei 10.833/2003) "
        "conforme regime do TOMADOR (empresa atual). Tomador em SN/MEI é "
        "dispensado de toda retenção (LC 123/2006 art. 13 §13). Dispensa "
        "automática de CSRF quando total < R$10 (IN RFB 459/2004). "
        "Idempotente por (empresa, R-4020, referencia_id)."
    ),
)
async def registrar_retencao_pj(
    empresa_id: UUID,
    payload: RegistrarRetencaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoReinfOut:
    evento = await ReinfService().registrar_retencao_r4020(
        session, ctx.tenant_id, empresa_id, payload
    )
    return EventoReinfOut.model_validate(evento)


@router.get(
    "/{empresa_id}/reinf/eventos",
    response_model=list[EventoReinfOut],
    summary="Lista eventos EFD-Reinf da empresa",
)
async def listar_eventos_reinf(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoEventoReinfIn | None = None,
    periodo: str | None = None,
    limite: int = 100,
) -> list[EventoReinfOut]:
    tipo_str = tipo.value if tipo else None
    periodo_date = parse_competencia_mensal(periodo) if periodo else None
    rows = await EfdReinfRepo(session).listar_empresa(
        empresa_id,
        tipo_evento=tipo_str,
        periodo=periodo_date,
        limite=limite,
    )
    return [EventoReinfOut.model_validate(r) for r in rows]
