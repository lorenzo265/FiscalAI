"""Reforma Tributária — CBS/IBS informacional (Sprint 14).

Bounded context da Reforma Tributária (LC 214/2025 + PLP 68/2024 em
tramitação). Camada 1 (determinística) — algoritmos puros + lookup SCD.

Princípios aplicados:

  * §8.3 (SCD Type 2) — alíquotas vivem em ``aliquota_cbs_ibs`` versionada
    por ``valid_from``/``valid_to`` com trigger de fechamento automático.
  * §8.4 (golden tests) — algoritmo ``calcula_cbs_ibs`` tem golden suite.
  * §8.8 (LLM não escreve fatos) — toda escrita em ``documento_fiscal``
    passa por pipeline determinístico (``integrar_documento.popular_*``).
  * §8.12 (estimativa labelada) — toda saída de schema carrega
    ``observacao_estimativa`` citando LC 214/2025.

Conteúdo desta sprint:

  * PR1: ``periodo_transicao``, ``calcula_cbs_ibs``, ``repo``
  * PR2: ``integrar_documento`` + parser NF-e estendido (em ``ingestao/``)
  * PR3: ``simulador``, ``service``, ``router``, ``schemas``
"""
