"""Golden tests de distribuição de lucros (Sprint 10 PR3).

FA8 m6 (2026-06-04): adicionados testes que confirmam que valor_tributavel
é quantizado (2 casas) antes de ser passado ao IRRF. Garante que bases com
>2 casas decimais (de receita×presunção) não causam centavo divergente.
ALGORITMO_VERSAO bumped para "distribuicao.v2".

Auditoria 2026-06-21 (fix/auditoria-fiscal-2026-06):
  Lei 15.270/2025 (vigência 01/01/2026) — retenção antecipada de 10% de
  IRRF na fonte sobre lucros/dividendos que excedam R$ 50.000,00 por mês
  (mesma PJ × mesma PF). Aplica-se a todos os regimes, inclusive Simples.
  A retenção incide sobre o TOTAL do mês (não só o excedente). Base vedada
  de qualquer dedução. Limite exclusivo: exatamente R$ 50.000,00 NÃO retém.
  Múltiplos pagamentos: retenção incremental (10%×total_acum − já_retido).
  Acrescentado campo ``retencao_dividendos_10pct`` no resultado.
  ALGORITMO_VERSAO bumped para "distribuicao.v3".
  Golden ``test_lp_exatamente_no_limite`` CORRIGIDO: R$ 100k paga a um sócio
  sem pagamentos anteriores no mês → retém 10% = R$ 10.000,00 (comportamento
  anterior (v2) fixava retenção zero — ERRADO desde 01/01/2026).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_distribuicao import (
    ALGORITMO_VERSAO,
    BaseCalculoReferencia,
    calcular_distribuicao,
)
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS


class TestDentroDoLimite:
    def test_simples_dentro_das_isento_integral(self) -> None:
        r = calcular_distribuicao(
            valor_distribuido=Decimal("50000.00"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.SIMPLES_DENTRO_DAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("50000.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        assert r.irrf_excedente is None
        assert r.valor_liquido_socio == Decimal("50000.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_lp_exatamente_no_limite(self) -> None:
        # CORRIGIDO (auditoria 2026-06-21): Lei 9.249/1995 isenta o excedente
        # (valor_tributavel=0, irrf_retido=0), mas a Lei 15.270/2025 retém
        # 10% sobre o total do mês (100k > 50k) = R$ 10.000,00.
        # Comportamento anterior (v2) fixava valor_liquido=100k — ERRADO desde
        # 01/01/2026. Agora: líquido = 100k − 10k = 90k.
        r = calcular_distribuicao(
            valor_distribuido=Decimal("100000.00"),
            limite_isento_apurado=Decimal("100000.00"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("100000.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        # Lei 15.270/2025: total_mes=100k > 50k → 10% × 100k = 10.000,00
        assert r.retencao_dividendos_10pct == Decimal("10000.00")
        assert r.total_acumulado_mes == Decimal("100000.00")
        # Líquido: 100k − 0 (irrf_excedente) − 10k (Lei 15.270) = 90k
        assert r.valor_liquido_socio == Decimal("90000.00")

    def test_mei_pequeno_valor_isento(self) -> None:
        r = calcular_distribuicao(
            valor_distribuido=Decimal("2000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.MEI,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("2000.00")
        assert r.valor_tributavel == Decimal("0.00")


class TestExcedente:
    def test_excedente_baixo_isento_irrf(self) -> None:
        # Excedente 2000 → faixa 1 IRRF → 0
        r = calcular_distribuicao(
            valor_distribuido=Decimal("12000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("10000.00")
        assert r.valor_tributavel == Decimal("2000.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 1
        assert r.irrf_retido == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("12000.00")

    def test_excedente_alto_irrf_faixa5(self) -> None:
        # Excedente 15000 → sem INSS → deps=0
        # IRRF_legal: base=15000→faixa 5→15000×27,5%−896=3229
        # IRRF_simpl: base=15000−564,80=14435,20→faixa 5→14435,20×27,5%−896=3073,68
        # min(3229 ; 3073,68) = 3073,68 → SIMPLIFICADO (FA2 M5)
        # Líquido = 25000 − 3073,68 = 21926,32
        r = calcular_distribuicao(
            valor_distribuido=Decimal("25000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("10000.00")
        assert r.valor_tributavel == Decimal("15000.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 5
        assert r.irrf_retido == Decimal("3073.68")
        assert r.irrf_excedente.metodo == "simplificado"
        # Líquido = 25000 − 3073,68 = 21926,32
        assert r.valor_liquido_socio == Decimal("21926.32")

    def test_excedente_com_dependentes(self) -> None:
        # Excedente 5000, 3 deps × 189,59 = 568,77 → base IRRF = 5000 − 568,77 = 4431,23
        # Faixa 4: 4431,23×22,5%−662,77 = 997,02675 − 662,77 = 334,25675 → 334,26
        r = calcular_distribuicao(
            valor_distribuido=Decimal("15000"),
            limite_isento_apurado=Decimal("10000"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=3,
        )
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 4
        assert r.irrf_retido == Decimal("334.26")
        assert r.valor_liquido_socio == Decimal("15000") - Decimal("334.26")


class TestLimiteZero:
    def test_limite_zero_tudo_tributavel(self) -> None:
        # Sem lucro contábil — tudo vira excedente tributável
        # IRRF_legal: 3000 → faixa 3 → 3000×15%−381,44 = 68,56
        # IRRF_simpl: base=2435,20 → faixa 2 → 2435,20×7,5%−169,44 = 13,20
        # min(68,56 ; 13,20) = 13,20 → SIMPLIFICADO (FA2 M5)
        r = calcular_distribuicao(
            valor_distribuido=Decimal("3000"),
            limite_isento_apurado=Decimal("0"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("0.00")
        assert r.valor_tributavel == Decimal("3000.00")
        assert r.irrf_retido == Decimal("13.20")


class TestM6Quantizacao:
    """m6 FA8: valor_tributavel quantizado antes de ir ao IRRF.

    Cenário reproduzível: limite_isento_apurado gerado por
    calcula_limite_isento pode ter >2 casas decimais (e.g.,
    100.000 × 0.32 = 32.000 — mas casos com presunção não-redonda
    como 0.0800 × receita ou combinações geram dízimas).
    O fix garante que a base do IRRF seja sempre truncada em 2 casas.
    """

    def test_limite_isento_com_multiplas_casas_decimais(self) -> None:
        """Limite com >2 casas não contamina base do IRRF (m6 FA8).

        limite_isento_apurado = 9999.999 (3 casas — simula saída de
        receita × presunção não-quantizada). Excedente = 0.001 → quantizado
        a 0.00 → IRRF zero (isento). Sem fix, 0.001 poderia ser passado ao
        IRRF gerando resultado não-determinístico.
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("10000.00"),
            limite_isento_apurado=Decimal("9999.999"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        # valor_tributavel deve ser quantizado: 10000.00 − 9999.999 = 0.001
        # → round HALF_EVEN → 0.00 → sem IRRF
        assert r.valor_tributavel == Decimal("0.00")
        assert r.irrf_retido == Decimal("0.00")
        assert r.irrf_excedente is None

    def test_limite_com_3_casas_gera_tributavel_quantizado(self) -> None:
        """Excedente com casas extras é quantizado corretamente (m6 FA8).

        valor_distribuido = 15000.00
        limite_isento     =  9999.005 (3 casas)
        excedente bruto   =  5000.995 → quantizado → 5001.00
        IRRF sobre 5001.00 (faixa 4): 5001×22,5% − 662,77 = 1125,225−662,77 = 462,455 → 462,46
        Simplificado: base=5001−564,80=4436,20 → faixa 4 → 4436,20×22,5%−662,77
                       = 998,145−662,77 = 335,375 → 335,38
        min(462,46 ; 335,38) = 335,38 → simplificado
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("15000.00"),
            limite_isento_apurado=Decimal("9999.005"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_tributavel == Decimal("5001.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.faixa == 4
        # Chave: valor_tributavel é Decimal com exatamente 2 casas
        assert r.valor_tributavel.as_tuple().exponent == -2

    def test_versao_v3(self) -> None:
        """ALGORITMO_VERSAO bumped para v3 pelo fix auditoria Lei 15.270/2025."""
        assert ALGORITMO_VERSAO == "distribuicao.v3"


class TestBordas:
    def test_valor_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="valor_distribuido"):
            calcular_distribuicao(
                Decimal("-1"), Decimal("100"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
            )

    def test_limite_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="limite_isento"):
            calcular_distribuicao(
                Decimal("100"), Decimal("-1"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
            )

    def test_dependentes_negativos_levanta(self) -> None:
        with pytest.raises(ValueError, match="dependentes"):
            calcular_distribuicao(
                Decimal("100"), Decimal("100"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, -1,
            )

    def test_zero_distribuicao(self) -> None:
        r = calcular_distribuicao(
            Decimal("0"), Decimal("100"),
            BaseCalculoReferencia.LUCRO_CONTABIL,
            IRRF_FAIXAS, 0,
        )
        assert r.valor_isento == Decimal("0.00")
        assert r.valor_tributavel == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("0.00")


class TestRetencaoLei15270:
    """Golden tests — Lei 15.270/2025 (vigência 01/01/2026).

    Retenção antecipada de 10% de IRRF na fonte sobre lucros/dividendos
    pagos/creditados pela MESMA PJ à MESMA PF que EXCEDAM R$ 50.000,00
    no mesmo mês calendário. Todos os regimes (inclusive Simples e MEI).
    Base = total bruto do mês, vedada qualquer dedução.
    Limite exclusivo: exatamente R$ 50.000,00 NÃO retém.
    """

    def test_borda_exatamente_50k_nao_retem(self) -> None:
        """Total do mês = R$ 50.000,00 → 'superior a' → NÃO retém.

        50000 > 50000 é falso; logo retencao_dividendos_10pct = 0.
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("50000.00"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
            # dividendos_ja_pagos_no_mes default 0
        )
        # total_acumulado_mes = 0 + 50000 = 50000 — NÃO supera o limite
        assert r.total_acumulado_mes == Decimal("50000.00")
        assert r.retencao_dividendos_10pct == Decimal("0.00")
        # isento integral (dentro do limite contábil)
        assert r.irrf_retido == Decimal("0.00")
        assert r.valor_liquido_socio == Decimal("50000.00")

    def test_borda_50k_mais_1_centavo_retem(self) -> None:
        """Total do mês = R$ 50.000,01 → retém 10% de 50.000,01.

        10% × 50.000,01 = 5.000,001 → quantize HALF_EVEN → R$ 5.000,00.
        (centavo: 5000.001 → dígito após 2ª casa = 1, menor que 5 → trunca → 5000.00)
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("50000.01"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.total_acumulado_mes == Decimal("50000.01")
        # 10% × 50000,01 = 5000,001 → ROUND_HALF_EVEN → 5000,00
        assert r.retencao_dividendos_10pct == Decimal("5000.00")
        # isento integral (valor_distribuido < limite_isento)
        assert r.irrf_retido == Decimal("0.00")
        # líquido = 50000,01 − 0 − 5000,00 = 45000,01
        assert r.valor_liquido_socio == Decimal("45000.01")

    def test_pagamento_unico_100k(self) -> None:
        """Pagamento único R$ 100.000 (sem acumulado anterior no mês).

        total_mes = 100.000 → 10% × 100.000 = R$ 10.000,00.
        Neste cenário o sócio tem limite_isento=0, então também incide
        IRRF progressivo sobre R$ 100.000 (faixa 5).
        Teste verifica exclusivamente a retenção da Lei 15.270.
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("100000.00"),
            limite_isento_apurado=Decimal("0.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.total_acumulado_mes == Decimal("100000.00")
        assert r.retencao_dividendos_10pct == Decimal("10000.00")

    def test_dois_pagamentos_no_mes_acumulado(self) -> None:
        """Dois pagamentos no mesmo mês: R$ 30.000 + R$ 30.000.

        1º pagamento: total_acum=30k ≤ 50k → retencao_10pct=0.
        2º pagamento: total_acum=60k > 50k → retencao_devida_mes=10%×60k=6.000
                      − já_retido=0 → retencao_neste_pgto=6.000,00.
        """
        # 1º pagamento do mês (R$ 30k, nenhum acumulado)
        r1 = calcular_distribuicao(
            valor_distribuido=Decimal("30000.00"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
            dividendos_ja_pagos_no_mes=Decimal("0.00"),
            retencao_lei_15270_ja_retida_no_mes=Decimal("0.00"),
        )
        assert r1.total_acumulado_mes == Decimal("30000.00")
        assert r1.retencao_dividendos_10pct == Decimal("0.00")
        assert r1.valor_liquido_socio == Decimal("30000.00")

        # 2º pagamento do mês (mais R$ 30k; acumulado anterior = 30k)
        r2 = calcular_distribuicao(
            valor_distribuido=Decimal("30000.00"),
            limite_isento_apurado=Decimal("80000.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
            dividendos_ja_pagos_no_mes=Decimal("30000.00"),
            retencao_lei_15270_ja_retida_no_mes=Decimal("0.00"),
        )
        assert r2.total_acumulado_mes == Decimal("60000.00")
        # 10% × 60.000 = 6.000 − 0 já retido = 6.000,00
        assert r2.retencao_dividendos_10pct == Decimal("6000.00")
        # isento integral (total limite=80k, ambos pagamentos somam 60k < 80k)
        assert r2.irrf_retido == Decimal("0.00")
        # líquido = 30k − 0 − 6k = 24k
        assert r2.valor_liquido_socio == Decimal("24000.00")

    def test_simples_nacional_retem_igual(self) -> None:
        """Simples Nacional: retenção da Lei 15.270 é idêntica ao LP.

        A Lei 15.270/2025 é regime-agnóstica — aplica-se a todos os regimes,
        inclusive Simples Nacional. O campo base_calculo_referencia não altera
        o cálculo da retenção de 10%.
        """
        r_sn = calcular_distribuicao(
            valor_distribuido=Decimal("80000.00"),
            limite_isento_apurado=Decimal("100000.00"),
            base_calculo_referencia=BaseCalculoReferencia.SIMPLES_DENTRO_DAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        r_lp = calcular_distribuicao(
            valor_distribuido=Decimal("80000.00"),
            limite_isento_apurado=Decimal("100000.00"),
            base_calculo_referencia=BaseCalculoReferencia.PRESUNCAO_LP,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        # Ambos devem ter a mesma retenção Lei 15.270 (regime não importa)
        assert r_sn.retencao_dividendos_10pct == r_lp.retencao_dividendos_10pct
        # 10% × 80.000 = 8.000,00
        assert r_sn.retencao_dividendos_10pct == Decimal("8000.00")
        assert r_sn.irrf_retido == Decimal("0.00")  # isento integral
        # líquido = 80k − 0 − 8k = 72k
        assert r_sn.valor_liquido_socio == Decimal("72000.00")

    def test_valor_distribuido_negativo_no_mes_levanta(self) -> None:
        """dividendos_ja_pagos_no_mes negativo deve levantar ValueError."""
        with pytest.raises(ValueError, match="dividendos_ja_pagos_no_mes"):
            calcular_distribuicao(
                Decimal("10000"), Decimal("10000"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
                dividendos_ja_pagos_no_mes=Decimal("-1"),
            )

    def test_retencao_anterior_negativa_levanta(self) -> None:
        """retencao_lei_15270_ja_retida_no_mes negativa deve levantar ValueError."""
        with pytest.raises(ValueError, match="retencao_lei_15270_ja_retida_no_mes"):
            calcular_distribuicao(
                Decimal("10000"), Decimal("10000"),
                BaseCalculoReferencia.LUCRO_CONTABIL,
                IRRF_FAIXAS, 0,
                retencao_lei_15270_ja_retida_no_mes=Decimal("-0.01"),
            )

    def test_coexistencia_irrf_excedente_e_retencao_10pct(self) -> None:
        """Ambos os mecanismos incidem simultaneamente quando há excedente.

        Sócio recebe R$ 80.000; limite_isento = R$ 60.000.
        Excedente = R$ 20.000 → IRRF progressivo (faixa 5, simplificado).
        total_mes = 80k > 50k → Lei 15.270 retém 10% × 80k = R$ 8.000,00.
        Os dois mecanismos são CUMULATIVOS.

        IRRF simplificado sobre 20k (deps=0):
          base = 20k − desconto_simplificado
          teto_faixa1 = 2259,20 → desconto = 25% × 2259,20 = 564,80
          base_simpl = 20000 − 564,80 = 19435,20
          faixa 5: 19435,20 × 27,5% − 896,00 = 5344,68 − 896,00 = 4448,68
          IRRF_legal: 20000 × 27,5% − 896 = 5500 − 896 = 4604,00
          min(4448,68 ; 4604,00) = 4448,68 → simplificado
        Líquido = 80000 − 4448,68 − 8000,00 = 67551,32
        """
        r = calcular_distribuicao(
            valor_distribuido=Decimal("80000.00"),
            limite_isento_apurado=Decimal("60000.00"),
            base_calculo_referencia=BaseCalculoReferencia.LUCRO_CONTABIL,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.valor_isento == Decimal("60000.00")
        assert r.valor_tributavel == Decimal("20000.00")
        assert r.irrf_excedente is not None
        assert r.irrf_excedente.metodo == "simplificado"
        assert r.irrf_retido == Decimal("4448.68")
        # Lei 15.270: 10% × 80.000 = 8.000,00
        assert r.retencao_dividendos_10pct == Decimal("8000.00")
        # Líquido = 80000 − 4448,68 − 8000 = 67551,32
        assert r.valor_liquido_socio == Decimal("67551.32")
