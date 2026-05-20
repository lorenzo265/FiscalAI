"""Golden tests do algoritmo de depreciação linear (Sprint 8 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.imobilizado.calcula_depreciacao import (
    ALGORITMO_VERSAO,
    BemView,
    calcular_parcela_mensal,
    deve_depreciar_competencia,
)


def _bem(
    valor: str = "60000.00",
    residual: str = "0",
    vida_meses: int = 60,
    aquisicao: date = date(2026, 1, 10),
    baixa: date | None = None,
    ativo: bool = True,
) -> BemView:
    return BemView(
        valor_aquisicao=Decimal(valor),
        valor_residual=Decimal(residual),
        vida_util_meses=vida_meses,
        data_aquisicao=aquisicao,
        data_baixa=baixa,
        ativo=ativo,
    )


# ── deve_depreciar_competencia ──────────────────────────────────────────────


class TestElegibilidade:
    def test_mes_da_aquisicao_nao_deprecia(self) -> None:
        bem = _bem(aquisicao=date(2026, 1, 10))
        assert deve_depreciar_competencia(bem, date(2026, 1, 1)) is False

    def test_mes_seguinte_a_aquisicao_deprecia(self) -> None:
        bem = _bem(aquisicao=date(2026, 1, 10))
        assert deve_depreciar_competencia(bem, date(2026, 2, 1)) is True

    def test_aquisicao_em_dezembro_proximo_e_janeiro_seguinte(self) -> None:
        bem = _bem(aquisicao=date(2025, 12, 20))
        assert deve_depreciar_competencia(bem, date(2025, 12, 1)) is False
        assert deve_depreciar_competencia(bem, date(2026, 1, 1)) is True

    def test_apos_baixa_nao_deprecia(self) -> None:
        bem = _bem(
            aquisicao=date(2026, 1, 10),
            baixa=date(2026, 6, 15),
        )
        # Mês da baixa em diante NÃO deprecia
        assert deve_depreciar_competencia(bem, date(2026, 6, 1)) is False
        assert deve_depreciar_competencia(bem, date(2026, 7, 1)) is False
        # Antes da baixa deprecia normal
        assert deve_depreciar_competencia(bem, date(2026, 5, 1)) is True

    def test_inativo_nao_deprecia(self) -> None:
        bem = _bem(ativo=False)
        assert deve_depreciar_competencia(bem, date(2026, 2, 1)) is False


# ── Golden cases — categorias da IN SRF 162/1998 ────────────────────────────


class TestGoldenLinear:
    def test_veiculo_50k_taxa_20_pct(self) -> None:
        # R$ 50.000 / 60 meses = R$ 833,33/mês
        bem = _bem(valor="50000.00", vida_meses=60, aquisicao=date(2026, 1, 10))
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("833.33")
        assert r.valor_acumulado == Decimal("833.33")
        assert r.saldo_contabil == Decimal("49166.67")
        assert r.eh_ultima_parcela is False
        assert r.versao == ALGORITMO_VERSAO

    def test_computador_5k_taxa_20_pct(self) -> None:
        # R$ 5.000 / 60 = R$ 83,33/mês
        bem = _bem(valor="5000.00", vida_meses=60, aquisicao=date(2026, 1, 5))
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("83.33")

    def test_edificacao_500k_taxa_4_pct(self) -> None:
        # R$ 500.000 / 300 meses = R$ 1.666,67/mês
        bem = _bem(valor="500000.00", vida_meses=300, aquisicao=date(2026, 1, 1))
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("1666.67")

    def test_maquina_100k_taxa_10_pct(self) -> None:
        # R$ 100.000 / 120 meses = R$ 833,33/mês
        bem = _bem(valor="100000.00", vida_meses=120)
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("833.33")

    def test_movel_10k_taxa_10_pct(self) -> None:
        bem = _bem(valor="10000.00", vida_meses=120)
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("83.33")


# ── Valor residual ──────────────────────────────────────────────────────────


class TestValorResidual:
    def test_valor_residual_reduz_base_depreciavel(self) -> None:
        # 50.000 − 5.000 = 45.000 base; / 60 = 750
        bem = _bem(valor="50000.00", residual="5000.00", vida_meses=60)
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("750.00")
        assert r.saldo_contabil == Decimal("49250.00")

    def test_residual_igual_valor_zera_parcela(self) -> None:
        bem = _bem(valor="1000.00", residual="1000.00", vida_meses=60)
        r = calcular_parcela_mensal(
            bem, date(2026, 2, 1), valor_acumulado_anterior=Decimal("0")
        )
        # Base depreciável = 0 → totalmente depreciado de cara
        assert r.valor_depreciado == Decimal("0.00")


# ── Fim da vida útil + ajuste da última parcela ─────────────────────────────


class TestUltimaParcela:
    def test_ultima_parcela_fecha_residuo(self) -> None:
        # R$ 1.000 / 3 = 333,33 → 3 parcelas seriam 999,99, faltaria 0,01
        bem = _bem(valor="1000.00", vida_meses=3, aquisicao=date(2026, 1, 1))
        # 2 parcelas já acumuladas (666,66)
        r = calcular_parcela_mensal(
            bem, date(2026, 4, 1), valor_acumulado_anterior=Decimal("666.66")
        )
        # Deve fechar exato em 1000
        assert r.valor_depreciado == Decimal("333.34")
        assert r.valor_acumulado == Decimal("1000.00")
        assert r.saldo_contabil == Decimal("0.00")
        assert r.eh_ultima_parcela is True

    def test_apos_totalmente_depreciado_retorna_zero(self) -> None:
        bem = _bem(valor="1000.00", vida_meses=3)
        r = calcular_parcela_mensal(
            bem, date(2026, 6, 1), valor_acumulado_anterior=Decimal("1000.00")
        )
        assert r.valor_depreciado == Decimal("0.00")
        assert r.valor_acumulado == Decimal("1000.00")


# ── Janela / baixa ──────────────────────────────────────────────────────────


class TestJanela:
    def test_mes_da_aquisicao_retorna_zero(self) -> None:
        bem = _bem(aquisicao=date(2026, 4, 10))
        r = calcular_parcela_mensal(
            bem, date(2026, 4, 1), valor_acumulado_anterior=Decimal("0")
        )
        assert r.valor_depreciado == Decimal("0.00")
        # Mantém saldo cheio (sem depreciação)
        assert r.saldo_contabil == bem.valor_aquisicao

    def test_apos_baixa_retorna_zero(self) -> None:
        bem = _bem(
            valor="6000.00",
            vida_meses=60,
            aquisicao=date(2026, 1, 1),
            baixa=date(2026, 4, 10),
        )
        # Maio de 2026 — já passou a baixa (abril)
        r = calcular_parcela_mensal(
            bem, date(2026, 5, 1), valor_acumulado_anterior=Decimal("300.00")
        )
        assert r.valor_depreciado == Decimal("0.00")


# ── Determinismo ────────────────────────────────────────────────────────────


class TestDeterminismo:
    def test_mesmo_input_mesmo_resultado(self) -> None:
        bem = _bem(valor="12345.67", residual="100.00", vida_meses=48)
        r1 = calcular_parcela_mensal(
            bem, date(2026, 3, 1), valor_acumulado_anterior=Decimal("500.00")
        )
        r2 = calcular_parcela_mensal(
            bem, date(2026, 3, 1), valor_acumulado_anterior=Decimal("500.00")
        )
        assert r1 == r2
