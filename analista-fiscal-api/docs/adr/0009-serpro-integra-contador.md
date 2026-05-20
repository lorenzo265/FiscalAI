# ADR 0009 — Camada federal: SERPRO Integra Contador

## Status

accepted (2026-05-10)

## Contexto

Para Simples Nacional, o produto precisa transmitir PGDAS-D, gerar DAS, consultar e-CAC, transmitir DCTFWeb, consultar Sicalc. Há três caminhos: scraping direto dos portais RFB (frágil, ilegal sob certas óticas, depende de CAPTCHA), terceirizar para um BPO (caro, lento), ou usar a plataforma oficial.

## Decisão

Adotar **SERPRO Integra Contador** como camada federal oficial. 27 serviços em 7 APIs (PGDAS-D, DCTFWeb, DARF, DAS, e-CAC, Procurações, Sicalc). Custo: ~R$0,96 por emissão completa de guia (3 chamadas). Requer certificado e-CNPJ por cliente.

Scraping fica **somente como último recurso** para rotas que SERPRO não cobrir — e mesmo assim exige aprovação explícita em ADR específico.

## Consequências

**Positivas:**
- Oficial e estável — RFB+SERPRO mantêm SLA, sem risco de quebra por mudança de UI.
- Cobertura completa do Simples Nacional federal.
- Custo previsível por chamada.
- Idempotência nativa via `idempotency_key`.

**Negativas:**
- Cada cliente precisa cadastrar certificado A1 (.pfx) — fricção de onboarding. Mitigação: assistente in-app com vídeo + suporte WhatsApp.
- Throttling SERPRO no dia 20 (vencimento DAS) — distribuir transmissão via Celery countdown nos 18–19.
- Custo unitário relevante em escala. Mitigação: cache de consultas, repassar custo no plano.

## Alternativas consideradas

- **Scraping direto** — frágil, depende de CAPTCHA, risco jurídico, alta manutenção.
- **BPO terceirizado** — lento, caro, sem API real.
- **Dispensar cobertura federal** — inviável; é o coração do produto para SN.

## Referências

- `PlanoBackend.md` §2.1, §7
- SERPRO Integra Contador: https://apicenter.estaleiro.serpro.gov.br/documentacao/api-integra-contador/
