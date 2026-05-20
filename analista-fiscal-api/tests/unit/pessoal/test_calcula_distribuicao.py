"""Golden tests de distribuição de lucros (Sprint 10 PR3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_distribuicao import (
    ALGORITMO_VERSAO,
    BaseCalculoReferencia,
    calcular_distribuicao,
)
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS


class TestDentroDoLimite:
    def test_simples_dentro_das_isento_integral(self) -> None:
        r = calcular_distribuicao(
            valor_distribuido=Decimal("50000.00"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.SIMPLES_DENTRO_DAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("50000.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        assert r.irrf_excedente is None
        assert r.valor_liquido_socio == Decimal("50000.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_lp_exatamente_no_limite(self) -> None:
        r = calcular_distribuicao(
            valor_distribuido=Decimal("100000.00"),
            limite_isento_apurado=Decimal("100000.00"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("100000.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("100000.00")

    def test_mei_pequeno_valor_isento(self) -> None:
        r = calcular_distribuicao(
            valor_distribuido=Decimal("2000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.MEI,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("2000.00")
        assert r.valor_tributavel == Decimal("0.00")


class TestExcedente:
    def test_excedente_baixo_isento_irrf(self) -> None:
        # Excedente 2000 → faixa 1 IRRF → 0
        r = calcular_distribuicao(
            valor_distribuido=Decimal("12000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("10000.00")
        assert r.valor_tributavel == Decimal("2000.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 1
        assert r.irrf_retido == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("12000.00")

    def test_excedente_alto_irrf_faixa5(self) -> None:
        # Excedente 15000 → sem INSS → base IRRF = 15000 → faixa 5
        # IRRF = 15000 × 27,5% − 896 = 4125 − 896 = 3229
        r = calcular_distribuicao(
            valor_distribuido=Decimal("25000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("10000.00")
        assert r.valor_tributavel == Decimal("15000.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 5
        assert r.irrf_retido == Decimal("3229.00")
        # Líquido = 25000 − 3229 = 21771
        assert r.valor_liquido_socio == Decimal("21771.00")

    def test_excedente_com_dependentes(self) -> None:
        # Excedente 5000, 3 deps × 189,59 = 568,77 → base IRRF = 5000 − 568,77 = 4431,23
        # Faixa 4: 4431,23×22,5%−662,77 = 997,02675 − 662,77 = 334,25675 → 334,26
        r = calcular_distribuicao(
            valor_distribuido=Decimal("15000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=3,
        )
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 4
        assert r.irrf_retido == Decimal("334.26")
        assert r.valor_liquido_socio == Decimal("15000") - Decimal("334.26")


class TestLimiteZero:
    def test_limite_zero_tudo_tributavel(self) -> None:
        # Sem lucro contábil — tudo vira excedente tributável
        r = calcular_distribuicao(
            valor_distribuido=Decimal("3000"),
            limite_isento_apurado=Decimal("0"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("0.00")
        assert r.valor_tributavel == Decimal("3000.00")
        # 3000 → faixa 3 (2826,65 < 3000 ≤ 3751,05) → 3000×15% − 381,44
        #   = 450 − 381,44 = 68,56
        assert r.irrf_retido == Decimal("68.56")


class TestBordas:
    def test_valor_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="valor_distribuido"):
            calcular_distribuicao(
                Decimal("-1"), Decimal("100"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
            )

    def test_limite_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="limite_isento"):
            calcular_distribuicao(
                Decimal("100"), Decimal("-1"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
            )

    def test_dependentes_negativos_levanta(self) -> None:
        with pytest.raises(ValueError, match="dependentes"):
            calcular_distribuicao(
                Decimal("100"), Decimal("100"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, -1,
            )

    def test_zero_distribuicao(self) -> None:
        r = calcular_distribuicao(
            Decimal("0"), Decimal("100"),
            BaseCalculoReferencia.LUCRO_CONTABIL,
            IRRF_FAIXAS, 0,
        )
        assert r.valor_isento == Decimal("0.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("0.00")
