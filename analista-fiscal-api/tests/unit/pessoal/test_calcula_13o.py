"""Golden tests do 13º salário — 1ª e 2ª parcelas (Sprint 10 PR2 + redutor Lei 15.270/2025)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_13o import (
    ALGORITMO_VERSAO,
    calcular_13o_primeira,
    calcular_13o_segunda,
)
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS
from tests.unit.pessoal.test_calcula_inss_2026 import FAIXAS_2026 as INSS_FAIXAS_2026
from tests.unit.pessoal.test_calcula_irrf_2026 import FAIXAS_2026 as IRRF_FAIXAS_2026


class TestPrimeiraParcela:
    def test_ano_completo_3000(self) -> None:
        # avos=12: base = 3000 × 12/12 = 3000; primeira = 1500
        r = calcular_13o_primeira(Decimal("3000.00"), 12)
        assert r.base_proporcional == Decimal("3000.00")
        assert r.valor_primeira_parcela == Decimal("1500.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_proporcional_8_meses(self) -> None:
        # avos=8: base = 3000 × 8/12 = 2000; primeira = 1000
        r = calcular_13o_primeira(Decimal("3000.00"), 8)
        assert r.base_proporcional == Decimal("2000.00")
        assert r.valor_primeira_parcela == Decimal("1000.00")

    def test_um_mes_apenas(self) -> None:
        # avos=1: base = 3000/12 = 250; primeira = 125
        r = calcular_13o_primeira(Decimal("3000.00"), 1)
        assert r.base_proporcional == Decimal("250.00")
        assert r.valor_primeira_parcela == Decimal("125.00")

    def test_salario_zero(self) -> None:
        r = calcular_13o_primeira(Decimal("0"), 12)
        assert r.valor_primeira_parcela == Decimal("0.00")

    def test_avos_zero_retorna_zero(self) -> None:
        """m8 FA8: avos=0 legítimo → retorna resultado zero (sem 13º a pagar).

        Ocorre quando admissão+demissão no mesmo mês com <15 dias trabalhados
        (Decreto 57.155/1965 — regra dos 15 dias). O mês não conta; o 13º é
        zero. Não deve lançar ValueError (comportamento simetrico com rescisão).
        """
        r = calcular_13o_primeira(Decimal("3000"), 0)
        assert r.base_proporcional == Decimal("0.00")
        assert r.valor_primeira_parcela == Decimal("0.00")
        assert r.avos == 0

    def test_avos_menos_um_levanta(self) -> None:
        """m8 FA8: avos negativos ainda são inválidos."""
        with pytest.raises(ValueError, match="avos deve estar entre 0 e 12"):
            calcular_13o_primeira(Decimal("3000"), -1)

    def test_avos_treze_levanta(self) -> None:
        with pytest.raises(ValueError, match="avos deve estar entre 0 e 12"):
            calcular_13o_primeira(Decimal("3000"), 13)

    def test_salario_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="salario não pode"):
            calcular_13o_primeira(Decimal("-1"), 12)


class TestSegundaParcela:
    def test_ano_completo_3000_sem_dep(self) -> None:
        # base = 3000; INSS escalonado: 253,41
        # IRRF_legal: base 2746,59 × 7,5% − 169,44 = 36,55
        # IRRF_simpl: base 2435,20 (3000−564,80) → faixa 2 → 13,20
        # min(36,55 ; 13,20) = 13,20 → simplificado (FA2 M5)
        # segunda = 3000 − 1500 − 253,41 − 13,20 = 1233,39
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.base_proporcional == Decimal("3000.00")
        assert r.inss.inss == Decimal("253.41")
        assert r.irrf.irrf == Decimal("13.20")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_segunda_parcela == Decimal("1233.39")

    def test_proporcional_6_meses_5000_com_1_dep(self) -> None:
        # avos=6: base = 5000 × 6/12 = 2500
        # INSS sobre 2500: 1518×7,5% + (2500−1518)×9% = 113,85 + 88,38 = 202,23
        # IRRF: base = 2500 − 202,23 − 189,59 = 2108,18 → faixa 1 → 0
        # primeira paga = 1250; segunda = 2500 − 1250 − 202,23 − 0 = 1047,77
        r = calcular_13o_segunda(
            salario=Decimal("5000.00"),
            avos=6,
            primeira_parcela_paga=Decimal("1250.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=1,
        )
        assert r.base_proporcional == Decimal("2500.00")
        assert r.inss.inss == Decimal("202.23")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.valor_segunda_parcela == Decimal("1047.77")

    def test_salario_alto_acima_teto(self) -> None:
        # avos=12, salario 15000 → base = 15000; INSS teto 951,63
        # IRRF: base = 15000 − 951,63 = 14048,37 → faixa 5 → 14048,37×27,5%−896 = 2967,30
        # primeira = 7500; segunda = 15000 − 7500 − 951,63 − 2967,30 = 3581,07
        r = calcular_13o_segunda(
            salario=Decimal("15000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("7500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.inss.inss == Decimal("951.63")
        assert r.inss.teto_aplicado is True
        assert r.irrf.irrf == Decimal("2967.30")
        assert r.valor_segunda_parcela == Decimal("3581.07")

    def test_primeira_diferente_da_metade(self) -> None:
        # base 3000, primeira paga 1000 (em vez de 1500)
        # IRRF 13,20 (simplificado vence — ver test_ano_completo_3000_sem_dep)
        # segunda = 3000 − 1000 − 253,41 − 13,20 = 1733,39
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1000.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_segunda_parcela == Decimal("1733.39")

    def test_primeira_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="primeira_parcela_paga"):
            calcular_13o_segunda(
                salario=Decimal("3000"),
                avos=12,
                primeira_parcela_paga=Decimal("-1"),
                faixas_inss=INSS_FAIXAS,
                faixas_irrf=IRRF_FAIXAS,
                dependentes=0,
            )

    def test_versao(self) -> None:
        r = calcular_13o_segunda(
            salario=Decimal("3000"),
            avos=12,
            primeira_parcela_paga=Decimal("1500"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO
        # Confirmar que o IRRF usa o método simplificado (FA2 M5)
        assert r.irrf.metodo == "simplificado"


class TestFgts13o:
    """Golden tests — FGTS do empregador no 13º salário (Lei 8.036/90 art.15).

    FIX PR3 #6: calcula_13o agora modela FGTS 8% sobre base_proporcional.
    FGTS do 13º registrado integralmente na 2ª parcela (1ª é adiantamento
    sem tributos) → total anual = 8% × base, contado uma única vez.
    """

    def test_fgts_13o_nao_registrado_primeira_parcela(self) -> None:
        """1ª parcela não tem fgts — apenas adiantamento de 50% da base."""
        # ResultadoFerias13oPrimeira não tem campo fgts_empregador por design.
        # Verificamos que base e primeira calculam corretamente.
        r = calcular_13o_primeira(Decimal("3000.00"), 12)
        assert r.base_proporcional == Decimal("3000.00")
        assert r.valor_primeira_parcela == Decimal("1500.00")

    def test_fgts_segunda_parcela_ano_completo_3000(self) -> None:
        # avos=12: base_13 = 3000; fgts = 3000 × 8% = 240.00
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.base_proporcional == Decimal("3000.00")
        assert r.base_fgts == Decimal("3000.00")
        assert r.fgts_empregador == Decimal("240.00")

    def test_fgts_segunda_parcela_proporcional_8_avos(self) -> None:
        # avos=8: base_13 = 3000×8/12 = 2000; fgts = 2000 × 8% = 160.00
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=8,
            primeira_parcela_paga=Decimal("1000.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.base_proporcional == Decimal("2000.00")
        assert r.base_fgts == Decimal("2000.00")
        assert r.fgts_empregador == Decimal("160.00")

    def test_fgts_total_anual_nao_duplica(self) -> None:
        """Soma dos fgts_empregador entre 1ª e 2ª parcela = 8% × base — sem duplicar.

        1ª parcela NÃO tem campo fgts_empregador (adiantamento puro).
        2ª parcela registra o FGTS total do 13º (= 8% × base_proporcional).
        Assim o total anual de FGTS do 13º = fgts_empregador da 2ª, exatamente 8%.
        """
        salario = Decimal("3000.00")
        avos = 12
        # 1ª parcela: adiantamento puro — sem FGTS
        r1 = calcular_13o_primeira(salario, avos)
        # 2ª parcela: FGTS total do 13º registrado aqui
        r2 = calcular_13o_segunda(
            salario=salario,
            avos=avos,
            primeira_parcela_paga=r1.valor_primeira_parcela,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        base_13 = r2.base_proporcional
        fgts_total_anual = r2.fgts_empregador  # 1ª não contribui
        # Deve ser exatamente 8% × base (sem duplicação da 1ª parcela)
        from decimal import ROUND_HALF_EVEN
        esperado = (base_13 * Decimal("0.08")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        assert fgts_total_anual == esperado  # 3000 × 8% = 240.00

    def test_versao_bumped(self) -> None:
        """Bump v3→v4 sinaliza ativação do redutor Lei 15.270/2025."""
        assert ALGORITMO_VERSAO == "13o.v4"


class TestDecimoTerceiroReductor2026:
    """Goldens do 13º com redutor Lei 15.270/2025 (competências ≥ 2026-01-01).

    O redutor se aplica ao IRRF EXCLUSIVO NA FONTE do 13º (Lei 8.134/1990
    art. 16 — cálculo separado). Referência = base_proporcional (13º bruto).
    Todos os valores conferidos à mão (ROUND_HALF_EVEN).
    """

    def test_13o_salario_4500_avos_12_isento_redutor_2026(self) -> None:
        # base = 4500 × 12/12 = 4500,00 ≤ 5000 → redutor zera o IRRF.
        # INSS sobre 4500 (INSS 2026):
        #   F1: 1621 × 7,5% = 121,5750
        #   F2: (2902,84−1621) × 9% = 115,3656
        #   F3: (4354,27−2902,84) × 12% = 174,1716
        #   F4: (4500−4354,27) × 14% = 145,73 × 14% = 20,4022
        #   Total = 431,5144 → 431,51
        # IRRF tradicional:
        #   base_legal = 4500 − 431,51 = 4068,49 → F4 → 4068,49×22,5%−675,49 = 239,92
        #   base_simpl = 4500 − 607,20 = 3892,80 → F4 → 3892,80×22,5%−675,49 = 875,88−675,49 = 200,39
        #   min(239,92; 200,39) = 200,39 → simplificado
        # Redutor: 4500 ≤ 5000 → zera → irrf = 0,00
        # segunda = 4500 − 2250 − 431,51 − 0,00 = 1818,49
        r = calcular_13o_segunda(
            salario=Decimal("4500.00"),
            avos=12,
            primeira_parcela_paga=Decimal("2250.00"),
            faixas_inss=INSS_FAIXAS_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            dependentes=0,
            aplicar_redutor_lei_15270=True,
        )
        assert r.base_proporcional == Decimal("4500.00")
        assert r.inss.inss == Decimal("431.51")
        assert r.irrf.irrf_tradicional == Decimal("200.39")
        assert r.irrf.redutor_lei_15270 == Decimal("200.39")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_segunda_parcela == Decimal("1818.49")

    def test_13o_salario_6000_avos_12_redutor_linear_2026(self) -> None:
        # base = 6000 × 12/12 = 6000,00; 5000 < 6000 ≤ 7350 → faixa linear.
        # INSS sobre 6000 (INSS 2026):
        #   F4: (6000−4354,27) × 14% = 1645,73 × 14% = 230,4022
        #   Total = 121,5750 + 115,3656 + 174,1716 + 230,4022 = 641,5144 → 641,51
        # IRRF:
        #   base_legal = 6000 − 641,51 = 5358,49 → F5 → 5358,49×27,5%−908,73 = 564,85
        #   base_simpl = 6000 − 607,20 = 5392,80 → F5 → 574,29
        #   min(564,85; 574,29) = 564,85 → legal
        # Redutor: 978,62 − 0,133145×6000 = 978,62 − 798,87 = 179,75
        # irrf_final = 564,85 − 179,75 = 385,10
        # segunda = 6000 − 3000 − 641,51 − 385,10 = 1973,39
        r = calcular_13o_segunda(
            salario=Decimal("6000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("3000.00"),
            faixas_inss=INSS_FAIXAS_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            dependentes=0,
            aplicar_redutor_lei_15270=True,
        )
        assert r.base_proporcional == Decimal("6000.00")
        assert r.inss.inss == Decimal("641.51")
        assert r.irrf.irrf_tradicional == Decimal("564.85")
        assert r.irrf.redutor_lei_15270 == Decimal("179.75")
        assert r.irrf.irrf == Decimal("385.10")
        assert r.irrf.metodo == "legal"
        assert r.valor_segunda_parcela == Decimal("1973.39")

    def test_2025_13o_nao_aplica_redutor(self) -> None:
        # Default (sem redutor) → goldens 2025 inalterados.
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=12,
            primeira_parcela_paga=Decimal("1500.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.irrf.redutor_lei_15270 == Decimal("0.00")
        # Golden histórico: irrf 2025 = 13,20 (simplificado)
        assert r.irrf.irrf == Decimal("13.20")


class TestAvosZeroM8:
    """m8 FA8 — avos=0 legítimo (admissão+demissão <15 dias no mesmo mês).

    Decreto 57.155/1965 art. 1º §2º: se o empregado trabalhou menos de
    15 dias no único mês do vínculo, o mês não conta para o 13º → avos=0.
    O 13º deve ser zero, sem lançar ValueError. Uniformiza com rescisão.

    O pré-cálculo de avos (regra dos 15 dias) é responsabilidade do service.
    """

    def test_primeira_parcela_avos_zero_retorna_zero(self) -> None:
        r = calcular_13o_primeira(Decimal("3000.00"), 0)
        assert r.avos == 0
        assert r.base_proporcional == Decimal("0.00")
        assert r.valor_primeira_parcela == Decimal("0.00")

    def test_segunda_parcela_avos_zero_retorna_zero(self) -> None:
        r = calcular_13o_segunda(
            salario=Decimal("3000.00"),
            avos=0,
            primeira_parcela_paga=Decimal("0.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.avos == 0
        assert r.base_proporcional == Decimal("0.00")
        assert r.inss.inss == Decimal("0.00")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.fgts_empregador == Decimal("0.00")
        assert r.valor_segunda_parcela == Decimal("0.00")

    def test_avos_negativo_ainda_levanta(self) -> None:
        """Avos negativos continuam inválidos mesmo após a correção m8."""
        with pytest.raises(ValueError, match="avos deve estar entre 0 e 12"):
            calcular_13o_primeira(Decimal("3000"), -1)

    def test_avos_treze_ainda_levanta(self) -> None:
        """Avos > 12 continuam inválidos."""
        with pytest.raises(ValueError, match="avos deve estar entre 0 e 12"):
            calcular_13o_primeira(Decimal("3000"), 13)
