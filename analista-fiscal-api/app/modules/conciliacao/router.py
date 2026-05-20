"""Endpoints REST de conciliação banco × NF (Sprint 7 PR3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.conciliacao.repo import ConciliacaoRepo
from app.modules.conciliacao.schemas import (
    MatchOut,
    RunConciliacaoIn,
    RunConciliacaoOut,
    TipoMatch,
)
from app.modules.conciliacao.service import ConciliacaoService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["conciliacao"])


@router.post(
    "/{empresa_id}/conciliacao/run",
    response_model=RunConciliacaoOut,
    status_code=200,
    summary="Executa algoritmo de conciliação banco × NF",
    description=(
        "Varre transações bancárias CONFIRMED ainda não conciliadas e pontua "
        "contra NFs do mesmo período (±15 dias). Score ≥80 vira AUTO, 50-79 "
        "vira SUGERIDA. Re-execução é segura: UNIQUE em (transacao,documento) "
        "garante idempotência."
    ),
)
async def run(
    empresa_id: UUID,
    payload: RunConciliacaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RunConciliacaoOut:
    return await ConciliacaoService().run(session, ctx.tenant_id, empresa_id, payload)


@router.post(
    "/{empresa_id}/conciliacao/{match_id}/confirmar",
    response_model=MatchOut,
    summary="Confirma um match (AUTO ou SUGERIDA → MANUAL)",
)
async def confirmar(
    empresa_id: UUID,
    match_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> MatchOut:
    return await ConciliacaoService().confirmar(
        session, empresa_id, match_id, ctx.usuario_id
    )


@router.post(
    "/{empresa_id}/conciliacao/{match_id}/rejeitar",
    response_model=MatchOut,
    summary="Rejeita um match sugerido",
)
async def rejeitar(
    empresa_id: UUID,
    match_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> MatchOut:
    return await ConciliacaoService().rejeitar(
        session, empresa_id, match_id, ctx.usuario_id
    )


@router.get(
    "/{empresa_id}/conciliacao",
    response_model=list[MatchOut],
    summary="Lista matches da empresa, opcionalmente filtrados por tipo",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoMatch | None = Query(default=None),
) -> list[MatchOut]:
    tipo_str = tipo.value if tipo else None
    rows = await ConciliacaoRepo(session).listar(empresa_id, tipo=tipo_str)
    out: list[MatchOut] = []
    for match, transacao, documento in rows:
        breakdown_raw = match.score_breakdown_json or {}
        criterios = (
            breakdown_raw.get("criterios")
            if isinstance(breakdown_raw, dict)
            else None
        )
        out.append(
            MatchOut(
                id=match.id,
                transacao_id=match.transacao_id,
                documento_fiscal_id=match.documento_fiscal_id,
                confianca=match.confianca,
                tipo=TipoMatch(match.tipo),
                algoritmo_versao=match.algoritmo_versao,
                score_breakdown=criterios if isinstance(criterios, list) else [],
                criado_em=match.criado_em,
                confirmado_em=match.confirmado_em,
                rejeitado_em=match.rejeitado_em,
                transacao_valor=transacao.valor,
                transacao_data=transacao.data_transacao,
                documento_valor=documento.valor_total,
                documento_data=(
                    documento.emitida_em.date() if documento.emitida_em else None
                ),
            )
        )
    return out
