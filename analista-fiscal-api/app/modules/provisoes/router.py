"""Endpoints REST provisões trabalhistas (Sprint 8 PR2)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.modules.provisoes.repo import ProvisoesRepo
from app.modules.provisoes.schemas import (
    GerarProvisaoIn,
    GerarProvisaoOut,
    ProvisaoMensalOut,
    TipoProvisao,
)
from app.modules.provisoes.service import ProvisoesService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["provisoes"])

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def _parse_competencia(competencia: str) -> date:
    if not _COMPETENCIA_RE.match(competencia):
        raise HTTPException(
            status_code=422, detail="Competência deve estar no formato AAAA-MM"
        )
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


@router.post(
    "/{empresa_id}/provisoes/{competencia}",
    response_model=GerarProvisaoOut,
    status_code=200,
    summary="Gera lote mensal de provisões trabalhistas",
    description=(
        "Calcula férias (1/12 + 1/3), 13º (1/12), INSS patronal 20% sobre "
        "ambos (zero para SN/MEI — LC 123/2006 art. 13) e FGTS 8% sobre "
        "ambos. Persiste como linhas agregadas por empresa. Idempotente "
        "via UNIQUE parcial."
    ),
)
async def gerar_provisao(
    empresa_id: UUID,
    competencia: str,
    payload: GerarProvisaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> GerarProvisaoOut:
    comp_date = _parse_competencia(competencia)
    return await ProvisoesService().gerar_provisao_mensal(
        session, ctx.tenant_id, empresa_id, comp_date, payload
    )


@router.get(
    "/{empresa_id}/provisoes",
    response_model=list[ProvisaoMensalOut],
    summary="Lista provisões mensais da empresa",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    competencia: str | None = Query(default=None),
    tipo: TipoProvisao | None = Query(default=None),
) -> list[ProvisaoMensalOut]:
    comp_date = _parse_competencia(competencia) if competencia else None
    tipo_str = tipo.value if tipo else None
    rows = await ProvisoesRepo(session).listar(
        empresa_id, competencia=comp_date, tipo=tipo_str
    )
    return [
        ProvisaoMensalOut(
            id=r.id,
            empresa_id=r.empresa_id,
            competencia=r.competencia,
            tipo=TipoProvisao(r.tipo),
            base_calculo=r.base_calculo,
            aliquota=r.aliquota,
            valor_provisao=r.valor_provisao,
            funcionario_id=r.funcionario_id,
        )
        for r in rows
    ]
