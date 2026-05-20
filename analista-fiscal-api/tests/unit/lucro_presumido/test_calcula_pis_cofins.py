"""Golden tests de PIS e Cofins cumulativos (Sprint 11 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.lucro_presumido.calcula_pis_cofins import (
    ALGORITMO_VERSAO_COFINS,
    ALGORITMO_VERSAO_PIS,
    calcular_cofins_cumulativo_mensal,
    calcular_pis_cumulativo_mensal,
)


class TestPis:
    def test_100k_sem_exclusoes(self) -> None:
        # 100.000 × 0,65% = 650
        r = calcular_pis_cumulativo_mensal(Decimal("100000.00"))
        assert r.base_calculo == Decimal("100000.00")
        assert r.aliquota == Decimal("0.0065")
        assert r.tributo == Decimal("650.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO_PIS

    def test_com_exclusoes(self) -> None:
        # 100.000 − 15.000 = 85.000 × 0,65% = 552,50
        r = calcular_pis_cumulativo_mensal(
            Decimal("100000.00"), exclusoes=Decimal("15000.00")
        )
        assert r.base_calculo == Decimal("85000.00")
        assert r.tributo == Decimal("552.50")

    def test_valor_quebrado(self) -> None:
        # 12345,67 × 0,65% = 80,2469... → 80,25 (ROUND_HALF_EVEN)
        r = calcular_pis_cumulativo_mensal(Decimal("12345.67"))
        assert r.tributo == Decimal("80.25")

    def test_zero(self) -> None:
        r = calcular_pis_cumulativo_mensal(Decimal("0"))
        assert r.tributo == Decimal("0.00")


class TestCofins:
    def test_100k_sem_exclusoes(self) -> None:
        # 100.000 × 3% = 3.000
        r = calcular_cofins_cumulativo_mensal(Decimal("100000.00"))
        assert r.aliquota == Decimal("0.0300")
        assert r.tributo == Decimal("3000.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO_COFINS

    def test_com_exclusoes(self) -> None:
        # 100.000 − 20.000 = 80.000 × 3% = 2.400
        r = calcular_cofins_cumulativo_mensal(
            Decimal("100000"), exclusoes=Decimal("20000")
        )
        assert r.tributo == Decimal("2400.00")

    def test_proporcao_pis_cofins(self) -> None:
        # Cofins deve ser exatamente 3/0,65 = ~4,6154× PIS
        receita = Decimal("250000")
        pis = calcular_pis_cumulativo_mensal(receita).tributo
        cofins = calcular_cofins_cumulativo_mensal(receita).tributo
        assert pis == Decimal("1625.00")     # 250000 × 0,65%
        assert cofins == Decimal("7500.00")  # 250000 × 3%


class TestExclusoesInvalidas:
    def test_exclusoes_negativas(self) -> None:
        with pytest.raises(ValueError, match="exclusoes"):
            calcular_pis_cumulativo_mensal(
                Decimal("100"), exclusoes=Decimal("-1")
            )

    def test_exclusoes_maior_que_receita(self) -> None:
        with pytest.raises(ValueError, match="exclusoes.*exceder"):
            calcular_cofins_cumulativo_mensal(
                Decimal("100"), exclusoes=Decimal("200")
            )

    def test_receita_negativa(self) -> None:
        with pytest.raises(ValueError, match="receita_bruta"):
            calcular_pis_cumulativo_mensal(Decimal("-1"))
