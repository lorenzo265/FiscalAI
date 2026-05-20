"""Golden tests do INSS empregado escalonado (Sprint 10 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_inss import (
    ALGORITMO_VERSAO,
    FaixaInss,
    calcular_inss_empregado,
)

# Faixas vigentes em 2025 (Portaria MPS/MF nº 6/2025).
FAIXAS_2025 = [
    FaixaInss(faixa=1, valor_ate=Decimal("1518.00"), aliquota=Decimal("0.0750")),
    FaixaInss(faixa=2, valor_ate=Decimal("2793.88"), aliquota=Decimal("0.0900")),
    FaixaInss(faixa=3, valor_ate=Decimal("4190.83"), aliquota=Decimal("0.1200")),
    FaixaInss(faixa=4, valor_ate=Decimal("8157.41"), aliquota=Decimal("0.1400")),
]


class TestGoldenIntraFaixa:
    """Salários cujo cálculo termina dentro de uma faixa específica."""

    def test_salario_minimo_so_faixa_1(self) -> None:
        # 1518,00 × 7,5% = 113,85
        r = calcular_inss_empregado(Decimal("1518.00"), FAIXAS_2025)
        assert r.inss == Decimal("113.85")
        assert r.teto_aplicado is False
        assert r.aliquota_efetiva == Decimal("0.0750")

    def test_salario_3000_atinge_faixa_3(self) -> None:
        # 1518,00 × 7,5%               = 113,8500
        # (2793,88 − 1518,00) × 9%     = 114,8292
        # (3000,00 − 2793,88) × 12%    =  24,7344
        #                          ----------
        #                          253,4136 → 253,41
        r = calcular_inss_empregado(Decimal("3000.00"), FAIXAS_2025)
        assert r.inss == Decimal("253.41")
        assert r.teto_aplicado is False

    def test_salario_5000_atinge_faixa_4(self) -> None:
        # 113,8500 + 114,8292 + 167,6340 + (5000−4190,83)×0,14
        # = 113,8500 + 114,8292 + 167,6340 + 113,2838 = 509,5970 → 509,60
        r = calcular_inss_empregado(Decimal("5000.00"), FAIXAS_2025)
        assert r.inss == Decimal("509.60")

    def test_salario_8157_41_teto_exato(self) -> None:
        # 113,8500 + 114,8292 + 167,6340 + 555,3212 = 951,6344 → 951,63
        r = calcular_inss_empregado(Decimal("8157.41"), FAIXAS_2025)
        assert r.inss == Decimal("951.63")
        assert r.teto_aplicado is False


class TestGoldenTeto:
    """Salários acima do teto ficam capados na faixa 4."""

    def test_salario_acima_teto_capa(self) -> None:
        r = calcular_inss_empregado(Decimal("12000.00"), FAIXAS_2025)
        assert r.inss == Decimal("951.63")
        assert r.teto_aplicado is True

    def test_salario_muito_acima_teto(self) -> None:
        r = calcular_inss_empregado(Decimal("50000.00"), FAIXAS_2025)
        assert r.inss == Decimal("951.63")
        assert r.teto_aplicado is True

    def test_aliquota_efetiva_teto(self) -> None:
        r = calcular_inss_empregado(Decimal("12000.00"), FAIXAS_2025)
        # 951,63 / 12000 = 0,07930... → 0,0793 com ROUND_HALF_EVEN
        assert r.aliquota_efetiva == Decimal("0.0793")


class TestBordas:
    def test_salario_zero(self) -> None:
        r = calcular_inss_empregado(Decimal("0"), FAIXAS_2025)
        assert r.inss == Decimal("0.00")
        assert r.aliquota_efetiva == Decimal("0")
        assert r.teto_aplicado is False

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="não pode ser negativo"):
            calcular_inss_empregado(Decimal("-1"), FAIXAS_2025)

    def test_faixas_vazias_levanta(self) -> None:
        with pytest.raises(ValueError, match="faixas não pode ser vazia"):
            calcular_inss_empregado(Decimal("1000"), [])

    def test_limite_inferior_faixa2_exato(self) -> None:
        # Salário exatamente 1518,01 — faixa 2 contribui só 1 centavo
        # 113,85 + 0,01 × 9% = 113,85 + 0,0009 = 113,8509 → 113,85
        r = calcular_inss_empregado(Decimal("1518.01"), FAIXAS_2025)
        assert r.inss == Decimal("113.85")


class TestEstrutura:
    def test_algoritmo_versao(self) -> None:
        r = calcular_inss_empregado(Decimal("3000"), FAIXAS_2025)
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_determinismo(self) -> None:
        r1 = calcular_inss_empregado(Decimal("4567.89"), FAIXAS_2025)
        r2 = calcular_inss_empregado(Decimal("4567.89"), FAIXAS_2025)
        assert r1 == r2

    def test_aceita_faixas_fora_de_ordem(self) -> None:
        # Função ordena internamente — input embaralhado deve dar mesmo resultado.
        embaralhadas = [FAIXAS_2025[3], FAIXAS_2025[0], FAIXAS_2025[2], FAIXAS_2025[1]]
        r_ord = calcular_inss_empregado(Decimal("3500"), FAIXAS_2025)
        r_emb = calcular_inss_empregado(Decimal("3500"), embaralhadas)
        assert r_ord == r_emb
