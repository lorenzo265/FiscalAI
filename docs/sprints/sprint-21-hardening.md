---
sprint: 21
titulo: "Hardening + segurança"
fase: 4
status: concluida
marco: "Pen test sem findings críticos; runbooks completos"
testes_finais: 2187
atualizado: 2026-05-31
---

# Sprint 21 — Hardening + Segurança

Objetivo: fechar os itens de segurança pré-production conforme §14.3 e §11.1 (Fase 4).

Relacionado: [[decisoes/adr-016-hardening-seguranca]] · [[pendencias/runbook-pentest-externo]] · [[roadmap]]

---

## PR1 — Bandit + análise estática + invariantes de segurança

**Testes adicionados:** +40 (total pós-PR1: 2161)

O que entrou:
- `pyproject.toml` — `bandit[toml]` em dev deps + `[tool.bandit]` config (excl. tests + alembic, skip B101).
- `app/shared/cache/cache.py` — `# nosec B311` em `random.randint` de TTL (não criptográfico).
- `app/config.py` — `# nosec B105` em `JWT_SECRET` e `META_WHATSAPP_VERIFY_TOKEN` (placeholders documentados).
- `tests/unit/security/test_jwt_invariants.py` — 10 golden tests: round-trip, expiração, assinatura adulterada, secret errado, separação PME/parceiro, claims obrigatórios (tid, sub UUID).
- `tests/unit/security/test_hmac_invariants.py` — 8 testes: HMAC válido, payload adulterado, secret errado, guards de inputs vazios, prefixo sha256=, structural `compare_digest`.
- `tests/unit/security/test_password_invariants.py` — 6 testes: salt aleatório, verificação correta/errada, rounds=12, Unicode.
- `tests/unit/security/test_sql_injection_prevention.py` — 16 testes: bind parameter `:tid/:cid`, UUID parse rejeita injection, schema UUID4 rejeita, `extra="forbid"`, f-string ausente.

---

## PR2 — Rate limiting Redis por tenant

**Testes adicionados:** +26 (total pós-PR2: 2187)

O que entrou:
- `app/shared/middleware/__init__.py`
- `app/shared/middleware/rate_limit.py` — `RateLimitMiddleware` (Starlette BaseHTTPMiddleware):
  - Limites: 1000 req/h padrão, 100 req/h em endpoints sensíveis (`/v1/auth`, `/v1/pgdas`, `/v1/sped`, `/v1/notas`, `/v1/certidoes`, `/v1/declaracao`).
  - Redis INCR + EXPIRE atômico; chave `rl:<tenant_id>:<unix_hora>`.
  - Fail-open em RedisError.
  - Headers RFC 6585: `X-RateLimit-Limit/Remaining/Reset`, `Retry-After`.
  - Extração de `tid` do JWT sem re-validação assinatura (apenas para identificar tenant).
- `app/main.py` — `app.add_middleware(RateLimitMiddleware)`.
- `tests/unit/middleware/test_rate_limit.py` — 26 golden tests: janela horária, chave Redis, limites por path, headers RFC 6585, Redis mockado (permitido/bloqueado/fail-open).

---

## PR3 — ADR + runbook pen test + vault write-back

O que entrou:
- `docs/decisoes/adr-016-hardening-seguranca.md`
- `docs/pendencias/runbook-pentest-externo.md` — scope, recompensas, checklist técnico, security headers.
- `docs/sprints/sprint-21-hardening.md` (este arquivo)
- `docs/roadmap.md` — Sprint 21 → ✅, Sprint 22 → 🔜
- `log_agente.md` — entradas PR1/PR2/PR3 + contagem final

---

## Definition of Done ✅

- [x] pytest: 2187 passed, 2 skipped
- [x] mypy strict: 0 erros
- [x] Bandit configurado em pyproject.toml
- [x] Rate limiting Redis ativo em main.py
- [x] Suite `tests/unit/security/` com 40 golden tests
- [x] ADR-016 documentado
- [x] Runbook pen test externo criado
- [x] Log de agente atualizado
- [x] Roadmap marcado ✅
