"""Golden tests do IRRF mensal (Sprint 10 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_irrf import (
    ALGORITMO_VERSAO,
    FaixaIrrf,
    calcular_irrf_mensal,
)

# Faixas vigentes (Lei 14.848/2024 + MP 1.171/2024, vigência fev/2024).
DEP = Decimal("189.59")
FAIXAS_VIGENTES = [
    FaixaIrrf(faixa=1, base_ate=Decimal("2259.20"), aliquota=Decimal("0.0000"),
              parcela_deduzir=Decimal("0.00"), deducao_dependente=DEP),
    FaixaIrrf(faixa=2, base_ate=Decimal("2826.65"), aliquota=Decimal("0.0750"),
              parcela_deduzir=Decimal("169.44"), deducao_dependente=DEP),
    FaixaIrrf(faixa=3, base_ate=Decimal("3751.05"), aliquota=Decimal("0.1500"),
              parcela_deduzir=Decimal("381.44"), deducao_dependente=DEP),
    FaixaIrrf(faixa=4, base_ate=Decimal("4664.68"), aliquota=Decimal("0.2250"),
              parcela_deduzir=Decimal("662.77"), deducao_dependente=DEP),
    FaixaIrrf(faixa=5, base_ate=Decimal("999999999.99"), aliquota=Decimal("0.2750"),
              parcela_deduzir=Decimal("896.00"), deducao_dependente=DEP),
]


class TestGoldenSemDependentes:
    def test_salario_baixo_isento(self) -> None:
        # base = 2000 − 150 (inss) − 0 = 1850 → faixa 1 (isenta)
        r = calcular_irrf_mensal(
            Decimal("2000.00"), Decimal("150.00"), 0, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("0.00")
        assert r.faixa == 1

    def test_salario_3000_faixa_2(self) -> None:
        # INSS de 3000 = 253,41; base = 3000 − 253,41 = 2746,59 → faixa 2
        # IRRF = 2746,59 × 7,5% − 169,44 = 205,9942 − 169,44 = 36,5542 → 36,55
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 2
        assert r.base_irrf == Decimal("2746.59")
        assert r.irrf == Decimal("36.55")

    def test_salario_5000_faixa_4(self) -> None:
        # INSS de 5000 = 509,60; base = 5000 − 509,60 = 4490,40 → faixa 4
        # IRRF = 4490,40 × 22,5% − 662,77 = 1010,34 − 662,77 = 347,57
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("509.60"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 4
        assert r.base_irrf == Decimal("4490.40")
        assert r.irrf == Decimal("347.57")

    def test_salario_alto_faixa_5(self) -> None:
        # INSS teto 951,63; base = 15000 − 951,63 = 14048,37 → faixa 5
        # IRRF = 14048,37 × 27,5% − 896,00 = 3863,30175 − 896 = 2967,30175 → 2967,30
        r = calcular_irrf_mensal(
            Decimal("15000.00"), Decimal("951.63"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 5
        assert r.irrf == Decimal("2967.30")


class TestGoldenComDependentes:
    def test_dependente_reduz_base(self) -> None:
        # Salário 3000, INSS 253,41, 2 deps
        # base = 3000 − 253,41 − (2 × 189,59) = 3000 − 253,41 − 379,18 = 2367,41
        # faixa 2: IRRF = 2367,41 × 7,5% − 169,44 = 177,55575 − 169,44
        #                = 8,11575 → 8,12
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 2, FAIXAS_VIGENTES
        )
        assert r.dependentes == 2
        assert r.deducao_dependentes == Decimal("379.18")
        assert r.base_irrf == Decimal("2367.41")
        assert r.faixa == 2
        assert r.irrf == Decimal("8.12")

    def test_muitos_dependentes_zera_irrf(self) -> None:
        # 5 deps × 189,59 = 947,95 → base = 3000 − 253,41 − 947,95 = 1798,64
        # → faixa 1 → IRRF = 0
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 5, FAIXAS_VIGENTES
        )
        assert r.faixa == 1
        assert r.irrf == Decimal("0.00")


class TestBordas:
    def test_salario_zero(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("0"), Decimal("0"), 0, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("0.00")
        assert r.base_irrf == Decimal("0.00")
        assert r.faixa == 1

    def test_base_negativa_vira_zero(self) -> None:
        # INSS + dependentes superam o bruto — base clampa em zero
        r = calcular_irrf_mensal(
            Decimal("1000"), Decimal("75"), 10, FAIXAS_VIGENTES
        )
        assert r.base_irrf == Decimal("0.00")
        assert r.irrf == Decimal("0.00")
        assert r.faixa == 1

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario_bruto não pode"):
            calcular_irrf_mensal(
                Decimal("-1"), Decimal("0"), 0, FAIXAS_VIGENTES
            )

    def test_inss_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="inss_empregado não pode"):
            calcular_irrf_mensal(
                Decimal("1000"), Decimal("-1"), 0, FAIXAS_VIGENTES
            )

    def test_dependentes_negativos_levanta(self) -> None:
        with pytest.raises(ValueError, match="dependentes não pode"):
            calcular_irrf_mensal(
                Decimal("1000"), Decimal("0"), -1, FAIXAS_VIGENTES
            )

    def test_faixas_vazias_levanta(self) -> None:
        with pytest.raises(ValueError, match="faixas não pode"):
            calcular_irrf_mensal(Decimal("3000"), Decimal("253"), 0, [])


class TestEstrutura:
    def test_algoritmo_versao(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_aceita_faixas_fora_de_ordem(self) -> None:
        embaralhadas = list(reversed(FAIXAS_VIGENTES))
        r1 = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        r2 = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, embaralhadas
        )
        assert r1 == r2
