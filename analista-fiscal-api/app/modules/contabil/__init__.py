"""Módulo contábil (Sprint 9).

PR1: Plano de contas hierárquico (SCD Type 2) + lançamentos em partidas
dobradas com validação de invariante Σ D = Σ C.
PR2: Motor de lançamentos automáticos a partir de fatos (NF, transação,
depreciação, provisão).
PR3: Balancete + diário + razão + encerramento mensal/anual.

Princípio §8.8 — algoritmos contábeis são Python puro. LLM nunca escreve
fato contábil.
"""

from app.modules.contabil.partidas import (
    ALGORITMO_VERSAO,
    ContaView,
    PartidaIn,
    validar_partidas,
)

__all__ = ["ALGORITMO_VERSAO", "ContaView", "PartidaIn", "validar_partidas"]
