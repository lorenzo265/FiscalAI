"""Golden tests de PIS e Cofins cumulativos (Sprint 11 PR1 + FA7-m3)."""

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
        assert r.saldo_exclusao_transportar == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO_PIS

    def test_com_exclusoes(self) -> None:
        # 100.000 − 15.000 = 85.000 × 0,65% = 552,50
        r = calcular_pis_cumulativo_mensal(
            Decimal("100000.00"), exclusoes=Decimal("15000.00")
        )
        assert r.base_calculo == Decimal("85000.00")
        assert r.tributo == Decimal("552.50")
        assert r.saldo_exclusao_transportar == Decimal("0.00")

    def test_valor_quebrado(self) -> None:
        # 12345,67 × 0,65% = 80,2469... → 80,25 (ROUND_HALF_EVEN)
        r = calcular_pis_cumulativo_mensal(Decimal("12345.67"))
        assert r.tributo == Decimal("80.25")

    def test_zero(self) -> None:
        r = calcular_pis_cumulativo_mensal(Decimal("0"))
        assert r.tributo == Decimal("0.00")
        assert r.saldo_exclusao_transportar == Decimal("0.00")


class TestCofins:
    def test_100k_sem_exclusoes(self) -> None:
        # 100.000 × 3% = 3.000
        r = calcular_cofins_cumulativo_mensal(Decimal("100000.00"))
        assert r.aliquota == Decimal("0.0300")
        assert r.tributo == Decimal("3000.00")
        assert r.saldo_exclusao_transportar == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO_COFINS

    def test_com_exclusoes(self) -> None:
        # 100.000 − 20.000 = 80.000 × 3% = 2.400
        r = calcular_cofins_cumulativo_mensal(
            Decimal("100000"), exclusoes=Decimal("20000")
        )
        assert r.tributo == Decimal("2400.00")
        assert r.saldo_exclusao_transportar == Decimal("0.00")

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

    def test_receita_negativa(self) -> None:
        with pytest.raises(ValueError, match="receita_bruta"):
            calcular_pis_cumulativo_mensal(Decimal("-1"))


class TestFA7M3ExclusoesExcedemReceita:
    """FA7-m3: exclusões > receita → base=0 + carryover (Lei 9.718/98 art.3º §2º).

    Antes do FA7, exclusoes > receita levantava ValueError — comportamento
    incorreto que impedia dedução legítima (cancelamentos de competências
    anteriores, exportações). O fix implementa:

      base = max(0, receita − exclusoes)
      saldo_exclusao_transportar = max(0, exclusoes − receita)

    O caller deve somar ``saldo_exclusao_transportar`` às exclusões do mês
    seguinte para que a empresa não perca a dedução.
    """

    def test_exclusoes_iguais_a_receita_base_zero(self) -> None:
        # 100 − 100 = 0 → base=0, tributo=0, sem carryover
        r = calcular_pis_cumulativo_mensal(
            Decimal("100.00"), exclusoes=Decimal("100.00")
        )
        assert r.base_calculo == Decimal("0.00")
        assert r.tributo == Decimal("0.00")
        assert r.saldo_exclusao_transportar == Decimal("0.00")

    def test_exclusoes_maiores_base_zero_carryover(self) -> None:
        # Receita jan=80k, exportação=120k → excede 40k
        # base=0, saldo=40k transportar fev
        r = calcular_pis_cumulativo_mensal(
            Decimal("80000.00"), exclusoes=Decimal("120000.00")
        )
        assert r.base_calculo == Decimal("0.00")
        assert r.tributo == Decimal("0.00")
        assert r.saldo_exclusao_transportar == Decimal("40000.00"), (
            "Excedente de exclusão deve ser transportado para o próximo mês, "
            "não descartado (Lei 9.718/98 art. 3º §2º)"
        )

    def test_cofins_exclusoes_maiores_base_zero_carryover(self) -> None:
        # Mesmo cenário, Cofins: base=0, saldo=40k
        r = calcular_cofins_cumulativo_mensal(
            Decimal("80000.00"), exclusoes=Decimal("120000.00")
        )
        assert r.base_calculo == Decimal("0.00")
        assert r.tributo == Decimal("0.00")
        assert r.saldo_exclusao_transportar == Decimal("40000.00")

    def test_carryover_aplicado_no_mes_seguinte(self) -> None:
        # jan: receita=80k, exclusão=120k → saldo=40k
        # fev: receita=100k, exclusão_propria=10k + carryover=40k → excl=50k
        # base_fev = 100k − 50k = 50k; PIS = 50k × 0,65% = 325
        jan = calcular_pis_cumulativo_mensal(
            Decimal("80000"), exclusoes=Decimal("120000")
        )
        assert jan.saldo_exclusao_transportar == Decimal("40000.00")

        # O caller soma carryover às exclusões de fevereiro
        excl_fev = Decimal("10000") + jan.saldo_exclusao_transportar
        fev = calcular_pis_cumulativo_mensal(
            Decimal("100000"), exclusoes=excl_fev
        )
        assert fev.base_calculo == Decimal("50000.00")
        assert fev.tributo == Decimal("325.00")
        assert fev.saldo_exclusao_transportar == Decimal("0.00")

    def test_carryover_com_novo_excesso_no_segundo_mes(self) -> None:
        # jan: receita=50k, exclusão=80k → saldo=30k
        # fev: receita=20k, exclusão_propria=5k + carryover=30k → excl=35k
        # base_fev = max(0, 20k-35k) = 0; novo saldo = 15k
        jan = calcular_cofins_cumulativo_mensal(
            Decimal("50000"), exclusoes=Decimal("80000")
        )
        assert jan.saldo_exclusao_transportar == Decimal("30000.00")

        excl_fev = Decimal("5000") + jan.saldo_exclusao_transportar
        fev = calcular_cofins_cumulativo_mensal(
            Decimal("20000"), exclusoes=excl_fev
        )
        assert fev.base_calculo == Decimal("0.00")
        assert fev.tributo == Decimal("0.00")
        assert fev.saldo_exclusao_transportar == Decimal("15000.00")

    def test_backward_compat_sem_excesso_saldo_zero(self) -> None:
        # Quando exclusoes < receita (caso normal), saldo=0 — sem regressão
        r = calcular_pis_cumulativo_mensal(
            Decimal("100000"), exclusoes=Decimal("30000")
        )
        assert r.base_calculo == Decimal("70000.00")
        assert r.tributo == Decimal("455.00")
        assert r.saldo_exclusao_transportar == Decimal("0.00")

    def test_algoritmo_versao_bumped(self) -> None:
        r_pis = calcular_pis_cumulativo_mensal(Decimal("1000"))
        r_cof = calcular_cofins_cumulativo_mensal(Decimal("1000"))
        assert r_pis.algoritmo_versao == ALGORITMO_VERSAO_PIS
        assert r_cof.algoritmo_versao == ALGORITMO_VERSAO_COFINS
        # Garantir que v2 está em vigor (guard anti-downgrade de versão)
        assert "v2" in ALGORITMO_VERSAO_PIS
        assert "v2" in ALGORITMO_VERSAO_COFINS
