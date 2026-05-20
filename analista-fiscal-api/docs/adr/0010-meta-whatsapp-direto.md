# ADR 0010 — WhatsApp via Meta Cloud API direto (sem BSP)

## Status

accepted (2026-05-10)

## Contexto

WhatsApp é canal principal de interação com o cliente PME (assistente, alertas, weekly digest). Em 2026 há dois caminhos: integrar direto com a Meta Cloud API ou contratar um BSP (Twilio, Z-API, Take Blip).

Pricing Meta (a partir de 01/07/2025, Brasil): utility ~$0.008/msg, marketing $0.0625/msg, service grátis dentro de 24h após msg do cliente, click-to-WhatsApp ad = 72h grátis.

## Decisão

Usar **Meta Cloud API direto** no MVP. BSP (Twilio) reservado para escala (>50k msgs/dia) ou requisito específico (multi-canal, sub-account).

## Consequências

**Positivas:**
- Custo mínimo: ~$0.008/msg utility, sem markup de BSP.
- Controle total: webhook próprio, retry próprio, observabilidade direta no Langfuse.
- Sem vendor lock-in adicional.

**Negativas:**
- Setup mais trabalhoso — Meta Business + verificação + número dedicado + template approval. Mitigação: documentar passo a passo em runbook e absorver no onboarding.
- Sem multi-tenancy de número WhatsApp gratuita — cada empresa pagante grande pode querer seu próprio número (cobrado à parte). Mitigação: 1 número compartilhado para o MVP; planos enterprise terão número dedicado.
- Compliance de templates é nossa responsabilidade — não há BSP curando.

## Alternativas consideradas

- **Twilio** — markup ~3× sobre Meta; faz sentido só em escala.
- **Z-API / Take Blip** — markup similar, focados em SMB; revisitar se UX direto da Meta tiver fricção.
- **Não usar WhatsApp** — fora de questão; é o canal core do mercado brasileiro PME.

## Referências

- `PlanoBackend.md` §2.1, §7
- Meta WhatsApp Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Pricing Meta 2025/2026: Spur + MessageCentral
