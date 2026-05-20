"""Endpoints REST de transmissão PGDAS-D (Sprint 6 PR2)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.modules.pgdas.repo import TransmissoesPgdasRepo
from app.modules.pgdas.schemas import (
    TransmissaoOut,
    TransmissaoStatus,
    TransmitirPgdasIn,
    TransmitirPgdasOut,
)
from app.modules.pgdas.service import PgdasService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["pgdas"])

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def _parse_competencia(competencia: str) -> date:
    if not _COMPETENCIA_RE.match(competencia):
        raise HTTPException(
            status_code=422, detail="Competência deve estar no formato AAAA-MM"
        )
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


@router.post(
    "/{empresa_id}/apuracoes/das/{competencia}/transmitir",
    response_model=TransmitirPgdasOut,
    status_code=202,
    summary="Transmite PGDAS-D ao SERPRO",
    description=(
        "Transmite a declaração mensal SN (PGDAS-D) ao Portal do Simples "
        "Nacional via SERPRO. Requer apuração já calculada (Sprint 2). "
        "Use eh_retificadora=true para substituir transmissão prévia."
    ),
)
async def transmitir(
    empresa_id: UUID,
    competencia: str,
    payload: TransmitirPgdasIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> TransmitirPgdasOut:
    comp_date = _parse_competencia(competencia)
    serpro_client = getattr(request.app.state, "serpro_client", None)
    return await PgdasService().transmitir(
        session,
        ctx.tenant_id,
        empresa_id,
        comp_date,
        eh_retificadora=payload.eh_retificadora,
        serpro_client=serpro_client,
    )


@router.get(
    "/{empresa_id}/apuracoes/das/transmissoes",
    response_model=list[TransmissaoOut],
    summary="Lista transmissões PGDAS-D da empresa",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    competencia: str | None = None,
) -> list[TransmissaoOut]:
    comp_date = _parse_competencia(competencia) if competencia else None
    rows = await TransmissoesPgdasRepo(session).listar(empresa_id, competencia=comp_date)
    return [
        TransmissaoOut(
            id=r.id,
            apuracao_id=r.apuracao_id,
            competencia=r.competencia,
            status=TransmissaoStatus(r.status),
            tentativa=r.tentativa,
            eh_retificadora=r.eh_retificadora,
            protocolo=r.protocolo,
            criado_em=r.criado_em,
        )
        for r in rows
    ]
