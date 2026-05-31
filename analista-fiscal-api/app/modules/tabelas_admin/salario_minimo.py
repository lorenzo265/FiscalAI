"""Salário mínimo nacional por ano-calendário (referência para validar
a primeira faixa de INSS/IRRF na entrada do painel admin).

Sprint 19.5 PR1. Pequena tabela seed manual mantida no código — não vale
criar SCD própria para 1 valor por ano que muda 1× ao ano. Quando o admin
postar tabela INSS/IRRF para um ano novo, **precisa atualizar este dict
no mesmo PR**: se o ano não está coberto, levanta ``ValueError`` claro
(o validador captura e devolve 422).

Fonte: Decreto anual de fixação do salário mínimo (entra em vigor 1º janeiro).

  * 2022 — Decreto 10.926/2021 — R$ 1.212,00
  * 2023 — Decreto 11.322/2022 (+ MP 1.172/2023) — R$ 1.320,00
  * 2024 — Decreto 11.864/2023 — R$ 1.412,00
  * 2025 — Decreto 12.342/2024 — R$ 1.518,00
  * 2026 — placeholder até decreto publicado: usar 2025 + reajuste mínimo
    legal (INPC + 2,5% real) para travar validação acima do INSS faixa 1
    sem inventar valor. Atualizar quando decreto sair em dezembro.

Não é tabela tributária stricto sensu — é referência cruzada usada apenas
para validar plausibilidade do INSS faixa 1 ("primeira faixa precisa cobrir
quem ganha 1 salário mínimo"). Mudança aqui não dispara recálculo fiscal.
"""

from __future__ import annotations

from decimal import Decimal


_SALARIO_MINIMO_POR_ANO: dict[int, Decimal] = {
    2022: Decimal("1212.00"),
    2023: Decimal("1320.00"),
    2024: Decimal("1412.00"),
    2025: Decimal("1518.00"),
    # Placeholder conservador para 2026 — decreto sai em dezembro/2025.
    # Sai do reajuste mínimo legal aplicado sobre 2025 (INPC ~3,5% + 2,5% real).
    # Substituir pelo valor oficial assim que publicado, no mesmo PR que
    # postar a tabela INSS 2026.
    2026: Decimal("1620.00"),
}


def salario_minimo_oficial(ano: int) -> Decimal:
    """Retorna o salário mínimo do ano-calendário ou levanta ``ValueError``.

    O caller (validador da Sprint 19.5) traduz o ValueError em
    ``VigenciaTributariaInvalida`` com mensagem específica, mantendo a
    função pura (golden-testable).
    """
    valor = _SALARIO_MINIMO_POR_ANO.get(ano)
    if valor is None:
        anos_cobertos = sorted(_SALARIO_MINIMO_POR_ANO.keys())
        raise ValueError(
            f"Salário mínimo do ano {ano} não cadastrado em "
            f"app/modules/tabelas_admin/salario_minimo.py. "
            f"Anos cobertos: {anos_cobertos}. Atualize o dict antes de "
            f"postar tabela tributária para este ano."
        )
    return valor


__all__ = ["salario_minimo_oficial"]
