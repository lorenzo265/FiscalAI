# ADR 0001 — Framework web: FastAPI

## Status

accepted (2026-05-10)

## Contexto

Precisamos escolher um framework web Python async para o backend do Analista Fiscal. Os candidatos sérios em 2026 são FastAPI 0.115+ e Litestar 2.x. O backend tem características específicas:

- Múltiplas integrações maduras (Focus NFe, SERPRO, Pluggy, Meta WhatsApp) — precisamos de bibliotecas estáveis e exemplos prontos.
- Alta carga de I/O (HTTP externo + DB + LLM), pouca CPU bruta — performance puramente síncrona não é o gargalo.
- Equipe pequena (1 senior + 1 mid) e mercado de hiring brasileiro pendente para FastAPI.
- Espelhamento de schemas com o frontend Next.js via Pydantic ↔ Zod.

## Decisão

Adotar **FastAPI 0.115+** com Uvicorn como ASGI server.

## Consequências

**Positivas:**
- Pydantic v2 nativo — espelha o Zod do frontend sem fricção.
- OpenAPI gerado automaticamente — base do `/docs/api/`.
- Ecossistema mais maduro: `fastapi-users`, `slowapi`, `prometheus-fastapi-instrumentator`, exemplos de SQLAlchemy 2.0 async em produção.
- Hiring no Brasil mais simples — FastAPI tem 4.5M downloads/dia e está em produção em OpenAI, Anthropic, Microsoft.

**Negativas:**
- Litestar é 10–20× mais rápido em payloads grandes graças ao msgspec — abrimos mão dessa performance bruta. Mitigação: nosso gargalo é I/O, não serialização.
- Dependency injection do FastAPI tem custo de runtime maior que o do Litestar. Mitigação: aceitar; perfilar antes de otimizar.

## Alternativas consideradas

- **Litestar 2.x** — superior tecnicamente em performance, msgspec, DI mais limpo. Rejeitado pelo risco de hiring + ecossistema menor para integrações brasileiras.
- **Django + DRF** — descartado: síncrono por padrão, schemas duplicados, fricção com SQLAlchemy 2.0 async.
- **Flask** — descartado: sem async first-class, OpenAPI manual.

## Referências

- `PlanoBackend.md` §3.1 e §3.6
- FastAPI docs: https://fastapi.tiangolo.com/
- Comparação Medium / uvik / byteiota (2026)
