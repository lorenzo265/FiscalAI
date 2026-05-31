"""Endpoints REST — Reforma Tributária (Sprint 14 PR3).

Quatro endpoints (todos sob ``/v1/empresas/{empresa_id}/reforma``):

  * ``GET  /simulacao``           — projeta CBS+IBS em 3 cenários.
  * ``GET  /aliquota-vigente``    — alíquota CBS/IBS para uma competência.
  * ``POST /recalcular-historico`` — backfill informacional do ano.
  * ``GET  /fase-atual``          — onde estamos no cronograma.

Todos os endpoints usam ``SessionDep`` (RLS multi-tenant). Cliente PME só
vê os documentos da própria empresa.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from app.modules.reforma.calcula_cbs_ibs import OBSERVACAO_ESTIMATIVA
from app.modules.reforma.schemas import (
    AliquotaCBSIBSOut,
    CargaAtualOut,
    CenarioOut,
    CenarioSimuladoOut,
    FaseAtualOut,
    FaseReformaOut,
    ImpactoFluxoCaixaOut,
    RecalcularHistoricoIn,
    RecalculoHistoricoOut,
    SimulacaoOut,
)
from app.modules.reforma.service import ReformaService
from app.shared.db.deps import SessionDep

router = APIRouter(prefix="/v1", tags=["reforma"])

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@router.get(
    "/empresas/{empresa_id}/reforma/simulacao",
    response_model=SimulacaoOut,
    summary="Simula impacto da Reforma (3 cenários — Sprint 14)",
)
async def simular_impacto(
    empresa_id: UUID,
    session: SessionDep,
    ano_alvo: int = Query(default=2033, ge=2026, le=2099),
) -> SimulacaoOut:
    resultado = await ReformaService(session).simular_impacto(
        empresa_id, ano_alvo=ano_alvo
    )
    return SimulacaoOut(
        empresa_id=resultado.empresa_id,
        periodo_inicio=resultado.periodo_base[0],
        periodo_fim=resultado.periodo_base[1],
        fase_atual=FaseReformaOut(resultado.fase_atual.value),
        receita_anualizada=resultado.receita_anualizada,
        carga_atual=CargaAtualOut(
            pis=resultado.carga_atual.pis,
            cofins=resultado.carga_atual.cofins,
            icms=resultado.carga_atual.icms,
            iss=resultado.carga_atual.iss,
            total=resultado.carga_atual.total,
        ),
        cenarios=[
            CenarioSimuladoOut(
                cenario=CenarioOut(c.cenario.value),
                aliquota_total=c.aliquota_total,
                cbs_projetada=c.cbs_projetada,
                ibs_projetada=c.ibs_projetada,
                total_projetado=c.total_projetado,
                delta_absoluto=c.delta_absoluto,
                delta_percentual=c.delta_percentual,
            )
            for c in resultado.cenarios
        ],
        impacto_fluxo_caixa_2027=ImpactoFluxoCaixaOut(
            media_icms_mensal=resultado.impacto_fluxo_caixa_2027.media_icms_mensal,
            prazo_medio_recolhimento_dias=(
                resultado.impacto_fluxo_caixa_2027.prazo_medio_recolhimento_dias
            ),
            capital_giro_perdido=(
                resultado.impacto_fluxo_caixa_2027.capital_giro_perdido
            ),
        ),
        observacao_estimativa=resultado.observacao_estimativa,
        fontes_norma=resultado.fontes_norma,
        algoritmo_versao=resultado.algoritmo_versao,
    )


@router.get(
    "/empresas/{empresa_id}/reforma/aliquota-vigente",
    response_model=AliquotaCBSIBSOut,
    summary="Alíquota CBS/IBS vigente para uma competência",
)
async def aliquota_vigente(
    empresa_id: UUID,
    session: SessionDep,
    competencia: date | None = Query(default=None),
) -> AliquotaCBSIBSOut:
    if competencia is None:
        competencia = datetime.now(_TZ_BR).date()
    aliquota = await ReformaService(session).aliquota_vigente(
        competencia, empresa_id=empresa_id
    )
    return AliquotaCBSIBSOut(
        fase=FaseReformaOut(aliquota.fase.value),
        aliquota_cbs=aliquota.aliquota_cbs,
        aliquota_ibs=aliquota.aliquota_ibs,
        valid_from=aliquota.valid_from,
        valid_to=aliquota.valid_to,
        fonte_norma=aliquota.fonte_norma,
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
        algoritmo_versao=aliquota.algoritmo_versao,
    )


@router.post(
    "/empresas/{empresa_id}/reforma/recalcular-historico",
    response_model=RecalculoHistoricoOut,
    summary="Backfill CBS/IBS informacional para documentos do ano",
)
async def recalcular_historico(
    empresa_id: UUID,
    payload: RecalcularHistoricoIn,
    session: SessionDep,
) -> RecalculoHistoricoOut:
    resultado = await ReformaService(session).recalcular_historico_documentos(
        empresa_id, ano=payload.ano, forcar=payload.forcar
    )
    await session.commit()
    return RecalculoHistoricoOut(
        ano=resultado.ano,
        atualizados=resultado.atualizados,
        ignorados=resultado.ignorados,
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
    )


@router.get(
    "/empresas/{empresa_id}/reforma/fase-atual",
    response_model=FaseAtualOut,
    summary="Fase atual da Reforma (informativo)",
)
async def fase_atual(
    empresa_id: UUID,  # noqa: ARG001 — empresa-aware para RLS uniforme
    session: SessionDep,
    competencia: date | None = Query(default=None),
) -> FaseAtualOut:
    if competencia is None:
        competencia = datetime.now(_TZ_BR).date()
    fase_enum = ReformaService(session).fase_atual(competencia)
    fontes: dict[str, str] = {
        "teste_2026": "LC 214/2025 art. 348 §3º",
        "transicao_2027_2032": "LC 214/2025 art. 349",
        "regime_pleno_2033": "LC 214/2025 art. 156-A §1º",
    }
    return FaseAtualOut(
        fase=FaseReformaOut(fase_enum.value),
        competencia=competencia,
        observacao_estimativa=OBSERVACAO_ESTIMATIVA,
        fonte_norma=fontes[fase_enum.value],
    )
