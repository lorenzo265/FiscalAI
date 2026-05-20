# ADR 0002 — Vector store: pgvector + pgvectorscale

## Status

accepted (2026-05-10)

## Contexto

A Sprint 4 introduz memória + RAG por empresa: cada cliente terá ~1k–10k fatos vetorizados (embeddings `nomic-embed-text`, 768-dim). No longo prazo (~5k empresas), isso projeta ~50M vetores teóricos, mas particionados por tenant via RLS — cada query toca no máximo dezenas de milhares de vetores.

## Decisão

Usar **pgvector 0.7+** dentro do mesmo Postgres 16. Quando a contagem por tenant ultrapassar ~2M vetores, ativar **pgvectorscale 0.4+** com índice StreamingDiskANN.

## Consequências

**Positivas:**
- Zero infra adicional — mesmo backup, mesmo monitoramento, mesma transação ACID com fatos fiscais.
- RLS Postgres já isola por tenant nativamente; vector store separado exigiria reimplementar isolamento.
- Custo zero de licença/serviço.
- Benchmark Tiger Data: pgvector entrega 471 QPS @ 99% recall em 50M vetores 768-dim — suficiente para nosso volume.

**Negativas:**
- Em escala extrema (>50M vetores ativos), pgvector tende a perder para Qdrant em throughput. Mitigação: revisitar quando virar problema real, não preventivo.
- HNSW em pgvector tem maior tempo de build de índice que Qdrant. Mitigação: índices construídos em background, não bloqueante.

## Alternativas consideradas

- **Qdrant** — superior em throughput puro de vetor, mas exige novo serviço, novo backup, novo modelo de isolamento por tenant.
- **Pinecone** — managed, caro, viola "dados em sa-east-1/southamerica-east1" (LGPD).
- **Weaviate** — adicional infra, sem ganho claro frente a pgvector na nossa escala.

## Referências

- `PlanoBackend.md` §2.4 e §3.2
- pgvector docs: https://github.com/pgvector/pgvector
- pgvectorscale + Tiger Data benchmark
