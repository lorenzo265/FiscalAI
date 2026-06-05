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


class TestFA7IrrfPisoDarfAcumulacao:
    """FA7-m1: Lei 9.430/1996 art. 68 §1º — piso R$10 DARF do IRRF.

    O IRRF (cód. 1708/5952) tem piso de R$10 por código de receita, mas a
    acumulação é **mensal** (todos os documentos do período somados). Logo:

    - A retenção por nota deve ocorrer normalmente, sem zerar o IRRF por
      documento isolado (seria incorreto sem o contexto de acumulação).
    - O controle do piso de R$10 é responsabilidade do módulo de DARF ao
      consolidar o período, não desta função pura de cálculo por documento.

    Este teste documenta e blinda o comportamento correto: documentos pequenos
    (abaixo de R$666,67 — limiar onde IR = R$10 exato) têm IRRF retido
    normalmente, sem dispensa automática. A CSRF pode ser dispensada
    independentemente (regra própria da IN 459/2004).
    """

    def test_nota_pequena_ir_retido_normalmente(self) -> None:
        # Nota de R$200 → IR = 200 × 1,5% = R$3,00
        # Apesar de R$3,00 < R$10, a retenção ocorre por nota (acumulação mensal).
        # CSRF = 200 × 4,65% = R$9,30 → dispensado (< R$10, regra IN 459/2004).
        r = calcular_retencao_pj_pj(
            Decimal("200.00"), RegimeTomador.LUCRO_PRESUMIDO
        )
        assert r.ir_retido == Decimal("3.00"), (
            "IRRF deve ser retido por nota independentemente do valor; "
            "piso de R$10 é por acumulação mensal (Lei 9.430/96 art. 68 §1º)"
        )
        assert r.csrf_dispensado is True   # IN 459/2004: CSRF < R$10 → dispensa

    def test_nota_minima_ir_acumula_mes(self) -> None:
        # Três notas de R$200 no mês: IR acumulado = 3 × R$3 = R$9 (<R$10).
        # A função retém R$3 por nota — o controle de piso fica no DARF.
        # Se a função zerasse IR < R$10, empresa perderia a dedução legal.
        notas = [Decimal("200.00")] * 3
        total_ir = sum(
            calcular_retencao_pj_pj(v, RegimeTomador.LUCRO_PRESUMIDO).ir_retido
            for v in notas
        )
        assert total_ir == Decimal("9.00"), (
            "Soma das retenções do mês = R$9,00 < R$10 → DARF não recolhe; "
            "mas a retenção por nota foi feita corretamente"
        )

    def test_nota_acima_do_limiar_ir_retido(self) -> None:
        # R$700 → IR = 700 × 1,5% = R$10,50 → claramente retido
        r = calcular_retencao_pj_pj(
            Decimal("700.00"), RegimeTomador.LUCRO_REAL
        )
        assert r.ir_retido == Decimal("10.50")
        assert r.sujeito_a_retencao is True
