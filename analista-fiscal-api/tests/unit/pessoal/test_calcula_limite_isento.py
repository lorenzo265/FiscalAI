"""Golden tests do `calcula_limite_isento` (Sprint 19.7 PR1 #15)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_limite_isento import (
    LimiteIsentoCalculado,
    calcular_limite_isento_lucro_presumido,
    calcular_limite_isento_simples_nacional,
)


# ── Lucro Presumido ────────────────────────────────────────────────────────


class TestLP:
    def test_lp_comercio_canonical(self) -> None:
        """Receita R$ 100k × presunção 8% = R$ 8k lucro presumido;
        impostos R$ 3k → limite R$ 5k."""
        calc = calcular_limite_isento_lucro_presumido(
            receita_periodo=Decimal("100000.00"),
            presuncao_irpj=Decimal("0.08"),
            irpj_pago=Decimal("1200.00"),
            csll_pago=Decimal("1080.00"),
            pis_pago=Decimal("650.00"),
            cofins_pago=Decimal("3000.00"),
        )
        # 100000 × 0.08 = 8000 lucro estimado
        # impostos = 1200 + 1080 + 650 + 3000 = 5930
        # limite = max(0, 8000 - 5930) = 2070
        assert calc.limite_isento == Decimal("2070.00")
        assert calc.lucro_estimado == Decimal("8000.00")
        assert calc.impostos_total == Decimal("5930.00")
        assert calc.base_calculo == "lucro_presumido_cnae"
        assert calc.presuncao_aplicada == Decimal("0.08")

    def test_lp_servico_presuncao_32(self) -> None:
        calc = calcular_limite_isento_lucro_presumido(
            receita_periodo=Decimal("50000.00"),
            presuncao_irpj=Decimal("0.32"),
            irpj_pago=Decimal("2400.00"),
            csll_pago=Decimal("1440.00"),
            pis_pago=Decimal("325.00"),
            cofins_pago=Decimal("1500.00"),
        )
        # 50000 × 0.32 = 16000 - 5665 = 10335
        assert calc.limite_isento == Decimal("10335.00")

    def test_lp_impostos_excedem_lucro_devolve_zero(self) -> None:
        """Se IRPJ+CSLL+PIS+COFINS > lucro presumido, limite = 0 (não negativo)."""
        calc = calcular_limite_isento_lucro_presumido(
            receita_periodo=Decimal("10000.00"),
            presuncao_irpj=Decimal("0.08"),
            irpj_pago=Decimal("1000.00"),
            csll_pago=Decimal("0"),
            pis_pago=Decimal("0"),
            cofins_pago=Decimal("0"),
        )
        # 10000 × 0.08 = 800, mas IRPJ 1000 > 800 → limite = 0
        assert calc.limite_isento == Decimal("0.00")

    def test_lp_zero_receita_zera_tudo(self) -> None:
        calc = calcular_limite_isento_lucro_presumido(
            receita_periodo=Decimal("0"),
            presuncao_irpj=Decimal("0.08"),
            irpj_pago=Decimal("0"),
            csll_pago=Decimal("0"),
            pis_pago=Decimal("0"),
            cofins_pago=Decimal("0"),
        )
        assert calc.limite_isento == Decimal("0.00")

    def test_lp_receita_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="receita_periodo"):
            calcular_limite_isento_lucro_presumido(
                receita_periodo=Decimal("-1"),
                presuncao_irpj=Decimal("0.08"),
                irpj_pago=Decimal("0"),
                csll_pago=Decimal("0"),
                pis_pago=Decimal("0"),
                cofins_pago=Decimal("0"),
            )

    def test_lp_presuncao_fora_intervalo_levanta(self) -> None:
        with pytest.raises(ValueError, match="presuncao_irpj"):
            calcular_limite_isento_lucro_presumido(
                receita_periodo=Decimal("1000"),
                presuncao_irpj=Decimal("1.5"),  # >1
                irpj_pago=Decimal("0"),
                csll_pago=Decimal("0"),
                pis_pago=Decimal("0"),
                cofins_pago=Decimal("0"),
            )

    def test_lp_imposto_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="irpj_pago"):
            calcular_limite_isento_lucro_presumido(
                receita_periodo=Decimal("1000"),
                presuncao_irpj=Decimal("0.08"),
                irpj_pago=Decimal("-1"),
                csll_pago=Decimal("0"),
                pis_pago=Decimal("0"),
                cofins_pago=Decimal("0"),
            )


# ── Simples Nacional ────────────────────────────────────────────────────────


class TestSN:
    def test_sn_anexo_iii_servicos_padrao(self) -> None:
        """Anexo III = 32% presunção; receita 100k → 32k lucro; DAS 6k → limite 26k."""
        calc = calcular_limite_isento_simples_nacional(
            receita_periodo=Decimal("100000.00"),
            anexo="III",
            das_pago_periodo=Decimal("6000.00"),
        )
        assert calc.lucro_estimado == Decimal("32000.00")
        assert calc.limite_isento == Decimal("26000.00")
        assert calc.presuncao_aplicada == Decimal("0.32")
        assert calc.base_calculo == "simples_anexo"

    def test_sn_anexo_i_comercio(self) -> None:
        """Anexo I = 20% (8% IRPJ + 12% CSLL). 100k × 0.20 - 4k DAS = 16k."""
        calc = calcular_limite_isento_simples_nacional(
            receita_periodo=Decimal("100000.00"),
            anexo="I",
            das_pago_periodo=Decimal("4000.00"),
        )
        assert calc.lucro_estimado == Decimal("20000.00")
        assert calc.limite_isento == Decimal("16000.00")

    def test_sn_anexo_desconhecido_cai_em_32(self) -> None:
        """Anexo inválido = 32% (caso comum em PME — serviços)."""
        calc = calcular_limite_isento_simples_nacional(
            receita_periodo=Decimal("1000.00"),
            anexo="XYZ",
            das_pago_periodo=Decimal("0"),
        )
        assert calc.presuncao_aplicada == Decimal("0.32")
        assert calc.lucro_estimado == Decimal("320.00")

    def test_sn_das_excede_lucro_devolve_zero(self) -> None:
        calc = calcular_limite_isento_simples_nacional(
            receita_periodo=Decimal("1000.00"),
            anexo="I",
            das_pago_periodo=Decimal("500.00"),  # > 20% × 1000 = 200
        )
        assert calc.limite_isento == Decimal("0.00")

    def test_sn_receita_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="receita_periodo"):
            calcular_limite_isento_simples_nacional(
                receita_periodo=Decimal("-1"),
                anexo="III",
                das_pago_periodo=Decimal("0"),
            )

    def test_sn_das_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="das_pago_periodo"):
            calcular_limite_isento_simples_nacional(
                receita_periodo=Decimal("1000"),
                anexo="III",
                das_pago_periodo=Decimal("-1"),
            )


# ── Snapshot / determinismo ────────────────────────────────────────────────


def test_snapshot_preserva_inputs() -> None:
    """LimiteIsentoCalculado guarda inputs auditáveis."""
    calc = calcular_limite_isento_lucro_presumido(
        receita_periodo=Decimal("50000.00"),
        presuncao_irpj=Decimal("0.08"),
        irpj_pago=Decimal("100"),
        csll_pago=Decimal("100"),
        pis_pago=Decimal("100"),
        cofins_pago=Decimal("100"),
    )
    assert isinstance(calc, LimiteIsentoCalculado)
    assert calc.receita_periodo == Decimal("50000.00")
    assert calc.algoritmo_versao == "limite_isento.v1"
