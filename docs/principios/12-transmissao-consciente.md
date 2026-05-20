---
tags: [principio, sped, certificado, compliance, bonus]
fonte: "[[PlanoBackend]] §8.12"
status: ativo
---

# 12 — Transmissão ao Fisco é ato consciente do cliente

> Princípio bônus §8.12. Fonte: [[PlanoBackend]].

## Regra

- **SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI):** o sistema **gera** o `.txt` oficial, **valida** localmente e **mostra** erros. O cliente/contador **baixa e transmite** via PVA/ReceitaNet com o certificado A1 **dele**. Não armazenamos o A1 do cliente.
- **PGDAS-D, DCTFWeb, DCTF (via SERPRO):** transmissão delegada pelo modelo oficial — cliente outorga procuração e-CAC ao escritório, que transmite com **seu próprio** A1 + token SERPRO. O certificado criptografado armazenado é o do escritório, nunca o do cliente.
- Cliente assina termo no onboarding; audit trail registra usuário + IP + recibo SERPRO + timestamp.

Decisão completa em ADR-0014.

## Relacionado

- [[principios/07-lgpd-first|07 — LGPD-first]]
- [[principios/11-out-of-scope|11 — Out-of-scope declarado]]
- [[pendencias/esocial-transmissao|Pendência: eSocial transmissão]]
