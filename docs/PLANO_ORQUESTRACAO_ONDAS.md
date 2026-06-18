# Plano de Orquestração por Ondas — método multi-agente do Arkan

> **O que é:** o MÉTODO pelo qual a sessão orquestradora (Claude Code) divide o trabalho em "ondas" e despacha a frota de subagentes (`.claude/agents/`). É a parte **atemporal** (grafo de dependências + mecanismos + freios); o **estado/histórico** vive em `docs/HANDOFF-ORQUESTRADOR.md` (append-only). Originado do plano de sessão de 2026-06-17.

---

## §0 — Contexto mínimo (projeto)
**Arkan** = SaaS fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido). Dois sub-projetos: `analista-fiscal-api/` (FastAPI + Postgres + Redis, backend) e `analista-fiscal-web/` (Next 15 + React 19 + Tailwind v4, frontend). Backend: roadmap 0–22 completo, em **hardening** + **production-ready** (12 sprints, `docs/PLANO_PRODUCTION_READY.md`). Frontend: **identidade v2 "Arkan Claro"** (`docs/arkan-claro-identidade-v2.md`); PRs do front em `docs/plano-experiencia-ux-v2.md` (X1–X19). Frota de 23 agentes + comandos: `docs/time_arkan.md`. Constituição: `CLAUDE.md`.

---

## §1 — Grafo de dependências ("o que afeta o que")

### 4 squads, amplamente independentes na largada
São os *tracks* paralelos. Nas fases iniciais quase não se tocam → é aí que mora o paralelismo barato:

| Squad | Toca | Depende de | Bloqueia |
|---|---|---|---|
| **Experiência** (front) | `analista-fiscal-web/**` | backends já prontos (BrasilAPI, assistente, faturamento) | nada do backend |
| **Plataforma** (infra) | Celery, S3, CI, webhook | Redis/Docker (local) · S3 (credencial PO) | transmissões, jobs, storage |
| **Fiscal Core** (cálculo) | `app/modules/**`, golden | credenciais ADN/SERPRO/cert (PO) p/ transmissão real | obrigações reais |
| **Qualidade** (gates) | transversal | os 3 acima | merge (não a largada) |

**Conclusão:** Experiência (conteúdo) + Plataforma (Celery local) + Fiscal (estrutura de módulo) **não colidem** → rodam em paralelo. O que serializa é *dentro* de cada squad.

### Dentro da Experiência (front) — o gargalo e a explosão
Regra-mãe (de `plano-experiencia-ux-v2.md`): **conteúdo antes da forma**.
```
TRILHA A (conteúdo) ─ traduções, erros, urgência ....... paralelos, SEM deps de tokens
TRILHA B (fluxo) ──── onboarding, assistente ........... deps de backends prontos
BASE v2 (gargalo SERIAL) ─ extract → tokens → primitivas (X7) → gabarito Notas (X8)
                                                          │ (só DEPOIS de X8 mergeado)
LOTES v2 (explosão PARALELA) ─ home + lotes de tela ─────┘  1 branch/worktree por lote
```
- A cadeia `X5→X6→X7→X8` é **serial** — roda no **tree principal** (worktree de tela só enxerga o design-system se ele já estiver na base — lição da Fase 3).
- **Conflito a evitar:** X7 reveste as mesmas telas que a Trilha A edita → **mergear A antes de X7**.

### Cruzamentos front↔back (as únicas amarras)
`onboarding CNPJ` ← BrasilAPI ✅ · `assistente` ← backend assistente ✅ · `monitores de limite` ← faturamento/open-finance ✅ · `"fechar o mês"` ← backend S5 (orquestração Reinf→DCTFWeb) ❌ → S5.

### Gates externos (não-código — caminho crítico do PO Lorenzo)
Bloqueiam *transmissão real*, não o desenvolvimento: credenciamento **ADN** (NFS-e), **SERPRO** prod, **certificado ICP-Brasil** (eSocial), **Portaria 2026** (tabelas INSS/IRRF), **gateway de billing**. Tudo pode ter código pronto + testado com mock/sandbox enquanto o credenciamento corre.

---

## §2 — Mecanismos multi-agente ("como executar em paralelo")

| Mecanismo | Quando rende | Já existe? | Veredito |
|---|---|---|---|
| **Orquestrador + subagente** (`Agent`) | implementação encapsulada, exploração, validação | ✅ é o modelo | **default** |
| **Subagente em background** (`run_in_background`) | N frentes longas simultâneas; notifica ao fim | ✅ | 1 por frente paralela |
| **Worktree** (`isolation:worktree`) | escrita paralela isolada **quando a base tem as deps** | ✅ | backend/conteúdo já; tela de v2 só pós-X8 |
| **Agent teams** | negociar conflito entre agentes | ✅ mas caro | evitar; só conflito real |
| **CI (GitHub Actions)** | gate de merge não-interativo | ✅ `ci.yml` + `qa-gates.yml` | mantém |
| **Hooks/pre-commit** | gate determinístico na sessão | ✅ | mantém (NUNCA hook de shell — quebra a sessão) |
| **ECC plugin** (`/multi-plan`, `/quality-gate`, AgentShield) | fan-out de sprint + security-scan | ❌ aspiracional | adiar até o volume justificar |

**Princípio do projeto:** autonomia total no reversível; **gate forte + OK humano (PO) no irreversível**. Coordenação **pelo repositório** (estes `.md`), nunca por chat.

⚠️ **Realidade da máquina (verificar a cada sessão — ver `HANDOFF-ORQUESTRADOR.md` §Lições):** os subagentes podem **não ter shell** → eles escrevem/analisam, o **orquestrador roda/valida/commita**. E worktrees do harness partem de uma **base antiga** (merge conflita só nos logs).

---

## §3 — O método de uma onda

1. **Dividir** a próxima sprint/objetivo em frentes pelo grafo (§1) — o que é independente roda junto.
2. **Etapa 0 (se preciso):** afinar a frota/contratos antes (ex.: recalibrar agentes para a v2).
3. **Despachar** 1 subagente por frente (worktree/background quando paralelo; tree principal para o gargalo serial).
4. **Validar** cada frente com a frota de gates (read-only) + execução do orquestrador (build/pytest/Docker) — ver §Gates.
5. **Consolidar** num worktree de integração (`feat/onda-N`), resolver conflitos de log (append-only), promover para `hardening` (FF) — **parar antes do push** (ato do PO).
6. **Write-back** em `HANDOFF-ORQUESTRADOR.md` (uma entrada por onda) + `log_agente.md`/`HANDOFF.md`.

**Gates por frente:** `reviewer` (front anti-slop v2 + invariantes) · `backend-reviewer` (10 princípios) · `security-auditor` (LGPD/PII) · `fiscal-validator` (golden+eval+mypy) · `content-fiscal` (correção de domínio) · `qa-integration` (Docker/RLS) · `frontend-verifier` (E2E/a11y/visual). Skills nativas: `/code-review`, `/security-review`. CI: `ci.yml` + `qa-gates.yml`.

---

## §4 — Roadmap de ondas (atualizar o status; histórico no HANDOFF-ORQUESTRADOR)

| Onda | Conteúdo | Status |
|---|---|---|
| **0 — Etapa 0** | recalibrar a frota de design v1 "Instrumento" → v2 "Arkan Claro" | ✅ feito (2026-06-17) |
| **1** | F1 conteúdo (X1–X3) · F2 tokens v2 (X5–X6) · F3 webhook→Celery | ✅ feito |
| **1.5** | validação profunda (gates frescos + integração + tooling QA no CI) | ✅ feito |
| **2** | `X7 primitivas v2 → X8 gabarito Notas` (serial) | ✅ X7→X8 feito (2026-06-18) · NFS-e Nacional NÃO iniciada (backend, paraleliza depois; espera ADN) |
| **3** | lotes de tela v2 (X9–X13, paralelo, 1 worktree/lote — base já com design-system) · onboarding CNPJ (X15) · assistente real (X16) · monitores de limite (X17) | 🔜 **próxima** |
| **4+** | eSocial real · orquestração Reinf→DCTFWeb (S5) · billing · brand pack · polish | conforme credenciais do PO |

**Para a Onda 2 concretamente:** ela é o **gargalo serial** do front (não paralelizável até X8). Rode `design-system` (X7) → `screen-implementer` na tela **Notas** (X8, o gabarito de ouro), no **tree principal**, com `reviewer` (gates v2) entre cada. Só depois de X8 mergeado os lotes de tela explodem em paralelo (Onda 3).
