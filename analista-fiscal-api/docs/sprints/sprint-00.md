# Sprint 0 — Setup

**Tema:** abrir o repositório do backend, deixar a infra de dev de pé e os ADRs assinados.

**Início:** 2026-05-10
**Critério de fechamento:** todos os marcos abaixo ✅. **Sem todos ✅, não começar Sprint 1** (regra explícita do Plano §16.4).

> Fonte literal: `PlanoBackend.md` §9 (linha "0 | Setup | Repo, Docker Compose, Postgres+Redis subindo, FastAPI hello-world, CI no GitHub Actions, ADR-001 a 004 escritos") + §16.4 (expande ADRs até 0010).

## Marcos binários

- [x] Estrutura de pastas conforme §4.2 do Plano (módulos/shared/workers/tests/infra/docs)
- [x] `pyproject.toml` (Poetry, Python 3.12) com stack mínima da Sprint 0 — sem dependências de domínio que ainda não vamos usar
- [x] `.gitignore` cobrindo Python, venv, .env, certificados, dados locais
- [x] `.env.example` (sem segredos reais)
- [x] `docker-compose.yml` sobe Postgres 16 + Redis 7 + Ollama + API com healthchecks
- [x] `infra/postgres/init.sql` habilita `pgcrypto` e `vector`
- [x] `infra/docker/Dockerfile.api` multi-stage (dev + prod)
- [x] `app/main.py` com `lifespan`, `/healthz` (liveness) e `/readyz` (postgres + redis)
- [x] `app/config.py` com `pydantic-settings` e fail-fast em prod com localhost
- [x] `app/shared/exceptions.py` (DomainError base) + `app/shared/logging.py` (structlog)
- [x] Alembic configurado (`alembic.ini` + `alembic/env.py` async) sem migrations
- [x] Testes de smoke (`tests/test_smoke.py`) cobrindo `/healthz` e `/openapi.json`
- [x] CI no GitHub Actions (`.github/workflows/ci.yml`): ruff + mypy + pytest com Postgres+Redis service containers
- [x] ADRs 0001 a 0010 escritos com status `accepted`
- [x] `README.md` com quickstart (`docker compose up`)
- [ ] **Validação manual:** `docker compose up -d --build` + `curl http://localhost:8000/healthz` retorna 200
- [ ] **Validação manual:** `curl http://localhost:8000/readyz` retorna 200 com checks postgres+redis ok
- [ ] **Validação manual:** `poetry install && poetry run pytest` passa em verde
- [ ] **Validação manual:** `poetry run ruff check . && poetry run mypy app` passa em verde
- [ ] **Validação manual:** primeiro PR em branch fecha CI verde no GitHub Actions

## Fora de escopo (rejeitar até Sprint 1+)

- ❌ Models de domínio (Tenant, Usuario, Empresa, DocumentoFiscal) — Sprint 1
- ❌ JWT, autenticação, dependency `get_session` com `SET LOCAL` — Sprint 1
- ❌ Migrations de schema fiscal — Sprint 1
- ❌ Celery worker rodando — Sprint 2
- ❌ Cliente HTTP para Focus/SERPRO/Pluggy — Sprint 5/6/7
- ❌ LLMClient e prompts — Sprint 3
- ❌ Terraform / K8s / Helm — Sprint 11+

## Próxima sprint

Sprint 1 — Fundação multi-tenant. Schemas: tenant, usuario, empresa. RLS ativo. JWT. Endpoints `POST /auth/register`, `POST /auth/login`. Testes de isolamento RLS bloqueando merge.
