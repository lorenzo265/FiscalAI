"""Golden tests do `calcula_hora_extra` (Sprint 19.8 PR1 #12).

FA8 m4 (2026-06-04): testes de adicional noturno atualizados para refletir
a correção da hora noturna reduzida (CLT art. 73 §1º — 52min30s por hora
noturna). Os valores antigos subestimavam o adicional em ~14,3%.

FA8 m5 (2026-06-04): novo teste confirma que ResultadoHoraExtra documenta
explicitamente que o valor é parcial (sem reflexo de DSR).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_hora_extra import (
    ALGORITMO_VERSAO,
    ResultadoHoraExtra,
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
        """10h reais noturnas → hora reduzida (CLT art. 73 §1º).

        Cálculo correto (FA8 m4 — hora noturna = 52min30s):
          horas_reduzidas = 10 × (60 / 52,5) = 11,4286h
          adicional = R$ 10,00/h × 20% × 11,4286 = R$ 22,86

        O valor antigo (R$ 20,00) ignorava a hora reduzida e subestimava
        o adicional em ~14,3%. Corrigido conforme CLT art. 73 §1º.
        """
        r = calcular_adicional_noturno(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_noturnas=Decimal("10"),
        )
        assert r.valor == Decimal("22.86")
        assert r.percentual_adicional == Decimal("0.20")
        # Campo de auditoria preenchido (m4)
        assert r.horas_noturnas_reduzidas == Decimal("11.4286")
        # horas_calculadas ainda guarda as horas reais (input original)
        assert r.horas_calculadas == Decimal("10")

    def test_percentual_via_cct_maior(self) -> None:
        """CCT pode prever 35% — admin informa.

        10h reais → 11,4286h reduzidas × R$ 10/h × 35% = R$ 40,00.
        Valor antigo (R$ 35,00) ignorava a hora reduzida — corrigido (FA8 m4).
        """
        r = calcular_adicional_noturno(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_noturnas=Decimal("10"),
            percentual=Decimal("0.35"),
        )
        assert r.valor == Decimal("40.00")
        assert r.horas_noturnas_reduzidas == Decimal("11.4286")

    def test_hora_noturna_reduzida_7h_reais_8h_nominais(self) -> None:
        """Golden canônico CLT art. 73 §1º: 7 horas reais = 8 horas nominais.

        7h × (60 / 52,5) = 8,0000h-reduzidas.
        Salário R$ 2.200 / 220h = R$ 10,00/h.
        Adicional = R$ 10,00 × 20% × 8,0000 = R$ 16,00.
        """
        r = calcular_adicional_noturno(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_noturnas=Decimal("7"),
        )
        assert r.horas_noturnas_reduzidas == Decimal("8.0000")
        assert r.valor == Decimal("16.00")

    def test_hora_extra_nao_tem_horas_reduzidas(self) -> None:
        """calcular_hora_extra não preenche horas_noturnas_reduzidas (campo None)."""
        r = calcular_hora_extra(
            salario_mensal=Decimal("2200"),
            jornada_semanal_horas=Decimal("44"),
            horas_extras=Decimal("4"),
        )
        assert r.horas_noturnas_reduzidas is None


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


def test_algoritmo_versao_v2() -> None:
    """FA8 m4: bump v1→v2 pela correção da hora noturna reduzida."""
    assert ALGORITMO_VERSAO == "hora_extra.v2"


class TestDsrDocumentado:
    """m5 FA8: ResultadoHoraExtra documenta que o valor é parcial (sem DSR)."""

    def test_resultado_hora_extra_tem_campo_horas_noturnas_reduzidas(self) -> None:
        """Campo horas_noturnas_reduzidas existe no dataclass (m4+m5 FA8)."""
        import dataclasses
        campos = {f.name for f in dataclasses.fields(ResultadoHoraExtra)}
        assert "horas_noturnas_reduzidas" in campos

    def test_docstring_menciona_dsr(self) -> None:
        """Docstring da classe menciona DSR e valor parcial (m5 FA8)."""
        doc = ResultadoHoraExtra.__doc__ or ""
        assert "DSR" in doc
        assert "parcial" in doc.lower() or "PARCIAL" in doc
