---
id: ADR-016
titulo: "Hardening de segurança — Sprint 21"
status: aceito
data: 2026-05-31
autores: [equipe-backend]
tags: [segurança, rate-limit, bandit, jwt, hmac, lgpd]
---

# ADR-016 — Hardening de segurança (Sprint 21)

## Contexto

Sprint 21 (Fase 4 — Lapidação) fecha os itens de segurança pré-production:
- Static analysis com `bandit` para detectar padrões Python inseguros.
- Rate limiting por tenant para resistir a abuso/brute-force.
- Suite de golden tests de invariantes de segurança bloqueando merge.
- Runbook para pen test externo e bug bounty.

A Fase 4 (§11.1 do Plano) exige: *pen test sem findings críticos*.

## Decisões

### 1. Bandit — análise estática de segurança

**Escolha:** `bandit` v1.8 com configuração em `pyproject.toml`.

- Excluídos: `tests/` (B101 — assert legítimo) e `alembic/` (código gerado).
- Inline `# nosec B311` em `cache.py` para `random.randint` de TTL (não criptográfico).
- Inline `# nosec B105` em `config.py` para defaults placeholder de chaves (JWT_SECRET, VERIFY_TOKEN).
- CI deve rodar `bandit -c pyproject.toml -r app/` e bloquear em HIGH/MEDIUM sem `nosec`.

**Por que não safety apenas?** `safety` verifica dependências com CVE; `bandit` verifica padrões no código. Ambos são necessários conforme §14.3.

### 2. Rate limiting — Redis INCR + EXPIRE

**Escolha:** `RateLimitMiddleware` (Starlette `BaseHTTPMiddleware`) com Redis INCR atômico por janela de 1 hora.

Limites conforme §14.3:
| Tipo de endpoint | Limite |
|---|---|
| Padrão | 1000 req/hora por tenant |
| Sensível (`/v1/auth`, `/v1/pgdas`, `/v1/sped`, `/v1/notas`, `/v1/certidoes`) | 100 req/hora por tenant |

**Algoritmo:**
- Chave Redis: `rl:<tenant_id>:<unix_hora>` — isolamento total por tenant por janela horária.
- INCR atômico: sem race condition entre check e increment.
- EXPIRE setado apenas na primeira req da janela (guard `contagem == 1`).
- Fail-open: Redis indisponível → requisição passa (disponibilidade > segurança neste cenário).
- Headers RFC 6585: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.

**Por que não token bucket ou sliding window?** INCR + EXPIRE (fixed window) é O(1), atômico, e suficiente para PMEs. Sliding window seria mais preciso na borda da janela, mas exige ZSET + Lua (complexidade desnecessária para o volume atual).

**Extração de tenant sem re-validação:** O middleware extrai o claim `tid` do JWT decoding base64 (sem verificar assinatura) apenas para identificar o tenant no rate limiting. A validação real da assinatura ocorre em `get_tenant_context` nos endpoints. Isso é seguro porque:
- Rate limiting é best-effort (fail-open).
- Um atacante que falsificar o `tid` apenas se prejudica ao consumir cota de outro tenant.

### 3. Testes de invariantes de segurança

**Escolha:** Suite dedicada `tests/unit/security/` com golden tests puros.

Módulos:
- `test_jwt_invariants.py` — expiração, assinatura adulterada, separação PME/parceiro, claims obrigatórios.
- `test_hmac_invariants.py` — HMAC-SHA256 Pluggy, compare_digest (timing-safe).
- `test_password_invariants.py` — bcrypt rounds=12, salt aleatório.
- `test_sql_injection_prevention.py` — RLS usa bind parameters, UUID parse rejeita injection, Pydantic `extra="forbid"`.

### 4. Pen test externo — processo

Ver `docs/pendencias/runbook-pentest-externo.md` para scope, entregáveis e critérios de aceite.

**Critério de go/no-go (§11.1 Fase 4):** sem findings críticos (CVSS ≥9.0) e sem findings high não mitigados.

## Consequências

- `bandit` entra no CI; findings HIGH/MEDIUM sem `nosec` bloqueiam merge.
- `RateLimitMiddleware` está ativo em produção desde o deploy desta sprint.
- Suite `tests/unit/security/` cobre os 4 vetores principais (JWT, HMAC, password, SQL injection).
- Pen test externo: pendência operacional documentada no runbook.

Relacionado: [[principios/07-lgpd-first]] · [[principios/01-rls-multi-tenant]] · [[sprints/sprint-21-hardening]]
