---
tags: [pendencia, marketplace, pagamento, sprint-13, fase-2]
fonte: "[[decisoes/adr-0015-marketplace-pagamento-provider-stub]]"
status: aberta
introduzida_em: 2026-05-21
sprint_origem: 13
---

# Pendência consciente — Provider de pagamento real (Stripe Connect / Pagar.me)

## O que falta

Sprint 13 PR3 entregou o ciclo de pagamento end-to-end via stub (`_FakeProvider` em `app/modules/marketplace/pagamento.py`). Provider real ainda não está plugado.

Fica para sprint dedicada:

1. **Implementação do Protocol `PaymentProvider`** com cliente do provider escolhido (Stripe Connect ou Pagar.me ou Pix Cobrança v2).
2. **Onboarding KYC do parceiro** — quando aprovar parceiro, gerar conta no provider e armazenar `provider_connect_id` em `contador_parceiro` (coluna nova).
3. **Webhook com assinatura HMAC** — endpoint `POST /v1/webhooks/pagamento` hoje confia no payload; trocar para validar `X-Stripe-Signature` ou equivalente.
4. **Split payment** — plataforma retém `comissao_plataforma` e repassa `valor - comissão` para o parceiro automaticamente.
5. **Reconciliação financeira** — relatório mensal de repasses vs. comissões retidas; cruzamento com `cobranca_consulta`.

## Critérios para disparar a sprint

Ver ADR 0015 §"Critérios para ativar provider real". Resumo:

- ≥10 pagantes reais aceitos no marketplace, OU
- ≥3 contadores parceiros aprovados com NDA assinado, OU
- Demanda explícita de beta-tester por cartão pelo app.

## Como mitigar enquanto não está pronto

Os primeiros pagantes podem fechar manualmente: Pix bancário direto entre cliente e contador + um endpoint admin para marcar `cobranca_consulta.status = 'paga'` (ainda não implementado — adicionar quando for necessário).

## Relacionado

- [[decisoes/adr-0015-marketplace-pagamento-provider-stub]]
- [[sprints/sprint-13-marketplace]]
- [[principios/09-idempotencia]] — `idempotency_key UNIQUE` já garantida no schema.
- [[modulos/marketplace]] — bounded context.
