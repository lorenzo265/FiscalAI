---
tags: [sprint, marketplace, fase-2, proxima]
fonte: "[[PlanoBackend]] §10, §5.8, §11"
status: proxima
fase: 2
marco: "50 pagantes + MRR R$10k+"
---

# Sprint 13 — Marketplace de contadores + primeiros pagantes

> **Próxima sprint a executar.** Fonte: [[PlanoBackend]] §10 (marketplace), §5.8 (modelagem), §11 (roadmap).

## Objetivo

Tabelas `contador_parceiro` + `consulta_marketplace`, fluxo de matching, pagamento via Pix/cartão e dashboard do parceiro.

## Marco Fase 2

- **50 empresas pagantes**
- **MRR R$10k+**
- Churn mensal <5%, onboarding <2h, CAC <R$500
- ≥10 consultas processadas no marketplace
- ≥5 contadores parceiros ativos

## Por que marketplace (não contadores internos)

| Modelo | Margem | Escalabilidade | Risco regulatório |
|---|---|---|---|
| Contadores internos | <40% | Linear | Alto |
| **Marketplace** | **80%+** | **Não-linear** | **Baixo** |

Decisão em [[decisoes/adr-001-postgres-rls|ADRs]] (ADR-0011 — Marketplace vs contadores internos).

## Fluxo

1. Cliente pergunta (WhatsApp/dashboard) → LLM classifica intent.
2. Se intent ∈ out-of-scope ([[principios/11-out-of-scope|§8.11]]): oferece 3 parceiros melhor avaliados na categoria + UF.
3. Cliente confirma compartilhamento → cria `consulta_marketplace`.
4. Parceiro recebe notificação (SLA 24h aceitar / 72h responder).
5. Responde no app → cliente avalia (1-5) → pagamento Pix/cartão, plataforma retém 20-30%.

## Modelagem (§5.8)

- `contador_parceiro` — CRC/OAB, especialidades JSONB, rating, SLA.
- `consulta_marketplace` — RLS por tenant ([[principios/01-rls-multi-tenant|§8.1]]); contador vê via role/policy separada; `idempotency_key` ([[principios/09-idempotencia|§8.9]]); campos LGPD `consentimento_*` e `pii_apagado_em` ([[principios/07-lgpd-first|§8.7]]).

## Categorias e pricing (resumo)

Consulta rápida R$80-150 (30%) · intimação simples/complexa R$200-1.000 (25%) · parecer R$800-1.500 (20%) · petição/defesa R$1.500-3.000+ (20%) · holding/sucessão R$3.000-15.000 (15%).

## Curadoria

CRC ativo (check mensal automático), OAB para casos jurídicos, 3+ anos, rating ≥4.0 nas 10 primeiras. Desligamento automático se rating <3.5 em 30 dias ou 3 SLAs seguidos descumpridos.

## Princípios em jogo

- [[principios/01-rls-multi-tenant|01 — RLS]] (consulta_marketplace + policy do parceiro)
- [[principios/07-lgpd-first|07 — LGPD]] (consentimento por consulta, revogação)
- [[principios/09-idempotencia|09 — Idempotência]] (idempotency_key)
- [[principios/11-out-of-scope|11 — Out-of-scope]] (gatilho do encaminhamento)

## Relacionado

- [[README|Hub do vault]]
- [[PlanoBackend]] §10 / §5.8 / §11
