"""Endpoints REST -- LGPD direito do titular (Marco 3).

  * ``GET /v1/lgpd/exportar`` -- portabilidade (LGPD art. 18, II): reune todos
    os dados do tenant autenticado num JSON estruturado e registra a
    solicitacao na trilha de auditoria.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.lgpd.schemas import ExportacaoLgpdOut
from app.modules.lgpd.service import LgpdService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/lgpd", tags=["lgpd"])
_service = LgpdService()


@router.get(
    "/exportar",
    response_model=ExportacaoLgpdOut,
    summary="Exporta todos os dados do tenant (portabilidade, LGPD art. 18)",
)
async def exportar(ctx: TenantDep, session: SessionDep) -> ExportacaoLgpdOut:
    resultado = await _service.exportar(
        session, tenant_id=ctx.tenant_id, usuario_id=ctx.usuario_id
    )
    return ExportacaoLgpdOut(**resultado)
