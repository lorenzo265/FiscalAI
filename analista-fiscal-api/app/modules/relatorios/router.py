"""Endpoints REST — relatórios contábeis (Sprint 12 PR1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.relatorios.repo import RelatorioRepo
from app.modules.relatorios.schemas import (
    GerarBalancoIn,
    GerarDfcIn,
    GerarDreAuxLpIn,
    GerarDreIn,
    GerarIndicadoresIn,
    RelatorioOut,
    TipoRelatorio,
)
from app.modules.relatorios.service import RelatoriosService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import RelatorioNaoEncontrado

router = APIRouter(prefix="/v1/empresas", tags=["relatorios"])


@router.post(
    "/{empresa_id}/relatorios/dre",
    response_model=RelatorioOut,
    status_code=201,
    summary="Gera DRE estruturada (Lei 6.404/1976 art. 187)",
    description=(
        "Cria snapshot imutável a partir do movimento das contas 4.x "
        "(receitas) e 5.x (despesas) no período + IRPJ/CSLL apurados na "
        "tabela ``apuracao_fiscal``. Idempotente: chamadas com mesmo "
        "(empresa, período) retornam o relatório ativo a menos que "
        "``forcar_regerar=true`` — nesse caso o anterior é marcado como "
        "``superseded_by`` da nova versão."
    ),
)
async def gerar_dre(
    empresa_id: UUID,
    payload: GerarDreIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    relatorio = await RelatoriosService().gerar_dre(
        session, ctx.tenant_id, empresa_id, payload
    )
    return RelatorioOut.model_validate(relatorio)


@router.get(
    "/{empresa_id}/relatorios",
    response_model=list[RelatorioOut],
    summary="Lista relatórios da empresa",
)
async def listar_relatorios(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoRelatorio | None = None,
    somente_ativos: bool = True,
    limite: int = 50,
) -> list[RelatorioOut]:
    tipo_str = tipo.value if tipo else None
    rows = await RelatorioRepo(session).listar(
        empresa_id, tipo=tipo_str, somente_ativos=somente_ativos, limite=limite,
    )
    return [RelatorioOut.model_validate(r) for r in rows]


@router.post(
    "/{empresa_id}/relatorios/balanco",
    response_model=RelatorioOut,
    status_code=201,
    summary="Gera Balanço Patrimonial (Lei 6.404 art. 178)",
    description=(
        "Snapshot na ``data_referencia``. Valida invariante "
        "ATIVO = PASSIVO + PL — se não fecha, ``diferenca`` no payload "
        "indica o desvio (típico antes do encerramento anual)."
    ),
)
async def gerar_balanco(
    empresa_id: UUID,
    payload: GerarBalancoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    relatorio = await RelatoriosService().gerar_balanco(
        session, ctx.tenant_id, empresa_id, payload
    )
    return RelatorioOut.model_validate(relatorio)


@router.post(
    "/{empresa_id}/relatorios/dfc",
    response_model=RelatorioOut,
    status_code=201,
    summary="Gera DFC método indireto (NBC TG 03 / Lei 6.404 art. 188)",
    description=(
        "Reusa DRE do período para derivar Lucro Líquido. Variações "
        "(clientes, estoques, fornecedores, encargos, imobilizado, caixa) "
        "vêm direto de ``saldo_conta_mes``. Aporte/empréstimos/distribuição "
        "aceitam override manual (MVP — plano contábil sem contas "
        "específicas para esses fluxos)."
    ),
)
async def gerar_dfc(
    empresa_id: UUID,
    payload: GerarDfcIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    relatorio = await RelatoriosService().gerar_dfc(
        session, ctx.tenant_id, empresa_id, payload
    )
    return RelatorioOut.model_validate(relatorio)


@router.post(
    "/{empresa_id}/relatorios/indicadores",
    response_model=RelatorioOut,
    status_code=201,
    summary="Gera Indicadores Financeiros (Liquidez, Endividamento, Margens, ROA/ROE)",
    description=(
        "Reusa internamente o DRE e o Balanço do período para calcular 11 "
        "indicadores clássicos. Divisões por zero retornam ``null`` no "
        "payload — frontend deve mostrar 'N/A'."
    ),
)
async def gerar_indicadores(
    empresa_id: UUID,
    payload: GerarIndicadoresIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    relatorio = await RelatoriosService().gerar_indicadores(
        session, ctx.tenant_id, empresa_id, payload
    )
    return RelatorioOut.model_validate(relatorio)


@router.post(
    "/{empresa_id}/relatorios/dre-aux-lp",
    response_model=RelatorioOut,
    status_code=201,
    summary="DRE auxiliar trimestral LP — reconciliação fiscal × contábil",
    description=(
        "Consolida o trimestre cruzando apurações fiscais (IRPJ, CSLL, "
        "PIS, Cofins, ICMS, ISS — Sprint 11) com o DRE contábil (Sprint "
        "12 PR1). Mostra total por tributo, base presumida vs. contábil, "
        "diferença de receita e carga tributária efetiva. Útil para "
        "auditoria pré-DCTFWeb."
    ),
)
async def gerar_dre_aux_lp(
    empresa_id: UUID,
    payload: GerarDreAuxLpIn,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    relatorio = await RelatoriosService().gerar_dre_aux_lp(
        session, ctx.tenant_id, empresa_id, payload
    )
    return RelatorioOut.model_validate(relatorio)


@router.get(
    "/{empresa_id}/relatorios/{relatorio_id}",
    response_model=RelatorioOut,
    summary="Detalha um relatório específico",
)
async def detalhar_relatorio(
    empresa_id: UUID,
    relatorio_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> RelatorioOut:
    r = await RelatorioRepo(session).por_id(relatorio_id)
    if r is None or r.empresa_id != empresa_id:
        raise RelatorioNaoEncontrado(
            f"Relatório {relatorio_id} não encontrado nesta empresa"
        )
    return RelatorioOut.model_validate(r)
