"""Imobilizado + depreciação automática (Sprint 8 PR1, IN SRF 162/1998).

Pipeline determinístico (§8.8 — LLM nunca escreve fatos):
  1. ``cadastrar_bem`` resolve taxa via :class:`TabelaDepreciacaoRfb` se o
     usuário não informar — usando a taxa vigente na ``data_aquisicao``.
  2. ``gerar_depreciacao_mensal(competencia)`` roda o algoritmo linear
     para cada bem ativo da empresa.
  3. Worker Celery (skeleton) dispara mensalmente — UNIQUE garante idempotência.
"""

from app.modules.imobilizado.calcula_depreciacao import (
    ALGORITMO_VERSAO,
    ResultadoDepreciacao,
    calcular_parcela_mensal,
    deve_depreciar_competencia,
)

__all__ = [
    "ALGORITMO_VERSAO",
    "ResultadoDepreciacao",
    "calcular_parcela_mensal",
    "deve_depreciar_competencia",
]
