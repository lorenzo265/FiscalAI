# ADR 0007 — Open Finance: Pluggy (primário) + Belvo (backup)

## Status

accepted (2026-05-10)

## Contexto

A Sprint 7 entrega conciliação bancária automática via Open Finance regulado pelo BACEN. Os candidatos sérios em 2026 são Pluggy e Belvo, ambos credenciados.

## Decisão

Adotar **Pluggy** como provider primário e **Belvo** como backup.

- Pluggy é Iniciadora de Pagamento autorizada pelo BCB (CNPJ 37.943.755/0001-30).
- Foco developer-first, widget de conexão pronto para integração.
- Cobertura ampla de bancos brasileiros via Open Finance regulado.

Belvo permanece como fallback caso Pluggy degrade ou cliente exija banco específico não suportado.

## Consequências

**Positivas:**
- Open Finance regulado — sem scraping, sem violação de TOS bancário, sem CAPTCHA.
- Widget de conexão pronto reduz fricção de onboarding.
- Webhooks para novas transações.

**Negativas:**
- Custo por conta conectada (~R$2,50/conta/mês). Mitigação: cobrar do cliente o uso (passar custo) ou limitar a 1 conta no plano básico.
- Dependência de fornecedor para fluxo importante. Mitigação: cliente abstrato + Belvo como swap.

## Alternativas consideradas

- **Belvo como primário** — opção igualmente válida; escolhido Pluggy pelo developer experience superior em 2026.
- **Scraping bancário direto** — viola TOS, frágil, ilegal sob LGPD.
- **Open Finance direto via BCB** — exige certificação como Receptora; inviável para o time.

## Referências

- `PlanoBackend.md` §2.1, §7
- Pluggy: https://docs.pluggy.ai/
- Belvo: https://developers.belvo.com/
