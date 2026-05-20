"""Conciliação banco × NF (Sprint 7 PR3).

Algoritmo determinístico que pontua pares (``TransacaoBancaria``,
``DocumentoFiscal``) por:

* Sinal compatível obrigatório (entrada/saída × direção da NF).
* Valor exato / próximo.
* Data ±1 / ±5 dias.
* CNPJ da contraparte presente na descrição da transação.

Score ≥ 80 → AUTO (aplicado sem revisão). 50-79 → SUGERIDA. <50 → ignorado.

Princípio §8.8 — LLM nunca escreve fatos. Aqui é puro Python.
"""

from app.modules.conciliacao.algoritmo import (
    ALGORITMO_VERSAO,
    ScoreMatch,
    pontuar_match,
)

__all__ = ["ALGORITMO_VERSAO", "ScoreMatch", "pontuar_match"]
