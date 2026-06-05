"""Golden tests de distribuição de lucros (Sprint 10 PR3).

FA8 m6 (2026-06-04): adicionados testes que confirmam que valor_tributavel
é quantizado (2 casas) antes de ser passado ao IRRF. Garante que bases com
>2 casas decimais (de receita×presunção) não causam centavo divergente.
ALGORITMO_VERSAO bumped para "distribuicao.v2".
"""

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
        # Excedente 15000 → sem INSS → deps=0
        # IRRF_legal: base=15000→faixa 5→15000×27,5%−896=3229
        # IRRF_simpl: base=15000−564,80=14435,20→faixa 5→14435,20×27,5%−896=3073,68
        # min(3229 ; 3073,68) = 3073,68 → SIMPLIFICADO (FA2 M5)
        # Líquido = 25000 − 3073,68 = 21926,32
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
        assert r.irrf_retido == Decimal("3073.68")
        assert r.irrf_excedente.metodo == "simplificado"
        # Líquido = 25000 − 3073,68 = 21926,32
        assert r.valor_liquido_socio == Decimal("21926.32")

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
        # IRRF_legal: 3000 → faixa 3 → 3000×15%−381,44 = 68,56
        # IRRF_simpl: base=2435,20 → faixa 2 → 2435,20×7,5%−169,44 = 13,20
        # min(68,56 ; 13,20) = 13,20 → SIMPLIFICADO (FA2 M5)
        r = calcular_distribuicao(
            valor_distribuido=Decimal("3000"),
            limite_isento_apurado=Decimal("0"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("0.00")
        assert r.valor_tributavel == Decimal("3000.00")
        assert r.irrf_retido == Decimal("13.20")


class TestM6Quantizacao:
    """m6 FA8: valor_tributavel quantizado antes de ir ao IRRF.

    Cenário reproduzível: limite_isento_apurado gerado por
    calcula_limite_isento pode ter >2 casas decimais (e.g.,
    100.000 × 0.32 = 32.000 — mas casos com presunção não-redonda
    como 0.0800 × receita ou combinações geram dízimas).
    O fix garante que a base do IRRF seja sempre truncada em 2 casas.
    """

    def test_limite_isento_com_multiplas_casas_decimais(self) -> None:
        """Limite com >2 casas não contamina base do IRRF (m6 FA8).

        limite_isento_apurado = 9999.999 (3 casas — simula saída de
        receita × presunção não-quantizada). Excedente = 0.001 → quantizado
        a 0.00 → IRRF zero (isento). Sem fix, 0.001 poderia ser passado ao
        IRRF gerando resultado não-determinístico.
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("10000.00"),
            limite_isento_apurado=Decimal("9999.999"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        # valor_tributavel deve ser quantizado: 10000.00 − 9999.999 = 0.001
        # → round HALF_EVEN → 0.00 → sem IRRF
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        assert r.irrf_excedente is None

    def test_limite_com_3_casas_gera_tributavel_quantizado(self) -> None:
        """Excedente com casas extras é quantizado corretamente (m6 FA8).

        valor_distribuido = 15000.00
        limite_isento     =  9999.005 (3 casas)
        excedente bruto   =  5000.995 → quantizado → 5001.00
        IRRF sobre 5001.00 (faixa 4): 5001×22,5% − 662,77 = 1125,225−662,77 = 462,455 → 462,46
        Simplificado: base=5001−564,80=4436,20 → faixa 4 → 4436,20×22,5%−662,77
                       = 998,145−662,77 = 335,375 → 335,38
        min(462,46 ; 335,38) = 335,38 → simplificado
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("15000.00"),
            limite_isento_apurado=Decimal("9999.005"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_tributavel == Decimal("5001.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 4
        # Chave: valor_tributavel é Decimal com exatamente 2 casas
        assert r.valor_tributavel.as_tuple().exponent == -2

    def test_versao_v2(self) -> None:
        """ALGORITMO_VERSAO bumped para v2 pelo fix m6 FA8."""
        assert ALGORITMO_VERSAO == "distribuicao.v2"


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
