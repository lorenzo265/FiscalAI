"""Endpoints REST de certidões (Sprint 6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.certidoes.repo import CertidoesRepo
from app.modules.certidoes.schemas import (
    CertidaoOut,
    CertidaoStatus,
    CertidaoTipo,
    EmitirCertidaoOut,
)
from app.modules.certidoes.service import CertidoesService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["certidoes"])


@router.post(
    "/{empresa_id}/certidoes/{tipo}",
    response_model=EmitirCertidaoOut,
    status_code=202,
    summary="Emitir certidão fiscal (CND/CRF/CNDT)",
    description=(
        "Solicita a emissão da certidão indicada. CND é emitida via SERPRO "
        "Integra Contador. CRF e CNDT registram emissão como 'processando' "
        "(integração automática chega no PR3 da Sprint 6)."
    ),
)
async def emitir(
    empresa_id: UUID,
    tipo: CertidaoTipo,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> EmitirCertidaoOut:
    serpro_client = getattr(request.app.state, "serpro_client", None)
    service = CertidoesService()
    return await service.emitir(
        session,
        ctx.tenant_id,
        empresa_id,
        tipo,
        serpro_client=serpro_client,
    )


@router.get(
    "/{empresa_id}/certidoes",
    response_model=list[CertidaoOut],
    summary="Listar certidões emitidas",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[CertidaoOut]:
    certidoes = await CertidoesRepo(session).listar(empresa_id)
    return [
        CertidaoOut(
            id=c.id,
            empresa_id=c.empresa_id,
            tipo=CertidaoTipo(c.tipo),
            numero=c.numero,
            status=CertidaoStatus(c.status),
            emitida_em=c.emitida_em,
            valid_until=c.valid_until,
            pdf_storage_key=c.pdf_storage_key,
        )
        for c in certidoes
    ]
