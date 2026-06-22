"""Golden tests do parcelamento ordinário (Sprint 11 PR3 + fix A6).

Fix A6: vencimentos postergam para o próximo dia útil quando caem em
sábado/domingo/feriado (IN RFB 1.300/2012 art. 26). O comportamento é
idêntico ao da agenda/gerar_calendario — posterga, nunca antecipa (≠ FGTS).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.parcelamentos.calcula_parcelamento import (
    ALGORITMO_VERSAO,
    TipoContribuinte,
    gerar_parcelamento_ordinario,
)

# ── Reconciliação de centavos ─────────────────────────────────────────────────


class TestReconciliacaoCentavos:
    """sum(parcelas) deve ser SEMPRE igual a divida_consolidada (FIX #13 PR6)."""

    def test_1000_em_3_parcelas_fecha_exato(self) -> None:
        # 1000 / 3 = 333,33 × 3 = 999,99 sem reconciliação → bug
        # Com fix: 333,33 + 333,33 + 333,34 = 1000,00
        r = gerar_parcelamento_ordinario(
            Decimal("1000.00"), 3, date(2026, 1, 1),
        )
        soma = sum(p.valor_projetado for p in r.parcelas)
        assert soma == Decimal("1000.00")
        # Última parcela absorve o centavo extra
        assert r.parcelas[-1].valor_projetado == Decimal("333.34")
        assert r.parcelas[0].valor_projetado == Decimal("333.33")

    def test_divisao_irregular_em_7_parcelas_fecha_exato(self) -> None:
        # 2001 / 7 = 285,857... → arredondado 285,86 × 7 = 2001,02 sem reconciliação → bug
        # 2001 / 7: parcela_base=285,86; última=2001 - 285,86×6 = 2001 - 1715,16 = 285,84
        r = gerar_parcelamento_ordinario(
            Decimal("2001.00"), 7, date(2026, 1, 1),
        )
        soma = sum(p.valor_projetado for p in r.parcelas)
        assert soma == Decimal("2001.00")

    def test_divisao_exata_todas_iguais(self) -> None:
        # 60.000 / 60 = 1.000,00 exato — todas devem ser iguais
        r = gerar_parcelamento_ordinario(
            Decimal("60000.00"), 60, date(2026, 1, 1),
        )
        soma = sum(p.valor_projetado for p in r.parcelas)
        assert soma == Decimal("60000.00")
        assert all(p.valor_projetado == Decimal("1000.00") for p in r.parcelas)

    def test_reconciliacao_pf_7_parcelas(self) -> None:
        # 1001 / 7 = 143,0142... → 143,01 × 7 = 1001,07 sem reconciliação
        r = gerar_parcelamento_ordinario(
            Decimal("1001.00"), 7, date(2026, 1, 1),
            contribuinte=TipoContribuinte.PF,
        )
        soma = sum(p.valor_projetado for p in r.parcelas)
        assert soma == Decimal("1001.00")

    @pytest.mark.parametrize("divida,n", [
        ("12000.00", 60),
        ("50000.00", 24),
        ("999.99", 3),
        ("1000.00", 3),
        ("2001.00", 7),
        ("10000.01", 6),
    ])
    def test_reconciliacao_invariante_parametrizado(self, divida: str, n: int) -> None:
        r = gerar_parcelamento_ordinario(
            Decimal(divida), n, date(2026, 6, 1),
        )
        soma = sum(p.valor_projetado for p in r.parcelas)
        assert soma == Decimal(divida)


class TestCronogramaBasico:
    def test_60k_em_60_parcelas(self) -> None:
        # 60.000 / 60 = 1.000 por parcela
        r = gerar_parcelamento_ordinario(
            Decimal("60000.00"), 60, date(2026, 5, 15),
        )
        assert r.parcela_base == Decimal("1000.00")
        assert len(r.parcelas) == 60
        assert r.parcelas[0].numero == 1
        assert r.parcelas[0].vencimento == date(2026, 6, 15)
        assert r.parcelas[-1].numero == 60
        # 60 meses após maio/2026 = maio/2031
        assert r.parcelas[-1].vencimento == date(2031, 5, 15)
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_24_parcelas_quebrado(self) -> None:
        # 50.000 / 24 = 2.083,3333... → 2.083,33
        r = gerar_parcelamento_ordinario(
            Decimal("50000.00"), 24, date(2026, 1, 10),
        )
        assert r.parcela_base == Decimal("2083.33")
        assert len(r.parcelas) == 24

    def test_uma_parcela_unica(self) -> None:
        # Dívida pequena em parcela única.
        # 05/04/2026 é domingo → posterga para 06/04/2026 (segunda).
        r = gerar_parcelamento_ordinario(
            Decimal("500.00"), 1, date(2026, 3, 5),
        )
        assert r.parcela_base == Decimal("500.00")
        assert len(r.parcelas) == 1
        assert r.parcelas[0].vencimento == date(2026, 4, 6)  # segunda (domingo postergado)


class TestParcelaMinimaPJ:
    def test_atinge_minima_exato(self) -> None:
        # 12.000 / 60 = 200 (exato — limite)
        r = gerar_parcelamento_ordinario(
            Decimal("12000.00"), 60, date(2026, 1, 1),
        )
        assert r.parcela_base == Decimal("200.00")
        assert r.parcela_minima_aplicavel == Decimal("200.00")

    def test_abaixo_minima_levanta(self) -> None:
        # 11.000 / 60 = 183,33 < 200
        with pytest.raises(ValueError, match="parcela_base.*200"):
            gerar_parcelamento_ordinario(
                Decimal("11000.00"), 60, date(2026, 1, 1),
            )


class TestParcelaMinimaPF:
    def test_pf_minima_100(self) -> None:
        # 6.000 / 60 = 100 (exato PF)
        r = gerar_parcelamento_ordinario(
            Decimal("6000.00"), 60, date(2026, 1, 1),
            contribuinte=TipoContribuinte.PF,
        )
        assert r.parcela_base == Decimal("100.00")
        assert r.parcela_minima_aplicavel == Decimal("100.00")

    def test_pf_abaixo_minima_levanta(self) -> None:
        with pytest.raises(ValueError, match="parcela_base.*100"):
            gerar_parcelamento_ordinario(
                Decimal("5000.00"), 60, date(2026, 1, 1),
                contribuinte=TipoContribuinte.PF,
            )


class TestDiaSemEquivalente:
    def test_31_janeiro_vai_para_28_fevereiro_postergado(self) -> None:
        # Adesão em 31/jan/2026 (não bissexto): candidato 28/fev/2026.
        # 28/02/2026 é sábado → posterga para 02/03/2026 (segunda).
        # Parcela 2: candidato 31/mar/2026 (terça) → mantém.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 12, date(2026, 1, 31),
        )
        assert r.parcelas[0].vencimento == date(2026, 3, 2)   # segunda (sábado postergado)
        assert r.parcelas[1].vencimento == date(2026, 3, 31)  # terça — dia útil

    def test_31_janeiro_em_ano_bissexto_vai_para_29(self) -> None:
        # 2024 é bissexto; 29/02/2024 é quinta-feira → dia útil, mantém.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 12, date(2024, 1, 31),
        )
        assert r.parcelas[0].vencimento == date(2024, 2, 29)

    def test_atravessa_ano(self) -> None:
        # Adesão dez/2026 → 1ª em jan/2027.
        # 10/01/2027 é domingo → posterga para 11/01/2027 (segunda).
        # 10/02/2027 é quarta → mantém.
        # 10/03/2027 é quarta → mantém.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 3, date(2026, 12, 10),
        )
        assert r.parcelas[0].vencimento == date(2027, 1, 11)  # segunda (domingo postergado)
        assert r.parcelas[1].vencimento == date(2027, 2, 10)  # quarta — dia útil
        assert r.parcelas[2].vencimento == date(2027, 3, 10)  # quarta — dia útil


class TestDiaUtilVencimento:
    """Golden cases A6 — postergação de vencimento para próximo dia útil.

    Comportamento esperado (IN RFB 1.300/2012 art. 26):
      * sábado  → próxima segunda (salvo feriado na segunda → terça, etc.)
      * domingo → próxima segunda (salvo feriado na segunda → terça, etc.)
      * feriado → próximo dia útil
      * dia útil → mantém
    """

    def test_vencimento_em_sabado_vai_para_segunda(self) -> None:
        # Adesão 05/jan/2026 (segunda); 1ª parcela nominal = 05/fev/2026 (quinta) → mantém.
        # Usamos adesão 31/jan/2026: 1ª parcela nominal = 28/fev/2026 (sábado) → 02/mar/2026.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 3, date(2026, 1, 31),
        )
        assert r.parcelas[0].vencimento == date(2026, 3, 2)  # segunda (sábado 28/fev postergado)
        assert r.parcelas[0].vencimento.weekday() == 0        # 0 = segunda

    def test_vencimento_em_domingo_vai_para_segunda(self) -> None:
        # Adesão 05/mar/2026; 1ª parcela nominal = 05/abr/2026 (domingo) → 06/abr/2026.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 1, date(2026, 3, 5),
        )
        assert r.parcelas[0].vencimento == date(2026, 4, 6)  # segunda (domingo 05/abr postergado)
        assert r.parcelas[0].vencimento.weekday() == 0

    def test_vencimento_em_feriado_vai_para_proximo_dia_util(self) -> None:
        # Adesão 21/abr/2026 (terça; Tiradentes — não altera adesão, só vencimento).
        # 1ª parcela nominal = 21/mai/2026 (quinta) → dia útil, mantém.
        # Testamos feriado passado explicitamente: 21/mai/2026 como feriado →
        # posterga para 22/mai/2026 (sexta).
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 1, date(2026, 4, 21),
            feriados=[date(2026, 5, 21)],
        )
        assert r.parcelas[0].vencimento == date(2026, 5, 22)  # sexta (feriado postergado)

    def test_vencimento_em_feriado_segunda_vai_para_terca(self) -> None:
        # Se o próximo dia útil após fim de semana também é feriado, avança mais um dia.
        # Nominal = sábado → segunda é feriado → terça.
        # Adesão: 31/jan/2026; parcela 1 nominal = 28/fev/2026 (sábado).
        # 02/mar/2026 (segunda) marcada como feriado → vai para 03/mar/2026 (terça).
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 1, date(2026, 1, 31),
            feriados=[date(2026, 3, 2)],
        )
        assert r.parcelas[0].vencimento == date(2026, 3, 3)  # terça

    def test_vencimento_em_dia_util_mantem(self) -> None:
        # Adesão 05/jan/2026 (segunda); 1ª parcela nominal = 05/fev/2026 (quinta) → mantém.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 1, date(2026, 1, 5),
        )
        assert r.parcelas[0].vencimento == date(2026, 2, 5)  # quinta — dia útil
        assert r.parcelas[0].vencimento.weekday() == 3       # 3 = quinta

    def test_sem_feriados_somente_fds_postergado(self) -> None:
        # Garante que sem feriados apenas sábado/domingo são tratados.
        # Adesão 10/dez/2026; parcela 1 nominal = 10/jan/2027 (domingo) → 11/jan/2027.
        r = gerar_parcelamento_ordinario(
            Decimal("12000"), 1, date(2026, 12, 10),
        )
        assert r.parcelas[0].vencimento == date(2027, 1, 11)  # segunda


class TestBordas:
    def test_divida_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="divida_consolidada"):
            gerar_parcelamento_ordinario(
                Decimal("0"), 10, date(2026, 1, 1),
            )

    def test_divida_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="divida_consolidada"):
            gerar_parcelamento_ordinario(
                Decimal("-1"), 10, date(2026, 1, 1),
            )

    def test_num_parcelas_zero_levanta(self) -> None:
        with pytest.raises(ValueError, match="num_parcelas"):
            gerar_parcelamento_ordinario(
                Decimal("1000"), 0, date(2026, 1, 1),
            )

    def test_num_parcelas_61_levanta(self) -> None:
        with pytest.raises(ValueError, match="num_parcelas"):
            gerar_parcelamento_ordinario(
                Decimal("100000"), 61, date(2026, 1, 1),
            )
