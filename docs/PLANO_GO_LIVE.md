# Plano Go-Live — "Tudo o que o código promete, sem mock"
**Data:** 2026-06-21 · Base: `docs/PRODUCTION_READINESS_AUDIT-2026-06-21.md` · Marco 1 (fundação) ✅ feito.

> Princípio: cada capacidade que hoje é stub/mock/placeholder vira real por **2 movimentos** — uma **ação de código (eu)** e/ou uma **ação externa sua (PO)**: conta, credencial, certificado, decisão jurídica, infra. Onde só há "eu", começo já. Onde há "você", fico bloqueado até a credencial/conta existir.

---

## A. SUAS AÇÕES (externas — só você pode fazer)

### A1. Contas & credenciais de integração (destravam "sem mock")
| O que | Para destravar | Como |
|---|---|---|
| **Gateway de pagamento** (Stripe ou Pagar.me/Asaas) | Billing + marketplace real | Criar conta PJ, pegar API keys (test+live), webhook secret |
| **Certificado ICP-Brasil A1** (e-CNPJ) | eSocial/Reinf/NFe transmissão real | Comprar A1 (.pfx) + senha; subir como segredo |
| **SERPRO Integra Contador** | Certidões reais + Reinf + e-CAC | Credenciar CNPJ no SERPRO, obter consumer key/secret prod |
| **Focus NFe (prod)** ou **ADN prefeitura** | NFS-e real | Token prod Focus, OU credenciamento ADN da(s) prefeitura(s)-alvo |
| **Pluggy (prod)** | Open Finance real | client_id/secret prod + webhook URL pública |
| **Meta WhatsApp** | Envio de digest/alertas | Aprovar template + WABA token + phone number id |
| **Gemini API key** (ou Ollama self-host) | Assistente IA real | Chave Google AI Studio (ou GPU p/ Ollama) |
| **Provedor de e-mail** (Resend/Postmark/SES) | E-mail transacional | Conta + domínio verificado (SPF/DKIM/DMARC) |

### A2. Infra de produção (AWS sa-east-1 — LGPD)
| O que | Por quê |
|---|---|
| Conta AWS + VPC sa-east-1 | Dados em território nacional (§8.7) |
| **RDS Postgres 16 Multi-AZ** (+ pgvector) | Banco gerenciado, backup automático |
| **ElastiCache Redis** | Broker Celery + cache + rate-limit |
| **EKS/ECS** ou VPS + o `docker-compose.prod.yml` | Rodar api+worker+beat (já prontos) |
| **S3 bucket** (sa-east-1) + IAM | Storage de SPED/DANFSE/holerite |
| **KMS key** | AES-256 em repouso (cert, PII) |
| **DNS + TLS** (Route53 + ACM/Let's Encrypt) + **nginx/ALB** | HTTPS, terminação TLS |
| **CloudFlare WAF / DDoS** | Borda |
| **Backup + restore drill testado** | Gate P4 (não basta ter backup — testar o restore) |
| **Sentry** (DSN) + **Grafana/Prometheus/Loki** (self-host) | Observabilidade (código já emite) |

### A3. Jurídico & negócio (não-código)
- **Termos de Uso + Política de Privacidade** (revisão jurídica) — BLOCKER LGPD.
- **DPO** designado + registro de tratamento (obrigatório >100 clientes).
- **Pen test externo** (fornecedor) — gate ADR-016 (sem findings críticos).
- **Decisão de pricing** dos planos (R$/mês por tier) e regras de trial.
- **Helpdesk** (ferramenta: Crisp/Intercom/Chatwoot) + **status page** (statuspage.io/Instatus).

---

## B. MINHAS AÇÕES (código — começo sem depender de você)

> Ordenadas por marco. Cada item: escrevo → valido (pytest+mypy+integração) → commito. Onde precisa da sua credencial p/ "ligar", deixo o código pronto atrás de flag/env (sem mock).

### Marco 2 — Negócio cobrável (billing) — *o maior buraco*
1. **Modelo de assinatura SCD**: tabelas `plano`, `assinatura`, `fatura`, `evento_billing` (RLS, imutável) + máquina de estados (trial→ativa→inadimplente→cancelada).
2. **Adapter de gateway** espelhando o `PaymentProvider` Protocol do marketplace: `StripeProvider`/`PagarmeProvider` (atrás de env keys) — sem `_FakeProvider`.
3. **Trial** (72h/14d) + **webhook de cobrança** (HMAC) + **dunning** (retry 3/7 dias via Celery).
4. **Nota da própria assinatura** (NFS-e da receita do Arkan) — task Celery.
5. **Frontend**: tela `/assinatura` (fatura, histórico, download NFS-e) + aviso de trial.

### Marco 3 — LGPD & segurança para lançar
6. **Endpoints `/lgpd/exportar` + `/lgpd/excluir`** (direito do titular) + audit trail de tratamento + retenção 5 anos.
7. **AES-256 envelope** (helpers pgcrypto/KMS) aplicado às colunas PII (CPF, XML de NF) — hoje só o cert é cifrado.
8. **Security headers** (HSTS/CSP/X-Frame-Options) middleware + **refresh token** (rotação JWT).
9. **AgentShield/Semgrep bloqueante** no CI + promover QA-gates soft→hard (commitar baseline Playwright).

### Marco 4 — Conectar TODO o resto à produção real (remover os últimos mocks)
10. **Storage S3 efetivo**: preencher `storage_key` em sped/notas/pessoal e ler/escrever via `S3Storage` (boto3) — hoje tudo em BYTEA. *(liga com seu A2 bucket)*
11. **Transmissão EFD-Reinf → SERPRO**: escrever o serviço de envio (espelhando `transmissao_esocial_service`) — hoje `status='preparado'` permanente. *(liga com A1 SERPRO+cert)*
12. **eSocial real**: nada a escrever (código pronto) — só ligar `ESOCIAL_TRANSMISSAO_ATIVA=True` + cert. *(seu A1)*
13. **NFS-e**: Focus já funciona; se for ADN, escrevo o routing. *(seu A1)*
14. **E-mail transacional**: cliente Resend/Postmark + templates (onboarding, fatura, alerta). *(liga com A1 e-mail)*
15. **Frontend produção**: `Dockerfile` (Next standalone) + `NEXT_PUBLIC_API_BASE_URL` por build-arg + `error.tsx`/retry/timeout (robustez da auditoria). *(liga com A2 deploy)*
16. **Onboarding CNPJ-first**: ligar o `BrasilApiClient` ao wizard (pré-preenche) + persistência de draft no backend.
17. **IaC**: Helm charts / Terraform sa-east-1 (ou refinar o compose.prod p/ ECS). *(co-construído com seu A2)*

---

## C. Caminho crítico (o que destrava o quê)
```
Marco 1 ✅ (feito) ──► M2 billing (eu, só gateway de você) ──► piloto pago possível
                  └──► M3 LGPD/segurança (eu) + termos/pentest (você) ──► pode lançar
                  └──► M4 integrações: cada uma é "código pronto + sua credencial"
                          eSocial/Reinf/NFe ──► certificado A1 + SERPRO (você)
                          S3 storage ──► bucket (você)
                          e-mail ──► provedor (você)
                  └──► Deploy real (você AWS) + IaC (eu) ──► produção no ar
```

**Regra de ouro:** eu deixo cada integração **pronta atrás de env/flag, sem mock**. No dia em que a credencial entra no `.env` de produção, a capacidade liga sozinha — nada de "demo".

## D. Por onde eu sigo agora (recomendação)
**Marco 2 (billing)** — é o maior buraco (não dá pra cobrar cliente hoje) e é quase todo meu; você só decide o gateway e pricing. Em paralelo posso ir limpando os mocks do Marco 4 que não dependem de você (storage wiring, Reinf service, LGPD endpoints, e-mail client — todos atrás de env).
