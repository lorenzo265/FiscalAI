"""Golden tests do algoritmo de provisão trabalhista (Sprint 8 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.provisoes.calcula_provisao import (
    ALGORITMO_VERSAO,
    calcular_provisoes,
    inss_patronal_aplicavel,
)


# ── inss_patronal_aplicavel ─────────────────────────────────────────────────


class TestInssAplicavel:
    def test_lucro_presumido_aplica(self) -> None:
        assert inss_patronal_aplicavel("lucro_presumido") is True

    def test_lucro_real_aplica(self) -> None:
        assert inss_patronal_aplicavel("lucro_real") is True

    def test_simples_nacional_nao_aplica(self) -> None:
        assert inss_patronal_aplicavel("simples_nacional") is False

    def test_mei_nao_aplica(self) -> None:
        assert inss_patronal_aplicavel("mei") is False

    def test_case_insensitive(self) -> None:
        assert inss_patronal_aplicavel("Simples_Nacional") is False


# ── Golden cases — Lucro Presumido (todas as 6 linhas pontuam) ──────────────


class TestGoldenLP:
    def test_folha_10k_lp(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")

        # 1/12 de 10.000 = 833,33
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")
        assert r.decimo_terceiro.tipo == "13_salario"

        # Férias: 1/12 + 1/3 sobre 1/12.
        # ferias_base = 833,33; 1/3 = 277,78 (ROUND_HALF_EVEN); total = 1111,11
        assert r.ferias.valor_provisao == Decimal("1111.11")
        assert r.ferias.tipo == "ferias"

        # INSS 20% sobre férias_total = 0,20 × 1111,11 = 222,22
        assert r.inss_ferias.valor_provisao == Decimal("222.22")
        assert r.inss_ferias.aliquota == Decimal("0.2000")

        # INSS 20% sobre 13º_base = 0,20 × 833,33 = 166,67 (ROUND_HALF_EVEN)
        assert r.inss_13.valor_provisao == Decimal("166.67")

        # FGTS 8% sobre férias_total = 0,08 × 1111,11 = 88,89
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        assert r.fgts_ferias.aliquota == Decimal("0.0800")

        # FGTS 8% sobre 13º_base = 0,08 × 833,33 = 66,67 (ROUND_HALF_EVEN)
        assert r.fgts_13.valor_provisao == Decimal("66.67")

        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_folha_grande_30k_lp(self) -> None:
        r = calcular_provisoes(Decimal("30000.00"), "lucro_presumido")
        # 30000/12 = 2500; 2500 + 833,33 (1/3) = 3333,33
        assert r.decimo_terceiro.valor_provisao == Decimal("2500.00")
        assert r.ferias.valor_provisao == Decimal("3333.33")
        # INSS sobre 3333,33 = 666,67 (ROUND_HALF_EVEN)
        assert r.inss_ferias.valor_provisao == Decimal("666.67")
        # FGTS sobre 3333,33 = 266,67 (ROUND_HALF_EVEN)
        assert r.fgts_ferias.valor_provisao == Decimal("266.67")

    def test_folha_pequena_3k_lp(self) -> None:
        r = calcular_provisoes(Decimal("3000.00"), "lucro_presumido")
        # 3000/12 = 250; 250 + 83,33 = 333,33
        assert r.decimo_terceiro.valor_provisao == Decimal("250.00")
        assert r.ferias.valor_provisao == Decimal("333.33")
        # INSS 20% × 333,33 = 66,67 (ROUND_HALF_EVEN)
        assert r.inss_ferias.valor_provisao == Decimal("66.67")
        # INSS 20% × 250 = 50
        assert r.inss_13.valor_provisao == Decimal("50.00")
        # FGTS 8% × 333,33 = 26,67 (ROUND_HALF_EVEN)
        assert r.fgts_ferias.valor_provisao == Decimal("26.67")
        # FGTS 8% × 250 = 20
        assert r.fgts_13.valor_provisao == Decimal("20.00")


# ── Simples Nacional / MEI — INSS zero ──────────────────────────────────────


class TestSimplesNacional:
    def test_sn_inss_zero(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "simples_nacional")
        # Férias e 13º iguais ao LP
        assert r.ferias.valor_provisao == Decimal("1111.11")
        assert r.decimo_terceiro.valor_provisao == Decimal("833.33")
        # INSS = 0
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_ferias.aliquota == Decimal("0")
        assert r.inss_13.valor_provisao == Decimal("0.00")
        # FGTS ainda incide (FGTS não é dispensado para SN)
        assert r.fgts_ferias.valor_provisao == Decimal("88.89")
        assert r.fgts_13.valor_provisao == Decimal("66.67")

    def test_mei_inss_zero(self) -> None:
        r = calcular_provisoes(Decimal("5000.00"), "mei")
        assert r.inss_ferias.valor_provisao == Decimal("0.00")
        assert r.inss_13.valor_provisao == Decimal("0.00")
        # 5000/12 = 416,67 (ROUND_HALF_EVEN)
        assert r.decimo_terceiro.valor_provisao == Decimal("416.67")


# ── Estrutura / borda ───────────────────────────────────────────────────────


class TestEstrutura:
    def test_retorna_6_linhas(self) -> None:
        r = calcular_provisoes(Decimal("1000"), "lucro_presumido")
        linhas = r.as_lista()
        assert len(linhas) == 6
        tipos = {l.tipo for l in linhas}
        assert tipos == {
            "ferias",
            "13_salario",
            "inss_ferias",
            "inss_13",
            "fgts_ferias",
            "fgts_13",
        }

    def test_folha_zero(self) -> None:
        r = calcular_provisoes(Decimal("0"), "lucro_presumido")
        for linha in r.as_lista():
            assert linha.valor_provisao == Decimal("0.00")

    def test_folha_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="não pode ser negativa"):
            calcular_provisoes(Decimal("-1"), "lucro_presumido")


# ── Determinismo ────────────────────────────────────────────────────────────


class TestDeterminismo:
    def test_mesmo_input_mesmo_resultado(self) -> None:
        r1 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido")
        r2 = calcular_provisoes(Decimal("7500.50"), "lucro_presumido")
        assert r1 == r2


# ── Aliquota persistida coerente (Fase 2 PR10) ───────────────────────────────


class TestAliquotaPersistidaSeisCasas:
    """Após Fase 2 PR10: ``provisao_mensal.aliquota`` é NUMERIC(8,6).

    O algoritmo persiste ``1/12 ≈ 0.083333`` (6 casas) — auditor que
    multiplicar base × aliquota_persistida obtém valor ≈ valor_provisao
    com erro ≤ R$ 0,01 (antes era R$ 0,03 em folha de R$ 10k).
    """

    def test_aliquota_ferias_seis_casas(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        # Esperado: 1/12 = 0.083333 (6 casas, ROUND_HALF_EVEN)
        assert r.ferias.aliquota == Decimal("0.083333")
        # Garante que NÃO é o valor antigo arredondado a 4 casas.
        assert r.ferias.aliquota != Decimal("0.0833")

    def test_aliquota_13_seis_casas(self) -> None:
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        assert r.decimo_terceiro.aliquota == Decimal("0.083333")

    def test_base_x_aliquota_aproxima_valor_provisao(self) -> None:
        """Reconciliação visual: base × aliquota ≈ valor_provisao."""
        r = calcular_provisoes(Decimal("10000.00"), "lucro_presumido")
        # 13º: base 10000 × 0.083333 = 833.33 → valor persistido 833.33
        produto = r.decimo_terceiro.base_calculo * r.decimo_terceiro.aliquota
        diferenca = (produto - r.decimo_terceiro.valor_provisao).copy_abs()
        # Erro ≤ R$ 0,01 (antes do PR10: ~R$ 0,03 com aliquota=0.0833)
        assert diferenca <= Decimal("0.01")

    def test_versao_bumped(self) -> None:
        """Bump v05→v06 sinaliza mudança na coluna aliquota persistida."""
        assert ALGORITMO_VERSAO == "prov-2026.06"
