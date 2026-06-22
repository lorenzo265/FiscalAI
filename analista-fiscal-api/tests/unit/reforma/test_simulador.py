"""Golden tests do simulador de impacto da Reforma (Sprint 14 PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.reforma.calcula_cbs_ibs import (
    OBSERVACAO_ESTIMATIVA,
    AliquotaCBSIBS,
)
from app.modules.reforma.periodo_transicao import FaseReforma
from app.modules.reforma.simulador import (
    ALGORITMO_VERSAO,
    CargaTributariaAnualizada,
    Cenario,
    projetar_impacto,
)


def _aliquota_pleno() -> AliquotaCBSIBS:
    """Vigência regime pleno 2033: CBS 8,8% + IBS 17,7% (total 26,5%)."""
    return AliquotaCBSIBS(
        fase=FaseReforma.PLENO,
        aliquota_cbs=Decimal("0.0880"),
        aliquota_ibs=Decimal("0.1770"),
        valid_from=date(2033, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 156-A §1º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


def _carga_padrao() -> CargaTributariaAnualizada:
    """Carga típica de uma PME LP — soma 12m."""
    return CargaTributariaAnualizada(
        pis=Decimal("6500.00"),
        cofins=Decimal("30000.00"),
        icms=Decimal("120000.00"),
        iss=Decimal("0.00"),
    )


def _projetar(
    *,
    receita: str = "1000000.00",
    carga: CargaTributariaAnualizada | None = None,
    icms_medio: str = "10000.00",
    prazo: int = 20,
):
    return projetar_impacto(
        empresa_id=uuid4(),
        periodo_base=(date(2025, 5, 1), date(2026, 4, 30)),
        fase_atual=FaseReforma.TESTE_2026,
        receita_anualizada=Decimal(receita),
        carga_atual=carga or _carga_padrao(),
        aliquota_pleno=_aliquota_pleno(),
        icms_medio_mensal=Decimal(icms_medio),
        prazo_recolhimento_dias=prazo,
    )


class TestTresCenarios:
    """Sempre 3 cenários ordenados: pessimista > realista > otimista."""

    def test_quantidade_e_ordem(self) -> None:
        r = _projetar()
        assert len(r.cenarios) == 3
        assert r.cenarios[0].cenario is Cenario.PESSIMISTA
        assert r.cenarios[1].cenario is Cenario.REALISTA
        assert r.cenarios[2].cenario is Cenario.OTIMISTA

    def test_pessimista_maior_que_realista_maior_que_otimista(self) -> None:
        r = _projetar()
        pessimista, realista, otimista = r.cenarios
        assert pessimista.total_projetado > realista.total_projetado
        assert realista.total_projetado > otimista.total_projetado

    def test_aliquotas_pessimista_realista_otimista_2pp(self) -> None:
        r = _projetar()
        pessimista, realista, otimista = r.cenarios
        # pleno 26,5% → pessimista 28,5% / realista 26,5% / otimista 24,5%
        assert realista.aliquota_total == Decimal("0.2650")
        assert pessimista.aliquota_total == Decimal("0.2850")
        assert otimista.aliquota_total == Decimal("0.2450")


class TestCalculoCenarioRealista:
    """Realista usa alíquota da tabela sem delta — golden numérico."""

    def test_receita_1mi_cbs_ibs_pleno(self) -> None:
        # Receita 1.000.000 × 26,5% (8,8% CBS + 17,7% IBS) = 265.000
        # CBS: 1.000.000 × 0,0880 = 88.000,00
        # IBS: 1.000.000 × 0,1770 = 177.000,00
        r = _projetar(receita="1000000.00")
        realista = r.cenarios[1]
        assert realista.cbs_projetada == Decimal("88000.00")
        assert realista.ibs_projetada == Decimal("177000.00")
        assert realista.total_projetado == Decimal("265000.00")

    def test_delta_absoluto_e_percentual(self) -> None:
        r = _projetar(receita="1000000.00")
        # carga_atual = 6500 + 30000 + 120000 + 0 = 156.500
        realista = r.cenarios[1]
        assert r.carga_atual.total == Decimal("156500.00")
        assert realista.delta_absoluto == Decimal("108500.00")
        # 108500 / 156500 = 0,6932...
        assert realista.delta_percentual > Decimal("0.69")
        assert realista.delta_percentual < Decimal("0.70")


class TestCargaZero:
    """Empresa sem carga atual (nova ou inativa)."""

    def test_carga_zero_delta_percentual_eh_zero(self) -> None:
        carga = CargaTributariaAnualizada(
            pis=Decimal("0"),
            cofins=Decimal("0"),
            icms=Decimal("0"),
            iss=Decimal("0"),
        )
        r = _projetar(carga=carga)
        for c in r.cenarios:
            # Divisão por zero é tratada — delta_percentual = 0
            assert c.delta_percentual == Decimal("0")
            # delta absoluto continua > 0 (projeção em si)
            assert c.delta_absoluto > Decimal("0")


class TestReceitaZero:
    def test_receita_zero_cenarios_zerados(self) -> None:
        r = _projetar(receita="0.00")
        for c in r.cenarios:
            assert c.cbs_projetada == Decimal("0.00")
            assert c.ibs_projetada == Decimal("0.00")
            assert c.total_projetado == Decimal("0.00")


class TestImpactoFluxoCaixa:
    """Split payment 2027 — capital de giro perdido."""

    def test_capital_giro_padrao(self) -> None:
        # ICMS médio 10.000 × (20/30) = 6.666,67 (HALF_EVEN)
        r = _projetar(icms_medio="10000.00", prazo=20)
        assert r.impacto_fluxo_caixa_2027.capital_giro_perdido == Decimal(
            "6666.67"
        )
        assert r.impacto_fluxo_caixa_2027.media_icms_mensal == Decimal(
            "10000.00"
        )
        assert r.impacto_fluxo_caixa_2027.prazo_medio_recolhimento_dias == 20

    def test_prazo_zero_capital_zero(self) -> None:
        r = _projetar(prazo=0)
        assert r.impacto_fluxo_caixa_2027.capital_giro_perdido == Decimal("0.00")

    def test_icms_zero_capital_zero(self) -> None:
        r = _projetar(icms_medio="0.00")
        assert r.impacto_fluxo_caixa_2027.capital_giro_perdido == Decimal("0.00")

    def test_prazo_60_dias_proporcional(self) -> None:
        # 10000 × 60/30 = 20000,00 (prazo dobrado vs 20d aproximadamente
        # triplicaria, mas o 6666,67 já tem perda de centavo do arredondamento)
        r60 = _projetar(icms_medio="10000.00", prazo=60)
        assert r60.impacto_fluxo_caixa_2027.capital_giro_perdido == Decimal(
            "20000.00"
        )


class TestContratoDeResultado:
    """Princípio §8.12 — observação obrigatória; algoritmo_versao constante."""

    def test_observacao_estimativa_cita_lc_214(self) -> None:
        r = _projetar()
        assert r.observacao_estimativa == OBSERVACAO_ESTIMATIVA
        assert "LC 214/2025" in r.observacao_estimativa

    def test_algoritmo_versao_constante(self) -> None:
        assert ALGORITMO_VERSAO == "reforma.simulador.v1"
        r = _projetar()
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_fontes_norma_incluem_split_payment(self) -> None:
        r = _projetar()
        assert any("LC 214/2025" in f for f in r.fontes_norma)
        assert any("EC 132/2023" in f or "split" in f.lower() for f in r.fontes_norma)


class TestValidacoes:
    """Defesa em profundidade — inputs inválidos levantam."""

    def test_receita_negativa_levanta(self) -> None:
        with pytest.raises(ValueError, match="receita"):
            _projetar(receita="-1.00")

    def test_icms_medio_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="icms"):
            _projetar(icms_medio="-1.00")

    def test_prazo_negativo_levanta(self) -> None:
        with pytest.raises(ValueError, match="prazo"):
            _projetar(prazo=-1)


class TestCenariosClampAliquota:
    """Alíquota não pode exceder 100% mesmo com delta positivo extremo."""

    def test_alta_aliquota_clamp_a_1(self) -> None:
        # Cria alíquota inflada para forçar pessimista > 100%
        aliquota_extrema = AliquotaCBSIBS(
            fase=FaseReforma.PLENO,
            aliquota_cbs=Decimal("0.50"),
            aliquota_ibs=Decimal("0.49"),
            valid_from=date(2033, 1, 1),
            valid_to=None,
            fonte_norma="teste",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
        r = projetar_impacto(
            empresa_id=uuid4(),
            periodo_base=(date(2025, 5, 1), date(2026, 4, 30)),
            fase_atual=FaseReforma.TESTE_2026,
            receita_anualizada=Decimal("100.00"),
            carga_atual=_carga_padrao(),
            aliquota_pleno=aliquota_extrema,
            icms_medio_mensal=Decimal("0.00"),
        )
        # pessimista = 0,99 + 0,02 = 1,01 → clamp para 1,00
        assert r.cenarios[0].aliquota_total == Decimal("1.00")
