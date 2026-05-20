from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.notas.schemas import EmitirNfseIn, EmitirNfseOut, NfseStatusOut
from app.modules.notas.service import NotasService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import EmpresaNaoEncontrada, FocusNfeErro, FocusNfeTimeout

router = APIRouter(prefix="/v1/empresas", tags=["notas"])


@router.post(
    "/{empresa_id}/notas/nfse",
    response_model=EmitirNfseOut,
    status_code=202,
    summary="Emitir NFS-e via Focus NFe",
    description=(
        "Solicita a emissão de uma Nota Fiscal de Serviço Eletrônica (NFS-e) pela "
        "Focus NFe. A emissão é assíncrona — o status inicial é 'processando'. "
        "Consulte o endpoint GET /notas/nfse/{ref} para acompanhar a autorização."
    ),
)
async def emitir_nfse(
    empresa_id: UUID,
    payload: EmitirNfseIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> EmitirNfseOut:
    focus_client = getattr(request.app.state, "focus_client", None)
    if focus_client is None:
        raise FocusNfeErro("FocusNfeClient não disponível — verifique inicialização")
    service = NotasService()
    try:
        return await service.emitir_nfse(
            session,
            ctx.tenant_id,
            empresa_id,
            payload,
            focus_client=focus_client,
        )
    except (EmpresaNaoEncontrada, FocusNfeErro, FocusNfeTimeout):
        raise


@router.get(
    "/{empresa_id}/notas/nfse/{focus_ref}",
    response_model=NfseStatusOut,
    summary="Consultar status de NFS-e",
)
async def status_nfse(
    empresa_id: UUID,
    focus_ref: str,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> NfseStatusOut:
    focus_client = getattr(request.app.state, "focus_client", None)
    if focus_client is None:
        raise FocusNfeErro("FocusNfeClient não disponível — verifique inicialização")
    service = NotasService()
    return await service.consultar_status(
        session,
        empresa_id,
        focus_ref,
        focus_client=focus_client,
    )
