"""Testes do helper ``popular_cbs_ibs_informacional`` (Sprint 14 PR2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.reforma.calcula_cbs_ibs import (
    ALGORITMO_VERSAO,
    AliquotaCBSIBS,
)
from app.modules.reforma.integrar_documento import (
    popular_cbs_ibs_informacional,
)
from app.modules.reforma.periodo_transicao import FaseReforma
from app.shared.exceptions import BaseCalculoInvalida


def _aliquota_2026() -> AliquotaCBSIBS:
    return AliquotaCBSIBS(
        fase=FaseReforma.TESTE_2026,
        aliquota_cbs=Decimal("0.0090"),
        aliquota_ibs=Decimal("0.0010"),
        valid_from=date(2026, 1, 1),
        valid_to=None,
        fonte_norma="LC 214/2025 art. 348 §3º",
        algoritmo_versao=ALGORITMO_VERSAO,
    )


def _doc(
    *,
    valor_total: str = "1000.00",
    valor_cbs: str | None = None,
    valor_ibs: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        valor_total=Decimal(valor_total),
        valor_cbs=Decimal(valor_cbs) if valor_cbs is not None else None,
        valor_ibs=Decimal(valor_ibs) if valor_ibs is not None else None,
    )


class TestCalculoInformacional:
    """NF sem extensão IBSCBSTot recebe CBS/IBS calculados."""

    def test_nf_sem_cbs_ibs_calcula(self) -> None:
        r = popular_cbs_ibs_informacional(_doc(), _aliquota_2026())
        assert r.calculou is True
        assert r.valor_cbs == Decimal("9.00")
        assert r.valor_ibs == Decimal("1.00")
        assert r.base_calculo == Decimal("1000.00")
        assert r.algoritmo_versao == ALGORITMO_VERSAO

    def test_observacao_estimativa_obrigatoria(self) -> None:
        r = popular_cbs_ibs_informacional(_doc(), _aliquota_2026())
        assert "LC 214/2025" in r.observacao
        assert "Estimativa" in r.observacao

    def test_base_zero_calcula_zero(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_total="0.00"), _aliquota_2026()
        )
        assert r.calculou is True
        assert r.valor_cbs == Decimal("0.00")
        assert r.valor_ibs == Decimal("0.00")


class TestIdempotencia:
    """Princípio §8.9 — se já tem valores, no-op."""

    def test_doc_ja_populado_nao_recalcula(self) -> None:
        r = popular_cbs_ibs_informacional(
            _doc(valor_cbs="42.00", valor_ibs="7.00"),
            _aliquota_2026(),
        )
        assert r.calculou is False
        assert r.valor_cbs == Decimal("42.00")
        assert r.valor_ibs == Decimal("7.00")
        assert "já presentes" in r.observacao

    def test_doc_parcial_recalcula_ambos(self) -> None:
        """Se só um dos dois está populado, recalcula ambos (consistência)."""
        # Apenas valor_cbs vindo do XML, valor_ibs = None → recalcula tudo
        r = popular_cbs_ibs_informacional(
            _doc(valor_cbs="9.00"),  # valor_ibs ausente
            _aliquota_2026(),
        )
        assert r.calculou is True
        # Recalcula informacional sobre valor_total (não preserva o cbs parcial)
        assert r.valor_cbs == Decimal("9.00")
        assert r.valor_ibs == Decimal("1.00")


class TestPropagacaoExcecao:
    """Defesa em profundidade — base inválida propaga BaseCalculoInvalida."""

    def test_valor_total_negativo_propaga(self) -> None:
        with pytest.raises(BaseCalculoInvalida):
            popular_cbs_ibs_informacional(
                _doc(valor_total="-1.00"), _aliquota_2026()
            )
