# Auditoria de Production-Readiness — Arkan / Analista Fiscal
**Data:** 2026-06-21 · **Método:** 8 assessores read-only por dimensão, fundamentados no código real (não no plano).

> Veredicto-mãe: **a base de código é forte (alpha/MVP sólido), mas o projeto NÃO está production-grade.** Falta a **camada de negócio (billing)**, a **camada de produção (deploy/IaC/observabilidade)** e a **camada operacional/legal (LGPD/suporte)**. Estimativa realista: **6–10 semanas** de trabalho focado, boa parte paralelizável; vários itens são atos externos do PO (AWS, gateway, jurídico, credenciais).

## O que já é forte (a fundação)
- **Fiscal correto** — auditoria 2026-06-21 fechada (Ondas A–C), 2682 testes, mypy strict 0, golden por cálculo, SCD Type 2 em 60+ migrations, IRRF 2026 + redutor ativos.
- **Segurança de código** — RLS multi-tenant (FORCE RLS), JWT tipo-separado, rate limiting Redis, redação de PII em logs, bcrypt 12, HMAC timing-safe, bandit no CI, config fail-fast em prod.
- **CI existe** — `.github/workflows/ci.yml` (ruff/mypy/bandit/pytest unit+eval + integração RLS + frontend build) bloqueante; `qa-gates.yml` (Lighthouse/axe/Semgrep/Gitleaks) — porém soft.
- **Arquitetura** — Dockerfile multi-stage, health `/healthz`+`/readyz`, storage abstrato (local/memory/s3), Celery dual-mode com beat (17 tasks), logging estruturado, eSocial transmissão real (opt-in + XMLDSig), geradores SPED completos.

---

## TIER 1 — BLOQUEADORES (impedem lançar comercialmente)

| # | Gap | Dimensão | Dono | Esforço |
|---|---|---|---|---|
| 1 | **Billing/assinatura SaaS 100% ausente** — sem modelo de plano, trial, cobrança recorrente, nota da própria assinatura. O marketplace tem stub de pagamento pronto, mas a **assinatura B2B (R$149–499/mês) não existe**. | Billing | code + **PO** (gateway) | L |
| 2 | **Gateway de pagamento real** (Stripe Connect / Pagar.me / Asaas) — conta + credenciais. | Billing | **PO** | L |
| 3 | **Infra de produção real** — IaC (Helm/Terraform) ausente; deploy sa-east-1, RDS Multi-AZ, TLS, DNS, KMS para segredos — tudo placeholder. | Infra | code (manifests) + **PO** (AWS) | L |
| 4 | **Celery não roda em produção** — pacote `celery[redis]` é opt-in; `Dockerfile.worker`/`.beat` são placeholders de 1 linha. Sem isso, **18 tasks agendadas ficam paradas** (SPED, certidões, alertas, depreciação). | Infra | code | S |
| 5 | **Termos de Uso + Política de Privacidade** — inexistentes; sem consentimento versionado. | Segurança/LGPD | **PO** (jurídico) | M |
| 6 | **Pen test externo** — ADR-016 exige "sem findings críticos" como gate; não rodou. | Segurança | **PO** (fornecedor) | L |

## TIER 2 — IMPORTANTE (antes de escalar / cobrar com tranquilidade)

| # | Gap | Dimensão | Dono | Esforço |
|---|---|---|---|---|
| 7 | **Observabilidade de produção** — Sentry, Prometheus `/metrics`, correlation-id middleware ausentes (runbook completo existe, mas é aspiracional). | Observabilidade | code | M |
| 8 | **Endpoints LGPD** `/lgpd/exportar` + `/lgpd/excluir` + audit trail de tratamento + retenção 5 anos. | Segurança/LGPD | code | M |
| 9 | **AES-256 em repouso** — só o cert SERPRO é cifrado; CPF/XML de NF em plaintext (helpers de envelope pendentes). | Segurança | code | M |
| 10 | **Storage S3 efetivo** — abstração pronta, mas tudo ainda em BYTEA (`storage_key=NULL`); boto3 não instalado. Aguenta ~100 empresas. | Fiscal/Infra | code + **PO** (bucket) | M |
| 11 | **Transmissão EFD-Reinf → SERPRO** — cálculo R-4020 pronto e auditável, mas zero integração (fica em `status='preparado'`). | Fiscal | code | M |
| 12 | **NFS-e Nacional (ADN) real** — hoje só Focus (agregador); ADN exige credencial+endpoint de prefeitura. | Fiscal | **PO** (credencial) | M |
| 13 | **E-mail transacional** (Resend/Postmark) — nenhum cliente de e-mail; bloqueia onboarding, billing, alertas. | Onboarding | code + **PO** (conta) | M |
| 14 | **Hardening da CI** — promover QA-gates de soft→bloqueante, baseline de snapshot Playwright commitada, cobertura (`--cov`) com gate, pre-commit instalado, AgentShield/Semgrep bloqueante, type-check no build do front. | CI/CD | code | M |
| 15 | **Frontend robustez** — `error.tsx` (error boundaries) ausentes; retry/timeout (AbortController) no fetch; mapear http_404/503; mais rotas no axe; contraste WCAG auditado. | Frontend | code | M |
| 16 | **Segurança de borda** — security headers (HSTS/CSP/X-Frame), WAF/CloudFlare, TLS 1.3 no proxy, refresh token. | Segurança/Infra | code (headers/refresh) + **PO** (WAF) | M |
| 17 | **Helpdesk + status page** — suporte operacional ausente. | Onboarding | **PO** (ferramenta) + code | M |

## TIER 3 — ACABAMENTO (profissionalismo, pós-piloto)
- Dashboards Grafana do Arkan; OTEL/Tempo tracing distribuído; Loki push.
- Frontend: testes unitários JS (Vitest), loading.tsx por rota, bundle-size gate, mensagens de erro com contexto.
- Dunning/retry de fatura; dashboard financeiro do cliente; alertas de trial via WhatsApp.
- Blocos SPED subnormalizados (CT-e/MDF-e, ISS RJ/SP) — "real quando o cliente pedir".
- Docs de API por domínio; runbooks de falha de onboarding; persistência de draft do onboarding no backend.

---

## Quem faz o quê

**Eu (código, sem depender de você) — posso começar já:**
- Celery production-ready (#4): instalar `celery[redis]`, Dockerfiles worker/beat reais, overlay `docker-compose.prod`.
- Observabilidade (#7): Sentry init, Prometheus `/metrics`, correlation-id middleware.
- LGPD endpoints (#8) + security headers (#16).
- **Billing model + lógica** (#1, parte code): tabelas de plano/assinatura/trial/fatura espelhando o padrão `PaymentProvider` do marketplace + adapter Stripe/Pagar.me skeleton; nota da própria assinatura via NFS-e.
- AES-256 envelope (#9) + wiring S3 (#10, parte code).
- Reinf→SERPRO (#11) espelhando o serviço de transmissão do eSocial.
- Hardening da CI (#14) + robustez do frontend (#15).
- E-mail transacional integração (#13, parte code).

**Você (atos externos):**
- Conta AWS (sa-east-1) + deploy + RDS Multi-AZ + KMS + DNS/TLS + CloudFlare WAF.
- Gateway de pagamento (Stripe/Pagar.me) — conta + credenciais.
- Termos + Política de Privacidade (jurídico) + DPO.
- Pen test externo (fornecedor).
- Credenciais de produção: SERPRO, ADN/prefeitura, Focus, ICP-Brasil; provedor de e-mail; helpdesk; status page; aprovação de template Meta WhatsApp.

## Sequência recomendada (marcos)
1. **M1 — Fundação de produção (~2 sem):** Celery real + Dockerfiles + observabilidade (Sentry/Prometheus/correlation-id) + hardening CI. *(quase tudo eu)*
2. **M2 — Negócio cobrável (~2–3 sem):** billing/assinatura + trial + nota da assinatura + e-mail transacional. *(eu escrevo; você habilita o gateway)*
3. **M3 — Segurança/LGPD para lançar (~2 sem):** endpoints LGPD + AES-256 + security headers + termos/privacidade + agendar pen test. *(misto)*
4. **M4 — Deploy real + piloto:** IaC + sa-east-1 + S3 + credenciais externas + 10 empresas em beta. *(você lidera o ambiente; eu, o código)*

> A correção fiscal (o que mais dói legalmente) já está feita. O caminho para "production-grade, profissional" agora é **infra + billing + ops/LGPD** — não mais matemática fiscal.
