"""Golden tests do `calcula_hora_extra` (Sprint 19.8 PR1 #12)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_hora_extra import (
    ALGORITMO_VERSAO,
    calcular_adicional_noturno,
    calcular_desconto_falta,
    calcular_hora_extra,
    calcular_salario_hora,
)


class TestSalarioHora:
    def test_canonico_44h_220h_mes(self) -> None:
        """Salário R$ 2.200 / 220h/mês = R$ 10,00/h."""
        h = calcular_salario_hora(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
        )
        assert h == Decimal("10.0000")

    def test_jornada_40h_200h_mes(self) -> None:
        h = calcular_salario_hora(
            salario_mensal=Decimal("1800"),
            jornada_semanal_horas=Decimal("40"),
        )
        # 1800 / (40 × 5) = 1800 / 200 = 9
        assert h == Decimal("9.0000")

    def test_salario_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario"):
            calcular_salario_hora(
                salario_mensal=Decimal("0"),
                jornada_semanal_horas=Decimal("44"),
            )

    def test_jornada_acima_44h_levanta(self) -> None:
        with pytest.raises(ValueError, match="jornada"):
            calcular_salario_hora(
                salario_mensal=Decimal("2200"),
                jornada_semanal_horas=Decimal("50"),
            )


class TestHoraExtra:
    def test_50_porcento_canonico(self) -> None:
        """4h × R$ 10/h × 1.5 = R$ 60."""
        r = calcular_hora_extra(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_extras=Decimal("4"),
        )
        assert r.valor == Decimal("60.00")
        assert r.salario_hora_normal == Decimal("10.0000")
        assert r.percentual_adicional == Decimal("0.5")

    def test_100_porcento_domingo_feriado(self) -> None:
        """4h × R$ 10/h × 2.0 = R$ 80."""
        r = calcular_hora_extra(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_extras=Decimal("4"),
            percentual_adicional=Decimal("1.0"),
        )
        assert r.valor == Decimal("80.00")

    def test_horas_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="horas_extras"):
            calcular_hora_extra(
                salario_mensal=Decimal("2200"),
                jornada_semanal_horas=Decimal("44"),
                horas_extras=Decimal("0"),
            )

    def test_percentual_fora_intervalo_levanta(self) -> None:
        with pytest.raises(ValueError, match="percentual"):
            calcular_hora_extra(
                salario_mensal=Decimal("2200"),
                jornada_semanal_horas=Decimal("44"),
                horas_extras=Decimal("4"),
                percentual_adicional=Decimal("3.0"),  # > 2.0
            )


class TestAdicionalNoturno:
    def test_20_porcento_padrao(self) -> None:
        """10h noturnas × R$ 10/h × 20% = R$ 20."""
        r = calcular_adicional_noturno(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_noturnas=Decimal("10"),
        )
        assert r.valor == Decimal("20.00")
        assert r.percentual_adicional == Decimal("0.20")

    def test_percentual_via_cct_maior(self) -> None:
        """CCT pode prever 35% — admin informa."""
        r = calcular_adicional_noturno(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_noturnas=Decimal("10"),
            percentual=Decimal("0.35"),
        )
        assert r.valor == Decimal("35.00")


class TestFalta:
    def test_falta_um_dia_canonica(self) -> None:
        """R$ 3.000 / 30 = R$ 100,00."""
        r = calcular_desconto_falta(
            salario_mensal=Decimal("3000"),
            dias_faltados=1,
        )
        assert r.valor_desconto == Decimal("100.00")
        assert r.salario_diario == Decimal("100.0000")
        assert r.dias_faltados == 1

    def test_falta_5_dias(self) -> None:
        r = calcular_desconto_falta(
            salario_mensal=Decimal("3000"),
            dias_faltados=5,
        )
        assert r.valor_desconto == Decimal("500.00")

    def test_dias_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="dias_faltados"):
            calcular_desconto_falta(
                salario_mensal=Decimal("3000"),
                dias_faltados=0,
            )

    def test_dias_acima_30_levanta(self) -> None:
        with pytest.raises(ValueError, match="dias_faltados"):
            calcular_desconto_falta(
                salario_mensal=Decimal("3000"),
                dias_faltados=31,
            )


def test_algoritmo_versao_v1() -> None:
    assert ALGORITMO_VERSAO == "hora_extra.v1"
