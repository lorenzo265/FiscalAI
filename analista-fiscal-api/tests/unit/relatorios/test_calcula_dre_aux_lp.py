"""Golden tests do DRE auxiliar trimestral LP (Sprint 12 PR3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.relatorios.calcula_dre_aux_lp import (
    ALGORITMO_VERSAO,
    ApuracaoFiscalInput,
    EntradaDreAuxLp,
    calcular_dre_aux_lp,
)


def _apur(tipo: str, valor: str, base: str | None = None) -> ApuracaoFiscalInput:
    return ApuracaoFiscalInput(
        tipo=tipo,
        valor=Decimal(valor),
        base_calculo=Decimal(base) if base is not None else None,
    )


class TestTrimestreCompleto:
    def test_lp_comercio_t1_completo(self) -> None:
        # Trimestre Jan-Mar:
        # Receita bruta contábil 300.000
        # IRPJ apurado: 1 linha trimestral 9.000 sobre base 24k (8% sobre 300k)
        # CSLL: 1 linha trimestral 3.240 sobre base 36k (12% sobre 300k)
        # PIS: 3 linhas mensais 650+650+650 = 1950 sobre 300k
        # Cofins: 3 linhas mensais 3000×3 = 9000
        # ICMS: 3 linhas mensais 7000 cada = 21000
        # Total tributos = 9000 + 3240 + 1950 + 9000 + 21000 = 44.190
        # Carga = 44190 / 300000 = 0,1473 (14,73%)
        entrada = EntradaDreAuxLp(
            ano=2026, trimestre=1,
            receita_bruta_contabil=Decimal("300000"),
            receita_liquida_contabil=Decimal("267810"),
            lucro_liquido_contabil=Decimal("50000"),
            apuracoes=[
                _apur("irpj", "9000", "24000"),
                _apur("csll", "3240", "36000"),
                _apur("pis", "650", "100000"),
                _apur("pis", "650", "100000"),
                _apur("pis", "650", "100000"),
                _apur("cofins", "3000", "100000"),
                _apur("cofins", "3000", "100000"),
                _apur("cofins", "3000", "100000"),
                _apur("icms", "7000"),
                _apur("icms", "7000"),
                _apur("icms", "7000"),
            ],
        )
        r = calcular_dre_aux_lp(entrada)
        assert r.ano == 2026
        assert r.trimestre == 1
        assert r.total_irpj == Decimal("9000.00")
        assert r.total_csll == Decimal("3240.00")
        assert r.total_pis == Decimal("1950.00")
        assert r.total_cofins == Decimal("9000.00")
        assert r.total_icms == Decimal("21000.00")
        assert r.total_iss == Decimal("0.00")
        assert r.total_tributos == Decimal("44190.00")
        assert r.base_irpj == Decimal("24000.00")
        assert r.base_csll == Decimal("36000.00")
        # Base PIS = soma das 3 bases mensais (Cofins não soma de novo)
        assert r.base_pis_cofins == Decimal("300000.00")
        assert r.diferenca_receita == Decimal("0.00")
        assert r.carga_tributaria_efetiva == Decimal("0.1473")
        assert r.algoritmo_versao == ALGORITMO_VERSAO
        assert len(r.tributos) == 11


class TestReconciliacao:
    def test_receita_contabil_diferente_da_fiscal(self) -> None:
        # Contábil reporta 100k, mas PIS+Cofins foram apurados sobre 90k
        # (diferença de 10k = vendas não escrituradas ou exclusões legais).
        entrada = EntradaDreAuxLp(
            ano=2026, trimestre=2,
            receita_bruta_contabil=Decimal("100000"),
            receita_liquida_contabil=Decimal("96000"),
            lucro_liquido_contabil=Decimal("15000"),
            apuracoes=[
                _apur("pis", "585", "90000"),
                _apur("cofins", "2700", "90000"),
            ],
        )
        r = calcular_dre_aux_lp(entrada)
        assert r.base_pis_cofins == Decimal("90000.00")
        # Diferença = contábil − fiscal = 10.000 (positivo: contábil > fiscal)
        assert r.diferenca_receita == Decimal("10000.00")

    def test_carga_zero_sem_tributos(self) -> None:
        entrada = EntradaDreAuxLp(
            ano=2026, trimestre=1,
            receita_bruta_contabil=Decimal("50000"),
            receita_liquida_contabil=Decimal("50000"),
            lucro_liquido_contabil=Decimal("10000"),
            apuracoes=[],
        )
        r = calcular_dre_aux_lp(entrada)
        assert r.total_tributos == Decimal("0.00")
        assert r.carga_tributaria_efetiva == Decimal("0.0000")

    def test_receita_zero_carga_none(self) -> None:
        entrada = EntradaDreAuxLp(
            ano=2026, trimestre=1,
            receita_bruta_contabil=Decimal("0"),
            receita_liquida_contabil=Decimal("0"),
            lucro_liquido_contabil=Decimal("0"),
            apuracoes=[],
        )
        r = calcular_dre_aux_lp(entrada)
        assert r.carga_tributaria_efetiva is None


class TestIss:
    def test_servicos_com_iss(self) -> None:
        # Prestador de serviços tributado por ISS (não ICMS)
        entrada = EntradaDreAuxLp(
            ano=2026, trimestre=3,
            receita_bruta_contabil=Decimal("80000"),
            receita_liquida_contabil=Decimal("76000"),
            lucro_liquido_contabil=Decimal("20000"),
            apuracoes=[
                _apur("iss", "4000"),  # 5% ISS
                _apur("pis", "520", "80000"),
                _apur("cofins", "2400", "80000"),
            ],
        )
        r = calcular_dre_aux_lp(entrada)
        assert r.total_iss == Decimal("4000.00")
        assert r.total_icms == Decimal("0.00")


class TestBordas:
    def test_trimestre_invalido(self) -> None:
        with pytest.raises(ValueError, match="trimestre"):
            calcular_dre_aux_lp(
                EntradaDreAuxLp(
                    ano=2026, trimestre=5,
                    receita_bruta_contabil=Decimal("100"),
                    receita_liquida_contabil=Decimal("100"),
                    lucro_liquido_contabil=Decimal("0"),
                    apuracoes=[],
                )
            )

    def test_trimestre_zero_invalido(self) -> None:
        with pytest.raises(ValueError, match="trimestre"):
            calcular_dre_aux_lp(
                EntradaDreAuxLp(
                    ano=2026, trimestre=0,
                    receita_bruta_contabil=Decimal("100"),
                    receita_liquida_contabil=Decimal("100"),
                    lucro_liquido_contabil=Decimal("0"),
                    apuracoes=[],
                )
            )

    def test_receita_negativa(self) -> None:
        with pytest.raises(ValueError, match="receita_bruta_contabil"):
            calcular_dre_aux_lp(
                EntradaDreAuxLp(
                    ano=2026, trimestre=1,
                    receita_bruta_contabil=Decimal("-1"),
                    receita_liquida_contabil=Decimal("0"),
                    lucro_liquido_contabil=Decimal("0"),
                    apuracoes=[],
                )
            )
