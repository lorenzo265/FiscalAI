# ADR 0006 — Emissão DFe: Focus NFe (primário) + PlugNotas (backup)

## Status

accepted (2026-05-10)

## Contexto

Precisamos emitir e consultar NF-e, NFS-e (padrão nacional ADN obrigatório desde 01/01/2026), NFC-e, CT-e, MDF-e e futuramente NFCom/DCe. Três caminhos: integração direta com cada SEFAZ + 5.500+ municípios (inviável), Nuvem Fiscal (desativada em 31/07/2026), ou um agregador SaaS.

## Decisão

Adotar **Focus NFe** como provider primário e **PlugNotas (TecnoSpeed)** como backup contingencial.

- Focus NFe cobre 1.200+ municípios para NFS-e; novos municípios em 15 dias por taxa fixa de R$199.
- API REST moderna, sem contrato mínimo, sem setup.
- Suporta todos os DFe relevantes para o escopo do produto.

PlugNotas mantido como contingência, com cliente abstrato para troca em ≤1 dia se Focus tiver incidente prolongado.

## Consequências

**Positivas:**
- Cobertura nacional sem precisar manter integração SEFAZ direta.
- Custo previsível por DFe.
- Tempo de implementação curto (Sprint 5).
- Webhooks para autorização/cancelamento — evita polling.

**Negativas:**
- Dependência de terceiro para fluxo crítico do cliente. Mitigação: backup PlugNotas + circuit breaker + retry com `idempotency_key`.
- Custo por DFe em escala alta pode justificar trazer NF-e direto. Decisão: revisitar em 1k+ empresas pagantes.

## Alternativas consideradas

- **Nuvem Fiscal** — descartado: serviço será desativado em 31/07/2026.
- **PlugNotas como primário** — equipe especializada e forte, mas Focus NFe tem cobertura municipal levemente melhor para nosso target inicial (PMEs em capitais e regiões metropolitanas).
- **Integração direta SEFAZ + 5.500 municípios** — inviável para um time de 2.

## Referências

- `PlanoBackend.md` §2.1, §3.4, §7
- Focus NFe: https://focusnfe.com.br/doc/
- PlugNotas: https://plugnotas.com.br/
