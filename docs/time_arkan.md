# time_arkan.md — Equipe de Agentes Arkan (devs + business)

> **Status:** FROTA COMPLETA (2026-06-07). **Lotes 1–3 construídos** — infra (settings + `.mcp.json` + CI + hooks + pre-commit), **16 agentes novos** (10 dev/gate + 6 business) e **6 comandos**. Histórico no §14. Falta: **reiniciar a sessão** para ativar os subagentes, e testar.
>
> **Decisões já cravadas pelo dono (2026-06-06):**
> 1. **Autonomia = alta com freios.** Livre no reversível (testes, build, lint, commits locais, leitura); confirmação obrigatória no irreversível/externo (push, deploy, emitir NF-e/eSocial/SPED real, mexer em tabela tributária já seedada). → §2
> 2. **Agente fiscal = propor + passar no gate.** Mudança de alíquota nunca é aplicada cega: gera migration SCD de nova vigência + golden test, roda a suite, e **para para aprovação humana**. → §9
> 3. **Verificação visual de frontend = browser real + Playwright.** O `frontend-verifier` usa `Claude_Preview` + Chrome real + Playwright E2E; o `reviewer` ganha gate visual. → §3
> 4. **MCPs versionados agora:** `Playwright` + `Postgres` (read-only) + `Context7`. GitHub fica pronto-mas-desligado; Sentry/Stripe documentados para depois. → §3
> 5. **Execução:** orquestrador encadeia + comandos slash + CI (base) + **hooks** (gates em eventos da sessão) + **Workflow** (lotes massivos, opt-in). Cron/agendado fica para depois. → §12
>
> Estende a frota de frontend existente (`.claude/agents/README.md`) para uma **frota unificada** (backend + frontend + negócio). Leia junto com `CLAUDE.md` (constituição) e `docs/PlanoBackend.md` (fonte de verdade do backend).

---

## 0. Propósito

Montar uma equipe de subagentes que o dono **roda sob demanda** ("rode o validador fiscal", "atualize a alíquota de INSS 2026", "verifique o front", "rode o pulse de negócio") e que executam validações, testes, atualizações e análises **sem pedir confirmação a cada passo** — porque a confiança vem de **gates automáticos impiedosos**, não da ausência de checagem.

Regra-mãe: **autonomia total no reversível; gate forte + OK humano no irreversível.** Num sistema fiscal multi-tenant, é o próprio projeto que manda isso (princípios §8.2, §8.4, §8.8, §8.12).

---

## 1. Como a frota coordena — "o repositório é o barramento"

Subagentes têm contexto próprio e só devolvem o resultado final ao orquestrador; **não há chat entre eles.** A coordenação é por **arquivos**:

| Canal | Papel | Quem escreve |
|---|---|---|
| `CLAUDE.md` | Constituição (lê-se primeiro) | humano + orquestrador |
| `time_arkan.md` (este) | Índice e contrato da frota | orquestrador |
| `docs/PlanoBackend.md` | Fonte de verdade do backend | humano |
| `log_agente.md` | Livro de passagem do **backend** | agentes de backend |
| `docs/HANDOFF.md` | Livro de passagem do **frontend/design** (append-only) | agentes de frontend |
| `hadoff-front-back.md` | Livro de passagem da **integração front↔back** | dev de integração |
| `docs/negocio/HANDOFF_NEGOCIO.md` | **NOVO** — livro de passagem do **business** | agentes de business |
| `docs/` (vault) | Invariantes: `principios/`, `modulos/`, `sprints/`, `decisoes/`, `pendencias/` | todos (write-back) |

**Sessão principal = orquestrador.** Todo agente faz **write-back obrigatório** no livro certo ao terminar — sem pedir confirmação.

---

## 2. Política de autonomia — "alta com freios"

### 2.1 LIVRE (roda sem confirmação)
- **Leitura sempre:** Read, Grep, Glob.
- **Testes e qualidade:** `pytest`, `mypy`, `ruff`, `bandit`, `poetry run *`, `npm run build|lint|test|format`.
- **DB local:** `alembic upgrade|downgrade|current|history`, `docker compose up|down|ps`.
- **Git local:** `git status|diff|log|add|commit|branch|checkout|switch|stash`.
- **GitHub read:** `gh pr view|list|diff|checks`, `gh run view`.

### 2.2 FREIO (confirmação obrigatória — e por quê)
| Ação | Por quê |
|---|---|
| `git push`, `git reset --hard`, `git rebase`, `--force` | Sai da máquina / reescreve história. |
| Deploy / publish / release | Outward-facing; ato consciente. |
| Emitir NF-e / transmitir eSocial / SPED **reais** | **§8.12** — transmissão é ato consciente do cliente. |
| Chamadas a Focus/SERPRO/Pluggy/Meta em **produção** | Custa dinheiro, efeito no mundo real. |
| `UPDATE`/`DELETE` em linha de tabela tributária seedada | **§8.3 + §8.8** — SCD: sempre INSERT de nova vigência. (DB já tem `REVOKE`; o freio é a 2ª trava.) |
| `rm -rf`, `Remove-Item -Recurse`, deleção em massa | Destrutivo. |
| Editar tokens/`globals.css`/primitivas fora do design-system | Contrato de design Arkan. |

### 2.3 Esboço do `.claude/settings.json`
```jsonc
{
  "permissions": {
    "allow": [
      "Bash(poetry run pytest:*)", "Bash(poetry run python -m pytest:*)",
      "Bash(poetry run mypy:*)", "Bash(poetry run ruff:*)", "Bash(poetry run bandit:*)",
      "Bash(poetry run alembic upgrade:*)", "Bash(poetry run alembic current:*)",
      "Bash(npm run build)", "Bash(npm run lint)", "Bash(npm run test:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status)", "Bash(git diff:*)",
      "Bash(git checkout:*)", "Bash(git switch:*)", "Bash(git branch:*)",
      "Bash(gh pr view:*)", "Bash(gh pr list:*)", "Bash(gh pr diff:*)", "Bash(gh run view:*)"
    ],
    "ask":  ["Bash(git push:*)", "Bash(git reset --hard:*)", "Bash(git rebase:*)", "Bash(gh pr merge:*)", "Bash(gh release:*)"],
    "deny": ["Bash(rm -rf:*)", "Bash(git push --force:*)"]
  }
}
```
> Freios "fiscais" são reforçados **no prompt de cada agente** ("Você NUNCA…") + trava do DB + flags de prod em `app/config.py` (todas `False` por default).

---

## 3. Ferramentas, browser e MCPs (capacidade da frota)

**Princípio (o que torna agentes melhores):** a **menor superfície que o papel exige**. Um gate que pode editar deixa de ser gate; um scout com `Write` vira risco. "Dar liberdade" = a **ferramenta certa no agente certo** + a allow-list ampla do §2 — **não** toda tool em todo agente.

### 3.1 Matriz de ferramentas por agente
Base `RWEGGB` = Read, Write, Edit, Glob, Grep, Bash.

| Agente | Base | Browser | Web | MCP | Read-only |
|---|---|---|---|---|---|
| `backend-scout` | Read,Grep,Glob | — | — | — | ✅ |
| `backend-dev` | RWEGGB | — | WebSearch | Context7 | — |
| `fiscal-validator` | Read,Grep,Glob,Bash | — | — | Postgres(ro) | ✅ parecer |
| `aliquota-smith` | RWEGGB | — | WebFetch | Postgres(ro) | — |
| `migration-smith` | RWEGGB | — | — | Postgres(ro) | — |
| `backend-reviewer` | Read,Grep,Glob,Bash | — | — | Postgres(ro) | ✅ |
| `qa-integration` | Read,Grep,Glob,Bash | — | — | Postgres(ro) | — |
| `ci-engineer` | RWEGGB | — | WebSearch | GitHub¹ | — |
| `security-auditor` | Read,Grep,Glob,Bash | — | — | — | ✅ |
| `frontend-verifier` 🆕 | Read,Grep,Glob,Bash | **Preview + Chrome + Playwright** | — | — | verifica→reporta |
| `reviewer` (front) | Read,Grep,Glob,Bash | **Preview** | — | — | ✅ |
| `screen-implementer` | RWEGGB | Preview (screenshot/console) | — | Context7 | — |
| `compliance-legal-watch` | Read,Write,Grep,Glob | — | WebSearch + WebFetch | — | lê web→propõe |
| `market-research` | Read,Write,Grep,Glob | — | WebSearch + WebFetch | — | lê web→propõe |
| `pricing-cac-forecast` | Read,Write,Grep,Glob | — | WebSearch | — | — |
| `content-fiscal` | Read,Write,Grep,Glob | — | WebSearch | — | — |
| `customer-success` | Read,Write,Grep,Glob,Bash | — | — | Sentry¹ | — |
| `product-analytics` | Read,Write,Grep,Glob,Bash | — | — | Postgres(ro), Sentry¹ | — |

¹ desligado por padrão — liga quando houver credencial/produção.

### 3.2 Browser (verificação visual de frontend)
- **`Claude_Preview`** (já conectado): sobe o dev server e **vê** a página — `screenshot` por rota (confere identidade Arkan: serifa+mono, fios 1px, sem pílula), `console_logs` (erro de hidratação/fetch), `snapshot`/`inspect` (árvore de a11y → "status = cor+ícone+palavra", foco visível), `eval` (checa `prefers-reduced-motion`).
- **Chrome real + Playwright** (decisão do dono): fluxos E2E completos versionados — wizard de emissão de NF, onboarding 5 passos, dark mode. O `frontend-verifier` gera os specs.
- **Freio:** browser aponta **só para `localhost`**; nunca navega autenticado pra fora com dado de tenant (LGPD).

### 3.3 Web (busca/leitura externa)
- `WebSearch`/`WebFetch` **só nos agentes que olham pra fora**: `compliance-legal-watch` (DOU/RFB/CFC), `market-research` (concorrência), `aliquota-smith` (abre a portaria que cita), `backend-dev` (docs de lib).
- **Freio (segurança):** conteúdo web é **não-confiável** (prompt injection). Quem lê web **não age** no mesmo passo — lê → resume → propõe; quem aplica (`aliquota-smith`) recebe o resumo e **passa pelo gate**.

### 3.4 MCPs do projeto — `.mcp.json` versionado
Instalar agora (baixa fricção, alto valor):

```jsonc
{
  "mcpServers": {
    "playwright": { "command": "npx", "args": ["-y", "@playwright/mcp@latest"] },
    "context7":   { "command": "npx", "args": ["-y", "@upstash/context7-mcp"] },
    "postgres": {
      "command": "pipx", "args": ["run", "postgres-mcp", "--access-mode=restricted"],
      "env": { "DATABASE_URI": "postgresql://postgres:postgres@localhost:5434/fiscal" }
    }
  }
}
```
| MCP | Dá | Agente | Caso concreto | Freio |
|---|---|---|---|---|
| **Playwright** (`@playwright/mcp`) | Browser E2E + gera specs | `frontend-verifier` | wizard NF, onboarding, dark mode | só localhost |
| **Postgres MCP Pro** (`crystaldba/postgres-mcp`, `--access-mode=restricted`) | Query read-only + `EXPLAIN` + health de índice | `fiscal-validator`, `qa` | inspeciona SCD (`valid_from`/`valid_to`), RLS, índices de perf | **read-only**; pré-req: DB local de pé |
| **Context7** (`@upstash/context7-mcp`) | Docs atualizadas da versão exata da lib | `backend-dev`, `screen-implementer` | API real de SQLAlchemy 2.0 / FastAPI / Next 15 / Pydantic v2 | read-only |

**Pronto-mas-desligado:** `GitHub MCP` (`github/github-mcp-server`, via `$env:GITHUB_TOKEN`) — PRs/issues/CI inline para `reviewer`/`ci-engineer`. **Depois (com prod):** `Sentry` (`mcp.sentry.dev` — cuidado LGPD com PII), `Redis` (`redis/mcp-redis`), `Stripe` (`@stripe/mcp` — quando o marketplace cobrar de verdade).

**Já conectados (reaproveitar):** `Claude_Preview`, `Claude_in_Chrome`, `Figma`, `scheduled-tasks`/`Cron`, `PushNotification`. **Redundantes (não instalar):** Filesystem e Fetch (já há tools nativas).

---

## 4. Roster — Devs (engenharia)

Modelo: **haiku** = scout · **sonnet** = implementação · **opus** = raciocínio crítico/gate.

### `backend-scout` — batedor read-only do backend  🆕
- **subagente · haiku · `Read, Grep, Glob`**
- **Quando:** "mapeie X no backend", "raio de impacto de Y" — antes de alterar, sem poluir o contexto do orquestrador.
- **Lê:** `CLAUDE.md`, `PlanoBackend.md`, `log_agente.md`, `app/modules/*`. **Escreve:** nada (só o mapa). Read-only absoluto.

### `backend-dev` — implementador de backend  🆕
- **subagente · sonnet · RWEGGB + WebSearch + Context7**
- **Quando:** implementar sprint/feature do `PlanoBackend.md` (`calcula_*` puro → repo → service → schemas → router, TDD golden).
- **Lê:** nota da sprint, nota do módulo, princípios citados, `log_agente.md`. **Escreve:** código + golden + `log_agente.md`.
- **Freios:** ❌ tabela seedada (chama `aliquota-smith`); ❌ integração em prod; ❌ `float`/`Any`; ❌ sessão sem `SET LOCAL app.tenant_id`.

### `fiscal-validator` — validador de cálculos e alíquotas  🆕 ⭐
- **subagente · opus · `Read, Grep, Glob, Bash` + Postgres(ro)**
- **Quando:** "valide o fiscal", após mudança em `calcula_*`/tabela SCD, e como gate no CI.
- **Faz:** roda `tests/unit` + `tests/eval` + `mypy`; cruza valores calculados contra faixas vigentes; sinaliza regressão de alíquota, `ALGORITMO_VERSAO` não bumpada, divergência de centavos.
- **Escreve:** **só parecer** `VERDE/VERMELHO`. Não conserta — reporta.

### `aliquota-smith` — atualizador de tabelas tributárias (SCD)  🆕
- **subagente · opus · RWEGGB + WebFetch + Postgres(ro)**
- **Fluxo (propor + gate):** acha vigência aberta → migration **INSERT nova vigência** (trigger fecha a anterior) → golden test com valores oficiais (cita a fonte) → `alembic upgrade head` → chama `fiscal-validator` → **PARA**, abre PR, aguarda OK humano (não faz merge/push).
- **Freios:** ❌ NUNCA `UPDATE`/`DELETE` em linha existente; ❌ NUNCA hardcoda alíquota; ❌ NUNCA merge/push.

### `migration-smith` — migrations Alembic com RLS  🆕
- **subagente · sonnet · RWEGGB + Postgres(ro)**
- **Faz:** migration 2 fases (nullable+popula → NOT NULL); em tabela de domínio **já inclui RLS policy**. Lê `principios/01-rls-multi-tenant` + `adr-001`. (Pode virar sub-rotina do `backend-dev`; separado por ser ponto de risco.)

### `backend-reviewer` — gate de contexto fresco do backend  🆕
- **subagente · opus · `Read, Grep, Glob, Bash` + Postgres(ro) · read-only**
- **Rubrica (10 princípios):** RLS; fatos imutáveis; SCD; **golden cobrindo cálculo**; citação + re-check; LGPD; **LLM não escreve fato**; idempotência; observabilidade; sem `float`/`Any`; `mypy` verde.
- **Escreve:** veredito no `log_agente.md`. Se REPROVA, nomeia o dono. Nunca corrige.

### `qa-integration` — integração e RLS  🆕
- **subagente · sonnet · `Read, Grep, Glob, Bash` + Postgres(ro)**
- **Faz:** `docker compose up` → `alembic upgrade head` → `pytest tests/integration` (RLS cross-tenant, auth, pipeline). Reporta. Externos só em sandbox.

### `ci-engineer` — pipeline e gates  🆕
- **subagente · sonnet · RWEGGB + WebSearch + GitHub¹**
- **Faz:** `ci.yml` (§8), `.pre-commit-config.yaml`, gates de merge. Hoje **não há CI** (gap nº 1).

### `security-auditor` — segurança e LGPD  🆕
- **subagente · opus · `Read, Grep, Glob, Bash` · read-only**
- **Faz:** `bandit -r app/`, segredos, auditoria RLS, LGPD (AES-256, PII redacted, sa-east-1), exposição de CFOP/CST. Propõe, não corrige.

### `frontend-verifier` — verificação visual/E2E do front  🆕
- **subagente · sonnet · `Read, Grep, Glob, Bash` + Preview + Chrome + Playwright**
- **Quando:** após revestir/alterar tela, antes do merge de frontend, e no CI noturno de E2E.
- **Faz:** sobe dev server, screenshot por rota (gates anti-slop visuais), lê console (hidratação), valida a11y (foco/roles/contraste), roda fluxos E2E (wizard NF, onboarding, dark mode) e **gera os specs Playwright**. Reporta; não conserta lógica.
- **Freio:** só `localhost`; não altera lógica/hook/dados.

### Frontend — **reusa** (não recriar)
`explorer` · `foundation` · `design-system` · `shell` · `screen-implementer` · `motion-polish` · `reviewer` (frota Arkan) + skills `fiscalai-frontend` e `frontend-design-architect`. **Upgrade:** `reviewer` e `screen-implementer` ganham `Claude_Preview` (gate/auto-conferência visual). Feature nova de front segue pela skill `fiscalai-frontend`.

---

## 5. Roster — Business

> Escrevem em `docs/negocio/` + write-back em `docs/negocio/HANDOFF_NEGOCIO.md`. Onde houver skill pronta, **reusa-se a skill**.

- **`market-research`** 🆕 — opus · Read,Write,Glob,Grep + **WebSearch+WebFetch**. Concorrência (Omie/Conta Azul/Bling), features, pricing, pulse mensal. Apoia-se na skill `analista-fiscal-market-research`. Toda afirmação **com fonte**.
- **`pricing-cac-forecast`** 🆕 — opus · Read,Write,Glob,Grep + WebSearch. Pricing (R$49–499 + marketplace 20–30%), elasticidade, CAC/LTV, break-even (~120–150 pagantes), MRR vs custo mês a mês. Lê `PlanoBackend.md` (§custos/metas).
- **`compliance-legal-watch`** 🆕 — opus · Read,Write,Glob,Grep + **WebSearch+WebFetch**. Monitora RFB/CFC/CRC/DOU/Reforma; digest do que afeta produto/disclaimer/alíquota; **abre tarefa pro `aliquota-smith`**. Cobre risco R5/R7.
- **`content-fiscal`** 🆕 — sonnet · Read,Write,Glob,Grep + WebSearch. Conteúdo educacional p/ PME (nunca expõe CFOP/CST cru), WhatsApp digest, copy de onboarding.
- **`customer-success`** 🆕 — sonnet · Read,Write,Glob,Grep,Bash + Sentry¹. Churn, health score, segmentação de uso, playbook onboarding (<2h). **Dep.: telemetria real ainda não existe → opera sobre dados simulados, com a limitação declarada.**
- **`product-analytics`** 🆕 — sonnet · Read,Write,Glob,Grep,Bash + Postgres(ro)/Sentry¹. Adoção por regime/coorte (Fator R, WhatsApp DAU/MAU). **Mesma dependência de telemetria.**

---

## 6. Reuso vs. novo

| Já existe (reusar) | Novo a criar |
|---|---|
| Frota frontend (7) + upgrade visual no `reviewer`/`screen-implementer` | **10 agentes de dev:** backend-scout, backend-dev, fiscal-validator, aliquota-smith, migration-smith, backend-reviewer, qa-integration, ci-engineer, security-auditor, **frontend-verifier** |
| Skills: `fiscalai-backend/frontend`, `analista-fiscal-br`, `frontend-design-architect`, `analista-fiscal-market-research` | **5 agentes de business** + `market-research` (wrapper) |
| Comando `/fechar-sprint` | Comandos `/validar-fiscal`, `/atualizar-aliquota`, `/verificar-front`, `/revisar-pr`, `/ci`, `/pulse-negocio` |
| MCPs já conectados (Preview, Chrome, Figma, Cron) | `.claude/settings.json` · `.mcp.json` (Playwright+Postgres ro+Context7) · `.github/workflows/ci.yml` · `docs/negocio/` |

---

## 7. Comandos slash

| Comando | Dispara | Faz |
|---|---|---|
| `/validar-fiscal [modulo?]` | `fiscal-validator` | Golden + eval + mypy; veredito VERDE/VERMELHO. |
| `/atualizar-aliquota [tributo] [ano]` | `aliquota-smith` → `fiscal-validator` | Migration SCD nova vigência + golden, roda suite, **para para aprovação**. |
| `/verificar-front [rota?]` | `frontend-verifier` | Sobe o app, screenshot + console + a11y + E2E. |
| `/revisar-pr` | `backend-reviewer` ou `reviewer` (pelo diff) | Gate de contexto fresco no diff. |
| `/ci` | `ci-engineer` | Cria/atualiza pipeline e pre-commit. |
| `/pulse-negocio` | `market-research` + `pricing-cac-forecast` + `compliance-legal-watch` | Digest mensal consolidado. |
| `/fechar-sprint [n]` | (já existe) | Gates + roadmap + write-back. |

---

## 8. CI/CD proposto (`.github/workflows/ci.yml`)

```yaml
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres: { image: pgvector/pgvector:pg16, env: { POSTGRES_PASSWORD: postgres }, ports: ["5434:5432"] }
      redis:    { image: redis:7.4, ports: ["6379:6379"] }
    steps:
      - uses: actions/checkout@v4
      - run: pipx install poetry && poetry install --with dev
      - run: poetry run alembic upgrade head
      - run: poetry run python -m pytest tests/unit tests/eval --tb=short   # golden = barreira
      - run: poetry run python -m mypy app/
      - run: poetry run ruff check .
      - run: poetry run bandit -r app/ -c pyproject.toml
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd analista-fiscal-web && npm ci && npm run build && npm run lint
      # E2E Playwright (frontend-verifier) entra como job opcional quando estabilizar
```
**Merge bloqueado** se qualquer job falhar. `tests/integration` (Docker pesado) roda só no merge para `main`.

---

## 9. Fluxo crítico — atualização de alíquota (propor + gate)

```
[portaria nova / DOU]
   → compliance-legal-watch detecta  → abre tarefa
   → /atualizar-aliquota INSS 2026
   → aliquota-smith:
       1. acha vigência aberta (valid_to IS NULL)
       2. migration INSERT nova vigência (trigger fecha a anterior)  — nunca UPDATE
       3. golden test com valores oficiais (cita a portaria)
       4. alembic upgrade head (local) + chama fiscal-validator
   → fiscal-validator: VERDE/VERMELHO
       — VERMELHO → volta pro aliquota-smith
       — VERDE → PARA: PR aberto, aguarda OK humano (sem merge/push)
   → [humano aprova] → merge → write-back: log_agente + pendência "tabelas 2026" resolvida
```
Respeita §8.3 (SCD), §8.4 (golden), §8.8 (LLM não escreve fato).

---

## 10. Write-back (DoD de todo agente)

Ao terminar qualquer etapa, registra — sem pedir confirmação: **data · agente · o que fez · arquivos · pendências · próximo agente.**
Backend → `log_agente.md` (+ vault). Frontend → `docs/HANDOFF.md`. Integração → `hadoff-front-back.md`. Business → `docs/negocio/HANDOFF_NEGOCIO.md`.

---

## 11. Ordem de construção (recomendada)

**Lote 1 — Espinha dev + gates fiscais** (destrava "testar alíquota no pipeline sem olhar")
`.claude/settings.json` · `.mcp.json` (Postgres ro + Context7 + Playwright) · `.github/workflows/ci.yml` · `backend-scout` · `backend-dev` · `fiscal-validator` · `backend-reviewer` · `aliquota-smith` · comandos `/validar-fiscal`, `/atualizar-aliquota`.

**Lote 2 — QA / infra / segurança + verificação visual**
`migration-smith` · `qa-integration` · `ci-engineer` · `security-auditor` · `frontend-verifier` · upgrade visual do `reviewer`/`screen-implementer` · `.pre-commit-config.yaml` · **hooks** (`settings.json`: gate pré-commit, auto-lint/golden pós-edição, lembrete de write-back) · comandos `/revisar-pr`, `/ci`, `/verificar-front`.

**Lote 3 — Business**
`docs/negocio/` + `HANDOFF_NEGOCIO.md` · `pricing-cac-forecast` · `compliance-legal-watch` · `content-fiscal` · `customer-success` · `product-analytics` · `market-research` · comando `/pulse-negocio`.

Cada lote fecha com: arquivos criados + tabela "Quem é quem" atualizada no `.claude/agents/README.md` + write-back.

Os **workflows nomeados** (§12.2) são escritos depois que os agentes existem (fim do Lote 2/3) e disparados sob demanda.

---

## 12. Modos de execução — como a frota roda sozinha

Você **não chama um agente por vez** (isso é só o modo manual de debug). O que dispara a frota:

| Modo | Gatilho | Você presente? | Uso na frota |
|---|---|---|---|
| Orquestrador encadeia | você dá o objetivo ("implemente a sprint 13") | sim, só o objetivo | a sessão roteia `scout → dev → fiscal-validator → reviewer` sozinha |
| Comando slash | `/atualizar-aliquota INSS 2026` | sim, 1 linha | pipelines repetidos (§7) |
| **Hook** ✅ | evento da sessão (editou `.py`, vai commitar) | sim, automático | gates determinísticos sem você lembrar |
| **Workflow** ✅ | "use uma workflow" (opt-in) | sim, roda em background + notifica | auditorias/migrações massivas |
| CI (Actions) | push/PR | **não** | gates de merge (§8) |
| Cron/agendado | horário | **não** | — futuro (não agora) |

A frota roda sozinha **tudo que é reversível**; ao bater num freio (PR de alíquota, NF a emitir) ela chama `PushNotification` e **para esperando seu OK**. "Sem olhar" = sem micro-gerenciar, com você no loop só no irreversível.

### 12.1 Hooks — gates automáticos em eventos (`.claude/settings.json` + `.pre-commit-config.yaml`)
Hooks rodam **comandos determinísticos** (lint/test/mypy) e podem **bloquear** uma ação — eles **não invocam subagentes**, automatizam os *gates*:
- **PreToolUse em `git commit`** → `pytest tests/unit` + `mypy app/`; **bloqueia** se vermelho (reforça "nunca commitar sem pytest+mypy" do `CLAUDE.md`).
- **PostToolUse em Edit/Write de `*.py`** → `ruff --fix` no arquivo; se for `calcula_*.py`, roda o golden do módulo e acusa regressão na hora.
- **Stop / SubagentStop** → confere o write-back: se o agente terminou sem atualizar `log_agente.md`/`HANDOFF.md`, injeta lembrete.
> Construídos com a skill `update-config`. Três camadas do mesmo gate: hook (sessão) + `.pre-commit` (git) + CI (servidor).

### 12.2 Workflows nomeados — lotes massivos sob demanda (`.claude/workflows/`)
Fan-out determinístico de muitos agentes em paralelo, com verificação adversarial. **Opt-in** (pode gastar muitos tokens): só disparo quando você diz "use a workflow X". Candidatos da casa:
- **`auditar-calculos`** — os 29 `calcula_*` em paralelo: cada um validado contra a legislação + golden, com 2–3 céticos tentando refutar o resultado, e síntese das divergências. (a forma mais forte de testar todas as alíquotas de uma vez)
- **`auditar-rls`** — toda tabela de domínio checada por policy RLS + teste de isolamento cross-tenant.
- **`verificar-todas-telas`** — `frontend-verifier` nas 48 rotas em paralelo: screenshot + console + a11y, relatório único.
- **`revisar-pr-multidim`** — o diff revisado em paralelo por dimensão (correção/perf/segurança/fiscal/a11y), cada achado verificado adversarialmente antes de entrar no parecer.

### 12.3 Quem invoca subagente vs. quem roda gate
- **Subagentes** (scout, dev, validator…) → invocados pelo **orquestrador**, por **comando** ou por **workflow**.
- **Gates determinísticos** (lint/test/mypy) → rodam por **hook**, **pre-commit** e **CI**, sem precisar de agente.
São as duas metades de "rodar sozinho": fan-out de inteligência (agentes) + barreira automática (gates).

---

## 13. Decisões em aberto (confirmar)

1. **Por onde começar a construção** — recomendo Lote 1.
2. **`migration-smith` separado** do `backend-dev`? — recomendo separado (risco RLS).
3. **`customer-success` e `product-analytics` sem telemetria** — operam sobre dados simulados até existir instrumentação. OK começar assim (limitação declarada) ou adiar os dois?
4. **`GitHub MCP`** — ligar agora (preciso do `$env:GITHUB_TOKEN`) ou deixar pronto-mas-desligado? — recomendo desligado até você gerar o PAT.
5. **`.claude/settings.json` e `.mcp.json`** versionados no repo (frota reproduzível) — recomendo sim.

---

## 14. Histórico de construção

- **2026-06-06 · Lote 1 (espinha dev + gates fiscais)** — criados: `.claude/settings.json` (allow-list alta-com-freios), `.mcp.json` (Playwright + Postgres ro + Context7), `.github/workflows/ci.yml` (jobs backend-quality + backend-integration + frontend); agentes `backend-scout`, `backend-dev`, `fiscal-validator`, `aliquota-smith`, `backend-reviewer`; comandos `/validar-fiscal`, `/atualizar-aliquota`; registro nos índices (`CLAUDE.md`, `docs/README.md`, `.claude/agents/README.md`). **Notas:** os subagentes só ficam ativos após **reiniciar a sessão** (ou `/agents`); o MCP `postgres` exige `docker compose up` + `uvx` instalado; no Windows o `.mcp.json` pode precisar de `cmd /c` antes de `npx`/`uvx`. **Próximo:** Lote 2.

- **2026-06-06 · Lote 2 (QA/infra/segurança + verificação visual)** — agentes `migration-smith`, `qa-integration`, `ci-engineer`, `security-auditor`, `frontend-verifier`; comandos `/revisar-pr`, `/ci`, `/verificar-front`; `.pre-commit-config.yaml`; hook **`.claude/hooks/command-guard.ps1`** (freios robustos Bash+PowerShell via `PreToolUse` no `settings.json`). **Correção de ambiente:** a Bash tool retorna exit 1 vazio para subagentes neste Windows → todos os agentes que rodam comando passaram a usar **`PowerShell`**; `reviewer`/`screen-implementer` ganharam `Claude_Preview`. **Pendência:** os agentes de frontend `foundation`/`design-system`/`shell`/`motion-polish` ainda têm `Bash` — trocar quando o frontend for retomado. **Próximo:** Lote 3.

- **2026-06-07 · Lote 3 (business)** — agentes `market-research`, `pricing-cac-forecast`, `compliance-legal-watch`, `content-fiscal`, `customer-success`, `product-analytics`; comando `/pulse-negocio`; estrutura `docs/negocio/` + `HANDOFF_NEGOCIO.md`. `customer-success`/`product-analytics` operam sobre dados simulados até existir telemetria (limitação declarada nos prompts). **Frota completa: 16 agentes novos + 6 comandos.**

---

> **Próximo passo:** **reiniciar a sessão** para ativar os 16 subagentes + o hook guard + aprovar os MCPs. Depois validar com `/validar-fiscal`, `backend-scout`, `security-auditor` (roteiro de teste). Pendências menores: trocar `Bash→PowerShell` nos 4 agentes de frontend restantes; commitar os 3 lotes quando quiser.
