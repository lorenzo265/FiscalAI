"""Provisões trabalhistas mensais (Sprint 8 PR2).

Pipeline determinístico (§8.8 — LLM nunca escreve fatos):

  1. Cliente informa ``folha_mes_total`` (modo agregado MVP).
  2. ``calcula_provisao.calcular_provisoes`` emite 6 linhas determinísticas:
       ferias = folha/12 + 1/3 sobre o 1/12 (constitucional, art. 7º XVII CF)
       13_salario = folha/12 (art. 7º VIII CF, Lei 4.090/1962)
       inss_ferias = 20% × ferias_base (Lei 8.212/1991 art. 22 I — patronal)
       inss_13     = 20% × 13_base
       fgts_ferias = 8%  × ferias_base (Lei 8.036/1990 art. 15)
       fgts_13     = 8%  × 13_base
  3. SN/MEI: INSS patronal NÃO se aplica (está dentro do DAS, LC 123/2006 art. 13).
  4. ``ProvisoesService.gerar_provisao_mensal`` persiste idempotente via UNIQUE
     parcial (empresa, competencia, tipo, funcionario_id IS NULL).
"""

from app.modules.provisoes.calcula_provisao import (
    ALGORITMO_VERSAO,
    LinhaProvisao,
    ResultadoProvisoes,
    calcular_provisoes,
    inss_patronal_aplicavel,
)

__all__ = [
    "ALGORITMO_VERSAO",
    "LinhaProvisao",
    "ResultadoProvisoes",
    "calcular_provisoes",
    "inss_patronal_aplicavel",
]
