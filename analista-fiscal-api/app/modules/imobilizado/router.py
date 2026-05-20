"""Endpoints REST imobilizado (Sprint 8 PR1)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.imobilizado.repo import BemImobilizadoRepo, DepreciacaoRepo
from app.modules.imobilizado.schemas import (
    BaixarBemIn,
    BemImobilizadoOut,
    CadastrarBemIn,
    CategoriaBem,
    DepreciacaoMensalOut,
    GerarDepreciacaoOut,
    MetodoDepreciacao,
)
from app.modules.imobilizado.service import ImobilizadoService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import BemNaoEncontrado

router = APIRouter(prefix="/v1/empresas", tags=["imobilizado"])

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def _parse_competencia(competencia: str) -> date:
    if not _COMPETENCIA_RE.match(competencia):
        raise HTTPException(
            status_code=422, detail="Competência deve estar no formato AAAA-MM"
        )
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


@router.post(
    "/{empresa_id}/imobilizado",
    response_model=BemImobilizadoOut,
    status_code=201,
    summary="Cadastra bem do imobilizado",
    description=(
        "Cadastra um ativo permanente. Taxa de depreciação e vida útil são "
        "opcionais — se omitidas, são resolvidas pela TabelaDepreciacaoRfb "
        "(IN SRF 162/1998) usando a categoria informada."
    ),
)
async def cadastrar(
    empresa_id: UUID,
    payload: CadastrarBemIn,
    ctx: TenantDep,
    session: SessionDep,
) -> BemImobilizadoOut:
    return await ImobilizadoService().cadastrar(
        session, ctx.tenant_id, empresa_id, payload
    )


@router.get(
    "/{empresa_id}/imobilizado",
    response_model=list[BemImobilizadoOut],
    summary="Lista bens do imobilizado",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[BemImobilizadoOut]:
    bens = await BemImobilizadoRepo(session).listar(empresa_id)
    return [
        BemImobilizadoOut(
            id=b.id,
            empresa_id=b.empresa_id,
            descricao=b.descricao,
            categoria=CategoriaBem(b.categoria),
            data_aquisicao=b.data_aquisicao,
            valor_aquisicao=b.valor_aquisicao,
            taxa_depreciacao_anual=b.taxa_depreciacao_anual,
            vida_util_meses=b.vida_util_meses,
            valor_residual=b.valor_residual,
            metodo_depreciacao=MetodoDepreciacao(b.metodo_depreciacao),
            documento_fiscal_id=b.documento_fiscal_id,
            data_baixa=b.data_baixa,
            motivo_baixa=b.motivo_baixa,
            ativo=b.ativo,
            criado_em=b.criado_em,
        )
        for b in bens
    ]


@router.get(
    "/{empresa_id}/imobilizado/{bem_id}",
    response_model=BemImobilizadoOut,
    summary="Detalha um bem",
)
async def detalhar(
    empresa_id: UUID,
    bem_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> BemImobilizadoOut:
    bem = await BemImobilizadoRepo(session).por_id(bem_id)
    if bem is None or bem.empresa_id != empresa_id:
        raise BemNaoEncontrado(f"Bem {bem_id} não encontrado")
    return BemImobilizadoOut(
        id=bem.id,
        empresa_id=bem.empresa_id,
        descricao=bem.descricao,
        categoria=CategoriaBem(bem.categoria),
        data_aquisicao=bem.data_aquisicao,
        valor_aquisicao=bem.valor_aquisicao,
        taxa_depreciacao_anual=bem.taxa_depreciacao_anual,
        vida_util_meses=bem.vida_util_meses,
        valor_residual=bem.valor_residual,
        metodo_depreciacao=MetodoDepreciacao(bem.metodo_depreciacao),
        documento_fiscal_id=bem.documento_fiscal_id,
        data_baixa=bem.data_baixa,
        motivo_baixa=bem.motivo_baixa,
        ativo=bem.ativo,
        criado_em=bem.criado_em,
    )


@router.post(
    "/{empresa_id}/imobilizado/{bem_id}/baixar",
    response_model=BemImobilizadoOut,
    summary="Baixa um bem (alienação, sinistro, perda)",
)
async def baixar(
    empresa_id: UUID,
    bem_id: UUID,
    payload: BaixarBemIn,
    ctx: TenantDep,
    session: SessionDep,
) -> BemImobilizadoOut:
    return await ImobilizadoService().baixar(session, empresa_id, bem_id, payload)


@router.post(
    "/{empresa_id}/imobilizado/depreciacao/{competencia}",
    response_model=GerarDepreciacaoOut,
    status_code=200,
    summary="Gera lote mensal de depreciação para a empresa",
    description=(
        "Roda o algoritmo linear (IN SRF 162/1998) sobre todos os bens "
        "depreciáveis ativos da empresa para a competência. Idempotente: "
        "pares (bem, competência) já processados são pulados."
    ),
)
async def gerar_depreciacao(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> GerarDepreciacaoOut:
    comp_date = _parse_competencia(competencia)
    return await ImobilizadoService().gerar_depreciacao_mensal(
        session, ctx.tenant_id, empresa_id, comp_date
    )


@router.get(
    "/{empresa_id}/imobilizado/{bem_id}/depreciacoes",
    response_model=list[DepreciacaoMensalOut],
    summary="Lista o histórico de depreciação de um bem",
)
async def listar_depreciacoes(
    empresa_id: UUID,
    bem_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[DepreciacaoMensalOut]:
    bem = await BemImobilizadoRepo(session).por_id(bem_id)
    if bem is None or bem.empresa_id != empresa_id:
        raise BemNaoEncontrado(f"Bem {bem_id} não encontrado")
    rows = await DepreciacaoRepo(session).listar_por_bem(bem_id)
    return [
        DepreciacaoMensalOut(
            id=r.id,
            bem_id=r.bem_id,
            competencia=r.competencia,
            valor_depreciado=r.valor_depreciado,
            valor_acumulado=r.valor_acumulado,
            saldo_contabil=r.saldo_contabil,
        )
        for r in rows
    ]
