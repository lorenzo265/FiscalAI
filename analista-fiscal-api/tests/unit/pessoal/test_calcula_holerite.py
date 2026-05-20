"""Golden tests do orquestrador de holerite (Sprint 10 PR1)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.pessoal.calcula_holerite import (
    ALGORITMO_VERSAO,
    calcular_holerite,
)

# Reaproveita os fixtures de faixas dos testes unitários adjacentes.
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS

ALIQ_FGTS_CLT = Decimal("0.0800")


class TestHoleriteGolden:
    def test_funcionario_3000_sem_dep(self) -> None:
        # INSS = 253,41; IRRF = 36,55; FGTS = 240,00
        # Líquido = 3000 − 253,41 − 36,55 = 2710,04
        r = calcular_holerite(
            salario_base=Decimal("3000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.inss.inss == Decimal("253.41")
        assert r.irrf.irrf == Decimal("36.55")
        assert r.fgts.fgts == Decimal("240.00")
        assert r.valor_liquido == Decimal("2710.04")

    def test_funcionario_5000_com_2_deps(self) -> None:
        # INSS = 509,60; IRRF base = 5000 − 509,60 − 379,18 = 4111,22 → faixa 4
        # IRRF = 4111,22 × 22,5% − 662,77 = 925,0245 − 662,77 = 262,2545 → 262,25
        # FGTS = 5000 × 8% = 400,00
        # Líquido = 5000 − 509,60 − 262,25 = 4228,15 (FGTS é encargo, não desconto)
        r = calcular_holerite(
            salario_base=Decimal("5000.00"),
            dependentes_irrf=2,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.inss.inss == Decimal("509.60")
        assert r.irrf.irrf == Decimal("262.25")
        assert r.fgts.fgts == Decimal("400.00")
        assert r.valor_liquido == Decimal("4228.15")

    def test_salario_minimo_isento_irrf(self) -> None:
        # 1518 × 7,5% = 113,85 (INSS); base IRRF = 1518 − 113,85 = 1404,15 → isenta
        # Líquido = 1518 − 113,85 = 1404,15. FGTS = 121,44
        r = calcular_holerite(
            salario_base=Decimal("1518.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.inss.inss == Decimal("113.85")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.irrf.faixa == 1
        assert r.fgts.fgts == Decimal("121.44")
        assert r.valor_liquido == Decimal("1404.15")

    def test_salario_alto_acima_teto_inss(self) -> None:
        # 15000 — INSS bate teto 951,63; IRRF faixa 5
        r = calcular_holerite(
            salario_base=Decimal("15000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.inss.inss == Decimal("951.63")
        assert r.inss.teto_aplicado is True
        assert r.irrf.faixa == 5
        # IRRF: base 14048,37 × 27,5% − 896 = 2967,30
        assert r.irrf.irrf == Decimal("2967.30")
        # Líquido = 15000 − 951,63 − 2967,30 = 11081,07
        assert r.valor_liquido == Decimal("11081.07")
        # FGTS = 15000 × 8% = 1200,00 (calculado sobre o bruto, não sobre teto INSS)
        assert r.fgts.fgts == Decimal("1200.00")


class TestEstrutura:
    def test_versao_consistente(self) -> None:
        r = calcular_holerite(
            salario_base=Decimal("3000"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_determinismo(self) -> None:
        kwargs = dict(
            salario_base=Decimal("4123.45"),
            dependentes_irrf=1,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        r1 = calcular_holerite(**kwargs)  # type: ignore[arg-type]
        r2 = calcular_holerite(**kwargs)  # type: ignore[arg-type]
        assert r1 == r2

    def test_fgts_nao_entra_no_liquido(self) -> None:
        # FGTS é encargo do empregador — funcionário recebe líquido = bruto − INSS − IRRF.
        # Validação explícita: muda alíquota FGTS e líquido não muda.
        kwargs = dict(
            salario_base=Decimal("3000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
        )
        r_clt = calcular_holerite(aliquota_fgts=Decimal("0.0800"), **kwargs)  # type: ignore[arg-type]
        r_ja = calcular_holerite(
            aliquota_fgts=Decimal("0.0200"), vinculo="jovem_aprendiz", **kwargs  # type: ignore[arg-type]
        )
        assert r_clt.valor_liquido == r_ja.valor_liquido
        assert r_clt.fgts.fgts != r_ja.fgts.fgts
