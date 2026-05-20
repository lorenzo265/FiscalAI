"""Golden tests do pró-labore — INSS 11% + IRRF (Sprint 10 PR3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_prolabore import (
    ALGORITMO_VERSAO,
    calcular_prolabore,
)
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS

TETO_2025 = Decimal("8157.41")


class TestProlaboreAbaixoTeto:
    def test_3000_sem_dep(self) -> None:
        # INSS = 3000 × 11% = 330,00
        # IRRF base = 3000 − 330 = 2670 → faixa 2 → 2670×7,5%−169,44 = 200,25 − 169,44 = 30,81
        # Líquido = 3000 − 330 − 30,81 = 2639,19
        r = calcular_prolabore(
            valor_bruto=Decimal("3000.00"),
            teto_previdenciario=TETO_2025,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.teto_aplicado is False
        assert r.base_inss == Decimal("3000.00")
        assert r.inss_socio == Decimal("330.00")
        assert r.irrf.irrf == Decimal("30.81")
        assert r.valor_liquido == Decimal("2639.19")
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
