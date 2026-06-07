"""Endpoints REST — Lucro Presumido (Sprint 11 PR1 + Sprint 20 PR1 + PR2)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.lucro_presumido.repo import ApuracaoLpRepo
from app.modules.lucro_presumido.schemas import (
    ApuracaoLpOut,
    ApurarIrpjCsllTrimestralIn,
    ApurarPisCofinsMensalIn,
    ChecklistTrimestreOut,
    GuiaPagamentoOut,
    MarcarPagoIn,
    PresuncaoResolvidaOut,
    SaudeLpOut,
)
from app.modules.lucro_presumido.service import LpChecklistService, LucroPresumidoService
from app.shared.competencia import parse_competencia_mensal
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["lucro_presumido"])


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
    em_date = parse_competencia_mensal(em) if em else date.today().replace(day=1)
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


# ── DARF — Sprint 20 PR1 ──────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/lp/irpj/{ano}/{trimestre}/darf",
    response_model=GuiaPagamentoOut,
    status_code=201,
    summary="Gera DARF IRPJ trimestral (código 2089)",
    description=(
        "Requer apuração IRPJ do trimestre já realizada. "
        "Idempotente: segundo POST retorna 409 DarfLpJaGerada."
    ),
)
async def gerar_darf_irpj(
    empresa_id: UUID,
    ano: int,
    trimestre: int,
    ctx: TenantDep,
    session: SessionDep,
) -> GuiaPagamentoOut:
    guia = await LucroPresumidoService().gerar_darf_irpj(
        session, ctx.tenant_id, empresa_id, ano, trimestre
    )
    await session.commit()
    return GuiaPagamentoOut.from_guia(guia)


@router.post(
    "/{empresa_id}/lp/csll/{ano}/{trimestre}/darf",
    response_model=GuiaPagamentoOut,
    status_code=201,
    summary="Gera DARF CSLL trimestral (código 2372)",
)
async def gerar_darf_csll(
    empresa_id: UUID,
    ano: int,
    trimestre: int,
    ctx: TenantDep,
    session: SessionDep,
) -> GuiaPagamentoOut:
    guia = await LucroPresumidoService().gerar_darf_csll(
        session, ctx.tenant_id, empresa_id, ano, trimestre
    )
    await session.commit()
    return GuiaPagamentoOut.from_guia(guia)


@router.post(
    "/{empresa_id}/lp/pis/{competencia}/darf",
    response_model=GuiaPagamentoOut,
    status_code=201,
    summary="Gera DARF PIS cumulativo mensal (código 8109)",
)
async def gerar_darf_pis(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> GuiaPagamentoOut:
    comp_date = parse_competencia_mensal(competencia)
    guia = await LucroPresumidoService().gerar_darf_pis(
        session, ctx.tenant_id, empresa_id, comp_date
    )
    await session.commit()
    return GuiaPagamentoOut.from_guia(guia)


@router.post(
    "/{empresa_id}/lp/cofins/{competencia}/darf",
    response_model=GuiaPagamentoOut,
    status_code=201,
    summary="Gera DARF Cofins cumulativo mensal (código 2172)",
)
async def gerar_darf_cofins(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> GuiaPagamentoOut:
    comp_date = parse_competencia_mensal(competencia)
    guia = await LucroPresumidoService().gerar_darf_cofins(
        session, ctx.tenant_id, empresa_id, comp_date
    )
    await session.commit()
    return GuiaPagamentoOut.from_guia(guia)


@router.get(
    "/{empresa_id}/lp/guias",
    response_model=list[GuiaPagamentoOut],
    summary="Lista guias de pagamento LP da empresa",
)
async def listar_guias(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    status: str | None = Query(default=None, description="Filtrar por status: a_pagar, pago, cancelado"),
    limite: int = Query(default=50, ge=1, le=200),
) -> list[GuiaPagamentoOut]:
    guias = await LucroPresumidoService().listar_guias(
        session, empresa_id, status=status, limite=limite
    )
    return [GuiaPagamentoOut.from_guia(g) for g in guias]


@router.post(
    "/{empresa_id}/lp/guias/{guia_id}/marcar-pago",
    response_model=GuiaPagamentoOut,
    summary="Marca guia de pagamento como paga",
)
async def marcar_guia_pago(
    empresa_id: UUID,
    guia_id: UUID,
    payload: MarcarPagoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> GuiaPagamentoOut:
    guia = await LucroPresumidoService().marcar_pago(
        session, empresa_id, guia_id, payload.pago_em
    )
    await session.commit()
    return GuiaPagamentoOut.from_guia(guia)


# ── Checklist LP — Sprint 20 PR2 ──────────────────────────────────────────────


@router.get(
    "/{empresa_id}/lp/trimestre/{ano}/{trimestre}/checklist",
    response_model=ChecklistTrimestreOut,
    summary="Checklist de obrigações LP do trimestre",
    description=(
        "Retorna o status de cada obrigação LP do trimestre: apurações IRPJ/CSLL "
        "trimestrais, PIS/Cofins mensais (×3), e as respectivas DARFs. "
        "Itens sem data de vencimento passada ficam como 'pendente'; "
        "após o vencimento sem pagamento → 'atrasado'."
    ),
)
async def checklist_trimestre(
    empresa_id: UUID,
    ano: int,
    trimestre: int,
    ctx: TenantDep,
    session: SessionDep,
) -> ChecklistTrimestreOut:
    c = await LpChecklistService().checklist_trimestre(
        session, empresa_id, ano, trimestre
    )
    return ChecklistTrimestreOut.from_checklist(c)


@router.post(
    "/{empresa_id}/lp/trimestre/{ano}/{trimestre}/fechar",
    response_model=ChecklistTrimestreOut,
    summary="Fecha trimestre LP (valida que tudo está concluído)",
    description=(
        "Verifica que todos os itens do checklist estão 'ok'. "
        "Retorna 409 ChecklistLpNaoConcluido se há pendentes ou atrasados."
    ),
)
async def fechar_trimestre(
    empresa_id: UUID,
    ano: int,
    trimestre: int,
    ctx: TenantDep,
    session: SessionDep,
) -> ChecklistTrimestreOut:
    c = await LpChecklistService().fechar_trimestre(
        session, empresa_id, ano, trimestre
    )
    return ChecklistTrimestreOut.from_checklist(c)


@router.get(
    "/{empresa_id}/lp/saude",
    response_model=SaudeLpOut,
    summary="Health score LP — últimos 4 trimestres encerrados",
    description=(
        "Agrega checklist dos últimos 4 trimestres encerrados em um score 0-100. "
        "score ≥ 90 → saudavel; ≥ 60 → atencao; < 60 → critico."
    ),
)
async def saude_lp(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    trimestres: int = Query(default=4, ge=1, le=8),
) -> SaudeLpOut:
    checklists_raw = await LpChecklistService().saude_lp(
        session, empresa_id, trimestres=trimestres
    )
    checklists_out = [ChecklistTrimestreOut.from_checklist(c) for c in checklists_raw]
    return SaudeLpOut.from_checklists(empresa_id, checklists_out)
