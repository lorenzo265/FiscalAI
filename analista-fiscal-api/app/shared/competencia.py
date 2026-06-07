"""Parsing robusto de competência fiscal mensal (``AAAA-MM``).

Helper compartilhado pelos routers que recebem competência na rota ou na
query-string. Centraliza a validação para que entrada malformada vire
HTTP 422 (``CompetenciaInvalida``) em vez de propagar um ``ValueError`` —
que o handler genérico transformaria em 500.
"""

from __future__ import annotations

import re
from datetime import date

from app.shared.exceptions import CompetenciaInvalida

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def parse_competencia_mensal(competencia: str) -> date:
    """Converte ``AAAA-MM`` no primeiro dia do mês.

    Levanta ``CompetenciaInvalida`` (HTTP 422) para formato inválido, mês fora
    de ``01`` a ``12`` ou ano fora de ``0001`` a ``9999``. Nunca propaga
    ``ValueError``.
    """
    if not _COMPETENCIA_RE.match(competencia):
        raise CompetenciaInvalida(
            f"Competência inválida: '{competencia}'. Use o formato AAAA-MM."
        )
    ano, mes = competencia.split("-")
    try:
        return date(int(ano), int(mes), 1)
    except ValueError as exc:
        raise CompetenciaInvalida(
            f"Competência inválida: '{competencia}'. O mês deve estar entre 01 e 12."
        ) from exc
