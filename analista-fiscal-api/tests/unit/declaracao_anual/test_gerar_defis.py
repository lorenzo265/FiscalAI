"""Golden tests do gerador puro DEFIS (Sprint 6 PR3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.declaracao_anual.gerar_defis import (
    GERADOR_VERSAO,
    ApuracaoMensalSN,
    DadosSocioeconomicos,
    SocioDefis,
    gerar_defis,
)


def _apuracao(mes: int, receita: str, das: str, ano: int = 2025) -> ApuracaoMensalSN:
    return ApuracaoMensalSN(
        competencia=f"{ano:04d}-{mes:02d}",
        receita_mes=Decimal(receita),
        valor_das=Decimal(das),
        anexo="III",
        anexo_efetivo="III",
    )


class TestGerarDefisGolden:
    def test_consolidacao_12_meses(self) -> None:
        apuracoes = tuple(
            _apuracao(m, "10000.00", "650.00") for m in range(1, 13)
        )
        resultado = gerar_defis(
            "12345678000195",
            2025,
            apuracoes,
            DadosSocioeconomicos(
                lucro_contabil_anual=Decimal("20000.00"),
                socios=(
                    SocioDefis(
                        cpf="52998224725",
                        nome="Sócio Único",
                        percentual_capital=Decimal("100.00"),
                    ),
                ),
            ),
        )
        assert resultado.receita_bruta_anual == Decimal("120000.00")
        assert resultado.total_das_anual == Decimal("7800.00")
        assert resultado.meses_apurados == 12
        assert resultado.algoritmo_versao == GERADOR_VERSAO

        payload = resultado.payload
        assert payload["identificacao"]["cnpj"] == "12345678000195"
        assert payload["receitas"]["receitaBrutaAnual"] == "120000.00"
        assert payload["informacoesEconomicas"]["lucroContabil"] == "20000.00"
        assert len(payload["socios"]) == 1
        assert payload["socios"][0]["percentualCapital"] == "100.00"

    def test_meses_parciais_aceitos(self) -> None:
        # Empresa que abriu em julho — 6 meses só
        apuracoes = tuple(_apuracao(m, "5000.00", "300.00") for m in range(7, 13))
        resultado = gerar_defis(
            "12345678000195",
            2025,
            apuracoes,
            DadosSocioeconomicos(),
        )
        assert resultado.meses_apurados == 6
        assert resultado.receita_bruta_anual == Decimal("30000.00")

    def test_sem_socios_aceito(self) -> None:
        resultado = gerar_defis(
            "12345678000195",
            2025,
            (_apuracao(1, "1000.00", "100.00"),),
            DadosSocioeconomicos(),
        )
        assert resultado.payload["socios"] == []


class TestValidacoes:
    def test_competencia_fora_do_ano_levanta(self) -> None:
        ap = _apuracao(1, "1000.00", "100.00", ano=2024)
        with pytest.raises(ValueError, match="fora do ano_base"):
            gerar_defis(
                "12345678000195", 2025, (ap,), DadosSocioeconomicos()
            )

    def test_quadro_societario_invalido(self) -> None:
        socios = (
            SocioDefis(
                cpf="52998224725",
                nome="A",
                percentual_capital=Decimal("60.00"),
            ),
            SocioDefis(
                cpf="11144477735",
                nome="B",
                percentual_capital=Decimal("30.00"),  # soma 90% ≠ 100%
            ),
        )
        with pytest.raises(ValueError, match="esperado 100"):
            gerar_defis(
                "12345678000195",
                2025,
                (_apuracao(1, "1000", "100"),),
                DadosSocioeconomicos(socios=socios),
            )

    def test_quadro_societario_tolerancia_centesimo(self) -> None:
        # Tolerância 0.01% — 99.995 + 0.005 = 100 → ok arredondado
        socios = (
            SocioDefis(
                cpf="52998224725",
                nome="A",
                percentual_capital=Decimal("99.99"),
            ),
            SocioDefis(
                cpf="11144477735",
                nome="B",
                percentual_capital=Decimal("0.01"),
            ),
        )
        # Não deve levantar
        gerar_defis(
            "12345678000195",
            2025,
            (_apuracao(1, "1000", "100"),),
            DadosSocioeconomicos(socios=socios),
        )


class TestDeterminismo:
    def test_mesmo_input_mesmo_payload(self) -> None:
        a = (_apuracao(3, "8000.00", "520.00"),)
        s = DadosSocioeconomicos(lucro_contabil_anual=Decimal("100"))
        r1 = gerar_defis("12345678000195", 2025, a, s)
        r2 = gerar_defis("12345678000195", 2025, a, s)
        assert r1.payload == r2.payload
