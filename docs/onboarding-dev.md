---
tags: [onboarding, dev, setup, guia]
atualizado: 2026-05-31
tempo_estimado: "30-60 min"
---

# Onboarding — Novo Desenvolvedor Backend

> Objetivo: você consegue rodar o servidor local, passar os testes e entender a estrutura em menos de 60 minutos.

Hub: [[README]] · [[PlanoBackend]] · [[review-checklist]]

---

## 1. Pré-requisitos

| Ferramenta | Versão mínima | Instalar |
|---|---|---|
| Python | 3.12+ | `pyenv install 3.12` ou Miniconda |
| Poetry | 1.8+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker + Compose | 24+ | Docker Desktop |
| Git | 2.40+ | `brew install git` / `winget install Git` |

---

## 2. Setup inicial (primeira vez)

```bash
# Clone
git clone <repo-url>
cd Apresentação-Ideia/analista-fiscal-api

# Instalar dependências Python
poetry install

# Copiar .env de exemplo
cp .env.example .env
# .env já tem defaults funcionais para dev local — não precisa editar para rodar testes

# Subir infraestrutura local (Postgres 16 + Redis 7)
docker compose up -d

# Rodar migrations
poetry run alembic upgrade head

# Verificar
poetry run python -m pytest tests/unit tests/eval -q
# Esperado: ~2187 passed, 2 skipped
```

---

## 3. Rodar o servidor

```bash
poetry run uvicorn app.main:app --reload
# API em: http://localhost:8000
# Docs interativos: http://localhost:8000/docs
# Healthcheck: http://localhost:8000/healthz
```

---

## 4. Estrutura do projeto

```
analista-fiscal-api/
├── app/
│   ├── config.py               ← Settings (pydantic-settings, lê .env)
│   ├── main.py                 ← FastAPI app + routers + lifespan
│   ├── modules/                ← Um pacote por bounded context fiscal
│   │   ├── empresa/            ← CNPJ, regime tributário, perfil
│   │   ├── fiscal/             ← DAS Simples Nacional
│   │   ├── lucro_presumido/    ← IRPJ, CSLL, PIS/Cofins, DARF, checklist
│   │   ├── contabil/           ← Plano de contas, lançamentos, balanço
│   │   ├── pessoal/            ← Folha CLT, eSocial
│   │   ├── advisor/            ← Regras determinísticas de sugestão
│   │   └── ... (~28 módulos)
│   └── shared/
│       ├── db/
│       │   ├── models.py       ← ~50 SQLAlchemy models (Mapped[])
│       │   ├── deps.py         ← Depends: get_session, get_tenant_context
│       │   └── rls.py          ← set_tenant_id → SET LOCAL RLS
│       ├── auth/               ← JWT: criar_token, verificar_token
│       ├── middleware/         ← RateLimitMiddleware (Redis)
│       ├── exceptions.py       ← ~60 DomainError → HTTP 4xx/5xx
│       ├── llm/                ← LLMClient, prompts, eval, citação
│       └── integrations/       ← Focus NFe, SERPRO, Pluggy, Meta WA
├── tests/
│   ├── unit/                   ← ~1900 testes puros (sem DB/Redis)
│   │   ├── fiscal/             ← Golden tests DAS SN
│   │   ├── lucro_presumido/    ← Golden tests LP + E2E
│   │   ├── security/           ← JWT, HMAC, bcrypt, SQL injection
│   │   └── middleware/         ← Rate limit
│   ├── eval/                   ← 166 casos LLM (intent, extração, citação)
│   └── integration/            ← Requer Docker (DB + Redis reais)
├── alembic/versions/           ← 52 migrations com RLS policy
└── docs/
    ├── PlanoBackend.md         ← SOURCE OF TRUTH absoluta
    ├── roadmap.md              ← Onde estamos (sprints 0-22)
    ├── adr/                    ← Decisões arquiteturais (0001-0016)
    ├── decisoes/               ← ADRs de estilo novo (adr-001+)
    ├── runbooks/               ← Deploy, on-call, backup
    └── principios/             ← Os 12 princípios invioláveis
```

---

## 5. Os 5 conceitos mais importantes

### 5.1 Multi-tenant via RLS (§8.1)

Cada empresa cliente é um **tenant**. O JWT carrega `tenant_id`. Todo endpoint autenticado usa:

```python
# deps.py — injetado automaticamente via Depends(get_session)
await session.execute(text("SET LOCAL ROLE fiscal_app"))
await set_tenant_id(session, ctx.tenant_id)
```

O PostgreSQL aplica a RLS policy: `empresa_id = current_setting('app.tenant_id')::uuid`. Empresa A nunca vê dados da Empresa B.

**Regra:** se criar endpoint sem `Depends(get_session)`, é bug grave.

### 5.2 Algoritmos puros antes de endpoints (§8.4)

A estrutura canônica de um módulo fiscal:

```
calcula_X.py   ← função pura Decimal-safe, zero I/O, golden test primeiro
repo.py        ← async SQLAlchemy, sem N+1, joins explícitos
service.py     ← orquestra calcula_X + repo; aceita repo por DI
router.py      ← thin: valida → service → response_model
schemas.py     ← Pydantic v2 com ConfigDict(extra='forbid')
```

**Regra:** golden test escrito **antes** do código de cálculo.

### 5.3 Fatos fiscais são imutáveis (§8.2)

Nunca `UPDATE` em tabelas de fatos. Cancelamento = nova linha com `evento='cancelou'` e `supersedes_id = <id_original>`.

### 5.4 LLM nunca escreve fatos (§8.8)

O LLM lê dados calculados e responde em linguagem natural com citação obrigatória. Ele **nunca** grava valores no banco. Se LLM responde sem citar fonte → re-check rejeita + retry.

### 5.5 Decimal para dinheiro, nunca float

```python
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
getcontext().prec = 28
valor = (receita * Decimal("0.073")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
```

---

## 6. Como criar uma feature nova (8 passos)

```
1. Ler PlanoBackend.md na seção da sprint
2. Modelar em shared/db/models.py + migration Alembic com RLS policy
3. Criar schemas Pydantic (ConfigDict extra='forbid')
4. Escrever golden tests PRIMEIRO (tests/unit/<módulo>/test_calcula_X.py)
5. Implementar calcula_X.py com algoritmo puro
6. Implementar repo.py (async, sem N+1)
7. Implementar service.py + router.py
8. Rodar: pytest tests/unit tests/eval -q && mypy app/ --strict
```

---

## 7. Comandos do dia-a-dia

```bash
# Rodar apenas os testes do módulo em que estou trabalhando
poetry run python -m pytest tests/unit/lucro_presumido --tb=short -v

# Verificar tipos
poetry run python -m mypy app/ --strict

# Linter
poetry run ruff check app/ tests/

# Ver migrations pendentes
poetry run alembic history | head -10
poetry run alembic current

# Gerar nova migration (revisar SEMPRE antes de aplicar)
poetry run alembic revision --autogenerate -m "sprint_XX_descricao"
```

---

## 8. O que NÃO fazer (atalhos que causam incidentes)

| ❌ Nunca | ✅ Em vez disso |
|---|---|
| `float` em cálculo monetário | `Decimal` com `quantize` |
| `SELECT *` em tabela grande | `select(Model).where(...).options(selectinload(...))` |
| Endpoint sem `Depends(get_session)` | Usar sempre o dep de sessão com RLS |
| Hardcode de alíquota | INSERT em SCD (valid_from/valid_to) |
| LLM gravando valor no DB | Pipeline determinístico grava; LLM só lê |
| `# type: ignore` sem justificativa | Corrigir o tipo ou ADR documentando o porquê |
| `print()` para debug | `structlog.get_logger(__name__).info(...)` |
| `time.sleep` em código async | `await asyncio.sleep(...)` |

---

## 9. Onde pedir ajuda

- **Dúvidas técnicas:** ler `PlanoBackend.md` na seção relevante, depois `docs/adr/` e `docs/decisoes/`
- **Decisão de stack:** se não está no Plano, criar ADR e discutir antes de implementar
- **Bug em produção:** seguir `docs/runbooks/on-call-playbook.md`
- **Dúvida fiscal (DAS, LP, eSocial):** verificar testes golden em `tests/unit/` — eles refletem a legislação
