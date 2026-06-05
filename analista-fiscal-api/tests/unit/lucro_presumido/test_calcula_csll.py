"""Golden tests da CSLL trimestral — Lucro Presumido.

FA3/M3: adiciona testes de compensação de CSLL retida na fonte (PCC).
Backward-compat: testes existentes (sem csll_a_compensar) mantidos.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.lucro_presumido.calcula_csll import (
    ALGORITMO_VERSAO,
    calcular_csll_trimestral,
)


class TestCsllComercio12pct:
    def test_receita_100k(self) -> None:
        # 100.000 × 12% = 12.000 base × 9% = 1.080
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("100000.00"),
            percentual_presuncao=Decimal("0.1200"),
        )
        assert r.base_presumida == Decimal("12000.00")
        assert r.base_total == Decimal("12000.00")
        assert r.aliquota == Decimal("0.0900")
        assert r.csll == Decimal("1080.00")
        # sem compensação: recolher = devida
        assert r.csll_a_recolher == Decimal("1080.00")
        assert r.csll_a_compensar == Decimal("0.00")
        assert r.csll_consumida == Decimal("0.00")
        assert r.csll_saldo_credor == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_receita_1M(self) -> None:
        # 1.000.000 × 12% × 9% = 10.800
        r = calcular_csll_trimestral(
            Decimal("1000000.00"), Decimal("0.1200")
        )
        assert r.csll == Decimal("10800.00")
        assert r.csll_a_recolher == Decimal("10800.00")


class TestCsllServicos32pct:
    def test_servicos_300k(self) -> None:
        # 300.000 × 32% × 9% = 8.640
        r = calcular_csll_trimestral(
            Decimal("300000.00"), Decimal("0.3200")
        )
        assert r.csll == Decimal("8640.00")
        assert r.csll_a_recolher == Decimal("8640.00")


class TestCsllAdicoes:
    def test_com_ganho_capital_e_aplicacoes(self) -> None:
        # 200.000 × 12% = 24.000 + 50.000 + 4.000 + 1.000 = 79.000
        # CSLL = 79.000 × 9% = 7.110
        r = calcular_csll_trimestral(
            Decimal("200000"), Decimal("0.1200"),
            ganhos_capital=Decimal("50000"),
            receitas_aplicacoes=Decimal("4000"),
            outras_adicoes=Decimal("1000"),
        )
        assert r.base_total == Decimal("79000.00")
        assert r.csll == Decimal("7110.00")
        assert r.csll_a_recolher == Decimal("7110.00")


# ── FA3 / M3 — Compensação de CSLL retida na fonte (PCC) ─────────────────────


class TestCsllCompensacaoRetencaoFonte:
    """Empresa LP de serviços sofre retenção PCC (4,65% = 1% CSLL + 3%
    Cofins + 0,65% PIS) em pagamentos PJ→PJ. A CSLL retida (1% sobre
    o bruto recebido) deve ser abatida da CSLL devida no trimestre.

    Base legal: Lei 9.430/1996 art. 64 c/c Lei 10.833/2003 art. 30 +
    IN RFB 1.234/2012.
    """

    def test_csll_compensada_parcialmente(self) -> None:
        """Caso principal: empresa recebeu R$300.000 em serviços PJ→PJ.
        Retenção CSLL = 1% × 300.000 = R$3.000.
        CSLL devida = 300.000 × 32% × 9% = R$8.640.
        CSLL a recolher = 8.640 − 3.000 = R$5.640.
        Saldo credor = 0 (retida < devida).
        """
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("300000.00"),
            percentual_presuncao=Decimal("0.3200"),
            csll_a_compensar=Decimal("3000.00"),
        )
        assert r.csll == Decimal("8640.00")              # devida bruta
        assert r.csll_a_compensar == Decimal("3000.00")
        assert r.csll_consumida == Decimal("3000.00")
        assert r.csll_a_recolher == Decimal("5640.00")
        assert r.csll_saldo_credor == Decimal("0.00")

    def test_csll_retida_maior_que_devida_gera_saldo_credor(self) -> None:
        """Empresa com receita baixa no trimestre: CSLL devida < retida.
        Receita = R$50.000 → base 32% = R$16.000 → CSLL devida = R$1.440.
        Retenção acumulada de trimestres anteriores = R$2.000.
        Consumida = min(2.000, 1.440) = 1.440 → recolher = 0.
        Saldo credor = 2.000 − 1.440 = R$560.
        """
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("50000.00"),
            percentual_presuncao=Decimal("0.3200"),
            csll_a_compensar=Decimal("2000.00"),
        )
        assert r.csll == Decimal("1440.00")              # devida bruta
        assert r.csll_a_compensar == Decimal("2000.00")
        assert r.csll_consumida == Decimal("1440.00")
        assert r.csll_a_recolher == Decimal("0.00")
        assert r.csll_saldo_credor == Decimal("560.00")

    def test_csll_compensada_exatamente_zerada(self) -> None:
        """Retida = devida → recolher = 0, saldo credor = 0."""
        # 100.000 × 12% × 9% = 1.080 devida; retida = 1.080
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("100000.00"),
            percentual_presuncao=Decimal("0.1200"),
            csll_a_compensar=Decimal("1080.00"),
        )
        assert r.csll == Decimal("1080.00")
        assert r.csll_a_recolher == Decimal("0.00")
        assert r.csll_saldo_credor == Decimal("0.00")
        assert r.csll_consumida == Decimal("1080.00")

    def test_backward_compat_sem_compensacao(self) -> None:
        """Chamadores que não passam csll_a_compensar recebem o mesmo
        resultado de antes: csll_a_recolher == csll."""
        r = calcular_csll_trimestral(
            receita_bruta_trimestre=Decimal("200000.00"),
            percentual_presuncao=Decimal("0.1200"),
        )
        assert r.csll_a_compensar == Decimal("0.00")
        assert r.csll_a_recolher == r.csll
        assert r.csll_saldo_credor == Decimal("0.00")

    def test_compensar_negativo_levanta_valueerror(self) -> None:
        with pytest.raises(ValueError, match="csll_a_compensar"):
            calcular_csll_trimestral(
                Decimal("100000"), Decimal("0.12"),
                csll_a_compensar=Decimal("-1"),
            )


class TestCsllBordas:
    def test_zero(self) -> None:
        r = calcular_csll_trimestral(Decimal("0"), Decimal("0.12"))
        assert r.csll == Decimal("0.00")
        assert r.csll_a_recolher == Decimal("0.00")

    def test_receita_negativa(self) -> None:
        with pytest.raises(ValueError, match="receita"):
            calcular_csll_trimestral(Decimal("-1"), Decimal("0.12"))

    def test_presuncao_invalida(self) -> None:
        with pytest.raises(ValueError, match="percentual_presuncao"):
            calcular_csll_trimestral(Decimal("100"), Decimal("1.5"))
