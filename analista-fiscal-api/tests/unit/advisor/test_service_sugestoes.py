"""Testes do AdvisorService.listar_sugestoes — orquestração I/O (Sprint 15 PR2)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.advisor.service import AdvisorService
from app.modules.advisor.simula_fator_r import SimulacaoFatorR
from app.modules.advisor.sugestoes_otimizacao import ApuracaoPendente
from app.shared.exceptions import EmpresaNaoEncontrada

_COMP = date(2026, 5, 15)


def _empresa(
    *,
    regime: str = "simples_nacional",
    anexo: str | None = "V",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        regime_tributario=regime,
        anexo_simples=anexo,
        cnae_principal="69.20-6/01",
        uf="SP",
    )


def _faixa(anexo: str) -> SimpleNamespace:
    """ORM-like row de tabela_simples_faixa."""
    return SimpleNamespace(
        faixa=1,
        rbt12_ate=Decimal("180000"),
        aliquota_nominal=Decimal("0.0600") if anexo == "III" else Decimal("0.1550"),
        parcela_deduzir=Decimal("0"),
    )


def _simulacao(
    *, deve_migrar: bool = True, economia: str = "5000.00"
) -> SimulacaoFatorR:
    return SimulacaoFatorR(
        fator_r_atual=Decimal("0.1500"),
        fator_r_limiar=Decimal("0.28"),
        folha_12m=Decimal("100000.00"),
        receita_12m=Decimal("720000.00"),
        folha_necessaria_28pct=Decimal("201600.00"),
        gap_folha_anual=Decimal("101600.00"),
        receita_mes_referencia=Decimal("60000.00"),
        das_anexo_iii_mensal=Decimal("3500.00"),
        das_anexo_v_mensal=Decimal("9750.00"),
        economia_mensal=Decimal("0"),
        economia_anual_estimada=Decimal(economia),
        anexo_atual_efetivo="V",
        anexo_recomendado="III",
        deve_migrar=deve_migrar,
        competencia_referencia=_COMP,
    )


# ── Caminho feliz ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listar_sugestoes_caminho_feliz_simples_anexo_v() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.folha_12m = AsyncMock(return_value=Decimal("100000"))
    sug_repo.receita_12m = AsyncMock(return_value=Decimal("720000"))
    sug_repo.apuracoes_das_pendentes = AsyncMock(return_value=[])
    tabela_repo = AsyncMock()
    tabela_repo.faixas_vigentes = AsyncMock(
        side_effect=lambda anexo, em: [_faixa(anexo)]
    )

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
        patch(
            "app.modules.advisor.service.TabelaSimplesRepo", return_value=tabela_repo
        ),
        patch(
            "app.modules.advisor.service.simular_fator_r",
            return_value=_simulacao(),
        ),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(
            empresa.id, competencia=_COMP
        )

    assert len(sugestoes) == 1
    assert sugestoes[0].codigo == "fator_r_migrar_anexo_iii"


# ── Empresa fora do Simples ou anexo I/II/IV — não tenta Fator R ────────────


@pytest.mark.asyncio
async def test_lucro_presumido_nao_simula_fator_r() -> None:
    empresa = _empresa(regime="lucro_presumido", anexo=None)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.apuracoes_das_pendentes = AsyncMock(return_value=[])

    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(
            empresa.id, competencia=_COMP
        )
    assert sugestoes == []
    # NÃO chamou folha/receita/faixas — caminho Fator R curto-circuita.
    sug_repo.folha_12m.assert_not_awaited()


@pytest.mark.asyncio
async def test_anexo_i_nao_simula_fator_r() -> None:
    empresa = _empresa(anexo="I")
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.apuracoes_das_pendentes = AsyncMock(return_value=[])
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(
            empresa.id, competencia=_COMP
        )
    assert sugestoes == []


@pytest.mark.asyncio
async def test_receita_zero_curto_circuita_fator_r() -> None:
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.folha_12m = AsyncMock(return_value=Decimal("50000"))
    sug_repo.receita_12m = AsyncMock(return_value=Decimal("0"))
    sug_repo.apuracoes_das_pendentes = AsyncMock(return_value=[])
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(empresa.id)
    assert sugestoes == []


# ── DAS pendente sem Fator R ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apuracao_atrasada_sem_fator_r_aplicavel() -> None:
    """Empresa LP com DAS atrasado de antes da mudança de regime — só parcelamento."""
    empresa = _empresa(regime="lucro_presumido", anexo=None)
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.apuracoes_das_pendentes = AsyncMock(
        return_value=[
            ApuracaoPendente(
                apuracao_id="x",
                tipo="das",
                competencia=date(2026, 1, 1),
                valor=Decimal("3000"),
                vencimento=date(2026, 2, 20),
                status="calculado",
            )
        ]
    )
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(
            empresa.id, competencia=_COMP
        )
    assert len(sugestoes) == 1
    assert sugestoes[0].codigo == "parcelar_das_atrasado"


# ── Erros propagados ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empresa_nao_encontrada_levanta_404() -> None:
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=None)
    with patch(
        "app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo
    ), pytest.raises(EmpresaNaoEncontrada):
        await AdvisorService(session).listar_sugestoes(uuid.uuid4())


# ── Sem faixas no banco (defeito operacional) ───────────────────────────────


@pytest.mark.asyncio
async def test_faixas_ausentes_curto_circuita_fator_r() -> None:
    """Quando o SCD não tem vigência para III/V, sugestão Fator R é pulada."""
    empresa = _empresa()
    session = AsyncMock()
    empresa_repo = AsyncMock()
    empresa_repo.por_id = AsyncMock(return_value=empresa)
    sug_repo = AsyncMock()
    sug_repo.folha_12m = AsyncMock(return_value=Decimal("100000"))
    sug_repo.receita_12m = AsyncMock(return_value=Decimal("720000"))
    sug_repo.apuracoes_das_pendentes = AsyncMock(return_value=[])
    tabela_repo = AsyncMock()
    tabela_repo.faixas_vigentes = AsyncMock(return_value=[])  # vazio
    with (
        patch("app.modules.advisor.service.EmpresaRepo", return_value=empresa_repo),
        patch("app.modules.advisor.service.SugestoesRepo", return_value=sug_repo),
        patch(
            "app.modules.advisor.service.TabelaSimplesRepo", return_value=tabela_repo
        ),
    ):
        sugestoes = await AdvisorService(session).listar_sugestoes(
            empresa.id, competencia=_COMP
        )
    assert sugestoes == []
