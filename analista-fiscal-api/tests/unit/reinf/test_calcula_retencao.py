"""Golden tests de retenção PJ→PJ — EFD-Reinf (Sprint 11 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.reinf.calcula_retencao import (
    ALGORITMO_VERSAO,
    RegimeTomador,
    calcular_retencao_pj_pj,
)


class TestTomadorLP:
    def test_servico_5k(self) -> None:
        # IR = 75; PIS = 32,50; Cofins = 150; CSLL = 50; CSRF total = 232,50
        # Líquido = 5000 − 75 − 232,50 = 4692,50
        r = calcular_retencao_pj_pj(
            Decimal("5000.00"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.sujeito_a_retencao is True
        assert r.ir_retido == Decimal("75.00")
        assert r.pis_retido == Decimal("32.50")
        assert r.cofins_retido == Decimal("150.00")
        assert r.csll_retido == Decimal("50.00")
        assert r.csrf_total == Decimal("232.50")
        assert r.csrf_dispensado is False
        assert r.valor_liquido_pago == Decimal("4692.50")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_servico_grande_10k(self) -> None:
        # IR = 150; PIS = 65; Cofins = 300; CSLL = 100; CSRF = 465
        # Líquido = 10000 − 150 − 465 = 9385
        r = calcular_retencao_pj_pj(
            Decimal("10000"), RegimeTomador.LUCRO_REAL
        )
        assert r.ir_retido == Decimal("150.00")
        assert r.csrf_total == Decimal("465.00")
        assert r.valor_liquido_pago == Decimal("9385.00")


class TestDispensaCsrfAteR10:
    """IN RFB 459/2004 art. 1º §3º — CSRF ≤ R$10 não retém PIS/Cofins/CSLL."""

    def test_servico_pequeno_dispensa(self) -> None:
        # 200,00 × 4,65% = 9,30 → < R$10 → dispensa CSRF, mas IR retém normal
        # IR = 200 × 1,5% = 3,00
        # Líquido = 200 − 3 = 197,00
        r = calcular_retencao_pj_pj(
            Decimal("200.00"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.csrf_total == Decimal("9.30")
        assert r.csrf_dispensado is True
        assert r.pis_retido == Decimal("0")
        assert r.cofins_retido == Decimal("0")
        assert r.csll_retido == Decimal("0")
        assert r.ir_retido == Decimal("3.00")
        assert r.valor_liquido_pago == Decimal("197.00")

    def test_limite_exato_nao_dispensa(self) -> None:
        # CSRF = 10,00 exato (≥ R$10) → não dispensa.
        # 10/0,0465 = 215,054... → usar valor que dê CSRF = 10,00 exato.
        # Vou testar com 215,06: CSRF = 215,06 × 4,65% = 10,000... arredondado
        # Mais seguro: usar 216,00 → CSRF = 10,044 → 10,04, não dispensa.
        r = calcular_retencao_pj_pj(
            Decimal("216.00"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.csrf_dispensado is False
        # PIS = 216 × 0,65% = 1,404 → 1,40
        # Cofins = 216 × 3% = 6,48
        # CSLL = 216 × 1% = 2,16
        # Total = 10,04
        assert r.csrf_total == Decimal("10.04")

    def test_limite_proximo_dispensa(self) -> None:
        # 214 × 0,65% = 1,391 → 1,39
        # 214 × 3% = 6,42; 214 × 1% = 2,14
        # CSRF total = 9,95 < R$10 → dispensa
        r = calcular_retencao_pj_pj(
            Decimal("214.00"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.csrf_total == Decimal("9.95")
        assert r.csrf_dispensado is True


class TestTomadorSimples:
    """LC 123/2006 art. 13 §13 — SN/MEI dispensados de toda retenção."""

    def test_simples_nacional_dispensado(self) -> None:
        r = calcular_retencao_pj_pj(
            Decimal("10000"), RegimeTomador.SIMPLES_NACIONAL
        )
        assert r.sujeito_a_retencao is False
        assert r.ir_retido == Decimal("0")
        assert r.csrf_total == Decimal("0")
        assert r.valor_liquido_pago == Decimal("10000.00")

    def test_mei_dispensado(self) -> None:
        r = calcular_retencao_pj_pj(
            Decimal("3000"), RegimeTomador.MEI
        )
        assert r.sujeito_a_retencao is False
        assert r.valor_liquido_pago == Decimal("3000.00")


class TestBordas:
    def test_servico_zero(self) -> None:
        r = calcular_retencao_pj_pj(
            Decimal("0"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.csrf_dispensado is True  # 0 < 10
        assert r.valor_liquido_pago == Decimal("0.00")

    def test_servico_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="valor_servico"):
            calcular_retencao_pj_pj(
                Decimal("-1"), RegimeTomador.LUCRO_PRESUMIDO
            )
