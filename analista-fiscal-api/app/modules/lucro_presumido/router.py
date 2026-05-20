"""Endpoints REST — Lucro Presumido (Sprint 11 PR1)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.lucro_presumido.repo import ApuracaoLpRepo
from app.modules.lucro_presumido.schemas import (
    ApuracaoLpOut,
    ApurarIrpjCsllTrimestralIn,
    ApurarPisCofinsMensalIn,
    PresuncaoResolvidaOut,
)
from app.modules.lucro_presumido.service import LucroPresumidoService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["lucro_presumido"])

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def _parse_competencia(competencia: str) -> date:
    if not _COMPETENCIA_RE.match(competencia):
        raise HTTPException(
            status_code=422, detail="Competência deve estar no formato AAAA-MM"
        )
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


@router.post(
    "/{empresa_id}/lp/irpj",
    response_model=ApuracaoLpOut,
    status_code=201,
    summary="Apura IRPJ trimestral (Lucro Presumido)",
    description=(
        "Resolve presunção pelo CNAE da empresa, calcula IRPJ 15% sobre base "
        "presumida + adicional 10% sobre o que exceder R$20.000 × meses. "
        "Persiste em ``apuracao_fiscal``. Idempotente por (empresa, trimestre)."
    ),
)
async def apurar_irpj(
    empresa_id: UUID,
    payload: ApurarIrpjCsllTrimestralIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoLpOut:
    apuracao = await LucroPresumidoService().apurar_irpj_trimestral(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ApuracaoLpOut.from_apuracao(apuracao)


@router.post(
    "/{empresa_id}/lp/csll",
    response_model=ApuracaoLpOut,
    status_code=201,
    summary="Apura CSLL trimestral (Lucro Presumido)",
)
async def apurar_csll(
    empresa_id: UUID,
    payload: ApurarIrpjCsllTrimestralIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoLpOut:
    apuracao = await LucroPresumidoService().apurar_csll_trimestral(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ApuracaoLpOut.from_apuracao(apuracao)


@router.post(
    "/{empresa_id}/lp/pis",
    response_model=ApuracaoLpOut,
    status_code=201,
    summary="Apura PIS cumulativo mensal (Lucro Presumido)",
)
async def apurar_pis(
    empresa_id: UUID,
    payload: ApurarPisCofinsMensalIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoLpOut:
    apuracao = await LucroPresumidoService().apurar_pis_mensal(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ApuracaoLpOut.from_apuracao(apuracao)


@router.post(
    "/{empresa_id}/lp/cofins",
    response_model=ApuracaoLpOut,
    status_code=201,
    summary="Apura Cofins cumulativo mensal (Lucro Presumido)",
)
async def apurar_cofins(
    empresa_id: UUID,
    payload: ApurarPisCofinsMensalIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoLpOut:
    apuracao = await LucroPresumidoService().apurar_cofins_mensal(
        session, ctx.tenant_id, empresa_id, payload
    )
    return ApuracaoLpOut.from_apuracao(apuracao)


@router.get(
    "/{empresa_id}/lp/apuracoes",
    response_model=list[ApuracaoLpOut],
    summary="Lista apurações LP da empresa (IRPJ/CSLL/PIS/Cofins)",
)
async def listar_apuracoes_lp(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: str | None = None,
    limite: int = 24,
) -> list[ApuracaoLpOut]:
    rows = await ApuracaoLpRepo(session).listar(empresa_id, tipo=tipo, limite=limite)
    return [ApuracaoLpOut.from_apuracao(r) for r in rows]


@router.get(
    "/{empresa_id}/lp/presuncao",
    response_model=PresuncaoResolvidaOut,
    summary="Diagnóstico: qual grupo de presunção o sistema escolheu",
    description=(
        "Útil pro frontend mostrar 'Sua empresa é tributada como X' antes da "
        "primeira apuração. Use ``em=AAAA-MM`` (default: mês atual)."
    ),
)
async def resolver_presuncao(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    em: str | None = None,
) -> PresuncaoResolvidaOut:
    em_date = _parse_competencia(em) if em else date.today().replace(day=1)
    resolvida = await LucroPresumidoService().resolver_presuncao(
        session, empresa_id, em_date
    )
    return PresuncaoResolvidaOut(
        grupo_atividade=resolvida.grupo_atividade,
        percentual_irpj=resolvida.percentual_irpj,
        percentual_csll=resolvida.percentual_csll,
        cnae_pattern=resolvida.cnae_pattern,
        prioridade=resolvida.prioridade,
        fonte=resolvida.fonte,
    )
