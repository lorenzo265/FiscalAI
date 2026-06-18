# HANDOFF — Orquestrador (ondas de execução multi-agente)

Livro de passagem **append-only** da **sessão orquestradora** — a sessão principal do Claude Code que conduz a frota de subagentes (`.claude/agents/`) pelas "ondas". Espelha `docs/HANDOFF.md` (frontend) e `log_agente.md` (backend), mas para a coordenação de **alto nível** que cruza front + back + infra.

> **NUNCA reescreva entradas anteriores. Só acrescente no fim.** O histórico é a memória da orquestração.

---

## 🚦 Você é um orquestrador começando do ZERO? Leia nesta ordem

1. **`CLAUDE.md`** (raiz) — a constituição: o que é o projeto, stack, os 10 princípios invioláveis, convenções, e a seção «Frontend» (identidade v2 "Arkan Claro").
2. **A última entrada do «Log» (fim deste arquivo)** — onde exatamente paramos e qual é a próxima onda.
3. **As «Lições operacionais» abaixo** — como a frota se comporta nesta máquina (custou caro descobrir).
4. **`docs/PLANO_ORQUESTRACAO_ONDAS.md`** — o MÉTODO: grafo de dependências ("o que afeta o que"), mecanismos multi-agente, e o roadmap de ondas.
5. **Planos de produto:** `docs/PLANO_PRODUCTION_READY.md` (12 sprints até o lançamento) · `docs/plano-experiencia-ux-v2.md` (PRs X1–X19 do front).
6. **A frota:** `docs/time_arkan.md` (os 23 agentes, comandos slash, modos de execução, freios).
7. **Memória do Claude Code** (recall automático, se mesma máquina): `project_state` · `orquestracao-frota` · `windows-env-quirks`.

**Seu papel:** você é o **engineering manager**. Quebra a próxima onda em frentes (pelo grafo do §1 do plano), despacha subagentes da frota, valida o resultado, e **PARA nos freios**. Os subagentes coordenam **pelo repositório** (estes arquivos), nunca por chat — o único canal pai→subagente é o prompt do despacho.

**Freios (NUNCA sem o PO Lorenzo):** `git push`, merge remoto, transmissão fiscal real (NF-e/eSocial/SPED), alteração de alíquota seedada, deploy, cobrança.

---

## ⚙️ Lições operacionais (LER SEMPRE — variam por sessão)

1. **Quem roda shell VARIA por sessão — teste no início** (`git status` / `echo hello`). Em 2026-06-17: o ORQUESTRADOR tinha Bash (git bash) funcional; os SUBAGENTES NÃO tinham shell (só Read/Grep/Glob). Mandar subagente "rodar pytest/git e commitar" → ele **TRAVA** (um `reviewer` gastou 39 min / 323 tool calls). **Padrão: subagente escreve/analisa → orquestrador roda/valida/commita.**
2. **PowerShell via Bash é bloqueado** (deny rule). Mas `poetry`/`pytest`/`git`/`npm`/`docker` **direto no git bash funcionam** — para o poetry, antes: `export PATH="/c/Users/loren/AppData/Roaming/Python/Scripts:$PATH"` (Device Guard).
3. **Worktrees do harness (`isolation:worktree`) partem de uma base ANTIGA** (não o HEAD). Ao mergear, conflito só em logs append-only → `sed -e '/^<<<<<<< /d' -e '/^=======$/d' -e '/^>>>>>>> /d'`. Diff real de uma branch: `git diff $(git merge-base hardening <branch>)..<branch>`.
4. **`.claude/agents/*` é gitignored** (config local; recarrega só ao reiniciar a sessão) → para mudar comportamento de agente já carregado, passe o contexto novo no **PROMPT do despacho** (o `CLAUDE.md`, lido em runtime, propaga o resto).
5. **Subagentes não commitam** (sem shell) → o orquestrador **preserva o trabalho deles** (commita no worktree do agente) e **valida no tree principal** (que tem `.venv`/`node_modules`). Padrão p/ validar sem trocar de branch: `git checkout <branch> -- <paths>` → build/pytest → reverter.
6. **Merge com tree sujo** (o PO costuma ter trabalho não-commitado): integrar num **worktree dedicado**, ou `stash -u` → `branch -f hardening <onda>` → `checkout` → `stash pop`.

---

## 📍 Estado atual (resumo — detalhe na última entrada do log)
- **Branch viva:** `hardening-fiscal-2026-06` (contém tudo; **NÃO pushada**).
- **Backend:** roadmap 0–22 completo; em hardening + production-ready.
- **Frontend:** identidade v2 "Arkan Claro"; Trilha A (conteúdo) + tokens v2 feitos.
- **Próxima onda:** **Onda 2** — `X7 primitivas v2 → X8 gabarito Notas` (serial, tree principal).
- **Backlog:** segurança do webhook · teste de integração do webhook · fixtures RLS quebrados por IBGE (alheio).

---

## Log (append-only)

### 2026-06-17 · orquestrador · Ondas 1 + 1.5 + consolidação + limpeza
- **Etapa 0:** recalibrou a frota de design (`CLAUDE.md §Frontend` + agentes) da v1 "Instrumento" → v2 "Arkan Claro" (número-herói mono, crop marks raros, respiro, gates §5).
- **Onda 1 (3 frentes paralelas):** **F1** = traduções fiscais (`analista-fiscal-web/src/lib/traducao/*`) + urgência 3 níveis; **F2** = tokens v2 (`globals.css` + `layout.tsx`, dark re-derivado, AA nos 2 temas); **F3** = webhook Pluggy → fila Celery (idempotente, tenant-aware). Cada frente: 1 subagente em worktree/background; o orquestrador validou (build verde, pytest 60 + mypy) e commitou (os subagentes não tinham shell).
- **Onda 1.5 (validação profunda):** 5 gates frescos (`reviewer`×2, `backend-reviewer`, `security-auditor`, `content-fiscal`) + integração (`qa-integration` por análise + pytest rodado pelo orquestrador). Achados tratados: **4 correções fiscais** aplicadas (DCTFWeb inclui patronal; REINF precisa retenções; Fator R "desconto"→"alíquota menor"; Anexo IV exemplos corretos). Tooling QA novo no CI: Lighthouse/axe + Playwright visual + Semgrep/Gitleaks. **Parecer: VERDE.**
- **Consolidação:** as 4 frentes integradas em `feat/onda-1` (worktree dedicado), promovidas para `hardening-fiscal-2026-06` via fast-forward. **Raiz e `docs/` limpos** — superados/consumidos arquivados em `legacy/` (ver `legacy/README.md`). Worktrees + branches de trabalho removidos (housekeeping). Git enxuto: só `hardening-fiscal-2026-06` + `main`.
- **Estado:** `hardening-fiscal-2026-06` @ `549804d` tem TUDO. **NÃO pushado** (ato do PO). Pendências do PO preservadas no working tree, **não-commitadas**: IBGE (`empresa/cnpj.py`, `schemas.py`, `tabelas_admin/*`, `onboarding/passo-cnpj.tsx`), migration `0058` (INSS 2026) + `test_calcula_inss_2026`, frota (`.github/ci.yml`, `.mcp.json`, `.pre-commit-config.yaml`, `.claude/commands/*`), business (`docs/negocio/`, `docs/time_arkan.md`).
- **Backlog aberto:** (1) **segurança do webhook** — rate limit no webhook público, cap de body, AES-256 de coluna (PII bancária), ADR do drain cross-tenant antes de ligar Celery real; (2) **teste de integração do webhook F3** (só há unit); (3) **fixtures RLS** (`test_rls_isolation.py`) quebrados porque criam empresa sem IBGE (agora obrigatório) — do workstream IBGE, urgente p/ a CI de integração.
- **Próximo orquestrador → faça:** **Onda 2** = `X7 primitivas v2 → X8 gabarito Notas` (SERIAL, tree principal — worktree de tela só enxerga o design-system se ele estiver na base). `design-system` (X7) → `screen-implementer` (X8, Notas = gabarito de ouro), `reviewer` (gates v2) entre cada. Só após X8 mergeado os lotes de tela explodem em paralelo (Onda 3). NFS-e Nacional no backend quando o PO credenciar o ADN. Roadmap: `docs/PLANO_ORQUESTRACAO_ONDAS.md §4` + `docs/plano-experiencia-ux-v2.md`.
