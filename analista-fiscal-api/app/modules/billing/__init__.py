"""Billing — assinatura SaaS do Arkan (Marco 2 produção).

Bounded context da cobrança recorrente da plataforma (assinatura do cliente
PME ao Arkan — distinto do marketplace, que cobra consultas a contadores).

Pipeline: catálogo de planos (``planos.py``, mock versionado) → ``service``
cria assinatura em trial + sessão de checkout via ``provider`` (Stripe real
atrás de env, ``_FakeBillingProvider`` em dev/teste) → webhook do Stripe
sincroniza status (ativa/inadimplente/cancelada) de forma idempotente.

Conexão com o gateway é atrás de ``STRIPE_SECRET_KEY``/``STRIPE_WEBHOOK_SECRET``
— sem chave, cai no fake (dev). Nunca há mock em produção: a credencial liga
o ``StripeProvider`` real.
"""
