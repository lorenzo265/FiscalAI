"""Migração de escritório antigo — importador SPED histórico (Sprint 18).

Bounded context responsável por **carregar dados pré-existentes** quando uma
PME chega trazida de outro escritório contábil. Ingere arquivos SPED (ECD,
ECF, EFD-Contribuições, EFD ICMS-IPI) gerados pelo escritório anterior e
reconstrói o grafo contábil-fiscal histórico para que o dashboard, DRE, DFC
e demais relatórios já entreguem comparativos no primeiro acesso.

Princípios cravados:

* **§8.1 RLS multi-tenant** — toda escrita acontece dentro da sessão
  ``SET LOCAL app.tenant_id`` ativa.
* **§8.2 Fatos imutáveis** — re-import de mesmo arquivo (mesmo hash) devolve
  o ``lote_importacao`` anterior sem reprocessar; hash diferente cria novo
  lote e marca o ``arquivo_sped`` antigo como ``superseded_by``.
* **§8.8 LLM nunca escreve fatos** — pipeline 100% determinístico:
  parser puro → ``LancamentoCandidato`` → ``_persistir`` idempotente.
* **§8.9 Idempotência** — ``UNIQUE (origem_tipo, origem_id)`` em
  ``lancamento_contabil`` + ``UNIQUE (empresa_id, hash_arquivo)`` em
  ``lote_importacao`` garantem que re-execuções não duplicam.
* **§8.10 Observabilidade** — cada lote emite
  ``migracao.lote.iniciado/concluido/falhou`` em ``structlog``.
* **§8.12 Transmissão é ato consciente** — importador NÃO transmite nada;
  apenas reconstrói o histórico já transmitido pelo escritório antigo.
"""
