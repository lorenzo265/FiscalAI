"""Golden tests do ICMS mensal (Sprint 11 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.icms.calcula_icms import (
    ALGORITMO_VERSAO,
    TipoOrigem,
    aliquota_interestadual,
    calcular_icms_mensal,
)


class TestAliquotaInterestadual:
    """Resolução do Senado 22/1989 + 13/2012."""

    def test_sul_sudeste_para_nordeste_7pct(self) -> None:
        # SP → BA: 7%
        assert aliquota_interestadual("SP", "BA") == Decimal("0.0700")

    def test_sul_sudeste_para_es_7pct(self) -> None:
        # MG → ES (ES é exceção do Sudeste): 7%
        assert aliquota_interestadual("MG", "ES") == Decimal("0.0700")

    def test_nordeste_para_sul_12pct(self) -> None:
        # BA → SP: 12%
        assert aliquota_interestadual("BA", "SP") == Decimal("0.1200")

    def test_norte_para_norte_12pct(self) -> None:
        # PA → AM: 12%
        assert aliquota_interestadual("PA", "AM") == Decimal("0.1200")

    def test_sudeste_para_sudeste_12pct(self) -> None:
        # SP → RJ: 12% (entre S/SE não cai em 7%, apenas para N/NE/CO+ES)
        assert aliquota_interestadual("SP", "RJ") == Decimal("0.1200")

    def test_importada_4pct(self) -> None:
        # Qualquer origem→destino, mercadoria importada: 4% (Res. 13/2012)
        assert aliquota_interestadual(
            "SP", "AM", origem=TipoOrigem.IMPORTADA
        ) == Decimal("0.0400")
        assert aliquota_interestadual(
            "BA", "RS", origem=TipoOrigem.IMPORTADA
        ) == Decimal("0.0400")

    def test_uf_igual_levanta(self) -> None:
        with pytest.raises(ValueError, match="operação interna"):
            aliquota_interestadual("SP", "SP")

    def test_uf_invalida_levanta(self) -> None:
        with pytest.raises(ValueError, match="UFs inválidas"):
            aliquota_interestadual("XX", "SP")


class TestApuracaoMensal:
    def test_saldo_devedor_simples(self) -> None:
        # Débito 10.000, crédito 6.000 → saldo a recolher 4.000
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="SP",
            aliquota_interna=Decimal("0.1800"),
            debito=Decimal("10000"),
            credito=Decimal("6000"),
        )
        assert r.saldo_apurado == Decimal("4000.00")
        assert r.icms_a_recolher == Decimal("4000.00")
        assert r.saldo_credor_a_transportar == Decimal("0.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_saldo_credor_transporta(self) -> None:
        # Débito 5.000, crédito 8.000 → credor 3.000 a transportar
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="RS",
            aliquota_interna=Decimal("0.1700"),
            debito=Decimal("5000"),
            credito=Decimal("8000"),
        )
        assert r.saldo_apurado == Decimal("-3000.00")
        assert r.icms_a_recolher == Decimal("0.00")
        assert r.saldo_credor_a_transportar == Decimal("3000.00")

    def test_saldo_credor_anterior_aplicado(self) -> None:
        # Débito 10k, crédito 6k, saldo anterior 2k → 10−6−2 = 2k a recolher
        r = calcular_icms_mensal(
            competencia="2026-05-01",
            uf="SP",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("10000"),
            credito=Decimal("6000"),
            saldo_credor_anterior=Decimal("2000"),
        )
        assert r.icms_a_recolher == Decimal("2000.00")

    def test_ajustes_aplicados(self) -> None:
        # 10k − 6k + 500 devedor − 200 credor = 4.300 a recolher
        r = calcular_icms_mensal(
            competencia="2026-05-01",
            uf="MG",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("10000"),
            credito=Decimal("6000"),
            ajustes_devedores=Decimal("500"),
            ajustes_credores=Decimal("200"),
        )
        assert r.saldo_apurado == Decimal("4300.00")
        assert r.icms_a_recolher == Decimal("4300.00")

    def test_zero_zero(self) -> None:
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="SP",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("0"),
            credito=Decimal("0"),
        )
        assert r.saldo_apurado == Decimal("0.00")
        assert r.icms_a_recolher == Decimal("0.00")
        assert r.saldo_credor_a_transportar == Decimal("0.00")


class TestBordas:
    def test_uf_invalida(self) -> None:
        with pytest.raises(ValueError, match="UF inválida"):
            calcular_icms_mensal(
                "2026-04-01", "XX", Decimal("0.18"),
                Decimal("100"), Decimal("0"),
            )

    def test_aliquota_invalida(self) -> None:
        with pytest.raises(ValueError, match="aliquota_interna"):
            calcular_icms_mensal(
                "2026-04-01", "SP", Decimal("1.5"),
                Decimal("100"), Decimal("0"),
            )

    def test_debito_negativo(self) -> None:
        with pytest.raises(ValueError, match="debito"):
            calcular_icms_mensal(
                "2026-04-01", "SP", Decimal("0.18"),
                Decimal("-1"), Decimal("0"),
            )

    def test_credito_negativo(self) -> None:
        with pytest.raises(ValueError, match="credito"):
            calcular_icms_mensal(
                "2026-04-01", "SP", Decimal("0.18"),
                Decimal("100"), Decimal("-1"),
            )

    def test_saldo_anterior_negativo(self) -> None:
        with pytest.raises(ValueError, match="saldo_credor_anterior"):
            calcular_icms_mensal(
                "2026-04-01", "SP", Decimal("0.18"),
                Decimal("100"), Decimal("0"),
                saldo_credor_anterior=Decimal("-1"),
            )
