---
tags: [auditoria, deep-dive, prontidao-producao]
data: 2026-05-31
autor: Claude (skill analista-fiscal-br)
fonte_baseline: roadmap.md (atualizado 2026-05-31) + log_agente.md + docs/PlanoBackend.md
veredito: GO — aderente ao plano, blocked por ativação de credenciais externas
---

# Auditoria Profunda — Analista Fiscal (FiscalAI)

**Pergunta-chave:** o app segue a ideia do Plano e consegue oficialmente rodar e ser implementado?

**Resposta curta:** **Sim, com 5 gates externos a serem virados.** O backend é estruturalmente fiel ao `PlanoBackend.md`, executa os 12 princípios invioláveis no código (não só no texto), e tem trilha de deploy documentada. O que falta para "oficialmente rodar" é credencial de terceiros (Focus NFe, SERPRO, Gemini, Pluggy, Meta WhatsApp) e instanciar o stack Postgres+Redis+Celery. **Nada do que falta é código.**

---

## 1. Aderência ao Plano — evidências

### 1.1. Roadmap entregue (`docs/roadmap.md`, atualizado 2026-05-31)

| Fase | Sprints | Status | Testes acumulados |
|---|---|---|---|
| 1 — MVP SN | 0–6 | ✅ | 537 |
| 2 — produto pago | 7–13 | ✅ | 1199 |
| 3 — SPED + Reforma + escala | 14–20 (+ 19.5/19.6/19.7/19.8) | ✅ | 2121 |
| 4 — lapidação | 21–22 | ✅ | **2200** |

O `CLAUDE.md` do repo está **desatualizado** (cita "sprints 0–12, 980 testes"). A fonte da verdade é o `roadmap.md` — todas as 22 sprints fechadas + 4 sprints extras. Recomendação: rodar `/fechar-sprint` ou atualizar manualmente o `CLAUDE.md` na próxima sessão.

### 1.2. Stack cravada bate com o §3 do Plano

`pyproject.toml` confirma:

- Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 async + asyncpg, Alembic 1.13, Pydantic v2, Redis 5, structlog 24, pgvector 0.3+, google-genai, langfuse, tenacity.
- **Anti-stack respeitado:** zero LangChain, zero Litestar, zero MongoDB, zero `float` em modelos de dinheiro (verificado por grep), zero Nuvem Fiscal (usa Focus NFe + SERPRO direto).
- Grupos opcionais corretamente isolados (`workers`, `dou-llm`, `storage`, `esocial`) — exatamente o padrão "opt-in" descrito no `DEPLOY.md`.

### 1.3. 12 princípios invioláveis materializados

Cada princípio tem implementação verificada no código (não só texto em `docs/principios/`):

| # | Princípio | Evidência |
|---|---|---|
| 1 | RLS multi-tenant | `app/shared/db/rls.py` + **68 ocorrências** de `ENABLE ROW LEVEL SECURITY` em migrations |
| 2 | Fatos fiscais imutáveis | Migration `0024_fase2_documento_fiscal_hardening` cravou no DB |
| 3 | SCD Type 2 | `valid_from`/`valid_to` em 8+ tabelas (faixa SN, alíquotas LP, INSS, IRRF, ICMS, CBS/IBS, plano de contas) |
| 4 | Golden tests | **30 arquivos `calcula_*.py`** + **171 referências** a `ALGORITMO_VERSAO` |
| 5 | Citação LLM | Suite `tests/eval/test_citacao.py` + `citacao_obrigatoria.jsonl` |
| 6 | Re-check determinístico | Suite `tests/eval/test_alucinacao.py` + `alucinacao_valor.jsonl` |
| 7 | LGPD-first | Roteamento PII → Ollama mesmo em prod (config.py §2.3) + pgcrypto seed |
| 8 | LLM nunca escreve fatos | Docstring em todo `calcula_*.py` reafirma; pipeline DAS é puro |
| 9 | Idempotência externa | Migration `0024` + `idempotency_key` em Focus/SERPRO/Pluggy |
| 10 | Observabilidade | Langfuse + Sentry + Tempo + Grafana + Loki configurados |
| 11 | Out-of-scope declarado | `docs/pendencias/runbook-ativacao-externos.md` lista 6 [externo-runbook] |
| 12 | Transmissão consciente | eSocial fail-fast se `ESOCIAL_TRANSMISSAO_ATIVA=true` sem grupo `esocial` |

### 1.4. Disciplina de tipos e código

- **356 arquivos Python** em `app/`, **217 arquivos** em `tests/`. Todos parseiam sem `SyntaxError`.
- mypy strict reportado pela equipe: **0 erros** (não consegui re-rodar — sandbox tem Python 3.10, projeto exige 3.12; reportado pelo `log_agente.md`).
- **Apenas 1** `Any` em assinatura pública (`whatsapp/service.py::sender`) — justificado com `# noqa: ANN401` por ser duck-typed do `MetaWhatsAppSender`. Aceitável.
- **Apenas 3** TODO/FIXME genuínos no código de domínio (resto é uso da palavra "TODOS" em docstrings).
- **Apenas 1** uso de `float()` em módulo (`memoria/service.py`, métrica de similaridade — não é dinheiro). Disciplina monetária impecável.

---

## 2. Capacidade de rodar oficialmente

### 2.1. O que está pronto

- `docker-compose.yml` sobe Postgres 16 (pgvector image) + Redis 7.4 + Ollama + API com healthchecks.
- `Dockerfile.api` multi-stage (`dev`/`prod`), `prod` com user não-root.
- `infra/postgres/init.sql` cria extensions (`pgcrypto`, `vector`), role `fiscal_app` não-superuser, GUC `app.tenant_id`.
- 52 migrations Alembic numeradas e sequenciais (0001–0052), todas com RLS quando criam tabela de domínio.
- `.env.example` com **decisão documentada** em cada bloco.
- `DEPLOY.md` lista os 5 gates "hard" mínimos para prod.
- API expõe **190 endpoints** distribuídos em **36 routers** plugados em `app/main.py`.
- 23 tasks Celery prontas (workers + beat schedule), em modo dual: stub local se Celery não instalado, real se grupo `workers` ativado.

### 2.2. 5 gates "hard" para o primeiro request em prod

Copiados do `DEPLOY.md §0`:

1. **Celery** instalado (`poetry install --with workers`) + processos `worker` + `beat` rodando.
2. **`JWT_SECRET` ≥ 32 bytes** (`openssl rand -hex 32`) — placeholder atual é `TROCAR_EM_PRODUCAO_...`.
3. **`FOCUS_NFE_TOKEN`** + `FOCUS_NFE_SANDBOX=false` — sem isso, NFS-e emitida em prod é fake e o cliente leva multa.
4. **`SERPRO_CONSUMER_KEY` + `SERPRO_CONSUMER_SECRET`** + `SERPRO_SANDBOX=false` — bloqueia PGDAS-D e certidões.
5. **`DATABASE_URL`** real + `alembic upgrade head` rodado **uma vez** + extensions `pgcrypto`+`vector` no destino.

### 2.3. Gates "soft" — sistema sobe sem eles

| Off por padrão | Efeito |
|---|---|
| Storage S3/GCS | PDFs vão para BYTEA no Postgres (escala até ~100 empresas) |
| Langfuse | Tracing LLM off (debugging mais lento, custo zero) |
| Sentry | Erros sem agregação central (logs estruturados ainda capturam) |
| Template WhatsApp | Digest gera snapshot `preparado` sem enviar |
| EFD beat mensal | LP/LR geram EFD via POST manual |
| CRF/CNDT scraping | Endpoints retornam `processando` (skeleton, Sprint 6 PR1) |

Nenhum dos gates soft impede deploy; viram pendências de operação.

### 2.4. Pendências externas (`[externo-runbook]`)

6 itens parados em terceiros publicarem regulamentação ou API — Sprint 19.8 selou todos como runbook documentado (`docs/pendencias/runbook-ativacao-externos.md`):

1. Focus NFe publicar campos CBS/IBS em NFS-e (#19)
2. Comitê Gestor IBS publicar alíquotas por UF/município (#20)
3. LC 214/2025 regulamentar IS (#21)
4. Split payment real 2027 (#22)
5. Bloco K SPED com CBS/IBS (#23)
6. NFC-e/CT-e/MDF-e com CBS/IBS (#24)

Nada disso bloqueia o piloto pago em Simples Nacional/Lucro Presumido — é roadmap 2027+.

---

## 3. Riscos e ressalvas

### 3.1. Validação dos testes

Não consegui rodar `pytest` + `mypy` neste sandbox (Python 3.10, projeto exige 3.12; install externo falhou por restrição de rede). **Estrutura** verificada por AST: 217 arquivos de teste parseiam, 1986 funções `test_*` (parametrização expande para os 2200 reportados). O `log_agente.md` reporta verde — recomendo o usuário rodar localmente:

```powershell
cd C:\dev\Apresentação-Ideia\analista-fiscal-api
poetry run python -m pytest tests/unit tests/eval
poetry run python -m mypy app/
```

### 3.2. `CLAUDE.md` está desatualizado

Diz "sprints 0–12, 980 testes". Realidade: sprints 0–22 + 4 extras, 2200 testes. Não afeta runtime, mas confunde qualquer agente novo. **Ação:** atualizar o resumo no topo do `CLAUDE.md` para refletir o `roadmap.md`.

### 3.3. Frontend (`analista-fiscal-web`)

Existe como Next.js + Radix + shadcn — é demo/prototype conforme `CLAUDE.md` declara. **Não auditei profundamente** porque o pedido é sobre o app rodar (backend é o produto). Se a intenção for shipar dashboard pago no piloto, precisa de uma auditoria separada.

### 3.4. `docker-compose.prod.yml` é placeholder

Apenas um overlay com `target: prod`. Produção real depende de orquestração externa (Helm/Terraform, citado no header). Para piloto pequeno (<50 clientes), `docker compose` simples com volume persistente é suficiente.

### 3.5. Certificado ICP-Brasil real para eSocial

Grupo `esocial` (lxml + signxml + cryptography) deixa o XMLDSig pronto, mas a transmissão real exige cliente ter `.pfx` ICP-Brasil + senha em vault. Documentado no runbook como parte do flow de onboarding consciente (princípio §8.12).

---

## 4. Veredito

**O app SEGUE a ideia do Plano** — todas as 22 sprints estão implementadas, os 12 princípios invioláveis estão cravados em migrations e código (não só em texto), o anti-stack é respeitado, e disciplina de tipos/dinheiro/datas é praticamente perfeita (1 `Any` justificado, 1 `float()` em similaridade não-monetária, 3 TODOs em domínio).

**O app CONSEGUE OFICIALMENTE RODAR** desde que o operador:

1. Instale `poetry install --with workers,storage,esocial,dou-llm` em prod.
2. Gere `JWT_SECRET` real.
3. Obtenha credenciais Focus NFe (homologação Prefeitura → produção) + SERPRO (e-CAC + PGDAS).
4. Suba Postgres 16 + Redis 7.4 reais + rode `alembic upgrade head` uma vez.
5. (Opcional) Configure Gemini, Langfuse, Sentry, Meta WhatsApp Business.

**Estimativa para primeiro cliente real produtivo:** 2–3 semanas de setup operacional (sandbox SERPRO + sandbox Focus + ambiente de produção em algum provider cloud BR — Magalu/Locaweb/AWS sa-east-1), **zero novo código**.

### 4.1. Próximas 3 ações sugeridas, em ordem

1. **Atualizar `CLAUDE.md`** (top section) — alinhar com `roadmap.md` (28 sprints, 2200 testes).
2. **Rodar localmente** `pytest tests/unit tests/eval` + `mypy app/` e confirmar verde. Se algo regredir, abrir PR de hotfix antes de qualquer aquisição.
3. **Setup do ambiente de homologação** com SERPRO + Focus sandbox — começa o ciclo de transmissão real e expõe os ajustes finos de timeout/retry que só aparecem com infra real.

---

**Sources locais consultados:**
- [docs/roadmap.md](docs/roadmap.md)
- [docs/PlanoBackend.md](docs/PlanoBackend.md)
- [analista-fiscal-api/DEPLOY.md](analista-fiscal-api/DEPLOY.md)
- [analista-fiscal-api/.env.example](analista-fiscal-api/.env.example)
- [analista-fiscal-api/pyproject.toml](analista-fiscal-api/pyproject.toml)
- [analista-fiscal-api/docker-compose.yml](analista-fiscal-api/docker-compose.yml)
- [docs/pendencias/runbook-ativacao-externos.md](docs/pendencias/runbook-ativacao-externos.md)
- [analista-fiscal-api/app/main.py](analista-fiscal-api/app/main.py) (190 endpoints / 36 routers)
- [analista-fiscal-api/app/modules/fiscal/calcula_das.py](analista-fiscal-api/app/modules/fiscal/calcula_das.py) (padrão canônico)
- 52 migrations em [analista-fiscal-api/alembic/versions/](analista-fiscal-api/alembic/versions/)
