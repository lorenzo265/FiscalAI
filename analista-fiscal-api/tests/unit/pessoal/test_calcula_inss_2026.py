"""Golden tests do INSS empregado 2026 (nova vigência SCD — migration 0058).

Valores oficiais 2026 — fonte primária citável:
  PORTARIA INTERMINISTERIAL MPS/MF Nº 13, de 09/01/2026 (DOU), reajuste do
  RGPS a partir da competência janeiro/2026. Confirmada na página oficial
  gov.br/INSS "Tabela de contribuição mensal"
  ("TABELAS VÁLIDAS A PARTIR DA COMPETÊNCIA JANEIRO DE 2026"):
  https://www.gov.br/inss/pt-br/direitos-e-deveres/inscricao-e-contribuicao/tabela-de-contribuicao-mensal

  Salário mínimo 2026 = R$ 1.621,00 · Teto (salário de contribuição) = R$ 8.475,55.

Faixas empregado 2026 (alíquota progressiva escalonada — padrão eSocial S-1210):
  faixa 1 — até R$ 1.621,00 → 7,5%
  faixa 2 — até R$ 2.902,84 → 9,0%
  faixa 3 — até R$ 4.354,27 → 12,0%
  faixa 4 — até R$ 8.475,55 → 14,0%

Todos os centavos abaixo foram conferidos à mão com ROUND_HALF_EVEN.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.pessoal.calcula_inss import (
    FaixaInss,
    calcular_inss_empregado,
)

# Faixas vigentes em 2026 (Portaria Interministerial MPS/MF nº 13/2026).
FAIXAS_2026 = [
    FaixaInss(faixa=1, valor_ate=Decimal("1621.00"), aliquota=Decimal("0.0750")),
    FaixaInss(faixa=2, valor_ate=Decimal("2902.84"), aliquota=Decimal("0.0900")),
    FaixaInss(faixa=3, valor_ate=Decimal("4354.27"), aliquota=Decimal("0.1200")),
    FaixaInss(faixa=4, valor_ate=Decimal("8475.55"), aliquota=Decimal("0.1400")),
]


class TestGoldenIntraFaixa2026:
    def test_salario_minimo_2026_so_faixa_1(self) -> None:
        # 1621,00 × 7,5% = 121,575 → 121,58 (HALF_EVEN: 7 ímpar sobe)
        r = calcular_inss_empregado(Decimal("1621.00"), FAIXAS_2026)
        assert r.inss == Decimal("121.58")
        assert r.teto_aplicado is False
        assert r.aliquota_efetiva == Decimal("0.0750")

    def test_salario_3000_atinge_faixa_3(self) -> None:
        # 1621,00 × 7,5%              = 121,5750
        # (2902,84 − 1621,00) × 9%    = 115,3656
        # (3000,00 − 2902,84) × 12%   =  11,6592
        #                          ----------
        #                          248,5998 → 248,60
        r = calcular_inss_empregado(Decimal("3000.00"), FAIXAS_2026)
        assert r.inss == Decimal("248.60")
        assert r.teto_aplicado is False

    def test_salario_5000_atinge_faixa_4(self) -> None:
        # 121,5750 + 115,3656 + (4354,27−2902,84)×12% + (5000−4354,27)×14%
        # = 121,5750 + 115,3656 + 174,1716 + 90,4022 = 501,5144 → 501,51
        r = calcular_inss_empregado(Decimal("5000.00"), FAIXAS_2026)
        assert r.inss == Decimal("501.51")
        assert r.teto_aplicado is False

    def test_salario_teto_exato_2026(self) -> None:
        # 121,5750 + 115,3656 + 174,1716 + (8475,55−4354,27)×14%
        # = 121,5750 + 115,3656 + 174,1716 + 576,9792 = 988,0914 → 988,09
        r = calcular_inss_empregado(Decimal("8475.55"), FAIXAS_2026)
        assert r.inss == Decimal("988.09")
        assert r.teto_aplicado is False


class TestGoldenTeto2026:
    def test_salario_acima_teto_capa(self) -> None:
        r = calcular_inss_empregado(Decimal("12000.00"), FAIXAS_2026)
        assert r.inss == Decimal("988.09")
        assert r.teto_aplicado is True

    def test_aliquota_efetiva_teto(self) -> None:
        r = calcular_inss_empregado(Decimal("12000.00"), FAIXAS_2026)
        # 988,09 / 12000 = 0,08234... → 0,0823
        assert r.aliquota_efetiva == Decimal("0.0823")


class TestRegressao2025NaoQuebra:
    """A vigência 2025 continua produzindo os mesmos centavos de antes
    (o INSERT 2026 é SCD — não mexe na tabela 2025)."""

    def test_2025_segue_intacta(self) -> None:
        faixas_2025 = [
            FaixaInss(faixa=1, valor_ate=Decimal("1518.00"), aliquota=Decimal("0.0750")),
            FaixaInss(faixa=2, valor_ate=Decimal("2793.88"), aliquota=Decimal("0.0900")),
            FaixaInss(faixa=3, valor_ate=Decimal("4190.83"), aliquota=Decimal("0.1200")),
            FaixaInss(faixa=4, valor_ate=Decimal("8157.41"), aliquota=Decimal("0.1400")),
        ]
        # Teto 2025: 951,63 (golden histórico de test_calcula_inss.py)
        r = calcular_inss_empregado(Decimal("8157.41"), faixas_2025)
        assert r.inss == Decimal("951.63")
