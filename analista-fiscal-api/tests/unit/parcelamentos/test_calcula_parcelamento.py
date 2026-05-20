"""Golden tests do parcelamento ordinário (Sprint 11 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.parcelamentos.calcula_parcelamento import (
    ALGORITMO_VERSAO,
    TipoContribuinte,
    gerar_parcelamento_ordinario,
)


class TestCronogramaBasico:
    def test_60k_em_60_parcelas(self) -> None:
        # 60.000 / 60 = 1.000 por parcela
        r = gerar_parcelamento_ordinario(
            Decimal("60000.00"), 60, date(2026, 5, 15),
        )
        assert r.parcela_base == Decimal("1000.00")
        assert len(r.parcelas) == 60
        assert r.parcelas[0].numero == 1
        assert r.parcelas[0].vencimento == date(2026, 6, 15)
        assert r.parcelas[-1].numero == 60
        # 60 meses após maio/2026 = maio/2031
        assert r.parcelas[-1].vencimento == date(2031, 5, 15)
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_24_parcelas_quebrado(self) -> None:
        # 50.000 / 24 = 2.083,3333... → 2.083,33
        r = gerar_parcelamento_ordinario(
            Decimal("50000.00"), 24, date(2026, 1, 10),
        )
        assert r.parcela_base == Decimal("2083.33")
        assert len(r.parcelas) == 24

    def test_uma_parcela_unica(self) -> None:
        # Dívida pequena em parcela única
        r = gerar_parcelamento_ordinario(
            Decimal("500.00"), 1, date(2026, 3, 5),
        )
        assert r.parcela_base == Decimal("500.00")
        assert len(r.parcelas) == 1
        assert r.parcelas[0].vencimento == date(2026, 4, 5)


class TestParcelaMinimaPJ:
    def test_atinge_minima_exato(self) -> None:
        # 12.000 / 60 = 200 (exato — limite)
        r = gerar_parcelamento_ordinario(
            Decimal("12000.00"), 60, date(2026, 1, 1),
        )
        assert r.parcela_base == Decimal("200.00")
        assert r.parcela_minima_aplicavel == Decimal("200.00")

    def test_abaixo_minima_levanta(self) -> None:
        # 11.000 / 60 = 183,33 < 200
        with pytest.raises(ValueError, match="parcela_base.*200"):
            gerar_parcelamento_ordinario(
                Decimal("11000.00"), 60, date(2026, 1, 1),
            )


class TestParcelaMinimaPF:
    def test_pf_minima_100(self) -> None:
        # 6.000 / 60 = 100 (exato PF)
        r = gerar_parcelamento_ordinario(
            Decimal("6000.00"), 60, date(2026, 1, 1),
            contribuinte=TipoContribuinte.PF,
        )
        assert r.parcela_base == Decimal("100.00")
        assert r.parcela_minima_aplicavel == Decimal("100.00")

    def test_pf_abaixo_minima_levanta(self) -> None:
        with pytest.raises(ValueError, match="parcela_base.*100"):
            gerar_parcelamento_ordinario(
                Decimal("5000.00"), 60, date(2026, 1, 1),
                contribuinte=TipoContribuinte.PF,
            )


class TestDiaSemEquivalente:
    def test_31_janeiro_vai_para_28_fevereiro(self) -> None:
        # Adesão em 31/jan/2026 (não bissexto): 1ª parcela em 28/fev
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 12, date(2026, 1, 31),
        )
        assert r.parcelas[0].vencimento == date(2026, 2, 28)
        assert r.parcelas[1].vencimento == date(2026, 3, 31)

    def test_31_janeiro_em_ano_bissexto_vai_para_29(self) -> None:
        # 2024 é bissexto; usar 2024 para testar
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 12, date(2024, 1, 31),
        )
        assert r.parcelas[0].vencimento == date(2024, 2, 29)

    def test_atravessa_ano(self) -> None:
        # Adesão dez/2026 → 1ª em jan/2027
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 3, date(2026, 12, 10),
        )
        assert r.parcelas[0].vencimento == date(2027, 1, 10)
        assert r.parcelas[1].vencimento == date(2027, 2, 10)
        assert r.parcelas[2].vencimento == date(2027, 3, 10)


class TestBordas:
    def test_divida_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="divida_consolidada"):
            gerar_parcelamento_ordinario(
                Decimal("0"), 10, date(2026, 1, 1),
            )

    def test_divida_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="divida_consolidada"):
            gerar_parcelamento_ordinario(
                Decimal("-1"), 10, date(2026, 1, 1),
            )

    def test_num_parcelas_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="num_parcelas"):
            gerar_parcelamento_ordinario(
                Decimal("1000"), 0, date(2026, 1, 1),
            )

    def test_num_parcelas_61_levanta(self) -> None:
        with pytest.raises(ValueError, match="num_parcelas"):
            gerar_parcelamento_ordinario(
                Decimal("100000"), 61, date(2026, 1, 1),
            )
