"""Endpoints REST -- LGPD direito do titular (Marco 3).

  * ``GET  /v1/lgpd/exportar`` -- portabilidade (LGPD art. 18, II): reune todos
    os dados do tenant autenticado num JSON estruturado e registra a
    solicitacao na trilha de auditoria.
  * ``POST /v1/lgpd/excluir`` -- esquecimento por anonimizacao (LGPD art. 18,
    VI): anonimiza a PII de pessoas naturais respeitando a imutabilidade fiscal
    (principio 8.2) e a guarda de 5 anos. Exige confirmacao explicita.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.modules.lgpd.schemas import (
    ConfirmacaoExclusaoIn,
    ExclusaoLgpdOut,
    ExportacaoLgpdOut,
)
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


@router.post(
    "/excluir",
    response_model=ExclusaoLgpdOut,
    summary="Esquecimento por anonimizacao (LGPD art. 18) -- preserva fatos fiscais",
)
async def excluir(
    payload: ConfirmacaoExclusaoIn, ctx: TenantDep, session: SessionDep
) -> ExclusaoLgpdOut:
    # ``payload`` so valida a confirmacao (confirmar=true); sem ele -> 422.
    _ = payload
    resultado = await _service.excluir(
        session, tenant_id=ctx.tenant_id, usuario_id=ctx.usuario_id
    )
    return ExclusaoLgpdOut(**resultado)
