"""Golden tests do pró-labore — INSS 11% + IRRF (Sprint 10 PR3 + redutor Lei 15.270/2025)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_prolabore import (
    ALGORITMO_VERSAO,
    calcular_prolabore,
)
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS
from tests.unit.pessoal.test_calcula_irrf_2026 import FAIXAS_2026 as IRRF_FAIXAS_2026

TETO_2025 = Decimal("8157.41")
TETO_2026 = Decimal("8475.55")  # Portaria MPS/MF 13/2026


class TestProlaboreAbaixoTeto:
    def test_3000_sem_dep(self) -> None:
        # INSS = 3000 × 11% = 330,00
        # IRRF_legal: base = 3000 − 330 = 2670 → faixa 2 → 2670×7,5%−169,44 = 30,81
        # IRRF_simpl: base = 2435,20 (3000−564,80) → faixa 2 → 13,20
        # min(30,81 ; 13,20) = 13,20 → SIMPLIFICADO (FA2 M5)
        # Líquido = 3000 − 330 − 13,20 = 2656,80
        r = calcular_prolabore(
            valor_bruto=Decimal("3000.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.teto_aplicado is False
        assert r.base_inss == Decimal("3000.00")
        assert r.inss_socio == Decimal("330.00")
        assert r.irrf.irrf == Decimal("13.20")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_liquido == Decimal("2656.80")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_5000_com_2_dep(self) -> None:
        # INSS = 5000 × 11% = 550
        # IRRF base = 5000 − 550 − 379,18 = 4070,82 → faixa 4 → 4070,82×22,5%−662,77
        #   = 915,9345 − 662,77 = 253,1645 → 253,16
        # Líquido = 5000 − 550 − 253,16 = 4196,84
        r = calcular_prolabore(
            valor_bruto=Decimal("5000.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=2,
        )
        assert r.inss_socio == Decimal("550.00")
        assert r.irrf.irrf == Decimal("253.16")
        assert r.valor_liquido == Decimal("4196.84")

    def test_salario_minimo_isento(self) -> None:
        # 1518 × 11% = 166,98; IRRF base = 1518 − 166,98 = 1351,02 → faixa 1 → 0
        r = calcular_prolabore(
            valor_bruto=Decimal("1518.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.inss_socio == Decimal("166.98")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.valor_liquido == Decimal("1351.02")


class TestProlaboreAcimaTeto:
    def test_15000_capa_no_teto(self) -> None:
        # INSS = 8157,41 × 11% = 897,3151 → 897,32
        # IRRF base = 15000 − 897,32 = 14102,68 → faixa 5 → 14102,68×27,5%−896
        #   = 3878,237 − 896 = 2982,237 → 2982,24
        # Líquido = 15000 − 897,32 − 2982,24 = 11120,44
        r = calcular_prolabore(
            valor_bruto=Decimal("15000.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.teto_aplicado is True
        assert r.base_inss == TETO_2025
        assert r.inss_socio == Decimal("897.32")
        assert r.irrf.irrf == Decimal("2982.24")
        assert r.valor_liquido == Decimal("11120.44")

    def test_exatamente_no_teto(self) -> None:
        r = calcular_prolabore(
            valor_bruto=TETO_2025,
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.teto_aplicado is False
        assert r.base_inss == TETO_2025


class TestAliquotaCustomizada:
    def test_aliquota_20pct(self) -> None:
        # Plano normal contribuinte individual (20%) — uso em sócio que não
        # opte pelo plano simplificado.
        r = calcular_prolabore(
            valor_bruto=Decimal("3000"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
            aliquota_inss=Decimal("0.2000"),
        )
        assert r.inss_socio == Decimal("600.00")
        assert r.aliquota_inss == Decimal("0.2000")


class TestBordas:
    def test_bruto_zero(self) -> None:
        r = calcular_prolabore(
            valor_bruto=Decimal("0"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.inss_socio == Decimal("0.00")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.valor_liquido == Decimal("0.00")

    def test_bruto_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="valor_bruto"):
            calcular_prolabore(
                Decimal("-1"), TETO_2025, IRRF_FAIXAS, 0
            )

    def test_teto_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="teto_previdenciario"):
            calcular_prolabore(
                Decimal("3000"), Decimal("0"), IRRF_FAIXAS, 0
            )

    def test_aliquota_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="aliquota_inss"):
            calcular_prolabore(
                Decimal("3000"), TETO_2025, IRRF_FAIXAS, 0,
                aliquota_inss=Decimal("-0.01"),
            )

    def test_dependentes_negativos_levanta(self) -> None:
        with pytest.raises(ValueError, match="dependentes"):
            calcular_prolabore(
                Decimal("3000"), TETO_2025, IRRF_FAIXAS, -1
            )

    def test_versao_bumped(self) -> None:
        assert ALGORITMO_VERSAO == "prolabore.v2"


class TestProlaboreReductor2026:
    """Goldens de pró-labore com redutor Lei 15.270/2025 (competências ≥ 2026-01-01).

    Referência do redutor = valor_bruto (rendimento tributável bruto do sócio).
    Todos os valores conferidos à mão (ROUND_HALF_EVEN).
    """

    def test_prolabore_4500_isento_redutor_2026(self) -> None:
        # Pró-labore 4500 ≤ 5000 → redutor zera o IRRF.
        # INSS = 4500 × 11% = 495,00 (plano simplificado — alíquota plana)
        # IRRF tradicional:
        #   base_legal = 4500 − 495,00 = 4005,00 → F4 (≤ 4664,68) → 4005×22,5%−675,49 = 901,125−675,49 = 225,64
        #   base_simpl = 4500 − 607,20 = 3892,80 → F4 → 3892,80×22,5%−675,49 = 875,88−675,49 = 200,39
        #   min(225,64; 200,39) = 200,39 → simplificado
        # Redutor: 4500 ≤ 5000 → zera → irrf_final = 0,00
        # Líquido = 4500 − 495,00 − 0,00 = 4005,00
        r = calcular_prolabore(
            valor_bruto=Decimal("4500.00"),
            teto_previdenciario=TETO_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            dependentes=0,
            aplicar_redutor_lei_15270=True,
        )
        assert r.inss_socio == Decimal("495.00")
        assert r.irrf.irrf_tradicional == Decimal("200.39")
        assert r.irrf.redutor_lei_15270 == Decimal("200.39")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_liquido == Decimal("4005.00")

    def test_prolabore_6500_redutor_linear_2026(self) -> None:
        # Pró-labore 6500, 5000 < 6500 ≤ 7350 → faixa linear.
        # INSS = 6500 × 11% = 715,00 (abaixo do teto 8475,55)
        # IRRF tradicional:
        #   base_legal = 6500 − 715,00 = 5785,00 → F5
        #     5785 × 27,5% − 908,73 = 1590,875 − 908,73 = 682,145 → 682,14
        #     (ROUND_HALF_EVEN: dígito antes do 5 é 4, par → não arredonda)
        #   base_simpl = 6500 − 607,20 = 5892,80 → F5 → 1620,52 − 908,73 = 711,79
        #   min(682,14; 711,79) = 682,14 → legal
        # Redutor: 978,62 − 0,133145×6500 = 978,62 − 865,4425 = 113,1775 → 113,18
        #   (ROUND_HALF_EVEN: dígito antes do 5 é 7, ímpar → arredonda para cima)
        # irrf_final = 682,14 − 113,18 = 568,96
        # Líquido = 6500 − 715,00 − 568,96 = 5216,04
        r = calcular_prolabore(
            valor_bruto=Decimal("6500.00"),
            teto_previdenciario=TETO_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            dependentes=0,
            aplicar_redutor_lei_15270=True,
        )
        assert r.inss_socio == Decimal("715.00")
        assert r.irrf.irrf_tradicional == Decimal("682.14")
        assert r.irrf.redutor_lei_15270 == Decimal("113.18")
        assert r.irrf.irrf == Decimal("568.96")
        assert r.irrf.metodo == "legal"
        assert r.valor_liquido == Decimal("5216.04")

    def test_prolabore_10000_acima_teto_redutor_2026(self) -> None:
        # Pró-labore 10000 > 7350 → sem redutor (tabela cheia).
        # INSS: 10000 > teto_2026 8475,55 → teto_aplicado → base_inss = 8475,55
        #   inss = 8475,55 × 11% = 932,3105 → 932,31
        # IRRF tradicional:
        #   base_legal = 10000 − 932,31 = 9067,69 → F5 → 9067,69×27,5%−908,73 = 2493,6148−908,73 = 1584,88
        #   base_simpl = 10000 − 607,20 = 9392,80 → F5 → 9392,80×27,5%−908,73 = 2583,02−908,73 = 1674,29
        #   min(1584,88; 1674,29) = 1584,88 → legal; redutor = 0 (> 7350)
        # Líquido = 10000 − 932,31 − 1584,88 = 7482,81
        r = calcular_prolabore(
            valor_bruto=Decimal("10000.00"),
            teto_previdenciario=TETO_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            dependentes=0,
            aplicar_redutor_lei_15270=True,
        )
        assert r.teto_aplicado is True
        assert r.inss_socio == Decimal("932.31")
        assert r.irrf.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf.irrf == Decimal("1584.88")
        assert r.irrf.metodo == "legal"
        assert r.valor_liquido == Decimal("7482.81")

    def test_2025_nao_aplica_redutor_prolabore(self) -> None:
        # Default False → sem redutor; goldens 2025 inalterados.
        r = calcular_prolabore(
            valor_bruto=Decimal("4500.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.irrf.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf.irrf > Decimal("0.00")
