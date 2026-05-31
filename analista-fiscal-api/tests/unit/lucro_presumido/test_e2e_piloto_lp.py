"""Testes E2E de piloto LP — 3 perfis empresariais (Sprint 20 PR3).

Valida a coerência end-to-end do stack de Lucro Presumido sem I/O:
  * calcula_irpj + calcula_csll + calcula_pis_cofins + calcula_darf_lp + calcula_checklist_lp.
  * Três perfis representativos de empresas LP reais.

Princípio §8.4: golden tests bloqueiam merge.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.lucro_presumido.calcula_checklist_lp import calcular_checklist_trimestre
from app.modules.lucro_presumido.calcula_csll import calcular_csll_trimestral
from app.modules.lucro_presumido.calcula_darf_lp import (
    calcular_darf_cofins,
    calcular_darf_csll,
    calcular_darf_irpj,
    calcular_darf_pis,
)
from app.modules.lucro_presumido.calcula_irpj import calcular_irpj_trimestral
from app.modules.lucro_presumido.calcula_pis_cofins import (
    calcular_cofins_cumulativo_mensal,
    calcular_pis_cumulativo_mensal,
)


# ── Perfil 1: Consultoria de TI (serviços) ────────────────────────────────────
# CNAE: 6201-5/01 | Presunção IRPJ 32% | CSLL 32%
# Receita: R$ 500.000/trimestre = R$ 1.666.667/mês


class TestConsultoriaTI:
    """Consultoria LP com receita R$500k/trimestre — presunção 32%."""

    RECEITA_TRIM = Decimal("500_000.00")
    RECEITA_MES = Decimal("166_666.67")
    PRESUNCAO_IRPJ = Decimal("0.32")
    PRESUNCAO_CSLL = Decimal("0.32")
    ALIQ_CSLL = Decimal("0.09")

    def test_irpj_t1_base_presumida(self) -> None:
        r = calcular_irpj_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_IRPJ
        )
        assert r.base_presumida == Decimal("160_000.00")

    def test_irpj_t1_adicional_ativado(self) -> None:
        r = calcular_irpj_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_IRPJ
        )
        # base 160.000 > limite 60.000 → adicional sobre 100.000
        assert r.irpj_adicional == Decimal("10_000.00")

    def test_irpj_t1_total_bruto(self) -> None:
        r = calcular_irpj_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_IRPJ
        )
        # normal = 160.000 × 15% = 24.000; adicional = 10.000 → total = 34.000
        assert r.irpj_total == Decimal("34_000.00")

    def test_csll_t1(self) -> None:
        r = calcular_csll_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_CSLL
        )
        # base = 160.000 × 9% = 14.400
        assert r.csll == Decimal("14_400.00")

    def test_pis_janeiro(self) -> None:
        r = calcular_pis_cumulativo_mensal(self.RECEITA_MES)
        # 166.666,67 × 0,65% = 1.083,33
        assert r.tributo == Decimal("1_083.33")

    def test_cofins_janeiro(self) -> None:
        r = calcular_cofins_cumulativo_mensal(self.RECEITA_MES)
        # 166.666,67 × 3% = 5.000,00
        assert r.tributo == Decimal("5_000.00")

    def test_darf_irpj_t1_codigo_e_vencimento(self) -> None:
        irpj = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_IRPJ)
        darf = calcular_darf_irpj(irpj.irpj_devido, 2026, 1)
        assert darf.codigo_receita == "2089"
        assert darf.data_vencimento == date(2026, 4, 30)
        assert darf.valor_principal == irpj.irpj_devido

    def test_darf_csll_t1(self) -> None:
        csll = calcular_csll_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_CSLL)
        darf = calcular_darf_csll(csll.csll, 2026, 1)
        assert darf.codigo_receita == "2372"
        assert darf.valor_principal == csll.csll

    def test_carga_tributaria_trimestral_t1(self) -> None:
        """Carga = IRPJ + CSLL + PIS×3 + Cofins×3."""
        irpj = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_IRPJ).irpj_total
        csll = calcular_csll_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_CSLL).csll
        pis3 = calcular_pis_cumulativo_mensal(self.RECEITA_MES).tributo * 3
        cofins3 = calcular_cofins_cumulativo_mensal(self.RECEITA_MES).tributo * 3
        carga = irpj + csll + pis3 + cofins3
        receita = self.RECEITA_TRIM
        # Carga percentual ~13,5% da receita bruta (serviços LP)
        percentual = carga / receita * 100
        assert Decimal("12") <= percentual <= Decimal("16")

    def test_checklist_t1_completo_com_todas_apuracoes(self) -> None:
        aps = frozenset({
            "irpj:2026-01-01", "csll:2026-01-01",
            "pis:2026-01-01", "pis:2026-02-01", "pis:2026-03-01",
            "cofins:2026-01-01", "cofins:2026-02-01", "cofins:2026-03-01",
        })
        darfs = frozenset({
            "2089:2026-01-01", "2372:2026-01-01",
            "8109:2026-01-01", "8109:2026-02-01", "8109:2026-03-01",
            "2172:2026-01-01", "2172:2026-02-01", "2172:2026-03-01",
        })
        c = calcular_checklist_trimestre(2026, 1, apuracoes_existentes=aps, darfs_existentes=darfs)
        assert c.completo is True
        assert c.percentual_conclusao == 100


# ── Perfil 2: Comércio varejista ──────────────────────────────────────────────
# CNAE: 4711-3/01 | Presunção IRPJ 8% | CSLL 12%
# Receita: R$ 1.200.000/trimestre


class TestComercioVarejista:
    """Comércio LP com receita R$1,2M/trimestre — presunção 8%/12%."""

    RECEITA_TRIM = Decimal("1_200_000.00")
    RECEITA_MES = Decimal("400_000.00")
    PRESUNCAO_IRPJ = Decimal("0.08")
    PRESUNCAO_CSLL = Decimal("0.12")

    def test_irpj_base_presumida_comercio(self) -> None:
        r = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_IRPJ)
        assert r.base_presumida == Decimal("96_000.00")

    def test_irpj_adicional_ativado_comercio(self) -> None:
        r = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_IRPJ)
        # base 96.000 > 60.000 → adicional sobre 36.000 = 3.600
        assert r.irpj_adicional == Decimal("3_600.00")
        assert r.irpj_total == Decimal("18_000.00")

    def test_csll_comercio(self) -> None:
        r = calcular_csll_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_CSLL)
        # base = 1.200.000 × 12% = 144.000 × 9% = 12.960
        assert r.csll == Decimal("12_960.00")

    def test_pis_cofins_comercio(self) -> None:
        pis = calcular_pis_cumulativo_mensal(self.RECEITA_MES)
        cofins = calcular_cofins_cumulativo_mensal(self.RECEITA_MES)
        # PIS: 400.000 × 0,65% = 2.600; Cofins: 400.000 × 3% = 12.000
        assert pis.tributo == Decimal("2_600.00")
        assert cofins.tributo == Decimal("12_000.00")

    def test_darf_irpj_comercio_codigo_e_valor(self) -> None:
        r = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO_IRPJ)
        darf = calcular_darf_irpj(r.irpj_devido, 2026, 2)
        assert darf.codigo_receita == "2089"
        assert darf.valor_principal == Decimal("18_000.00")
        assert darf.data_vencimento == date(2026, 7, 31)

    def test_carga_tributaria_menor_que_servicos(self) -> None:
        """Comércio com presunção 8% paga menos IRPJ do que serviços com 32%."""
        irpj_com = calcular_irpj_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_IRPJ
        ).irpj_total
        irpj_srv = calcular_irpj_trimestral(
            self.RECEITA_TRIM, Decimal("0.32")
        ).irpj_total
        assert irpj_com < irpj_srv

    def test_ciclo_anual_4_trimestres_coerente(self) -> None:
        """4 trimestres idênticos → total anual = 4 × trimestral."""
        irpj_trim = calcular_irpj_trimestral(
            self.RECEITA_TRIM, self.PRESUNCAO_IRPJ
        ).irpj_total
        assert irpj_trim * 4 == Decimal("72_000.00")


# ── Perfil 3: Serviços de pequeno porte ──────────────────────────────────────
# Presunção 32% | Receita R$ 150.000/trimestre (baixa — sem adicional)


class TestServicosPorte:
    """Serviços LP com receita R$150k/trimestre — sem adicional de 10%."""

    RECEITA_TRIM = Decimal("150_000.00")
    RECEITA_MES = Decimal("50_000.00")
    PRESUNCAO = Decimal("0.32")

    def test_irpj_sem_adicional(self) -> None:
        r = calcular_irpj_trimestral(self.RECEITA_TRIM, self.PRESUNCAO)
        # base = 48.000 < 60.000 → sem adicional
        assert r.irpj_adicional == Decimal("0.00")
        assert r.irpj_total == Decimal("7_200.00")

    def test_csll_pequeno_porte(self) -> None:
        r = calcular_csll_trimestral(self.RECEITA_TRIM, self.PRESUNCAO)
        # base = 48.000 × 9% = 4.320
        assert r.csll == Decimal("4_320.00")

    def test_pis_pequeno_porte(self) -> None:
        r = calcular_pis_cumulativo_mensal(self.RECEITA_MES)
        # 50.000 × 0,65% = 325
        assert r.tributo == Decimal("325.00")

    def test_cofins_pequeno_porte(self) -> None:
        r = calcular_cofins_cumulativo_mensal(self.RECEITA_MES)
        # 50.000 × 3% = 1.500
        assert r.tributo == Decimal("1_500.00")

    def test_darf_pis_dezembro_vencimento_jan(self) -> None:
        r = calcular_pis_cumulativo_mensal(self.RECEITA_MES)
        darf = calcular_darf_pis(r.tributo, date(2026, 12, 1))
        assert darf.data_vencimento == date(2027, 1, 25)

    def test_darf_cofins_dezembro_vencimento_jan(self) -> None:
        r = calcular_cofins_cumulativo_mensal(self.RECEITA_MES)
        darf = calcular_darf_cofins(r.tributo, date(2026, 12, 1))
        assert darf.data_vencimento == date(2027, 1, 25)

    def test_checklist_t4_meses_corretos(self) -> None:
        c = calcular_checklist_trimestre(
            2026, 4,
            apuracoes_existentes=frozenset(),
            darfs_existentes=frozenset(),
        )
        pis_items = [i for i in c.itens if i.tipo.startswith("apuracao_pis_")]
        meses = {i.competencia.month for i in pis_items}
        assert meses == {10, 11, 12}

    def test_invariante_darf_codigo_unico_por_tributo(self) -> None:
        """Códigos de receita são distintos entre IRPJ, CSLL, PIS e Cofins."""
        irpj = calcular_darf_irpj(Decimal("1000"), 2026, 1)
        csll = calcular_darf_csll(Decimal("1000"), 2026, 1)
        pis = calcular_darf_pis(Decimal("100"), date(2026, 1, 1))
        cofins = calcular_darf_cofins(Decimal("500"), date(2026, 1, 1))
        codigos = {irpj.codigo_receita, csll.codigo_receita, pis.codigo_receita, cofins.codigo_receita}
        assert len(codigos) == 4  # todos distintos

    def test_invariante_pis_e_cofins_mesmo_vencimento(self) -> None:
        """PIS e Cofins da mesma competência têm o mesmo vencimento."""
        pis = calcular_darf_pis(Decimal("100"), date(2026, 3, 1))
        cofins = calcular_darf_cofins(Decimal("500"), date(2026, 3, 1))
        assert pis.data_vencimento == cofins.data_vencimento == date(2026, 4, 25)

    def test_invariante_irpj_e_csll_mesmo_vencimento_trimestral(self) -> None:
        """IRPJ e CSLL do mesmo trimestre têm o mesmo vencimento."""
        irpj = calcular_darf_irpj(Decimal("7200"), 2026, 1)
        csll = calcular_darf_csll(Decimal("4320"), 2026, 1)
        assert irpj.data_vencimento == csll.data_vencimento
