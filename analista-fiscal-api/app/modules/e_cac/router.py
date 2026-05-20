"""Endpoints REST do monitor e-CAC (Sprint 6 PR2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.e_cac.repo import MensagensECacRepo
from app.modules.e_cac.schemas import (
    MensagemOut,
    Prioridade,
    SyncResultadoOut,
    TipoMensagem,
)
from app.modules.e_cac.service import ECacService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["e-cac"])


@router.post(
    "/{empresa_id}/e-cac/sync",
    response_model=SyncResultadoOut,
    summary="Sincronizar caixa postal e-CAC com SERPRO",
)
async def sync(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> SyncResultadoOut:
    serpro_client = getattr(request.app.state, "serpro_client", None)
    return await ECacService().sincronizar(
        session,
        ctx.tenant_id,
        empresa_id,
        serpro_client=serpro_client,
    )


@router.get(
    "/{empresa_id}/e-cac/mensagens",
    response_model=list[MensagemOut],
    summary="Listar mensagens e-CAC",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[MensagemOut]:
    rows = await MensagensECacRepo(session).listar(empresa_id)
    return [
        MensagemOut(
            id=m.id,
            empresa_id=m.empresa_id,
            assunto=m.assunto,
            recebida_em=m.recebida_em,
            lida_em=m.lida_em,
            tipo=TipoMensagem(m.tipo) if m.tipo else None,
            prioridade=Prioridade(m.prioridade) if m.prioridade else None,
            prazo_resposta=m.prazo_resposta,
            encaminhada_marketplace=m.encaminhada_marketplace,
        )
        for m in rows
    ]
