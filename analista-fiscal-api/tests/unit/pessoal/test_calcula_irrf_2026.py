"""Golden tests do IRRF mensal 2026 — tabela Lei 15.191/2025 + redutor Lei 15.270/2025.

Achado 🔴 #1 do auto de infração 2026-06-21 / pendência #9 do log_agente.md.

FONTES OFICIAIS
---------------
  * Tabela progressiva mensal 2026 (faixas, alíquotas, parcela a deduzir,
    dedução por dependente R$ 189,59, desconto simplificado R$ 607,20):
    Lei 15.191/2025. Vigência da SCD ``tabela_irrf_faixa``: 2026-01-01
    (migration 0059).
  * Redutor mensal da retenção: Lei 15.270/2025, vigência 01/01/2026.
    Exemplos resolvidos confirmados na página oficial da RFB:
    https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/exemplos-de-aplicacao-da-lei-15-270-2025

MÉTODO DO REDUTOR (confirmado nos exemplos da RFB)
--------------------------------------------------
  Referência = RENDIMENTO TRIBUTÁVEL BRUTO (o "salário", NÃO a base de cálculo —
  texto literal da RFB: "se utiliza nessa tabela de redução o valor do salário,
  e não o da base de cálculo"). Aplicado APÓS o IRRF tradicional (método mais
  benéfico), com piso 0:
      salario_bruto ≤ 5.000,00            → IRRF efetivo 0,00 (isenção efetiva)
      5.000,01 ≤ salario_bruto ≤ 7.350,00 → redutor = max(0, 978,62 − 0,133145 × salario_bruto)
                                            IRRF final = max(0, irrf_tradicional − redutor)
      salario_bruto > 7.350,00            → tabela cheia, sem redutor

Todos os centavos abaixo conferidos À MÃO (ROUND_HALF_EVEN), com a conta no
comentário de cada caso.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.pessoal.calcula_irrf import (
    ALGORITMO_VERSAO,
    FaixaIrrf,
    calcular_irrf_mensal,
)

# ── Tabela progressiva mensal 2026 (Lei 15.191/2025) — espelha o seed 0059 ──
DEP_2026 = Decimal("189.59")
FAIXAS_2026 = [
    FaixaIrrf(faixa=1, base_ate=Decimal("2428.80"), aliquota=Decimal("0.0000"),
              parcela_deduzir=Decimal("0.00"), deducao_dependente=DEP_2026),
    FaixaIrrf(faixa=2, base_ate=Decimal("2826.65"), aliquota=Decimal("0.0750"),
              parcela_deduzir=Decimal("182.16"), deducao_dependente=DEP_2026),
    FaixaIrrf(faixa=3, base_ate=Decimal("3751.05"), aliquota=Decimal("0.1500"),
              parcela_deduzir=Decimal("394.16"), deducao_dependente=DEP_2026),
    FaixaIrrf(faixa=4, base_ate=Decimal("4664.68"), aliquota=Decimal("0.2250"),
              parcela_deduzir=Decimal("675.49"), deducao_dependente=DEP_2026),
    FaixaIrrf(faixa=5, base_ate=Decimal("999999999.99"), aliquota=Decimal("0.2750"),
              parcela_deduzir=Decimal("908.73"), deducao_dependente=DEP_2026),
]

# desconto simplificado mensal = 0,25 × 2428,80 = 607,20
_DESCONTO_SIMPL_2026 = Decimal("607.20")


class TestRedutorBordas:
    """Bordas exatas da faixa do redutor (Lei 15.270/2025)."""

    def test_5000_isencao_efetiva(self) -> None:
        # salario_bruto = 5000,00 (≤ 5.000) → redutor zera o IRRF tradicional.
        # INSS 501,51 (progressivo 2026, realista). Tradicional:
        #   base_simpl = 5000 − 607,20 = 4392,80 → faixa 4
        #     irrf_simpl = 4392,80×0,225 − 675,49 = 988,38 − 675,49 = 312,89
        #   base_legal = 5000 − 501,51 = 4498,49 → faixa 4
        #     irrf_legal = 4498,49×0,225 − 675,49 = 1012,16025 − 675,49 = 336,67
        #   tradicional = min(336,67 ; 312,89) = 312,89 (simplificado)
        # redutor (≤5000) = 312,89 → irrf_final = 0,00
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("501.51"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.irrf_tradicional == Decimal("312.89")
        assert r.redutor_lei_15270 == Decimal("312.89")
        assert r.irrf == Decimal("0.00")
        assert r.metodo == "simplificado"

    def test_5000_01_primeiro_centavo_acima(self) -> None:
        # salario_bruto = 5000,01 → entra na fórmula linear.
        #   redutor = 978,62 − 0,133145×5000,01
        #           = 978,62 − 665,72633145 = 312,89366855 → 312,89
        #   base_simpl = 5000,01 − 607,20 = 4392,81 → faixa 4
        #     irrf_simpl = 4392,81×0,225 − 675,49 = 988,38225 − 675,49 = 312,89225 → 312,89
        #   tradicional = 312,89 ; redutor capado ao imposto = 312,89
        #   irrf_final = 312,89 − 312,89 = 0,00 (transição suave; sem degrau)
        r = calcular_irrf_mensal(
            Decimal("5000.01"), Decimal("501.51"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.irrf_tradicional == Decimal("312.89")
        assert r.redutor_lei_15270 == Decimal("312.89")
        assert r.irrf == Decimal("0.00")

    def test_7350_borda_superior_redutor_quase_zero(self) -> None:
        # salario_bruto = 7350,00 (= teto da faixa do redutor).
        #   redutor = 978,62 − 0,133145×7350 = 978,62 − 978,61575 = 0,00425 → 0,00
        # INSS 0 (isola a aritmética). Tradicional:
        #   base_simpl = 7350 − 607,20 = 6742,80 → faixa 5
        #     irrf_simpl = 6742,80×0,275 − 908,73 = 1854,27 − 908,73 = 945,54
        #   base_legal = 7350 → faixa 5
        #     irrf_legal = 7350×0,275 − 908,73 = 2021,25 − 908,73 = 1112,52
        #   tradicional = min(1112,52 ; 945,54) = 945,54 (simplificado)
        #   irrf_final = 945,54 − 0,00 = 945,54
        r = calcular_irrf_mensal(
            Decimal("7350.00"), Decimal("0.00"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.irrf_tradicional == Decimal("945.54")
        assert r.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf == Decimal("945.54")
        assert r.metodo == "simplificado"

    def test_7350_01_tabela_cheia_sem_redutor(self) -> None:
        # salario_bruto = 7350,01 (> 7.350) → tabela cheia, redutor = 0.
        # INSS 0. base_simpl = 7350,01 − 607,20 = 6742,81 → faixa 5
        #   irrf_simpl = 6742,81×0,275 − 908,73 = 1854,27275 − 908,73 = 945,54275 → 945,54
        # irrf_final = 945,54 ; redutor = 0,00 (continuidade com o caso 7350,00)
        r = calcular_irrf_mensal(
            Decimal("7350.01"), Decimal("0.00"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf == Decimal("945.54")
        assert r.irrf_tradicional == Decimal("945.54")


class TestExemplosOficiaisRFB:
    """Reproduz exemplos resolvidos da página oficial da RFB (Lei 15.270/2025)."""

    def test_exemplo4_rfb_6000(self) -> None:
        # Exemplo 4 RFB: salário 6.000,00, INSS 649,60.
        #   base_legal = 6000 − 649,60 = 5350,40 → faixa 5
        #     irrf_legal = 5350,40×0,275 − 908,73 = 1471,36 − 908,73 = 562,63  (= RFB)
        #   base_simpl = 6000 − 607,20 = 5392,80 → faixa 5
        #     irrf_simpl = 5392,80×0,275 − 908,73 = 1483,02 − 908,73 = 574,29
        #   tradicional = min(562,63 ; 574,29) = 562,63 (legal)  ← bate com a RFB
        #   redutor = 978,62 − 0,133145×6000 = 978,62 − 798,87 = 179,75  (= RFB)
        #   irrf_final = 562,63 − 179,75 = 382,88  ← IRRF final oficial da RFB
        r = calcular_irrf_mensal(
            Decimal("6000.00"), Decimal("649.60"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.irrf_tradicional == Decimal("562.63")
        assert r.redutor_lei_15270 == Decimal("179.75")
        assert r.irrf == Decimal("382.88")
        assert r.metodo == "legal"

    def test_exemplo5_rfb_7607_sem_redutor(self) -> None:
        # Exemplo 5 RFB: salário 7.607,20, base de cálculo 7.000,00 (simplificado).
        # Reproduzido com INSS = 607,20 (empata as bases legal/simpl em 7000,00,
        # como no exemplo oficial, onde o simplificado é o mais benéfico).
        #   base_simpl = 7607,20 − 607,20 = 7000,00 → faixa 5
        #     irrf_simpl = 7000×0,275 − 908,73 = 1925 − 908,73 = 1016,27  (= RFB)
        #   salário 7607,20 > 7350 → redutor = 0 (tabela cheia)
        #   irrf_final = 1016,27  ← IRRF oficial da RFB (sem redutor)
        r = calcular_irrf_mensal(
            Decimal("7607.20"), Decimal("607.20"), 0, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.irrf_tradicional == Decimal("1016.27")
        assert r.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf == Decimal("1016.27")


class TestRedutorComDependentes:
    def test_6000_dois_dependentes(self) -> None:
        # salário 6.000, INSS 649,60, 2 deps × 189,59 = 379,18.
        #   base_legal = 6000 − 649,60 − 379,18 = 4971,22 → faixa 5
        #     irrf_legal = 4971,22×0,275 − 908,73 = 1367,0855 − 908,73 = 458,3555 → 458,36
        #   base_simpl = 6000 − 607,20 = 5392,80 → faixa 5 → 574,29
        #   tradicional = min(458,36 ; 574,29) = 458,36 (legal)
        #   redutor (salário 6000) = 179,75
        #   irrf_final = 458,36 − 179,75 = 278,61
        r = calcular_irrf_mensal(
            Decimal("6000.00"), Decimal("649.60"), 2, FAIXAS_2026,
            aplicar_redutor_lei_15270=True,
        )
        assert r.deducao_dependentes == Decimal("379.18")
        assert r.irrf_tradicional == Decimal("458.36")
        assert r.redutor_lei_15270 == Decimal("179.75")
        assert r.irrf == Decimal("278.61")
        assert r.metodo == "legal"


class TestRetrocompatibilidadeSemRedutor:
    """Sem aplicar_redutor (default) o resultado é a tabela cheia — usado
    para competências < 2026 e para comparar o efeito do redutor."""

    def test_6000_sem_redutor_mantem_tradicional(self) -> None:
        # Mesmo caso do exemplo 4, mas redutor desligado (competência < 2026):
        # IRRF = irrf_tradicional = 562,63 (sem abatimento).
        r = calcular_irrf_mensal(
            Decimal("6000.00"), Decimal("649.60"), 0, FAIXAS_2026,
        )
        assert r.irrf == Decimal("562.63")
        assert r.irrf_tradicional == Decimal("562.63")
        assert r.redutor_lei_15270 == Decimal("0.00")

    def test_5000_sem_redutor_nao_zera(self) -> None:
        # Sem redutor, salário 5000 NÃO é isento (prova que a isenção efetiva
        # vem do redutor, não da tabela): IRRF tradicional = 312,89.
        r = calcular_irrf_mensal(
            Decimal("5000.00"), Decimal("501.51"), 0, FAIXAS_2026,
        )
        assert r.irrf == Decimal("312.89")
        assert r.redutor_lei_15270 == Decimal("0.00")


class TestTabela2026Faixas:
    """Confirma que a tabela 2026 isenta corretamente até R$ 2.428,80 (a falha
    do seed antigo, que isentava só até 2.259,20)."""

    def test_isento_ate_2428_80(self) -> None:
        # base_legal = 2428,80 (INSS 0, sem deps) → faixa 1 (isenta) → 0,00.
        # No seed antigo (2.259,20) essa base cairia na faixa 2 e reteria IRRF.
        r = calcular_irrf_mensal(
            Decimal("2428.80"), Decimal("0.00"), 0, FAIXAS_2026,
        )
        assert r.faixa == 1
        assert r.irrf == Decimal("0.00")

    def test_algoritmo_versao_v3(self) -> None:
        r = calcular_irrf_mensal(
            Decimal("3000"), Decimal("253.41"), 0, FAIXAS_2026,
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO
        assert ALGORITMO_VERSAO == "irrf.mensal.v3"
