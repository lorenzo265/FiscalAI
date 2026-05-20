---
tags: [review, checklist, qualidade, rubrica]
fonte: "[[PlanoBackend]] §8 + CLAUDE.md"
uso: "Rubrica de auto-review do diff antes de declarar PR pronto"
---

# ✅ Review checklist — rubrica de PR

> Rubrica derivada dos 12 [[README|princípios invioláveis]]. **Rodar contra o diff antes de declarar o PR pronto.** Qualquer item ❌ bloqueia merge igual a teste vermelho.
>
> Uso com o agente: *"Revise este diff contra `docs/review-checklist.md` — marque cada item ✅/❌/N/A e justifique os ❌."*

---

## 🔒 Multi-tenant & dados

- [ ] Toda tabela de domínio nova tem `tenant_id NOT NULL` + RLS policy na migration. → [[principios/01-rls-multi-tenant]]
- [ ] Nenhuma sessão SQLAlchemy abre sem `SET LOCAL app.tenant_id`. → [[principios/01-rls-multi-tenant]]
- [ ] Cancelamento/alteração de fato gera **nova linha** (`supersedes`/`evento`), nunca `DELETE`/`UPDATE` destrutivo. → [[principios/02-fatos-imutaveis]]
- [ ] Alíquota/tabela tributária só muda via `INSERT` de nova vigência (`valid_from`/`valid_to`). Zero hardcode. → [[principios/03-scd-type-2]]

## 🧮 Cálculo fiscal

- [ ] Todo `calcula_*.py` é puro, Decimal-safe e carrega `ALGORITMO_VERSAO`. → [[principios/04-golden-tests]]
- [ ] Há golden test cobrindo o cálculo e ele bloqueia merge. → [[principios/04-golden-tests]]
- [ ] Dinheiro é `Decimal` + `quantize(ROUND_HALF_EVEN)`, persistido em `NUMERIC(14,2)`. **Zero `float`.** → [[principios/03-scd-type-2]]
- [ ] Cálculo histórico usa a vigência da **data do fato**, não a mais recente. → [[principios/03-scd-type-2]]

## 🤖 LLM / IA

- [ ] Resposta LLM passa pelo validador de citação (sem citação → reject). → [[principios/05-citacao-llm]]
- [ ] Valores/datas/CNPJs da resposta passam por re-check determinístico (regex) contra os fatos. → [[principios/06-recheck-deterministico]]
- [ ] LLM apenas **lê** grafo/apurações; nenhum fato é persistido por caminho do LLM. → [[principios/08-llm-nao-escreve-fatos]]
- [ ] Tema out-of-scope (Tier 3) é **encaminhado ao marketplace**, nunca respondido. → [[principios/11-out-of-scope]]

## 🔌 Integrações & infra

- [ ] Todo `POST` a Focus/SERPRO/Pluggy usa `idempotency_key`; retry reusa a mesma key. → [[principios/09-idempotencia]]
- [ ] Logging é `structlog` estruturado (Decimal → str). **Zero `print()`.** → [[principios/10-observabilidade]]
- [ ] CNPJ/CPF/email são redacted antes de chegar ao Loki. → [[principios/10-observabilidade]] · [[principios/07-lgpd-first]]
- [ ] Dado pessoal: AES-256 em repouso, território nacional, consentimento versionado. → [[principios/07-lgpd-first]]
- [ ] Transmissão ao Fisco respeita o modelo de certificado correto (escritório vs. cliente). → [[principios/12-transmissao-consciente]]

## 🧰 Mecânica de código (mypy strict)

- [ ] Zero `Any` / `dict[str, Any]` em contrato público de service/router.
- [ ] `from __future__ import annotations` em arquivos com type hints; imports absolutos a partir de `app.`.
- [ ] Datas sempre aware (`ZoneInfo("America/Sao_Paulo")`).
- [ ] Módulo segue o padrão: `calcula_*` puro → `repo` → `service` (DI) → `router` thin → `schemas` (`extra="forbid"` em inputs).
- [ ] Nenhuma dependência banida adicionada (LangChain, Litestar, MongoDB, etc.).

## 🚪 Portões finais

- [ ] `poetry run python -m pytest tests/unit tests/eval` verde.
- [ ] `poetry run python -m mypy app/` sem erros.
- [ ] Sprint do Plano respeitada (sem pular, sem escopo extra não documentado).

## 🔁 Write-back (Definition of Done)

- [ ] `log_agente.md` atualizado (contagem de testes + o que entrou).
- [ ] Pendências resolvidas marcadas `status: resolvida` em [[dashboard|docs/pendencias]].
- [ ] Decisão nova → ADR em `docs/decisoes/`; módulo/sprint novos linkados no [[README]].
- [ ] Nenhum `[[link]]` vermelho introduzido sem confirmar.

---

Relacionado: [[README]] · [[dashboard]] · [[PlanoBackend]] §8
