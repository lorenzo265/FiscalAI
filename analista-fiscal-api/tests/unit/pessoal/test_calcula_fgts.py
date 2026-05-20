"""Golden tests do FGTS (Sprint 10 PR1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_fgts import ALGORITMO_VERSAO, calcular_fgts


class TestGolden:
    def test_clt_8pct(self) -> None:
        r = calcular_fgts(Decimal("3000.00"), Decimal("0.0800"))
        assert r.fgts == Decimal("240.00")
        assert r.aliquota == Decimal("0.0800")
        assert r.vinculo == "clt"

    def test_clt_salario_quebrado(self) -> None:
        # 3567,89 × 8% = 285,4312 → 285,43
        r = calcular_fgts(Decimal("3567.89"), Decimal("0.0800"))
        assert r.fgts == Decimal("285.43")

    def test_jovem_aprendiz_2pct(self) -> None:
        r = calcular_fgts(
            Decimal("1500.00"), Decimal("0.0200"), vinculo="jovem_aprendiz"
        )
        assert r.fgts == Decimal("30.00")
        assert r.vinculo == "jovem_aprendiz"

    def test_salario_zero(self) -> None:
        r = calcular_fgts(Decimal("0"), Decimal("0.0800"))
        assert r.fgts == Decimal("0.00")


class TestBordas:
    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario_bruto"):
            calcular_fgts(Decimal("-1"), Decimal("0.0800"))

    def test_aliquota_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="aliquota"):
            calcular_fgts(Decimal("1000"), Decimal("-0.01"))


class TestEstrutura:
    def test_algoritmo_versao(self) -> None:
        r = calcular_fgts(Decimal("1000"), Decimal("0.0800"))
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_arredondamento_half_even(self) -> None:
        # 12,345 × 0,08 = 0,9876 → 0,99 (ROUND_HALF_EVEN: 0,9876 → 0,99)
        r = calcular_fgts(Decimal("12.345"), Decimal("0.0800"))
        assert r.fgts == Decimal("0.99")
