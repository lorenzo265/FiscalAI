"""Golden tests do gerador DASN-SIMEI (Sprint 6 PR3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.declaracao_anual.gerar_dasn_simei import (
    GERADOR_VERSAO,
    DadosDasnSimei,
    gerar_dasn_simei,
)


class TestGerarDasnGolden:
    def test_mei_dentro_do_limite(self) -> None:
        r = gerar_dasn_simei(
            "12345678000195",
            2025,
            DadosDasnSimei(
                receita_comercio_industria=Decimal("30000.00"),
                receita_servicos=Decimal("20000.00"),
                teve_empregado=True,
            ),
        )
        assert r.receita_bruta_anual == Decimal("50000.00")
        assert r.excedeu_limite_mei is False
        p = r.payload
        assert p["anoCalendario"] == 2025
        assert p["receitas"]["receitaBrutaAnual"] == "50000.00"
        assert p["receitas"]["limiteAplicavel"] == "81000.00"
        assert p["informacoesAuxiliares"]["teveEmpregadoNoAno"] is True
        assert r.algoritmo_versao == GERADOR_VERSAO

    def test_mei_estoura_limite(self) -> None:
        r = gerar_dasn_simei(
            "12345678000195",
            2025,
            DadosDasnSimei(
                receita_comercio_industria=Decimal("85000.00"),
                receita_servicos=Decimal("0"),
            ),
        )
        assert r.excedeu_limite_mei is True
        assert r.payload["receitas"]["excedeuLimite"] is True

    def test_mei_caminhoneiro_limite_ampliado(self) -> None:
        r = gerar_dasn_simei(
            "12345678000195",
            2025,
            DadosDasnSimei(
                receita_servicos=Decimal("200000.00"),
                eh_caminhoneiro=True,
            ),
        )
        # R$200k cabe no limite R$251.600 do MEI Caminhoneiro
        assert r.excedeu_limite_mei is False
        assert r.payload["receitas"]["limiteAplicavel"] == "251600.00"
        assert r.payload["identificacao"]["atividadeMeiCaminhoneiro"] is True

    def test_mei_caminhoneiro_estoura_limite_ampliado(self) -> None:
        r = gerar_dasn_simei(
            "12345678000195",
            2025,
            DadosDasnSimei(
                receita_servicos=Decimal("260000.00"),
                eh_caminhoneiro=True,
            ),
        )
        assert r.excedeu_limite_mei is True

    def test_receita_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="negativas"):
            gerar_dasn_simei(
                "12345678000195",
                2025,
                DadosDasnSimei(receita_servicos=Decimal("-1")),
            )
