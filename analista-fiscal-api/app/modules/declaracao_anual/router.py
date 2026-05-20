"""Endpoints REST das declarações anuais (Sprint 6 PR3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.declaracao_anual.repo import DeclaracaoAnualRepo
from app.modules.declaracao_anual.schemas import (
    DeclaracaoAnualOut,
    DeclaracaoStatus,
    GerarDasnSimeiIn,
    GerarDefisIn,
    TipoDeclaracao,
    TransmitirOut,
)
from app.modules.declaracao_anual.service import DeclaracaoAnualService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["declaracao-anual"])


@router.post(
    "/{empresa_id}/declaracoes/defis",
    response_model=DeclaracaoAnualOut,
    status_code=201,
    summary="Gera DEFIS (declaração anual SN)",
    description=(
        "Consolida as 12 apurações DAS do ano e dados socioeconômicos "
        "(sócios, lucro contábil, estoque, despesas) para gerar a DEFIS. "
        "A transmissão ao SERPRO é feita em endpoint separado para que o "
        "cliente revise o payload antes (§8.12)."
    ),
)
async def gerar_defis(
    empresa_id: UUID,
    payload: GerarDefisIn,
    ctx: TenantDep,
    session: SessionDep,
) -> DeclaracaoAnualOut:
    return await DeclaracaoAnualService().gerar_defis(
        session, ctx.tenant_id, empresa_id, payload
    )


@router.post(
    "/{empresa_id}/declaracoes/dasn-simei",
    response_model=DeclaracaoAnualOut,
    status_code=201,
    summary="Gera DASN-SIMEI (declaração anual MEI)",
)
async def gerar_dasn_simei(
    empresa_id: UUID,
    payload: GerarDasnSimeiIn,
    ctx: TenantDep,
    session: SessionDep,
) -> DeclaracaoAnualOut:
    return await DeclaracaoAnualService().gerar_dasn_simei(
        session, ctx.tenant_id, empresa_id, payload
    )


@router.post(
    "/{empresa_id}/declaracoes/{declaracao_id}/transmitir",
    response_model=TransmitirOut,
    status_code=202,
    summary="Transmite DEFIS ou DASN-SIMEI gerada",
)
async def transmitir(
    empresa_id: UUID,
    declaracao_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> TransmitirOut:
    serpro_client = getattr(request.app.state, "serpro_client", None)
    return await DeclaracaoAnualService().transmitir(
        session, empresa_id, declaracao_id, serpro_client=serpro_client
    )


@router.get(
    "/{empresa_id}/declaracoes",
    response_model=list[DeclaracaoAnualOut],
    summary="Lista declarações anuais da empresa",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[DeclaracaoAnualOut]:
    rows = await DeclaracaoAnualRepo(session).listar(empresa_id)
    return [
        DeclaracaoAnualOut(
            id=r.id,
            empresa_id=r.empresa_id,
            tipo=TipoDeclaracao(r.tipo),
            ano_base=r.ano_base,
            status=DeclaracaoStatus(r.status),
            protocolo=r.protocolo,
            transmitida_em=r.transmitida_em,
        )
        for r in rows
    ]
