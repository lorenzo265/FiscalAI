# Sprint 1 — Fundação multi-tenant

**Tema:** schemas `tenant / usuario / empresa` com RLS ativo + JWT + endpoints de auth + testes de isolamento.

**Início:** 2026-05-10
**Critério de fechamento:** todos os marcos abaixo ✅. **Testes de isolamento RLS bloqueando merge.**

> Fonte literal: `PlanoBackend.md` §9 — "Schemas: tenant, usuario, empresa. RLS ativo. JWT. Endpoint POST /auth/register, POST /auth/login. Testes de isolamento."

## Marcos binários

- [x] `app/shared/db/base.py` — `DeclarativeBase` SQLAlchemy 2.0
- [x] `app/shared/db/models.py` — `Tenant`, `Usuario`, `Empresa` com `tenant_id NOT NULL`, constraints, índices
- [x] `app/shared/db/deps.py` — `get_session` (SET LOCAL RLS), `get_anon_session`, `get_tenant_context`
- [x] `app/shared/db/rls.py` — `session_with_tenant` para workers Celery (Sprint 2+)
- [x] `app/shared/auth/password.py` — `hash_senha` + `verificar_senha` (bcrypt cost 12)
- [x] `app/shared/auth/jwt.py` — `TenantContext`, `criar_token`, `verificar_token`
- [x] `app/modules/empresa/cnpj.py` — `validar_cnpj` (algoritmo oficial dois dígitos verificadores)
- [x] `app/modules/auth/schemas.py` — `RegisterIn`, `LoginIn`, `TokenOut`, `RegisterOut`
- [x] `app/modules/empresa/schemas.py` — `EmpresaIn`, `EmpresaOut`, `RegimeTributario`, `AnexoSimples`, `PerfilUI`
- [x] `app/modules/auth/repo.py` — `TenantRepo`, `UsuarioRepo`
- [x] `app/modules/empresa/repo.py` — `EmpresaRepo`
- [x] `app/modules/auth/service.py` — `AuthService.registrar()`, `AuthService.login()`
- [x] `app/modules/empresa/service.py` — `EmpresaService.criar()`, `.listar()`, `.buscar()`
- [x] `app/modules/auth/router.py` — `POST /auth/register`, `POST /auth/login`
- [x] `app/modules/empresa/router.py` — `POST /v1/empresas`, `GET /v1/empresas`, `GET /v1/empresas/{id}`
- [x] `alembic/versions/0001_sprint1_fundacao.py` — tabelas + RLS policies
- [x] `alembic/env.py` atualizado — `target_metadata = Base.metadata`
- [x] `app/main.py` atualizado — `session_factory` no lifespan + routers incluídos
- [x] `app/config.py` atualizado — `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`
- [x] `app/shared/exceptions.py` atualizado — `TokenInvalido`, `CredenciaisInvalidas`, `SlugJaCadastrado`, `EmailJaCadastrado`, `CnpjInvalido`, `CnpjJaCadastrado`, `EmpresaNaoEncontrada`, `TenantNaoEncontrado`
- [x] `tests/unit/empresa/test_cnpj.py` — 20 golden cases (válidos + inválidos por dígito, sequência, formato)
- [x] `tests/unit/auth/test_password.py` — testes bcrypt (hash, verify, custo 12)
- [x] `tests/unit/auth/test_jwt.py` — testes JWT (criar, verificar, adulterado)
- [x] `tests/integration/test_auth.py` — fluxo register/login end-to-end com Postgres real
- [x] `tests/integration/test_rls_isolation.py` — tenant A não vê dados de tenant B (barreira de merge)
- [x] CI atualizado — `alembic upgrade head` antes do pytest + `JWT_SECRET` como env var
- [ ] **Validação manual:** `docker compose up -d && poetry run alembic upgrade head` → sem erros
- [ ] **Validação manual:** `POST /auth/register` → 201 com token
- [ ] **Validação manual:** `POST /auth/login` com slug/email/senha corretos → 200 com token
- [ ] **Validação manual:** `GET /v1/empresas` sem token → 401
- [ ] **Validação manual:** `poetry run pytest` → todos os testes passando
- [ ] **Validação manual:** `poetry run mypy app` → sem erros
- [ ] **Validação manual:** `poetry run ruff check .` → sem erros

## Decisões de design (fora do Plano, documentadas aqui)

| Decisão | Escolha | Justificativa |
|---|---|---|
| Login identifier | `tenant_slug + email + senha` | Segue `UNIQUE(tenant_id, email)` do schema §5.1 — email não é globalmente único |
| JWT payload | `sub=user_id, tid=tenant_id, exp, iat` | Mínimo para RLS; sem refresh token no MVP |
| Lifespan session factory | Criado no lifespan, exposto em `app.state.session_factory` | Compartilhado entre `get_session` e `get_anon_session` — único pool de conexões |
| Auth session | `get_anon_session` sem SET LOCAL | Register/login precisam de sessão antes de conhecer o tenant_id |
| RLS policy | `NULLIF(current_setting(..., TRUE), '')::uuid = tenant_id` | Seguro quando GUC não está definido (NULL ≠ UUID → sem rows) |
| bcrypt | `bcrypt` direto (v4.x com type stubs) | `passlib` tem incompatibilidade com `bcrypt >= 4.0` |
| Empresa CRUD | Incluído em Sprint 1 | Auth sem empresa é inútil; sem scope creep — é consequência direta |
| `perfil_ui` derivado | `sn_sem_funcionarios` default para SN | Sem dados de folha ainda — Sprint 9 permite atualização |

## Fora de escopo (rejeitar até Sprint 2+)

- ❌ Refresh tokens / revogação
- ❌ Verificação de e-mail / reset de senha
- ❌ Roles granulares (além de "autenticado")
- ❌ Audit trail (`audit_log` table) — Sprint 4
- ❌ Rate limiting — Sprint 6
- ❌ Empresa update/delete — Sprint 2+
- ❌ Celery, LLM, integrações externas

## Próxima sprint

Sprint 2 — Ingestão XML NF-e + DAS Simples Nacional. Parser `nfelib`, upload + IMAP. Calculadora DAS com 5 anexos + Fator R + RBT12. Golden tests obrigatórios.
