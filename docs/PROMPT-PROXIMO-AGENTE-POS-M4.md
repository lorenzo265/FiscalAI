# Prompt do próximo agente — Pendências pós-M4 (Arkan)

**Escrito por:** orquestrador (claude-opus-4-8), 2026-06-29 · **Estado base:** `origin/main @ 3c7d65d`

Você é o **orquestrador** de um sistema fiscal-contábil multi-tenant para PMEs brasileiras (Arkan, ex-FiscalAI). Leia a `CLAUDE.md` da raiz PRIMEIRO. Este documento te dá o contexto para **continuar de onde paramos** sem reler a sessão inteira.

---

## 0. COMO OPERAR — freios e gates (NÃO PULE)

### Freios do PO (Lorenzo) — invioláveis sem "ok" explícito dele
NUNCA, sem autorização explícita do PO **na conversa**:
- `git push` / merge remoto · deploy · transmissão fiscal real (eSocial/Reinf/NFe) · cobrança real (Stripe) · alteração de alíquota/tabela tributária **seedada**.

**Fluxo correto:** trabalhe em **branch** (worktree se for paralelizar) → valide tudo → consolide na `main` por **fast-forward LOCAL** → **PERGUNTE antes de `git push`**. Cada push é uma autorização própria (não vale "liberei o anterior"). Mensagens de commit terminam com `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

> Nota prática: o classificador de segurança bloqueia push se a autorização for ambígua. Peça um "pode pushar" claro.

### Gates obrigatórios antes de declarar um PR pronto
- **Backend:** rode o subagente **`backend-reviewer`** (contexto fresco) sobre o diff ANTES do merge. Gate verde = `pytest tests/unit tests/eval` + `mypy app/` + `ruff check .`.
- **Frontend:** subagente **`reviewer`** (contexto fresco) + `npm run type-check` (`tsc --noEmit`) + `npm run build`.
- Endereçe as ressalvas do reviewer **antes** de consolidar (mesmo as 🟡 — pelo menos corrija comentários enganosos).

### Write-back obrigatório (sem pedir confirmação)
- Backend → `log_agente.md` (raiz): contagem de testes + o que entrou + pendências.
- Frontend → `docs/HANDOFF.md` (append-only): data · agente · o que fez · arquivos · pendências · próximo.
- Memória do orquestrador em `~/.claude/projects/.../memory/` (índice em `MEMORY.md`).

### Skills
Backend → `fiscalai-backend` · Frontend feature → `fiscalai-frontend` · Design/identidade → `frontend-design-architect`.
⚠️ **A skill `fiscalai-frontend` está DESATUALIZADA no tema:** ela descreve um dark/neon. O app está em **"Arkan Claro" (light v2)** — tokens `--color-ink` / `--color-paper` / `--color-green` / `--font-serif`. NÃO volte ao dark. As 5 leis de UX dela seguem válidas.

---

## 1. AMBIENTE — lições operacionais (poupam horas)

- **Shell varia por sessão** (PowerShell + Bash/Git Bash). Prefira caminhos absolutos.
- **Poetry** (Device Guard bloqueia `poetry.exe` direto):
  ```bash
  export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"
  cd "C:/dev/Apresentação-Ideia/analista-fiscal-api"
  ```
- **DB Postgres:** `localhost:5434` (container `fiscal_postgres`, DSN `fiscal:fiscal@localhost:5434/fiscal`). **SUBIU nesta sessão e está `healthy`** → você PODE rodar integração (`pytest tests/integration`), migrations reais (`alembic upgrade head`) e o MCP `postgres`. Subir: `cd analista-fiscal-api && docker compose up -d postgres redis`.
- **Celery é opt-in** (grupo `--with workers`, **não instalado** no env dev) → tasks rodam em **stub mode** (`enqueue` = no-op; `_beat_schedule()` retorna `{}`). O registro de tasks (`include` dinâmico em `celery_app._descobrir_modulos_tasks`) JÁ foi corrigido — em prod com Celery as 21 tasks registram.
- **O path do projeto tem acento** (`Apresentação-Ideia`) — cuidado em scripts/regex.
- **Frontend é real-backend-first** (NÃO mock): `src/lib/api/*` → `src/lib/http.ts` (`fetchJson`, com timeout/retry) → backend `:8000` via `NEXT_PUBLIC_API_BASE_URL`. JWT real no localStorage. Verificação em browser exige o backend `:8000` de pé.
- **Comandos de gate:**
  ```bash
  # backend
  poetry run python -m pytest tests/unit tests/eval -q   # ~36s, 2782 passed/3 skip
  poetry run python -m mypy app/                          # 0 erros / 388 arq
  poetry run ruff check .
  poetry run python -m pytest tests/integration           # precisa do DB :5434 (agora UP)
  # frontend
  cd analista-fiscal-web && npm run type-check && npm run build
  ```

---

## 2. ESTADO ATUAL — `origin/main @ 3c7d65d` (2026-06-29, PUSHADO)

Backend **sprints 0–22 completas**. Marcos de produção (PLANO_GO_LIVE) e pontas soltas, **todos feitos e pushados**:

| Bloco | Entregue |
|---|---|
| **M1** | observabilidade (Sentry/Prometheus/correlation-id) + Celery worker/beat (Dockerfiles + compose.prod) + CI hardening |
| **M2** | billing Stripe (`app/modules/billing`, webhook idempotente, `_FakeBillingProvider`) |
| **M3** | LGPD (`/lgpd/exportar`+`/excluir`), AES-256-GCM PII, refresh token rotação, security headers, Gitleaks |
| **M4** | storage S3 p/ SPED · EFD-Reinf→SERPRO · e-mail transacional (provider+templates+task) · Dockerfile front |
| **Pontas soltas front** | logout, robustez (timeout/retry no fetch, `error.tsx`), e fiação §3.3 (PUT empresa, e-CAC, monitor RFB, Reforma CBS/IBS) |
| **E-mail nos fluxos** | onboarding (auth), fatura (billing webhook), alerta fiscal (worker agendado `agenda.alertar_vencimentos`) |
| **Fix Celery** | `include` dinâmico → as 21 tasks registram no worker |

**Métricas:** 2782 unit+eval (3 skip) · 36 integração · mypy 0/388 · ruff verde · front tsc/build verde.

---

## 3. PENDÊNCIAS — o trabalho que sobra (priorizado)

> Fonte canônica do mapa de pontas soltas: **`docs/auditoria-pontas-soltas-be-fe.md`** (§3.2 módulos órfãos, §3.4 lacunas). O roadmap de produção: **`docs/PLANO_GO_LIVE.md`**.

### 3a. Ativações de OPS do PO (NÃO-código — você não faz, mas lembra o PO)
Tudo já está atrás de env/flag; **no dia em que a credencial entra no `.env`, liga sozinho:**
- `EMAIL_API_KEY` + **domínio verificado no Resend** + **Celery instalado/deployado** (p/ os 3 e-mails saírem).
- **Cert ICP-Brasil A1** (destrava transmissão eSocial **e** Reinf — hoje o pipeline é inerte).
- Credenciais **SERPRO / ADN / Pluggy / Meta / Gemini**.
- **Stripe Prices** (IDs reais) · **bucket S3 sa-east-1 + IAM** (liga o storage SPED) · deploy AWS · termos+privacidade · pen test.

### 3b. Código que VOCÊ pode fazer (em ordem de custo/valor)

1. **[pequeno, alto valor] Reinf — cabear o cert A1.** `router._construir_servico_transmissao` passa `cert_p12_bytes=None` fixo → mesmo com `REINF_TRANSMISSAO_ATIVA=True` o assinador é inerte. Mesma pendência do eSocial (#20). Wire do cert do storage cifrado. **Não transmita de verdade sem o PO.**
2. **[pequeno] Robustez do e-mail at-least-once** — ligar `Idempotency-Key` do Resend (chave estável do caller) p/ não duplicar recibo/alerta. + cleanup do leak httpx por-request do eSocial/Reinf (cliente via lifespan ou `try/finally aclose`).
3. **[médio-grande] Módulos de backend prontos SEM tela (§3.2 — capacidade desperdiçada).** Cada um é uma tela nova (cadeia front completa: schema Zod → adapter → hook → tela com estados). Prioridade por valor de negócio:
   - **advisor** (8 endpoints: anomalias, sugestões Fator R, digest semanal — o "cérebro" do produto) → **conciliação Match** (NF×banco) → **ICMS** mensal / **declaração anual** (DEFIS/DASN) → **imobilizado** / **provisões** / **sócios-pró-labore-distribuição** / **reinf retenções PJ→PJ** / **multa-juros** (simulador) → **marketplace** / **migração** (import SPED/CSV) / **tabelas-admin**.
   - Tela **Notas** é o gabarito de ouro a imitar; respeite as 5 leis de UX (nunca expor CFOP/CST/NCM crus; status > número; 1 ação por alerta; dashboard = health report; 3 camadas).
4. **[médio — precisa backend novo] §3.4 Manifesto de entrada de NF-e** — obrigação legal (180 dias); o botão hoje é ilusório e **não há endpoint**. Precisa módulo backend (manifestação do destinatário via SEFAZ/ADN) + tela. Avalie com `analista-fiscal-br`.
5. **[pequeno] §3.4 Convite de usuários** — hoje é mock (`setTimeout`+toast fake). Gestão multi-usuário (visão do contador?) não está claramente escopada — confirme o escopo com o PO antes.

### 3c. Pendências conscientes do backend (já documentadas em `log_agente.md`)
Tabelas INSS/IRRF/FGTS 2026 (issue #9, aguarda Portaria — fluxo `/atualizar-aliquota` com o agente `aliquota-smith`), CRF/CNDT scraping, lançamento contábil automático da folha, eSocial XML real, Sintegra/RFB scraping, etc. Ver a seção "Pendências conscientes" do `log_agente.md`.

---

## 4. ONDE ACHAR AS COISAS

| O que | Onde |
|---|---|
| Como o front fala com o back (contratos) | `src/lib/http.ts` (`fetchJson`), `src/lib/api/*`, `docs/HANDOFF.md` |
| Mapa de pontas soltas / módulos órfãos | `docs/auditoria-pontas-soltas-be-fe.md` |
| Roadmap de produção (PO × orquestrador) | `docs/PLANO_GO_LIVE.md` |
| Identidade visual v2 (vence sobre tudo) | `docs/arkan-claro-identidade-v2.md` |
| Plano backend (fonte de verdade) | `docs/PlanoBackend.md` + `app/shared/db/models.py` |
| Frota de subagentes | `.claude/agents/*.md` + `docs/time_arkan.md` |
| Padrão de e-mail nos fluxos (recém-feito) | `app/workers/tasks/email_enviar.py` (`enfileirar_email`), `app/workers/tasks/alerta_fiscal.py` (worker agendado modelo) |
| Padrão de worker agendado cross-tenant | `app/workers/tasks/advisor_enviar_digests.py` |

---

## 5. PRIMEIRO PASSO SUGERIDO
Confirme o estado (`git log --oneline -6`, gate verde), pergunte ao PO **qual frente** ele quer (ops vs código; e se código, qual item da §3b). Para módulos órfãos (§3.2), **mapeie com `backend-scout`/`explorer` ANTES** de implementar — o backend já existe; o trabalho é quase todo de **tela**. Recomendação forte: comece pelo **advisor** (maior diferencial) ou feche os itens pequenos da §3b.1/3b.2 primeiro.
