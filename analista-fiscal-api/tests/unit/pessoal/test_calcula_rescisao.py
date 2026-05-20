"""Golden tests de rescisão — 5 modalidades CLT (Sprint 10 PR2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.pessoal.calcula_rescisao import (
    ALGORITMO_VERSAO,
    RescisaoTipo,
    aviso_previo_dias,
    calcular_rescisao,
)
from tests.unit.pessoal.test_calcula_inss import FAIXAS_2025 as INSS_FAIXAS
from tests.unit.pessoal.test_calcula_irrf import FAIXAS_VIGENTES as IRRF_FAIXAS


class TestAvisoPrevioDias:
    def test_zero_anos(self) -> None:
        assert aviso_previo_dias(0) == 30

    def test_um_ano(self) -> None:
        assert aviso_previo_dias(1) == 33

    def test_dez_anos(self) -> None:
        assert aviso_previo_dias(10) == 60

    def test_vinte_anos_capa_em_90(self) -> None:
        # 30 + 3×20 = 90 (no limite)
        assert aviso_previo_dias(20) == 90

    def test_acima_limite_capa(self) -> None:
        # 30 + 3×25 = 105, capa em 90
        assert aviso_previo_dias(25) == 90

    def test_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="anos_completos_servico"):
            aviso_previo_dias(-1)


class TestSemJustaCausa:
    """Modalidade canônica — empregador despede. Todas as verbas + multa 40%."""

    def test_3_anos_salario_3000_sem_dep(self) -> None:
        # Cenário: 3 anos, salário 3000, demissão dia 15 de um mês.
        # Aviso devido: 30 + 3×3 = 39 dias; indenizado 100% → 39
        # avos_13o = 12 (cobre o ano), avos_ferias_prop = 12, ferias_venc = 30
        # saldo_fgts_acumulado = 8640 (suposto)
        #
        # Verbas:
        #   saldo = 3000×15/30 = 1500
        #   aviso = 3000×39/30 = 3900
        #   13º   = 3000
        #   fv    = 4000 (30 dias + 1/3)
        #   fp    = 4000
        #   bruto = 1500 + 3900 + 3000 + 4000 + 4000 = 16400
        #
        # INSS saldo (1500): só faixa 1 = 1500×7,5% = 112,50
        # IRRF saldo: base = 1500−112,50 = 1387,50 → faixa 1 → 0
        # INSS 13º (3000): mesmo cálculo do 13º normal = 253,41
        # IRRF 13º: base = 3000−253,41 = 2746,59 → faixa 2 → 36,55
        # FGTS rescisão = 8% × (saldo+13º+aviso) = 0,08 × (1500+3000+3900) = 0,08 × 8400 = 672
        # Multa = 40% × (8640 + 672) = 0,40 × 9312 = 3724,80
        # Líquido = 16400 − (112,50+0+253,41+36,55) = 16400 − 402,46 = 15997,54
        r = calcular_rescisao(
            tipo=RescisaoTipo.SEM_JUSTA_CAUSA,
            salario=Decimal("3000.00"),
            anos_completos_servico=3,
            dias_trabalhados_mes_demissao=15,
            avos_13o=12,
            avos_ferias_proporcionais=12,
            ferias_vencidas_dias=30,
            saldo_fgts_acumulado=Decimal("8640.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.aviso_dias_devidos == 39
        assert r.aviso_dias_indenizados == 39
        assert r.verbas.saldo_salario == Decimal("1500.00")
        assert r.verbas.aviso_indenizado == Decimal("3900.00")
        assert r.verbas.decimo_terceiro_proporcional == Decimal("3000.00")
        assert r.verbas.ferias_vencidas == Decimal("4000.00")
        assert r.verbas.ferias_proporcionais == Decimal("4000.00")
        assert r.verbas.valor_bruto_total == Decimal("16400.00")
        assert r.inss_saldo.inss == Decimal("112.50")
        assert r.irrf_saldo.irrf == Decimal("0.00")
        assert r.inss_13o is not None
        assert r.inss_13o.inss == Decimal("253.41")
        assert r.irrf_13o is not None
        assert r.irrf_13o.irrf == Decimal("36.55")
        assert r.fgts_rescisao == Decimal("672.00")
        assert r.multa_fgts == Decimal("3724.80")
        assert r.multa_fgts_pct == Decimal("0.40")
        assert r.valor_liquido_a_pagar == Decimal("15997.54")
        assert r.algoritmo_versao == ALGORITMO_VERSAO


class TestComJustaCausa:
    """Só saldo + férias vencidas. Sem aviso, sem 13º, sem multa."""

    def test_so_saldo_e_ferias_venc(self) -> None:
        # Salário 3000, dia 10 do mês, com 30 dias de férias venc
        # Saldo = 3000×10/30 = 1000
        # Aviso = 0 (justa causa)
        # 13º = 0 (perde direito)
        # Férias venc = 30+1/3 = 4000
        # Férias prop = 0
        # bruto = 1000 + 4000 = 5000
        # INSS saldo (1000): faixa 1 = 75,00
        # IRRF saldo: base = 925 → faixa 1 → 0
        # FGTS rescisão = 0,08 × 1000 = 80 (só saldo)
        # Multa = 0
        # Líquido = 5000 − 75 = 4925
        r = calcular_rescisao(
            tipo=RescisaoTipo.COM_JUSTA_CAUSA,
            salario=Decimal("3000.00"),
            anos_completos_servico=5,
            dias_trabalhados_mes_demissao=10,
            avos_13o=8,  # ignorado para CJC
            avos_ferias_proporcionais=8,  # ignorado para CJC
            ferias_vencidas_dias=30,
            saldo_fgts_acumulado=Decimal("10000"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.aviso_dias_indenizados == 0
        assert r.verbas.aviso_indenizado == Decimal("0")
        assert r.verbas.decimo_terceiro_proporcional == Decimal("0")
        assert r.verbas.ferias_vencidas == Decimal("4000.00")
        assert r.verbas.ferias_proporcionais == Decimal("0")
        assert r.verbas.saldo_salario == Decimal("1000.00")
        assert r.verbas.valor_bruto_total == Decimal("5000.00")
        assert r.inss_13o is None
        assert r.irrf_13o is None
        assert r.fgts_rescisao == Decimal("80.00")  # só sobre saldo
        assert r.multa_fgts == Decimal("0.00")
        assert r.multa_fgts_pct == Decimal("0")
        assert r.valor_liquido_a_pagar == Decimal("4925.00")


class TestPedidoDemissao:
    """Saldo + 13º prop + férias venc + prop + 1/3. Sem aviso, sem multa."""

    def test_pedido_2_anos(self) -> None:
        # avos_13o=6, avos_fp=6, 0 férias venc
        # Saldo = 3000×20/30 = 2000
        # Aviso = 0
        # 13º = 3000×6/12 = 1500
        # FV = 0
        # FP = 1500 + 500 = 2000
        # bruto = 2000 + 1500 + 2000 = 5500
        # INSS saldo (2000): 113,85 + (2000−1518)×9% = 113,85 + 43,38 = 157,23
        # IRRF saldo: base = 2000−157,23 = 1842,77 → faixa 1 → 0
        # INSS 13º (1500): 1500×7,5% = 112,50
        # IRRF 13º: base = 1500−112,50 = 1387,50 → faixa 1 → 0
        # FGTS rescisão = 8% × (saldo+13º+0) = 0,08 × 3500 = 280
        # Multa = 0
        # Líquido = 5500 − (157,23+0+112,50+0) = 5500 − 269,73 = 5230,27
        r = calcular_rescisao(
            tipo=RescisaoTipo.PEDIDO_DEMISSAO,
            salario=Decimal("3000.00"),
            anos_completos_servico=2,
            dias_trabalhados_mes_demissao=20,
            avos_13o=6,
            avos_ferias_proporcionais=6,
            ferias_vencidas_dias=0,
            saldo_fgts_acumulado=Decimal("5000"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.aviso_dias_indenizados == 0
        assert r.verbas.aviso_indenizado == Decimal("0")
        assert r.verbas.decimo_terceiro_proporcional == Decimal("1500.00")
        assert r.verbas.ferias_proporcionais == Decimal("2000.00")
        assert r.fgts_rescisao == Decimal("280.00")
        assert r.multa_fgts == Decimal("0.00")
        assert r.valor_liquido_a_pagar == Decimal("5230.27")


class TestMutuoAcordo:
    """484-A: metade aviso + 20% multa + demais integrais."""

    def test_mutuo_3_anos(self) -> None:
        # Aviso devido = 39, indenizado 50% → 19 (truncado por int())
        # Saldo = 3000×15/30 = 1500
        # Aviso = 3000×19/30 = 1900
        # 13º = 3000 (avos=12, integral)
        # FP = 4000
        # FV = 4000
        # bruto = 1500+1900+3000+4000+4000 = 14400
        # INSS saldo (1500): 112,50; IRRF: base 1387,50 → 0
        # INSS 13º (3000): 253,41; IRRF: 36,55
        # FGTS rescisão = 8% × (1500+3000+1900) = 0,08 × 6400 = 512
        # Multa = 20% × (saldo_acum + fgts_resc) = 0,20 × (8640 + 512) = 0,20 × 9152 = 1830,40
        # Líquido = 14400 − (112,50+0+253,41+36,55) = 14400 − 402,46 = 13997,54
        r = calcular_rescisao(
            tipo=RescisaoTipo.MUTUO_ACORDO,
            salario=Decimal("3000.00"),
            anos_completos_servico=3,
            dias_trabalhados_mes_demissao=15,
            avos_13o=12,
            avos_ferias_proporcionais=12,
            ferias_vencidas_dias=30,
            saldo_fgts_acumulado=Decimal("8640.00"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.aviso_dias_devidos == 39
        assert r.aviso_dias_indenizados == 19
        assert r.verbas.aviso_indenizado == Decimal("1900.00")
        assert r.fgts_rescisao == Decimal("512.00")
        assert r.multa_fgts_pct == Decimal("0.20")
        assert r.multa_fgts == Decimal("1830.40")
        assert r.valor_liquido_a_pagar == Decimal("13997.54")


class TestTerminoDeterminado:
    """Sem aviso, sem multa. 13º + férias prop integrais."""

    def test_termino_1_ano(self) -> None:
        # avos_13o=12 (cobre ano todo do término), avos_fp=12, 0 venc
        # Saldo = 3000×20/30 = 2000
        # Aviso = 0
        # 13º = 3000
        # FV = 0
        # FP = 4000
        # bruto = 2000+3000+0+4000 = 9000
        # INSS saldo (2000) = 157,23; IRRF saldo = 0
        # INSS 13º (3000) = 253,41; IRRF 13º = 36,55
        # FGTS = 0,08 × (2000+3000+0) = 400
        # Multa = 0
        # Líquido = 9000 − (157,23+0+253,41+36,55) = 9000 − 447,19 = 8552,81
        r = calcular_rescisao(
            tipo=RescisaoTipo.TERMINO_DETERMINADO,
            salario=Decimal("3000.00"),
            anos_completos_servico=1,
            dias_trabalhados_mes_demissao=20,
            avos_13o=12,
            avos_ferias_proporcionais=12,
            ferias_vencidas_dias=0,
            saldo_fgts_acumulado=Decimal("2880"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.verbas.aviso_indenizado == Decimal("0")
        assert r.fgts_rescisao == Decimal("400.00")
        assert r.multa_fgts == Decimal("0.00")
        assert r.valor_liquido_a_pagar == Decimal("8552.81")


class TestBordas:
    @pytest.fixture
    def kwargs_base(self) -> dict:
        return dict(
            tipo=RescisaoTipo.SEM_JUSTA_CAUSA,
            salario=Decimal("3000"),
            anos_completos_servico=1,
            dias_trabalhados_mes_demissao=15,
            avos_13o=6,
            avos_ferias_proporcionais=6,
            ferias_vencidas_dias=0,
            saldo_fgts_acumulado=Decimal("1000"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )

    def test_salario_negativo(self, kwargs_base: dict) -> None:
        kwargs_base["salario"] = Decimal("-1")
        with pytest.raises(ValueError, match="salario"):
            calcular_rescisao(**kwargs_base)

    def test_dias_trab_invalido(self, kwargs_base: dict) -> None:
        kwargs_base["dias_trabalhados_mes_demissao"] = 32
        with pytest.raises(ValueError, match="dias_trabalhados"):
            calcular_rescisao(**kwargs_base)

    def test_avos_13_invalido(self, kwargs_base: dict) -> None:
        kwargs_base["avos_13o"] = 13
        with pytest.raises(ValueError, match="avos_13o"):
            calcular_rescisao(**kwargs_base)

    def test_avos_fp_invalido(self, kwargs_base: dict) -> None:
        kwargs_base["avos_ferias_proporcionais"] = -1
        with pytest.raises(ValueError, match="avos_ferias_proporcionais"):
            calcular_rescisao(**kwargs_base)

    def test_ferias_venc_invalido(self, kwargs_base: dict) -> None:
        kwargs_base["ferias_vencidas_dias"] = 31
        with pytest.raises(ValueError, match="ferias_vencidas_dias"):
            calcular_rescisao(**kwargs_base)

    def test_saldo_fgts_negativo(self, kwargs_base: dict) -> None:
        kwargs_base["saldo_fgts_acumulado"] = Decimal("-1")
        with pytest.raises(ValueError, match="saldo_fgts_acumulado"):
            calcular_rescisao(**kwargs_base)


class TestEstrutura:
    def test_versao(self) -> None:
        r = calcular_rescisao(
            tipo=RescisaoTipo.SEM_JUSTA_CAUSA,
            salario=Decimal("3000"),
            anos_completos_servico=1,
            dias_trabalhados_mes_demissao=15,
            avos_13o=6,
            avos_ferias_proporcionais=6,
            ferias_vencidas_dias=0,
            saldo_fgts_acumulado=Decimal("1000"),
            faixas_inss=INSS_FAIXAS,
            faixas_irrf=IRRF_FAIXAS,
            dependentes=0,
        )
        assert r.algoritmo_versao == ALGORITMO_VERSAO
