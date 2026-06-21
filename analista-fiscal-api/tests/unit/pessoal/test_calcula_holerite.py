"""Golden tests do orquestrador de holerite (Sprint 10 PR1 + redutor Lei 15.270/2025)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.pessoal.calcula_holerite import (
    ALGORITMO_VERSAO,
    calcular_holerite,
)

# Reaproveita os fixtures de faixas dos testes unitários adjacentes.
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS
from tests.unit.pessoal.test_calcula_inss_2026 import FAIXAS_2026 as INSS_FAIXAS_2026
from tests.unit.pessoal.test_calcula_irrf_2026 import FAIXAS_2026 as IRRF_FAIXAS_2026

ALIQ_FGTS_CLT = Decimal("0.0800")


class TestHoleriteGolden:
    def test_funcionario_3000_sem_dep(self) -> None:
        # INSS = 253,41; FGTS = 240,00
        # IRRF_legal: base 2746,59 × 7,5% − 169,44 = 36,55
        # IRRF_simpl: base 2435,20 (3000−564,80) → faixa 2 → 13,20
        # min(36,55 ; 13,20) = 13,20 → SIMPLIFICADO (FA2 M5)
        # Líquido = 3000 − 253,41 − 13,20 = 2733,39
        r = calcular_holerite(
            salario_base=Decimal("3000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        assert r.inss.inss == Decimal("253.41")
        assert r.irrf.irrf == Decimal("13.20")
        assert r.irrf.metodo == "simplificado"
        assert r.fgts.fgts == Decimal("240.00")
        assert r.valor_liquido == Decimal("2733.39")

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
        assert ALGORITMO_VERSAO == "holerite.clt.v2"

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


class TestHoleriteReductor2026:
    """Goldens de holerite com redutor Lei 15.270/2025 (competências ≥ 2026-01-01).

    Usa tabelas 2026: INSS (Portaria MPS/MF 13/2026) e IRRF (Lei 15.191/2025).
    Todos os valores conferidos à mão (ROUND_HALF_EVEN).
    """

    def test_salario_4500_isento_redutor_2026(self) -> None:
        # Salário 4500 ≤ 5000 → redutor zera o IRRF.
        # INSS 2026:
        #   F1: 1621 × 7,5% = 121,5750
        #   F2: (2902,84 − 1621) × 9% = 1281,84 × 9% = 115,3656
        #   F3: (4354,27 − 2902,84) × 12% = 1451,43 × 12% = 174,1716
        #   F4: (4500 − 4354,27) × 14% = 145,73 × 14% = 20,4022
        #   Total = 431,5144 → 431,51
        # IRRF tradicional (simplificado vence):
        #   base_simpl = 4500 − 607,20 = 3892,80 → F4 → 3892,80×22,5%−675,49 = 875,88−675,49 = 200,39
        #   base_legal = 4500 − 431,51 = 4068,49 → F4 → 4068,49×22,5%−675,49 = 239,92
        #   min(200,39; 239,92) = 200,39 → simplificado
        # Redutor: 4500 ≤ 5000 → irrf_final = 0,00
        # Líquido = 4500 − 431,51 − 0,00 = 4068,49
        r = calcular_holerite(
            salario_base=Decimal("4500.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            aliquota_fgts=ALIQ_FGTS_CLT,
            aplicar_redutor_lei_15270=True,
        )
        assert r.inss.inss == Decimal("431.51")
        assert r.irrf.irrf_tradicional == Decimal("200.39")
        assert r.irrf.redutor_lei_15270 == Decimal("200.39")
        assert r.irrf.irrf == Decimal("0.00")
        assert r.irrf.metodo == "simplificado"
        assert r.valor_liquido == Decimal("4068.49")

    def test_salario_6000_redutor_linear_2026(self) -> None:
        # Salário 6000 → faixa linear do redutor (5000,01..7350).
        # INSS 2026:
        #   F1: 121,5750; F2: 115,3656; F3: 174,1716
        #   F4: (6000 − 4354,27) × 14% = 1645,73 × 14% = 230,4022
        #   Total = 641,5144 → 641,51
        # IRRF tradicional:
        #   base_legal = 6000 − 641,51 = 5358,49 → F5 → 5358,49×27,5%−908,73 = 1473,5848−908,73 = 564,85
        #   base_simpl = 6000 − 607,20 = 5392,80 → F5 → 5392,80×27,5%−908,73 = 1483,02−908,73 = 574,29
        #   min(564,85; 574,29) = 564,85 → legal
        # Redutor: 978,62 − 0,133145×6000 = 978,62 − 798,87 = 179,75
        # irrf_final = 564,85 − 179,75 = 385,10
        # Líquido = 6000 − 641,51 − 385,10 = 4973,39
        r = calcular_holerite(
            salario_base=Decimal("6000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            aliquota_fgts=ALIQ_FGTS_CLT,
            aplicar_redutor_lei_15270=True,
        )
        assert r.inss.inss == Decimal("641.51")
        assert r.irrf.irrf_tradicional == Decimal("564.85")
        assert r.irrf.redutor_lei_15270 == Decimal("179.75")
        assert r.irrf.irrf == Decimal("385.10")
        assert r.irrf.metodo == "legal"
        assert r.valor_liquido == Decimal("4973.39")

    def test_salario_8000_acima_teto_redutor_2026(self) -> None:
        # Salário 8000 > 7350 → tabela cheia (sem redutor).
        # INSS 2026:
        #   F1: 121,5750; F2: 115,3656; F3: 174,1716
        #   F4: (8000 − 4354,27) × 14% = 3645,73 × 14% = 510,4022
        #   Total = 921,5144 → 921,51
        # IRRF (tabela cheia — redutor = 0):
        #   base_legal = 8000 − 921,51 = 7078,49 → F5 → 7078,49×27,5%−908,73 = 1946,5848−908,73 = 1037,85
        #   base_simpl = 8000 − 607,20 = 7392,80 → F5 → 7392,80×27,5%−908,73 = 2033,02−908,73 = 1124,29
        #   min(1037,85; 1124,29) = 1037,85 → legal
        # Redutor = 0,00 (> 7350)
        # Líquido = 8000 − 921,51 − 1037,85 = 6040,64
        r = calcular_holerite(
            salario_base=Decimal("8000.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS_2026,
            faixas_irrf=IRRF_FAIXAS_2026,
            aliquota_fgts=ALIQ_FGTS_CLT,
            aplicar_redutor_lei_15270=True,
        )
        assert r.inss.inss == Decimal("921.51")
        assert r.irrf.redutor_lei_15270 == Decimal("0.00")
        assert r.irrf.irrf == Decimal("1037.85")
        assert r.irrf.metodo == "legal"
        assert r.valor_liquido == Decimal("6040.64")

    def test_2025_nao_aplica_redutor(self) -> None:
        # Sem aplicar_redutor_lei_15270 (default) → tabela cheia.
        # Prova que competências ≤ 2025 não recebem o redutor.
        r_sem = calcular_holerite(
            salario_base=Decimal("4500.00"),
            dependentes_irrf=0,
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            aliquota_fgts=ALIQ_FGTS_CLT,
        )
        # Sem redutor: IRRF deve ser > 0 para salário 4500 (tabela 2025)
        assert r_sem.irrf.redutor_lei_15270 == Decimal("0.00")
        assert r_sem.irrf.irrf > Decimal("0.00")
