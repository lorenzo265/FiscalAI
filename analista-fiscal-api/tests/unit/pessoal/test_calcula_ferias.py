"""Golden tests de férias — gozadas + 1/3 + abono pecuniário (Sprint 10 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_ferias import (
    ALGORITMO_VERSAO,
    calcular_ferias,
)
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS


class TestFeriasIntegrais:
    def test_30_dias_3000_sem_dep(self) -> None:
        # Remuneração: 3000; 1/3: 1000; bruto: 4000
        # INSS sobre 4000: 373,41 (escalonado, 3 faixas até 4000)
        # IRRF_legal: base = 4000 − 373,41 = 3626,59 → faixa 3 → 162,55
        # IRRF_simpl: base = 4000 − 564,80 = 3435,20 → faixa 3 → 3435,20×15%−381,44
        #           = 515,28 − 381,44 = 133,84
        # min(162,55 ; 133,84) = 133,84 → SIMPLIFICADO (FA2 M5)
        # Líquido = 4000 + 0 − 373,41 − 133,84 = 3492,75
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=30,
            dias_vendidos=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.remuneracao_gozados == Decimal("3000.00")
        assert r.terco_gozados == Decimal("1000.00")
        assert r.bruto_tributavel == Decimal("4000.00")
        assert r.abono_pecuniario == Decimal("0")
        assert r.inss.inss == Decimal("373.41")
        assert r.irrf.irrf == Decimal("133.84")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_liquido == Decimal("3492.75")

    def test_15_dias_isento_irrf(self) -> None:
        # 15 dias de 3000: remun = 1500; 1/3 = 500; bruto = 2000
        # INSS: 1518×7,5% + (2000−1518)×9% = 113,85 + 43,38 = 157,23
        # IRRF: base = 2000 − 157,23 = 1842,77 → faixa 1 → 0
        # Líquido: 2000 − 157,23 = 1842,77
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=15,
            dias_vendidos=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.bruto_tributavel == Decimal("2000.00")
        assert r.inss.inss == Decimal("157.23")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.valor_liquido == Decimal("1842.77")


class TestAbonoPecuniario:
    def test_20_gozados_10_vendidos(self) -> None:
        # Vende 10 dias (máximo): abono = 3000×10/30 + 1/3 = 1000 + 333,33 = 1333,33 (isento)
        # Gozados 20: remun = 2000; 1/3 = 666,67; bruto = 2666,67
        # INSS sobre 2666,67: 217,23 (escalonado)
        # IRRF_legal: base = 2666,67 − 217,23 = 2449,44 → faixa 2 → 14,27
        # IRRF_simpl: base = 2666,67 − 564,80 = 2101,87 → faixa 1 → 0
        # min(14,27 ; 0) = 0 → SIMPLIFICADO (FA2 M5)
        # Líquido = 2666,67 + 1333,33 − 217,23 − 0 = 3782,77
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=20,
            dias_vendidos=10,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.bruto_tributavel == Decimal("2666.67")
        assert r.abono_pecuniario == Decimal("1333.33")
        assert r.inss.inss == Decimal("217.23")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_liquido == Decimal("3782.77")

    def test_abono_nao_entra_inss(self) -> None:
        # 30 gozados sem abono vs 20+10 com abono: INSS+IRRF DEVEM diferir
        # (bases diferentes — 4000 vs 2666,67), mas abono não vai pra base.
        r_sem = calcular_ferias(
            Decimal("3000"), 30, 0, INSS_FAIXAS, IRRF_FAIXAS, 0
        )
        r_com = calcular_ferias(
            Decimal("3000"), 20, 10, INSS_FAIXAS, IRRF_FAIXAS, 0
        )
        assert r_sem.inss.inss != r_com.inss.inss
        # Confirma que o abono é apenas adicionado ao líquido
        assert r_com.abono_pecuniario > Decimal("0")


class TestBordas:
    def test_dias_gozados_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="dias_gozados"):
            calcular_ferias(
                Decimal("3000"), 0, 0, INSS_FAIXAS, IRRF_FAIXAS, 0
            )

    def test_dias_gozados_31_levanta(self) -> None:
        with pytest.raises(ValueError, match="dias_gozados"):
            calcular_ferias(
                Decimal("3000"), 31, 0, INSS_FAIXAS, IRRF_FAIXAS, 0
            )

    def test_dias_vendidos_11_levanta(self) -> None:
        with pytest.raises(ValueError, match="dias_vendidos"):
            calcular_ferias(
                Decimal("3000"), 20, 11, INSS_FAIXAS, IRRF_FAIXAS, 0
            )

    def test_soma_superior_30_levanta(self) -> None:
        with pytest.raises(ValueError, match="não pode passar de 30"):
            calcular_ferias(
                Decimal("3000"), 25, 10, INSS_FAIXAS, IRRF_FAIXAS, 0
            )

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario"):
            calcular_ferias(
                Decimal("-1"), 30, 0, INSS_FAIXAS, IRRF_FAIXAS, 0
            )


class TestEstrutura:
    def test_versao(self) -> None:
        r = calcular_ferias(
            Decimal("3000"), 30, 0, INSS_FAIXAS, IRRF_FAIXAS, 0
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_determinismo(self) -> None:
        r1 = calcular_ferias(
            Decimal("4567.89"), 22, 8, INSS_FAIXAS, IRRF_FAIXAS, 2
        )
        r2 = calcular_ferias(
            Decimal("4567.89"), 22, 8, INSS_FAIXAS, IRRF_FAIXAS, 2
        )
        assert r1 == r2


class TestFgtsFerias:
    """Golden tests — FGTS do empregador em férias gozadas (Lei 8.036/90 art.15).

    FIX PR3 #5: calcula_ferias agora modela FGTS 8% sobre bruto tributável
    (férias gozadas + 1/3 constitucional). Abono pecuniário NÃO integra base.
    """

    def test_fgts_20_dias_salario_3000(self) -> None:
        # remuneracao_gozados = 3000 × 20/30 = 2000.00
        # terco_gozados       = 2000 / 3 = 666.67
        # bruto_tributavel    = 2666.67
        # base_fgts           = 2666.67 (abono=0 pois dias_vendidos=0)
        # fgts_empregador     = 2666.67 × 8% = 213.3336 → 213.33
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=20,
            dias_vendidos=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.bruto_tributavel == Decimal("2666.67")
        assert r.base_fgts == Decimal("2666.67")
        assert r.fgts_empregador == Decimal("213.33")

    def test_fgts_30_dias_salario_3000(self) -> None:
        # bruto_tributavel = 3000 + 1000 = 4000.00
        # fgts_empregador  = 4000.00 × 8% = 320.00
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=30,
            dias_vendidos=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.base_fgts == Decimal("4000.00")
        assert r.fgts_empregador == Decimal("320.00")

    def test_fgts_nao_incide_sobre_abono_pecuniario(self) -> None:
        # 20 gozados + 10 vendidos: bruto_tributavel = 2666.67 (20 dias + 1/3)
        # abono_pecuniario = 1333.33 (isento — NÃO entra na base FGTS)
        # base_fgts = bruto_tributavel = 2666.67 (abono excluído)
        # fgts_empregador = 2666.67 × 8% = 213.33
        r = calcular_ferias(
            salario=Decimal("3000.00"),
            dias_gozados=20,
            dias_vendidos=10,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.abono_pecuniario == Decimal("1333.33")
        assert r.base_fgts == Decimal("2666.67")
        assert r.fgts_empregador == Decimal("213.33")
        # base_fgts deve ser igual ao bruto_tributavel (abono excluído)
        assert r.base_fgts == r.bruto_tributavel

    def test_versao_bumped(self) -> None:
        """Bump v1→v2 sinaliza adição do campo fgts_empregador."""
        assert ALGORITMO_VERSAO == "ferias.v2"
