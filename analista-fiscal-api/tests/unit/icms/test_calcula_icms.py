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

    def test_fecp_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="aliquota_fecp"):
            calcular_icms_mensal(
                "2026-04-01", "RJ", Decimal("0.18"),
                Decimal("100"), Decimal("0"),
                aliquota_fecp=Decimal("-0.01"),
            )


class TestFA7M2IcmsRjFecp:
    """FA7-m2: RJ — ICMS interna=18% + FECP=2% = efetiva 20%.

    Lei estadual RJ 4.056/2002: FECP é adicional separado ao ICMS, não
    embutido na alíquota_interna. Seed corrigido em migration 0055:
    interna=0.18, fecp=0.02 (antes: interna=0.20 com FECP embutido).

    Prova de consistência: efetivo RJ ANTES e DEPOIS da correção = 20%.
    """

    def test_rj_efetivo_20pct_interna_18_fecp_2(self) -> None:
        # Golden principal: com seed corrigido (interna=0.18, fecp=0.02)
        # a alíquota efetiva deve continuar 20% (= 18% + 2% FECP).
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="RJ",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("10000"),
            credito=Decimal("0"),
            aliquota_fecp=Decimal("0.02"),
        )
        assert r.aliquota_interna == Decimal("0.18")
        assert r.aliquota_fecp == Decimal("0.02")
        assert r.aliquota_efetiva == Decimal("0.20"), (
            "Alíquota efetiva RJ = interna 18% + FECP 2% = 20%"
        )
        # O saldo apurado não depende da alíquota (débito/crédito já vêm
        # calculados pela NF); o teste prova que os campos estão corretos.
        assert r.saldo_apurado == Decimal("10000.00")
        assert r.icms_a_recolher == Decimal("10000.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_rj_seed_corrigido_nao_emite_dupla_contagem(self) -> None:
        # Prova que somar interna+fecp dentro da função dá 20%,
        # não 22% (que seria dupla contagem se fecp já estivesse em interna).
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="RJ",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("5000"),
            credito=Decimal("1000"),
            aliquota_fecp=Decimal("0.02"),
        )
        assert r.aliquota_efetiva == Decimal("0.20")
        assert r.aliquota_efetiva != Decimal("0.22"), (
            "Não há dupla contagem: FECP não está embutido em interna"
        )
        assert r.icms_a_recolher == Decimal("4000.00")

    def test_sem_fecp_efetiva_igual_interna(self) -> None:
        # UFs sem FECP: efetiva == interna (backward-compat).
        r = calcular_icms_mensal(
            competencia="2026-04-01",
            uf="SP",
            aliquota_interna=Decimal("0.18"),
            debito=Decimal("8000"),
            credito=Decimal("3000"),
        )
        assert r.aliquota_fecp == Decimal("0")
        assert r.aliquota_efetiva == Decimal("0.18")
        assert r.icms_a_recolher == Decimal("5000.00")

    def test_rj_vs_sp_mesma_base_efetiva_20pct(self) -> None:
        # Prova que o total do RJ (18%+2%) é idêntico à situação
        # anterior onde interna=0.20 (mas zerava fecp): resultado idêntico.
        # Isso garante backward-compat de valores fiscais.
        debito = Decimal("20000")
        credito = Decimal("5000")

        # Seed antigo: interna=0.20 (FECP embutido), fecp=0 → efetiva=0.20
        r_antes = calcular_icms_mensal(
            "2026-04-01", "RJ", Decimal("0.20"),
            debito, credito,
            aliquota_fecp=Decimal("0"),
        )
        # Seed novo: interna=0.18, fecp=0.02 → efetiva=0.20
        r_depois = calcular_icms_mensal(
            "2026-04-01", "RJ", Decimal("0.18"),
            debito, credito,
            aliquota_fecp=Decimal("0.02"),
        )
        assert r_antes.aliquota_efetiva == Decimal("0.20")
        assert r_depois.aliquota_efetiva == Decimal("0.20")
        # Saldo apurado idêntico (débito e crédito inalterados)
        assert r_antes.icms_a_recolher == r_depois.icms_a_recolher, (
            "ICMS a recolher do RJ deve ser idêntico antes e depois da "
            "correção do seed: FECP separado não muda o total efetivo 20%"
        )
