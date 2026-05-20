# ADR 0003 — Estratégia de LLM em 3 camadas

## Status

accepted (2026-05-10)

## Contexto

O produto usa LLM para: (1) classificação de intent WhatsApp, (2) extração estruturada simples (foto de boleto → JSON), (3) síntese de respostas em linguagem natural, (4) raciocínio sobre intimações e-CAC e SPED. Cada caso tem perfil diferente de custo, latência e sensibilidade de dados (LGPD).

Premissa inviolável (§8.8 do Plano): **LLM nunca escreve fatos no banco.** Pipeline determinístico ingere/calcula; LLM só lê e cita.

## Decisão

Adotar arquitetura híbrida em **3 camadas**:

1. **Local (Ollama + Gemma 3 4B Q4_K_M)** — backup offline e privacy-first para dados sensíveis (CPF, valores). Embeddings via `nomic-embed-text` (grátis, 768-dim).
2. **Cloud econômico (Gemini 2.5 Flash Lite)** — classificação de intent, extração estruturada simples. $0.10/$0.40 por 1M tok.
3. **Cloud raciocínio (Gemini 2.5 Flash com fallback para Pro)** — síntese final de resposta WhatsApp/dashboard, análise de intimações. $0.30/$2.50 por 1M tok (cache hit: $0.03 = -90%).

**Cache de prompts obrigatório** — system prompt 7 dias, contexto de empresa 1h, RAG 5min.

## Consequências

**Positivas:**
- Custo controlado: ~R$300/mês para 100 empresas (com 80% cache hit).
- Privacy-first: dados sensíveis nunca saem do servidor.
- Resiliência: queda de Gemini não derruba o produto; Ollama assume.
- Cada chamada vai para o modelo de menor custo capaz de resolver.

**Negativas:**
- Roteamento entre camadas adiciona complexidade — exige `LLMClient` unificado e política de roteamento clara.
- Gemma 3 4B é inferior ao Gemini Flash em PT-BR fiscal — usar só onde a tarefa for simples ou os dados forem sensíveis demais.
- Hardware com GPU (RTX 4090 / A40) para Ollama em prod.

## Alternativas consideradas

- **Claude / GPT em produção** — caro demais para o volume (rejeitado em §3.6).
- **Free tier Gemini com dados reais** — Google treina com isso, viola LGPD.
- **Apenas Ollama local** — qualidade insuficiente para síntese e raciocínio em PT-BR fiscal.
- **Apenas Gemini cloud** — perde resiliência e privacy-first; custo cresce linearmente.

## Referências

- `PlanoBackend.md` §2.2, §3.3, §6, §8.8
- Gemini API pricing: https://ai.google.dev/pricing
- Ollama: https://ollama.com/
