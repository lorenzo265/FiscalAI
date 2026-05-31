"""Smoke tests para os 6 tipos restantes (Sprint 19.5 PR1).

Para cada tipo (IRRF, FGTS, SN, Presunção LP, ICMS UF, CBS/IBS):

  * 1 happy path (cria vigência via service com repo mockado).
  * 1 caminho de erro de validação (specific por tipo).

INSS tem cobertura mais densa em ``test_service.py`` por ser o caso canônico.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.modules.tabelas_admin.schemas import (
    AliquotaCbsIbsIn,
    AliquotaIcmsUfIn,
    FaixaIrrfIn,
    PresuncaoLpIn,
)
from app.modules.tabelas_admin.service import TabelaAdminService
from app.shared.exceptions import VigenciaTributariaInvalida

from tests.unit.tabelas_admin._helpers import (
    vigencia_cbs_ibs_valida,
    vigencia_fgts_valida,
    vigencia_icms_uf_valida,
    vigencia_irrf_valida,
    vigencia_presuncao_valida,
    vigencia_simples_valida,
)


def _svc_com_repos(**overrides: AsyncMock) -> tuple[
    TabelaAdminService, AsyncMock, AsyncMock, AsyncMock
]:
    """Cria service com log_repo / scd_repo mockados — atributos do scd_repo
    devolvem por default: max_valid_from_* = None, inserir_* = 3, snapshot_* = [].
    """
    log_repo = AsyncMock()
    log_repo.por_idempotency_key = AsyncMock(return_value=None)
    log_repo.criar = AsyncMock(side_effect=lambda li: li)

    scd_repo = AsyncMock()
    # Defaults — sobrescrevíveis por overrides.
    for attr in (
        "max_valid_from_inss",
        "max_valid_from_irrf",
        "max_valid_from_fgts",
        "max_valid_from_simples",
        "max_valid_from_presuncao",
        "max_valid_from_icms",
        "max_valid_from_cbs_ibs",
    ):
        setattr(scd_repo, attr, AsyncMock(return_value=None))
    for attr in (
        "inserir_inss",
        "inserir_irrf",
        "inserir_fgts",
        "inserir_simples_nacional",
        "inserir_presuncao_lp",
        "inserir_icms_uf",
        "inserir_cbs_ibs",
    ):
        setattr(scd_repo, attr, AsyncMock(return_value=3))
    for name, mock in overrides.items():
        setattr(scd_repo, name, mock)

    session = AsyncMock()
    svc = TabelaAdminService(log_repo=log_repo, scd_repo=scd_repo)
    return svc, log_repo, scd_repo, session


# ── IRRF ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_irrf_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_irrf_valida()
    log = await svc.criar_vigencia_irrf(session, payload)
    assert log.tipo_tabela == "irrf"
    scd_repo.inserir_irrf.assert_awaited_once()


@pytest.mark.asyncio
async def test_irrf_aliquotas_nao_progressivas_falha() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    faixas = [
        FaixaIrrfIn(
            faixa=1, base_ate=Decimal("2428.80"),
            aliquota=Decimal("0"), parcela_deduzir=Decimal("0"),
        ),
        FaixaIrrfIn(
            faixa=2, base_ate=Decimal("2826.65"),
            aliquota=Decimal("0.25"), parcela_deduzir=Decimal("182.16"),
        ),
        FaixaIrrfIn(
            faixa=3, base_ate=Decimal("3751.05"),
            aliquota=Decimal("0.15"),  # ← retrocede
            parcela_deduzir=Decimal("394.16"),
        ),
        FaixaIrrfIn(
            faixa=4, base_ate=Decimal("4664.68"),
            aliquota=Decimal("0.225"), parcela_deduzir=Decimal("675.49"),
        ),
        FaixaIrrfIn(
            faixa=5, base_ate=Decimal("999999999.99"),
            aliquota=Decimal("0.275"), parcela_deduzir=Decimal("908.73"),
        ),
    ]
    payload = vigencia_irrf_valida(faixas=faixas)
    with pytest.raises(VigenciaTributariaInvalida, match="progressiv"):
        await svc.criar_vigencia_irrf(session, payload)
    scd_repo.inserir_irrf.assert_not_awaited()


# ── FGTS ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fgts_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_fgts_valida()
    log = await svc.criar_vigencia_fgts(session, payload)
    assert log.tipo_tabela == "fgts"
    scd_repo.inserir_fgts.assert_awaited_once()


@pytest.mark.asyncio
async def test_fgts_aliquota_zero_falha_plausibilidade() -> None:
    from app.modules.tabelas_admin.schemas import AliquotaFgtsIn

    svc, _, scd_repo, session = _svc_com_repos()
    aliquotas = [
        AliquotaFgtsIn(vinculo="clt", aliquota=Decimal("0"))  # < min 0.01
    ]
    payload = vigencia_fgts_valida(aliquotas=aliquotas)
    with pytest.raises(VigenciaTributariaInvalida, match="plausível"):
        await svc.criar_vigencia_fgts(session, payload)


# ── Simples Nacional ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simples_nacional_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_simples_valida()
    log = await svc.criar_vigencia_simples_nacional(session, payload)
    assert log.tipo_tabela == "simples_nacional"
    scd_repo.inserir_simples_nacional.assert_awaited_once()


@pytest.mark.asyncio
async def test_simples_anti_regressao_por_anexo() -> None:
    """max_valid_from_simples('III') retorna 2026-01-01 → POST com 2026-01-01 falha.
    Demonstra que a regressão é por anexo (anexo IV não impacta anexo III).
    """
    svc, _, _, session = _svc_com_repos(
        max_valid_from_simples=AsyncMock(return_value=date(2026, 1, 1))
    )
    payload = vigencia_simples_valida(
        anexo="III", valid_from=date(2026, 1, 1)
    )
    with pytest.raises(
        VigenciaTributariaInvalida, match="posterior à vigência ativa"
    ):
        await svc.criar_vigencia_simples_nacional(session, payload)


# ── Presunção LP ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_presuncao_lp_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_presuncao_valida()
    log = await svc.criar_vigencia_presuncao_lp(session, payload)
    assert log.tipo_tabela == "presuncao_lp"
    scd_repo.inserir_presuncao_lp.assert_awaited_once()


@pytest.mark.asyncio
async def test_presuncao_csll_implausivel_falha() -> None:
    svc, _, _, session = _svc_com_repos()
    presuncoes = [
        PresuncaoLpIn(
            grupo_atividade="Indústria",
            cnae_pattern="10",
            percentual_irpj=Decimal("0.08"),
            percentual_csll=Decimal("0.50"),  # > 0.40 limite plausível
            prioridade=20,
        )
    ]
    payload = vigencia_presuncao_valida(presuncoes=presuncoes)
    with pytest.raises(VigenciaTributariaInvalida, match="CSLL"):
        await svc.criar_vigencia_presuncao_lp(session, payload)


# ── ICMS UF ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_icms_uf_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_icms_uf_valida()
    log = await svc.criar_vigencia_icms_uf(session, payload)
    assert log.tipo_tabela == "icms_uf"
    scd_repo.inserir_icms_uf.assert_awaited_once()


@pytest.mark.asyncio
async def test_icms_uf_invalida_falha() -> None:
    svc, _, _, session = _svc_com_repos()
    aliquotas = [
        AliquotaIcmsUfIn(
            uf="XX",
            aliquota_interna=Decimal("0.18"),
            aliquota_fecp=Decimal("0"),
        )
    ]
    payload = vigencia_icms_uf_valida(aliquotas=aliquotas)
    with pytest.raises(VigenciaTributariaInvalida, match="27 UFs"):
        await svc.criar_vigencia_icms_uf(session, payload)


# ── CBS / IBS ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cbs_ibs_happy_path() -> None:
    svc, _, scd_repo, session = _svc_com_repos()
    payload = vigencia_cbs_ibs_valida()
    log = await svc.criar_vigencia_cbs_ibs(session, payload)
    assert log.tipo_tabela == "cbs_ibs"
    scd_repo.inserir_cbs_ibs.assert_awaited_once()


@pytest.mark.asyncio
async def test_cbs_ibs_fase_invalida_falha() -> None:
    svc, _, _, session = _svc_com_repos()
    aliquotas = [
        AliquotaCbsIbsIn(
            fase="fase_que_nao_existe",
            regime=None,
            cnae_pattern=None,
            classificacao_lc214="geral",
            aliquota_cbs=Decimal("0.009"),
            aliquota_ibs=Decimal("0.001"),
            observacao=None,
        )
    ]
    payload = vigencia_cbs_ibs_valida(aliquotas=aliquotas)
    with pytest.raises(VigenciaTributariaInvalida, match="LC 214"):
        await svc.criar_vigencia_cbs_ibs(session, payload)
