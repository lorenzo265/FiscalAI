"""Golden tests do IRRF mensal (Sprint 10 PR1 + FA2 M4/M5).

FA2 M4: pensao_alimenticia judicial é dedução legal da base (Lei 9.250/1995).
FA2 M5: desconto simplificado mensal (Lei 14.848/2024) = 25% × teto faixa 1
        (2259,20 × 25% = 564,80). O método mais benéfico é aplicado
        automaticamente; ResultadoIrrf.metodo indica qual foi escolhido.

Goldens afetados por M5 (desconto simplificado ganha):
  * test_salario_3000_faixa_2:
      irrf_legal=36,55 vs irrf_simpl=13,20 → simplificado (−23,35 BRL).
  * test_salario_5000_faixa_4:
      irrf_legal=347,57 vs irrf_simpl=335,15 → simplificado (−12,42 BRL).
  Esses valores são FISCALMENTE CORRETOS — a lei garante o método mais benéfico.

Goldens não afetados (legal ganha):
  * test_salario_alto_faixa_5: irrf_legal=2967,30 vs irrf_simpl=3073,68.
  * test_dependente_reduz_base: irrf_legal=8,12 vs irrf_simpl=13,20.
  * test_muitos_dependentes_zera_irrf: irrf_legal=0 vs irrf_simpl=13,20.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_irrf import (
    ALGORITMO_VERSAO,
    FaixaIrrf,
    calcular_irrf_mensal,
)

# Faixas vigentes (Lei 14.848/2024 + MP 1.171/2024, vigência fev/2024).
DEP = Decimal("189.59")
FAIXAS_VIGENTES = [
    FaixaIrrf(faixa=1, base_ate=Decimal("2259.20"), aliquota=Decimal("0.0000"),
              parcela_deduzir=Decimal("0.00"), deducao_dependente=DEP),
    FaixaIrrf(faixa=2, base_ate=Decimal("2826.65"), aliquota=Decimal("0.0750"),
              parcela_deduzir=Decimal("169.44"), deducao_dependente=DEP),
    FaixaIrrf(faixa=3, base_ate=Decimal("3751.05"), aliquota=Decimal("0.1500"),
              parcela_deduzir=Decimal("381.44"), deducao_dependente=DEP),
    FaixaIrrf(faixa=4, base_ate=Decimal("4664.68"), aliquota=Decimal("0.2250"),
              parcela_deduzir=Decimal("662.77"), deducao_dependente=DEP),
    FaixaIrrf(faixa=5, base_ate=Decimal("999999999.99"), aliquota=Decimal("0.2750"),
              parcela_deduzir=Decimal("896.00"), deducao_dependente=DEP),
]

# desconto_simplificado = 0,25 × 2259,20 = 564,80
_DESCONTO_SIMPL = Decimal("564.80")


class TestGoldenSemDependentes:
    def test_salario_baixo_isento(self) -> None:
        # base_legal = 2000 − 150 − 0 = 1850 → faixa 1 → 0
        # base_simpl = 2000 − 564,80 = 1435,20 → faixa 1 → 0
        # min(0, 0) = 0 → metodo=legal (empate → legal)
        r = calcular_irrf_mensal(
            Decimal("2000.00"), Decimal("150.00"), 0, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("0.00")
        assert r.faixa == 1
        assert r.metodo == "legal"

    def test_salario_3000_faixa_2(self) -> None:
        # base_legal = 3000 − 253,41 = 2746,59 → faixa 2
        # irrf_legal = 2746,59 × 7,5% − 169,44 = 205,99425 − 169,44 = 36,55425 → 36,55
        # base_simpl = 3000 − 564,80 = 2435,20 → faixa 2
        # irrf_simpl = 2435,20 × 7,5% − 169,44 = 182,64 − 169,44 = 13,20
        # min(36,55 ; 13,20) = 13,20 → SIMPLIFICADO (−23,35 BRL vs método legal)
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 2
        assert r.base_irrf == Decimal("2435.20")  # base do simplificado
        assert r.irrf == Decimal("13.20")
        assert r.metodo == "simplificado"

    def test_salario_5000_faixa_4(self) -> None:
        # base_legal = 5000 − 509,60 = 4490,40 → faixa 4
        # irrf_legal = 4490,40 × 22,5% − 662,77 = 1010,34 − 662,77 = 347,57
        # base_simpl = 5000 − 564,80 = 4435,20 → faixa 4
        # irrf_simpl = 4435,20 × 22,5% − 662,77 = 997,92 − 662,77 = 335,15
        # min(347,57 ; 335,15) = 335,15 → SIMPLIFICADO (−12,42 BRL vs método legal)
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("509.60"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 4
        assert r.base_irrf == Decimal("4435.20")  # base do simplificado
        assert r.irrf == Decimal("335.15")
        assert r.metodo == "simplificado"

    def test_salario_alto_faixa_5(self) -> None:
        # base_legal = 15000 − 951,63 = 14048,37 → faixa 5
        # irrf_legal = 14048,37 × 27,5% − 896 = 3863,30175 − 896 = 2967,30175 → 2967,30
        # base_simpl = 15000 − 564,80 = 14435,20 → faixa 5
        # irrf_simpl = 14435,20 × 27,5% − 896 = 3969,68 − 896 = 3073,68
        # min(2967,30 ; 3073,68) = 2967,30 → LEGAL GANHA
        r = calcular_irrf_mensal(
            Decimal("15000.00"), Decimal("951.63"), 0, FAIXAS_VIGENTES
        )
        assert r.faixa == 5
        assert r.irrf == Decimal("2967.30")
        assert r.metodo == "legal"


class TestGoldenComDependentes:
    def test_dependente_reduz_base(self) -> None:
        # base_legal = 3000 − 253,41 − 379,18 = 2367,41 → faixa 2
        # irrf_legal = 2367,41 × 7,5% − 169,44 = 177,55575 − 169,44 = 8,11575 → 8,12
        # base_simpl = 3000 − 564,80 = 2435,20 → faixa 2
        # irrf_simpl = 13,20
        # min(8,12 ; 13,20) = 8,12 → LEGAL GANHA (dedução por deps supera desconto)
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 2, FAIXAS_VIGENTES
        )
        assert r.dependentes == 2
        assert r.deducao_dependentes == Decimal("379.18")
        assert r.base_irrf == Decimal("2367.41")  # base do legal
        assert r.faixa == 2
        assert r.irrf == Decimal("8.12")
        assert r.metodo == "legal"

    def test_muitos_dependentes_zera_irrf(self) -> None:
        # base_legal = 3000 − 253,41 − 947,95 = 1798,64 → faixa 1 → 0
        # base_simpl = 2435,20 → faixa 2 → 13,20
        # min(0 ; 13,20) = 0 → LEGAL GANHA
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 5, FAIXAS_VIGENTES
        )
        assert r.faixa == 1
        assert r.irrf == Decimal("0.00")
        assert r.metodo == "legal"


class TestPensaoAlimenticia:
    """M4 — Pensão alimentícia judicial como dedução legal (Lei 9.250/1995)."""

    def test_pensao_reduz_base_e_irrf(self) -> None:
        # Salário 3000, INSS 253,41, 0 deps, pensão 300
        # base_legal = 3000 − 253,41 − 0 − 300 = 2446,59 → faixa 2
        # irrf_legal = 2446,59 × 7,5% − 169,44 = 183,49425 − 169,44 = 14,05425 → 14,05
        # base_simpl = 2435,20 → irrf_simpl = 13,20
        # min(14,05 ; 13,20) = 13,20 → SIMPLIFICADO
        r = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 0, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("300.00"),
        )
        assert r.pensao_alimenticia == Decimal("300.00")
        assert r.irrf == Decimal("13.20")
        assert r.metodo == "simplificado"

    def test_pensao_alta_legal_vence(self) -> None:
        # Salário 5000, INSS 509,60, 2 deps (379,18), pensão 500
        # base_legal = 5000 − 509,60 − 379,18 − 500 = 3611,22 → faixa 3
        # irrf_legal = 3611,22 × 15% − 381,44 = 541,683 − 381,44 = 160,24
        # base_simpl = 5000 − 564,80 = 4435,20 → faixa 4 → 335,15
        # min(160,24 ; 335,15) = 160,24 → LEGAL GANHA
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("509.60"), 2, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("500.00"),
        )
        assert r.pensao_alimenticia == Decimal("500.00")
        assert r.metodo == "legal"
        assert r.irrf == Decimal("160.24")

    def test_pensao_zero_backward_compat(self) -> None:
        # Comportamento idêntico ao caso sem pensão (default=0)
        r_sem = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        r_com_zero = calcular_irrf_mensal(
            Decimal("3000.00"), Decimal("253.41"), 0, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("0.00"),
        )
        assert r_sem == r_com_zero

    def test_pensao_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="pensao_alimenticia"):
            calcular_irrf_mensal(
                Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES,
                pensao_alimenticia=Decimal("-1"),
            )

    def test_muitos_deps_mais_pensao_legal_vence(self) -> None:
        # 4 deps × 189,59 = 758,36 + pensão 300 = total dedução 1058,36
        # base_legal = 5000 − 509,60 − 758,36 − 300 = 3432,04 → faixa 3
        # irrf_legal = 3432,04 × 15% − 381,44 = 514,806 − 381,44 = 133,37
        # base_simpl = 4435,20 → 335,15
        # min(133,37 ; 335,15) = 133,37 → LEGAL GANHA
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("509.60"), 4, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("300.00"),
        )
        assert r.metodo == "legal"
        assert r.irrf == Decimal("133.37")


class TestDescontoSimplificado:
    """M5 — Desconto simplificado mensal derivado da SCD (Lei 14.848/2024)."""

    def test_desconto_derivado_da_faixa_1(self) -> None:
        # Verifica que o desconto simplificado = 0,25 × base_ate da faixa 1.
        # Com FAIXAS_VIGENTES: teto_faixa_1 = 2259,20 → desconto = 564,80.
        # Salário 3500, INSS 300, 0 deps:
        # base_legal = 3500 − 300 = 3200 → faixa 3 (≤ 3751,05)
        #   irrf_legal = 3200 × 15% − 381,44 = 480 − 381,44 = 98,56
        # base_simpl = 3500 − 564,80 = 2935,20 → faixa 3 (> 2826,65; ≤ 3751,05)
        #   irrf_simpl = 2935,20 × 15% − 381,44 = 440,28 − 381,44 = 58,84
        # min(98,56 ; 58,84) = 58,84 → SIMPLIFICADO
        r = calcular_irrf_mensal(
            Decimal("3500.00"), Decimal("300.00"), 0, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("58.84")
        assert r.metodo == "simplificado"
        # Confirma base do simplificado = bruto − desconto
        assert r.base_irrf == Decimal("3500.00") - _DESCONTO_SIMPL

    def test_simplificado_resultado_menor(self) -> None:
        # Garante invariante: irrf ≤ IRRF calculado só pelo método legal.
        # Salário 4000, INSS 400, 0 deps:
        # base_legal = 3600 → faixa 3 → 3600×15%−381,44 = 540−381,44 = 158,56
        # base_simpl = 3435,20 → faixa 3 → 3435,20×15%−381,44 = 515,28−381,44 = 133,84
        # min(158,56 ; 133,84) = 133,84 → SIMPLIFICADO
        r = calcular_irrf_mensal(
            Decimal("4000.00"), Decimal("400.00"), 0, FAIXAS_VIGENTES
        )
        assert r.metodo == "simplificado"
        assert r.irrf == Decimal("133.84")

    def test_legal_vence_com_muitas_deducoes(self) -> None:
        # Salário alto, 3 deps + grande pensão → legal < simplificado.
        # Salário 5000, INSS 509,60, 3 deps × 189,59 = 568,77, pensão 400
        # base_legal = 5000 − 509,60 − 568,77 − 400 = 3521,63 → faixa 3
        # irrf_legal = 3521,63 × 15% − 381,44 = 528,2445 − 381,44 = 146,80
        # base_simpl = 4435,20 → faixa 4 → 335,15
        # min(146,80 ; 335,15) = 146,80 → LEGAL GANHA
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("509.60"), 3, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("400.00"),
        )
        assert r.metodo == "legal"
        assert r.irrf == Decimal("146.80")


class TestBordas:
    def test_salario_zero(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("0"), Decimal("0"), 0, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("0.00")
        assert r.base_irrf == Decimal("0.00")
        assert r.faixa == 1

    def test_base_negativa_vira_zero(self) -> None:
        # INSS + dependentes superam o bruto — base clampa em zero
        r = calcular_irrf_mensal(
            Decimal("1000"), Decimal("75"), 10, FAIXAS_VIGENTES
        )
        assert r.irrf == Decimal("0.00")
        assert r.faixa == 1

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario_bruto não pode"):
            calcular_irrf_mensal(
                Decimal("-1"), Decimal("0"), 0, FAIXAS_VIGENTES
            )

    def test_inss_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="inss_empregado não pode"):
            calcular_irrf_mensal(
                Decimal("1000"), Decimal("-1"), 0, FAIXAS_VIGENTES
            )

    def test_dependentes_negativos_levanta(self) -> None:
        with pytest.raises(ValueError, match="dependentes não pode"):
            calcular_irrf_mensal(
                Decimal("1000"), Decimal("0"), -1, FAIXAS_VIGENTES
            )

    def test_faixas_vazias_levanta(self) -> None:
        with pytest.raises(ValueError, match="faixas não pode"):
            calcular_irrf_mensal(Decimal("3000"), Decimal("253"), 0, [])


class TestEstrutura:
    def test_algoritmo_versao(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO
        assert ALGORITMO_VERSAO == "irrf.mensal.v2"

    def test_resultado_tem_campo_metodo(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        assert r.metodo in ("legal", "simplificado")

    def test_resultado_tem_campo_pensao(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES,
            pensao_alimenticia=Decimal("200.00"),
        )
        assert r.pensao_alimenticia == Decimal("200.00")

    def test_aceita_faixas_fora_de_ordem(self) -> None:
        embaralhadas = list(reversed(FAIXAS_VIGENTES))
        r1 = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_VIGENTES
        )
        r2 = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, embaralhadas
        )
        assert r1 == r2
