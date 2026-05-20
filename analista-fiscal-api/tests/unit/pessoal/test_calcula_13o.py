"""Golden tests do 13º salário — 1ª e 2ª parcelas (Sprint 10 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_13o import (
    ALGORITMO_VERSAO,
    calcular_13o_primeira,
    calcular_13o_segunda,
)
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS


class TestPrimeiraParcela:
    def test_ano_completo_3000(self) -> None:
        # avos=12: base = 3000 × 12/12 = 3000; primeira = 1500
        r = calcular_13o_primeira(Decimal("3000.00"), 12)
        assert r.base_proporcional == Decimal("3000.00")
        assert r.valor_primeira_parcela == Decimal("1500.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_proporcional_8_meses(self) -> None:
        # avos=8: base = 3000 × 8/12 = 2000; primeira = 1000
        r = calcular_13o_primeira(Decimal("3000.00"), 8)
        assert r.base_proporcional == Decimal("2000.00")
        assert r.valor_primeira_parcela == Decimal("1000.00")

    def test_um_mes_apenas(self) -> None:
        # avos=1: base = 3000/12 = 250; primeira = 125
        r = calcular_13o_primeira(Decimal("3000.00"), 1)
        assert r.base_proporcional == Decimal("250.00")
        assert r.valor_primeira_parcela == Decimal("125.00")

    def test_salario_zero(self) -> None:
        r = calcular_13o_primeira(Decimal("0"), 12)
        assert r.valor_primeira_parcela == Decimal("0.00")

    def test_avos_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="avos deve estar entre"):
            calcular_13o_primeira(Decimal("3000"), 0)

    def test_avos_treze_levanta(self) -> None:
        with pytest.raises(ValueError, match="avos deve estar entre"):
            calcular_13o_primeira(Decimal("3000"), 13)

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario não pode"):
            calcular_13o_primeira(Decimal("-1"), 12)


class TestSegundaParcela:
    def test_ano_completo_3000_sem_dep(self) -> None:
        # base = 3000; INSS escalonado: 253,41; IRRF: base 2746,59 × 7,5% − 169,44 = 36,55
        # primeira paga = 1500; segunda = 3000 − 1500 − 253,41 − 36,55 = 1210,04
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.base_proporcional == Decimal("3000.00")
        assert r.inss.inss == Decimal("253.41")
        assert r.irrf.irrf == Decimal("36.55")
        assert r.valor_segunda_parcela == Decimal("1210.04")

    def test_proporcional_6_meses_5000_com_1_dep(self) -> None:
        # avos=6: base = 5000 × 6/12 = 2500
        # INSS sobre 2500: 1518×7,5% + (2500−1518)×9% = 113,85 + 88,38 = 202,23
        # IRRF: base = 2500 − 202,23 − 189,59 = 2108,18 → faixa 1 → 0
        # primeira paga = 1250; segunda = 2500 − 1250 − 202,23 − 0 = 1047,77
        r = calcular_13o_segunda(
            salario=Decimal("5000.00"),
            avos=6,
            primeira_parcela_paga=Decimal("1250.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=1,
        )
        assert r.base_proporcional == Decimal("2500.00")
        assert r.inss.inss == Decimal("202.23")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.valor_segunda_parcela == Decimal("1047.77")

    def test_salario_alto_acima_teto(self) -> None:
        # avos=12, salario 15000 → base = 15000; INSS teto 951,63
        # IRRF: base = 15000 − 951,63 = 14048,37 → faixa 5 → 14048,37×27,5%−896 = 2967,30
        # primeira = 7500; segunda = 15000 − 7500 − 951,63 − 2967,30 = 3581,07
        r = calcular_13o_segunda(
            salario=Decimal("15000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("7500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.inss.inss == Decimal("951.63")
        assert r.inss.teto_aplicado is True
        assert r.irrf.irrf == Decimal("2967.30")
        assert r.valor_segunda_parcela == Decimal("3581.07")

    def test_primeira_diferente_da_metade(self) -> None:
        # base 3000, primeira paga 1000 (em vez de 1500): segunda = 3000 − 1000 − 253,41 − 36,55 = 1710,04
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1000.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_segunda_parcela == Decimal("1710.04")

    def test_primeira_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="primeira_parcela_paga"):
            calcular_13o_segunda(
                salario=Decimal("3000"),
                avos=12,
                primeira_parcela_paga=Decimal("-1"),
                faixas_inss=INSS_FAIXAS,
                faixas_irrf=IRRF_FAIXAS,
                dependentes=0,
            )

    def test_versao(self) -> None:
        r = calcular_13o_segunda(
            salario=Decimal("3000"),
            avos=12,
            primeira_parcela_paga=Decimal("1500"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO
