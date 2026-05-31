"""Golden tests do cálculo CBS/IBS informacional (Sprint 14 PR1)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.reforma.calcula_cbs_ibs import (
    ALGORITMO_VERSAO,
    OBSERVACAO_ESTIMATIVA,
    AliquotaCBSIBS,
    calcular_cbs_ibs,
)
from app.modules.reforma.periodo_transicao import FaseReforma
from app.shared.exceptions import BaseCalculoInvalida


def _aliquota_2026() -> AliquotaCBSIBS:
    """Vigência teste_2026: CBS 0,9% + IBS 0,1%."""
    return AliquotaCBSIBS(
        fase=FaseReforma.TESTE_2026,
        aliquota_cbs=Decimal("0.0090"),
        aliquota_ibs=Decimal("0.0010"),
        valid_from=date(2026, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 348 §3º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


def _aliquota_pleno() -> AliquotaCBSIBS:
    """Vigência regime_pleno_2033: CBS 8,8% + IBS 17,7%."""
    return AliquotaCBSIBS(
        fase=FaseReforma.PLENO,
        aliquota_cbs=Decimal("0.0880"),
        aliquota_ibs=Decimal("0.1770"),
        valid_from=date(2033, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 156-A §1º",
        algoritmo_versao="reforma.cbs-ibs.v1",
    )


class TestCalculoBasico2026:
    """Cálculo informacional 2026 — CBS 0,9% + IBS 0,1%."""

    def test_base_1000_brl(self) -> None:
        r = calcular_cbs_ibs(Decimal("1000.00"), _aliquota_2026())
        assert r.valor_cbs == Decimal("9.00")
        assert r.valor_ibs == Decimal("1.00")
        assert r.valor_total == Decimal("10.00")
        assert r.fase is FaseReforma.TESTE_2026
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_base_um_brl(self) -> None:
        # 1,00 × 0,9% = 0,009 → quantize 2 casas HALF_EVEN → 0,01? Banker's
        # arredonda 0,005 para par; aqui 0,0090 → 0,01 (nove é ímpar, mas
        # 0,009 está mais perto de 0,01 que de 0,00). Confirma na suite.
        r = calcular_cbs_ibs(Decimal("1.00"), _aliquota_2026())
        assert r.valor_cbs == Decimal("0.01")
        assert r.valor_ibs == Decimal("0.00")
        assert r.valor_total == Decimal("0.01")

    def test_base_zero(self) -> None:
        r = calcular_cbs_ibs(Decimal("0.00"), _aliquota_2026())
        assert r.valor_cbs == Decimal("0.00")
        assert r.valor_ibs == Decimal("0.00")
        assert r.valor_total == Decimal("0.00")
        # Observação obrigatória mesmo com base zero
        assert r.observacao_estimativa == OBSERVACAO_ESTIMATIVA

    def test_base_com_centavos(self) -> None:
        # 1234,56 × 0,9% = 11,11104 → 11,11 (HALF_EVEN; quarto dec é 1)
        # 1234,56 × 0,1% = 1,23456  → 1,23
        r = calcular_cbs_ibs(Decimal("1234.56"), _aliquota_2026())
        assert r.valor_cbs == Decimal("11.11")
        assert r.valor_ibs == Decimal("1.23")
        assert r.valor_total == Decimal("12.34")


class TestCalculoRegimePleno:
    """Cálculo no regime pleno — CBS 8,8% + IBS 17,7% (total 26,5%)."""

    def test_base_10000_brl(self) -> None:
        r = calcular_cbs_ibs(Decimal("10000.00"), _aliquota_pleno())
        assert r.valor_cbs == Decimal("880.00")
        assert r.valor_ibs == Decimal("1770.00")
        assert r.valor_total == Decimal("2650.00")
        assert r.fase is FaseReforma.PLENO

    def test_fonte_norma_preservada(self) -> None:
        r = calcular_cbs_ibs(Decimal("100.00"), _aliquota_pleno())
        assert "156-A" in r.fonte_norma


class TestQuantizacaoHalfEven:
    """ROUND_HALF_EVEN (banker's rounding) — exigido pelo §8.5 do Plano."""

    def test_centavo_par_arredonda_para_baixo(self) -> None:
        # 2,50 × 0,01 = 0,025 → quantize HALF_EVEN para 2 casas com
        # alíquota 1% → 0,02 (par mais próximo). Mas como temos 4 casas de
        # alíquota: 2,50 × 0,0100 = 0,0250 → 0,02 (banker's para par).
        aliquotas = AliquotaCBSIBS(
            fase=FaseReforma.TESTE_2026,
            aliquota_cbs=Decimal("0.0100"),
            aliquota_ibs=Decimal("0.0000"),
            valid_from=date(2026, 1, 1),
            valid_to=None,
            fonte_norma="teste",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
        r = calcular_cbs_ibs(Decimal("2.50"), aliquotas)
        assert r.valor_cbs == Decimal("0.02")

    def test_centavo_impar_arredonda_para_par(self) -> None:
        # 3,50 × 0,01 = 0,035 → banker's vai para par mais próximo 0,04
        aliquotas = AliquotaCBSIBS(
            fase=FaseReforma.TESTE_2026,
            aliquota_cbs=Decimal("0.0100"),
            aliquota_ibs=Decimal("0.0000"),
            valid_from=date(2026, 1, 1),
            valid_to=None,
            fonte_norma="teste",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
        r = calcular_cbs_ibs(Decimal("3.50"), aliquotas)
        assert r.valor_cbs == Decimal("0.04")


class TestValidacaoBase:
    """Princípio §8.6 — base inválida levanta exceção, nunca calcula errado."""

    def test_base_negativa_levanta(self) -> None:
        with pytest.raises(BaseCalculoInvalida, match="negativa"):
            calcular_cbs_ibs(Decimal("-1.00"), _aliquota_2026())

    def test_base_nan_levanta(self) -> None:
        with pytest.raises(BaseCalculoInvalida, match="finita"):
            calcular_cbs_ibs(Decimal("NaN"), _aliquota_2026())

    def test_base_tipo_errado_levanta(self) -> None:
        with pytest.raises(BaseCalculoInvalida, match="Decimal"):
            calcular_cbs_ibs(100.0, _aliquota_2026())  # type: ignore[arg-type]


class TestAliquotaForaDeRange:
    """Defesa em profundidade — alíquota fora de [0,1] levanta ValueError
    mesmo com seed corrompido (o CHECK no DB já deveria impedir).
    """

    def test_aliquota_cbs_negativa(self) -> None:
        bad = AliquotaCBSIBS(
            fase=FaseReforma.TESTE_2026,
            aliquota_cbs=Decimal("-0.01"),
            aliquota_ibs=Decimal("0.001"),
            valid_from=date(2026, 1, 1),
            valid_to=None,
            fonte_norma="teste",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
        with pytest.raises(ValueError, match="aliquota_cbs"):
            calcular_cbs_ibs(Decimal("100.00"), bad)

    def test_aliquota_ibs_maior_que_um(self) -> None:
        bad = AliquotaCBSIBS(
            fase=FaseReforma.PLENO,
            aliquota_cbs=Decimal("0.10"),
            aliquota_ibs=Decimal("1.10"),
            valid_from=date(2033, 1, 1),
            valid_to=None,
            fonte_norma="teste",
            algoritmo_versao="reforma.cbs-ibs.v1",
        )
        with pytest.raises(ValueError, match="aliquota_ibs"):
            calcular_cbs_ibs(Decimal("100.00"), bad)


class TestContratoDeResultado:
    """Princípio §8.12 — toda saída CBS/IBS é labelada estimativa."""

    def test_observacao_estimativa_obrigatoria(self) -> None:
        r = calcular_cbs_ibs(Decimal("1000.00"), _aliquota_2026())
        assert r.observacao_estimativa == OBSERVACAO_ESTIMATIVA
        assert "LC 214/2025" in r.observacao_estimativa
        assert "Estimativa" in r.observacao_estimativa

    def test_algoritmo_versao_constante(self) -> None:
        assert ALGORITMO_VERSAO == "reforma.cbs-ibs.v1"
        r = calcular_cbs_ibs(Decimal("100.00"), _aliquota_2026())
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_valor_total_eh_soma_das_parcelas(self) -> None:
        # Invariante: total = CBS + IBS (não recalcula da base × soma de alíquotas)
        r = calcular_cbs_ibs(Decimal("12345.67"), _aliquota_pleno())
        assert r.valor_total == r.valor_cbs + r.valor_ibs
