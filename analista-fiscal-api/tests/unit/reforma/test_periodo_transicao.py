"""Testes do cronograma da Reforma (Sprint 14 PR1)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.reforma.periodo_transicao import (
    INICIO_PLENO,
    INICIO_TESTE_2026,
    INICIO_TRANSICAO,
    FaseReforma,
    fase,
)
from app.shared.exceptions import PeriodoReformaNaoMapeado


class TestMapeamentoBasico:
    """Cada fase mapeada para a janela correta da LC 214/2025."""

    @pytest.mark.parametrize(
        "competencia",
        [
            date(2026, 1, 1),
            date(2026, 6, 15),
            date(2026, 12, 31),
        ],
    )
    def test_teste_2026(self, competencia: date) -> None:
        assert fase(competencia) is FaseReforma.TESTE_2026

    @pytest.mark.parametrize(
        "competencia",
        [
            date(2027, 1, 1),
            date(2029, 7, 15),
            date(2032, 12, 31),
        ],
    )
    def test_transicao(self, competencia: date) -> None:
        assert fase(competencia) is FaseReforma.TRANSICAO

    @pytest.mark.parametrize(
        "competencia",
        [
            date(2033, 1, 1),
            date(2040, 5, 22),
            date(2099, 12, 31),
        ],
    )
    def test_pleno(self, competencia: date) -> None:
        assert fase(competencia) is FaseReforma.PLENO


class TestBordasExatas:
    """Transições no primeiro dia de cada fase (princípio §8.3)."""

    def test_ultimo_dia_pre_reforma_levanta(self) -> None:
        with pytest.raises(PeriodoReformaNaoMapeado, match="2026"):
            fase(date(2025, 12, 31))

    def test_primeiro_dia_teste_2026(self) -> None:
        assert fase(INICIO_TESTE_2026) is FaseReforma.TESTE_2026

    def test_ultimo_dia_teste_2026(self) -> None:
        assert fase(date(2026, 12, 31)) is FaseReforma.TESTE_2026

    def test_primeiro_dia_transicao(self) -> None:
        assert fase(INICIO_TRANSICAO) is FaseReforma.TRANSICAO

    def test_ultimo_dia_transicao(self) -> None:
        assert fase(date(2032, 12, 31)) is FaseReforma.TRANSICAO

    def test_primeiro_dia_pleno(self) -> None:
        assert fase(INICIO_PLENO) is FaseReforma.PLENO


class TestPreReformaLevanta:
    """Períodos anteriores a 2026 não são mapeados (out-of-scope §8.11)."""

    def test_2024_levanta(self) -> None:
        with pytest.raises(PeriodoReformaNaoMapeado):
            fase(date(2024, 1, 1))

    def test_2025_levanta_mensagem_cita_norma(self) -> None:
        with pytest.raises(PeriodoReformaNaoMapeado, match="LC 214/2025"):
            fase(date(2025, 6, 1))
