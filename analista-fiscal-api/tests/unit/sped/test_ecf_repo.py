"""Testes dos repositórios ECF (Sprint 16 PR2) — helpers puros."""

from __future__ import annotations

from datetime import date

from app.modules.sped.ecf.repo import _meses_do_trimestre, _numero_trimestre


class TestNumeroTrimestre:
    def test_janeiro_eh_t1(self) -> None:
        assert _numero_trimestre(date(2025, 1, 1)) == 1

    def test_marco_eh_t1(self) -> None:
        assert _numero_trimestre(date(2025, 3, 1)) == 1

    def test_abril_eh_t2(self) -> None:
        assert _numero_trimestre(date(2025, 4, 1)) == 2

    def test_julho_eh_t3(self) -> None:
        assert _numero_trimestre(date(2025, 7, 1)) == 3

    def test_outubro_eh_t4(self) -> None:
        assert _numero_trimestre(date(2025, 10, 1)) == 4

    def test_dezembro_eh_t4(self) -> None:
        assert _numero_trimestre(date(2025, 12, 1)) == 4


class TestMesesDoTrimestre:
    def test_t1_jan_fev_mar(self) -> None:
        assert _meses_do_trimestre(2025, 1) == [
            date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)
        ]

    def test_t2_abr_mai_jun(self) -> None:
        assert _meses_do_trimestre(2025, 2) == [
            date(2025, 4, 1), date(2025, 5, 1), date(2025, 6, 1)
        ]

    def test_t3_jul_ago_set(self) -> None:
        assert _meses_do_trimestre(2025, 3) == [
            date(2025, 7, 1), date(2025, 8, 1), date(2025, 9, 1)
        ]

    def test_t4_out_nov_dez(self) -> None:
        assert _meses_do_trimestre(2025, 4) == [
            date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)
        ]
