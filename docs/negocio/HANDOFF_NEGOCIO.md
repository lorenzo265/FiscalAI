# HANDOFF — Negócio (Arkan)

Livro de passagem **append-only** da frota de business. Cada agente registra ao terminar:
**data · agente · o que fez · arquivos · próximo.**

Estrutura de `docs/negocio/`:
- `pesquisa/` — market-research (concorrência, ICP, mercado)
- `financeiro/` — pricing-cac-forecast (pricing, CAC/LTV, forecast)
- `compliance/` — compliance-legal-watch (digests de legislação)
- `conteudo/` — content-fiscal (material educacional)
- `clientes/` — customer-success (churn, health, onboarding)
- `analytics/` — product-analytics (adoção por segmento)

> Toda afirmação de mercado/legislação carrega **fonte + data**. Dados de uso simulados são **rotulados** como tais. A frota de business **propõe**; decisões de preço/produto/legislação são do humano.

---

## Registro

- **2026-06-07 · orquestrador · Lote 3 criado** — 6 agentes de business + esta estrutura. Nenhuma análise rodada ainda; aguardando a primeira tarefa (ex.: `/pulse-negocio`).
