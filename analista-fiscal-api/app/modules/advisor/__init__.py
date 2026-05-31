"""AI Advisor proativo — Sprint 15.

Bounded context que detecta saltos atípicos em apurações fiscais e
gera alertas/sugestões proativas (anomaly detection, Fator R, digest
semanal WhatsApp). Camada 1 (determinística) — algoritmos puros sobre
séries temporais de ``apuracao_fiscal``; Camada 3 (LLM cloud) entra só
na redação final do digest semanal (PR3).

Princípios aplicados:

  * §8.4 (golden tests) — algoritmo ``calcula_anomalias`` tem suite golden.
  * §8.8 (LLM não escreve fatos) — anomaly detection é 100% determinístico.
  * §8.9 (idempotência) — UNIQUE parcial em ``anomalia_fiscal`` evita duplo
    alerta; re-detecção produz nova linha + ``supersedes`` da antiga.
  * §8.10 (observabilidade) — ``algoritmo_versao`` persistido para auditoria.
  * §8.12 (estimativa labelada) — toda mensagem cita método, amostra e fonte.

Conteúdo desta sprint:

  * PR1: ``calcula_anomalias``, ``repo``, ``service``, ``router`` — anomaly
         detection + endpoints + worker Celery diário.
  * PR2: ``simula_fator_r``, ``sugestoes_otimizacao`` — Fator R + sugestões.
  * PR3: ``gera_digest_semanal``, integração WhatsApp — digest proativo.
"""
