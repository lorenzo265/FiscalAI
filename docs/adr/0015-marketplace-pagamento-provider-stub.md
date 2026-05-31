---
tags: [adr, marketplace, pagamento, sprint-13, fase-2]
fonte: "[[PlanoBackend]] §10 (marketplace) + Sprint 13 PR3"
status: accepted
data: 2026-05-21
---

# ADR 0015 — Marketplace de pagamentos: stub idempotente no MVP, provider real em sprint dedicada

## Status

accepted (2026-05-21)

## Contexto

A Sprint 13 PR3 fecha o ciclo de vida da consulta do marketplace com o ato de pagamento (§10.2 do Plano: "8. Pagamento: cliente paga via Pix/cartão; plataforma retém 20-30%"). O Plano lista as faixas de comissão por categoria (§10.3) mas **não crava** o provider de pagamento — deixa "Pix/cartão" como capacidade desejada.

Opções avaliadas:

1. **Stripe Connect** — split payment nativo (plataforma + parceiro), KYC integrado, webhooks HMAC. Custo: 3,99% + R$0,39 por transação cartão (no Brasil); Pix com custo mais baixo (~R$0,99). Requer cadastro PJ na Stripe + onboarding de cada contador parceiro como "Connected Account" (KYC documental).
2. **Pagar.me / Mercado Pago / Asaas** — provedores nacionais com split nativo, custo similar (~3,5–4,5%), Pix mais barato (~R$0,69), KYC mais simples.
3. **Pix Cobrança v2 direto via PSP** — emite QR Code/copia-cola, sem cartão. Custo baixíssimo (~R$0,10), mas não cobre cartão e o split entre plataforma/parceiro é manual (reconciliação posterior).
4. **Stub idempotente** — interface `PaymentProvider` + impl `_FakeProvider` que persiste cobrança em `cobranca_consulta`, gera URL determinística (`https://fiscalai.local/checkout/<consulta_id>`) e expõe webhook autenticado por payload (em prod: HMAC do provider). Provider real entra depois.

## Decisão

Adotar a **opção 4 (stub idempotente)** para a Sprint 13 PR3. O schema completo (`cobranca_consulta` com `idempotency_key UNIQUE`, RLS por tenant, status enum, audit timestamps) já está cravado no DB (migration `0033`). O ``PaymentProvider`` é Protocol — basta injetar outra classe (`StripeConnectProvider` / `PagarmeProvider`) para ativar provider real, sem refator de service ou schema.

Provider real fica para sprint dedicada (provavelmente Sprint 13.1 ou Sprint 14 PR isolado) — escolha entre Stripe Connect vs Pagar.me será feita com base nos primeiros 10 pagantes reais (Marco Fase 2: 50). Critérios de decisão documentados em `docs/pendencias/marketplace-pagamento-real.md`.

## Consequências

**Positivas:**

- MVP fecha o ciclo end-to-end sem dependência externa nem KYC de parceiros. Suite continua determinística e rápida (sem mock de Stripe).
- Schema +RLS +idempotência +máquina de estado ficam validados em produção desde o dia 1. Quando o provider real entrar, o trabalho é só a impl do Protocol + endpoint webhook com assinatura HMAC.
- Permite cobrar **manualmente** os primeiros pagantes (Pix bancário direto + marcar `paga_em` via endpoint admin) enquanto o provider real não está ativo — sem bloquear receita.

**Negativas:**

- Cliente não consegue pagar de fato pela plataforma na Sprint 13 — depende de comunicação out-of-band para os primeiros pagantes. Mitigação: o número alvo (10 consultas processadas no marketplace pela Fase 2) é pequeno o suficiente para tratamento manual.
- Stub não exercita assinatura HMAC do provider — quando entrar, precisa de testes integration cobrindo replay attacks e signature spoofing.

## Critérios para ativar provider real

Disparar a sprint de ativação quando UM dos abaixo for verdade:

- ≥10 pagantes reais aceitos no marketplace (volume justifica automação).
- ≥3 contadores parceiros aprovados com NDA assinado (existem partes para receber split).
- Demanda explícita do beta-tester para "quero pagar com cartão pelo app" (aceitação manual incomoda).

A escolha entre Stripe Connect vs Pagar.me considerará: custo total da transação no perfil esperado (ticket médio R$200-2500), latência de onboarding KYC do parceiro, qualidade da documentação do split, suporte em português.

## Relacionado

- [[principios/09-idempotencia]] — `idempotency_key UNIQUE` cravada em `cobranca_consulta`.
- [[principios/07-lgpd-first]] — webhook não acessa PII; só `provider_externo_id` + `status`.
- [[principios/12-transmissao-consciente]] — cliente faz POST explícito em `/pagar` (ato consciente, não automático).
- [[pendencias/marketplace-pagamento-real]] — rastreamento da ativação.
- [[sprints/sprint-13-marketplace]] — sprint que originou a decisão.
