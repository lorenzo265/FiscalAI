"""Golden tests da CSLL trimestral — Lucro Presumido (Sprint 11 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.lucro_presumido.calcula_csll import (
    ALGORITMO_VERSAO,
    calcular_csll_trimestral,
)


class TestCsllComercio12pct:
    def test_receita_100k(self) -> None:
        # 100.000 × 12% = 12.000 base × 9% = 1.080
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("100000.00"),
            percentual_presuncao=Decimal("0.1200"),
        )
        assert r.base_presumida == Decimal("12000.00")
        assert r.base_total == Decimal("12000.00")
        assert r.aliquota == Decimal("0.0900")
        assert r.csll == Decimal("1080.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_receita_1M(self) -> None:
        # 1.000.000 × 12% × 9% = 10.800
        r = calcular_csll_trimestral(
            Decimal("1000000.00"), Decimal("0.1200")
        )
        assert r.csll == Decimal("10800.00")


class TestCsllServicos32pct:
    def test_servicos_300k(self) -> None:
        # 300.000 × 32% × 9% = 8.640
        r = calcular_csll_trimestral(
            Decimal("300000.00"), Decimal("0.3200")
        )
        assert r.csll == Decimal("8640.00")


class TestCsllAdicoes:
    def test_com_ganho_capital_e_aplicacoes(self) -> None:
        # 200.000 × 12% = 24.000 + 50.000 + 4.000 + 1.000 = 79.000
        # CSLL = 79.000 × 9% = 7.110
        r = calcular_csll_trimestral(
            Decimal("200000"), Decimal("0.1200"),
            ganhos_capital=Decimal("50000"),
            receitas_aplicacoes=Decimal("4000"),
            outras_adicoes=Decimal("1000"),
        )
        assert r.base_total == Decimal("79000.00")
        assert r.csll == Decimal("7110.00")


class TestCsllBordas:
    def test_zero(self) -> None:
        r = calcular_csll_trimestral(Decimal("0"), Decimal("0.12"))
        assert r.csll == Decimal("0.00")

    def test_receita_negativa(self) -> None:
        with pytest.raises(ValueError, match="receita"):
            calcular_csll_trimestral(Decimal("-1"), Decimal("0.12"))

    def test_presuncao_invalida(self) -> None:
        with pytest.raises(ValueError, match="percentual_presuncao"):
            calcular_csll_trimestral(Decimal("100"), Decimal("1.5"))
