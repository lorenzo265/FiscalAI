"""Testes do AliquotaCbsIbsRepo — lookup SCD com scoring por especificidade
(Sprint 14 PR1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.reforma.repo import AliquotaCbsIbsRepo
from app.shared.exceptions import (
    AliquotaCbsIbsAusente,
    PeriodoReformaNaoMapeado,
)


def _row(
    *,
    fase: str = "teste_2026",
    regime: str | None = None,
    cnae_pattern: str | None = None,
    classificacao_lc214: str | None = None,
    aliquota_cbs: str = "0.0090",
    aliquota_ibs: str = "0.0010",
    valid_from: date = date(2026, 1, 1),
    valid_to: date | None = None,
    fonte_norma: str = "LC 214/2025 art. 348",
    algoritmo_versao: str = "reforma.cbs-ibs.v1",
    observacao: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        fase=fase,
        regime=regime,
        cnae_pattern=cnae_pattern,
        classificacao_lc214=classificacao_lc214,
        aliquota_cbs=Decimal(aliquota_cbs),
        aliquota_ibs=Decimal(aliquota_ibs),
        valid_from=valid_from,
        valid_to=valid_to,
        fonte_norma=fonte_norma,
        algoritmo_versao=algoritmo_versao,
        observacao=observacao,
    )


def _mock_session(rows: list[SimpleNamespace]) -> AsyncMock:
    """Mock AsyncSession.execute(...).scalars().all() -> rows."""
    session = AsyncMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=rows)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars)
    session.execute = AsyncMock(return_value=result)
    return session


class TestVigenciaGeral:
    """Linha geral (todos os filtros NULL) sempre casa."""

    @pytest.mark.asyncio
    async def test_vigencia_geral_unica(self) -> None:
        session = _mock_session([_row()])
        repo = AliquotaCbsIbsRepo(session)
        r = await repo.vigente(date(2026, 6, 15))
        assert r.aliquota_cbs == Decimal("0.0090")
        assert r.aliquota_ibs == Decimal("0.0010")
        assert r.fonte_norma == "LC 214/2025 art. 348"

    @pytest.mark.asyncio
    async def test_vigencia_geral_com_filtros_aceita(self) -> None:
        """Geral (NULL nos filtros) casa mesmo quando cliente passa regime/cnae."""
        session = _mock_session([_row()])
        repo = AliquotaCbsIbsRepo(session)
        r = await repo.vigente(
            date(2026, 6, 15),
            regime="lucro_presumido",
            cnae="47.30",
            classificacao="geral",
        )
        assert r.aliquota_cbs == Decimal("0.0090")


class TestEspecificidadeVenceEmpate:
    """Vigência mais específica vence a geral quando ambas casam."""

    @pytest.mark.asyncio
    async def test_regime_especifico_vence_geral(self) -> None:
        rows = [
            _row(),  # geral
            _row(regime="lucro_presumido", aliquota_cbs="0.0095"),  # específica
        ]
        session = _mock_session(rows)
        repo = AliquotaCbsIbsRepo(session)
        r = await repo.vigente(date(2026, 6, 15), regime="lucro_presumido")
        assert r.aliquota_cbs == Decimal("0.0095")

    @pytest.mark.asyncio
    async def test_cnae_prefix_match(self) -> None:
        rows = [
            _row(),  # geral
            _row(cnae_pattern="47", aliquota_cbs="0.0080"),  # comércio
            _row(cnae_pattern="47.30", aliquota_cbs="0.0070"),  # combustível
        ]
        session = _mock_session(rows)
        repo = AliquotaCbsIbsRepo(session)
        # CNAE 47.30 deve casar com a mais específica (47.30)
        r = await repo.vigente(date(2026, 6, 15), cnae="47.30")
        assert r.aliquota_cbs == Decimal("0.0070")

    @pytest.mark.asyncio
    async def test_classificacao_lc214(self) -> None:
        rows = [
            _row(),  # geral
            _row(classificacao_lc214="reducao_60", aliquota_cbs="0.0036"),
        ]
        session = _mock_session(rows)
        repo = AliquotaCbsIbsRepo(session)
        r = await repo.vigente(date(2026, 6, 15), classificacao="reducao_60")
        assert r.aliquota_cbs == Decimal("0.0036")


class TestSemVigenciaCobertura:
    """Gap de seed levanta — princípio §8.3."""

    @pytest.mark.asyncio
    async def test_sem_linhas_levanta(self) -> None:
        session = _mock_session([])
        repo = AliquotaCbsIbsRepo(session)
        with pytest.raises(AliquotaCbsIbsAusente, match="Sem vigência"):
            await repo.vigente(date(2026, 6, 15))

    @pytest.mark.asyncio
    async def test_pre_reforma_levanta_antes_de_consultar(self) -> None:
        """Para competência < 2026, periodo_transicao.fase() já levanta."""
        session = _mock_session([_row()])
        repo = AliquotaCbsIbsRepo(session)
        with pytest.raises(PeriodoReformaNaoMapeado):
            await repo.vigente(date(2025, 12, 31))
