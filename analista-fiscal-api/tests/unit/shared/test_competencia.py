"""Unit tests para o parsing robusto de competência mensal (AAAA-MM).

Regressão: entrada malformada (mês 00/13, ano 0000, formato errado) deve virar
``CompetenciaInvalida`` (HTTP 422), nunca propagar ``ValueError`` → 500.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.shared.competencia import parse_competencia_mensal
from app.shared.exceptions import CompetenciaInvalida


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("2026-01", date(2026, 1, 1)),
        ("2026-12", date(2026, 12, 1)),
        ("2026-04", date(2026, 4, 1)),
        ("0001-01", date(1, 1, 1)),
        ("9999-12", date(9999, 12, 1)),
    ],
)
def test_competencia_valida(entrada: str, esperado: date) -> None:
    assert parse_competencia_mensal(entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        "2026-13",  # mês fora de 1..12
        "2026-00",  # mês zero
        "2026-99",
        "0000-01",  # ano 0 estoura ValueError no date()
    ],
)
def test_mes_ou_ano_invalido_vira_422(entrada: str) -> None:
    with pytest.raises(CompetenciaInvalida) as exc:
        parse_competencia_mensal(entrada)
    assert exc.value.http_status == 422
    assert exc.value.codigo == "CompetenciaInvalida"


@pytest.mark.parametrize(
    "entrada",
    [
        "",
        "2026",
        "2026-1",  # mês com 1 dígito
        "26-01",  # ano com 2 dígitos
        "2026-01-01",  # dia sobrando
        "2026/01",
        "abc-de",
        "  2026-01  ",  # espaços não são tolerados
    ],
)
def test_formato_invalido_vira_422(entrada: str) -> None:
    with pytest.raises(CompetenciaInvalida) as exc:
        parse_competencia_mensal(entrada)
    assert exc.value.http_status == 422
