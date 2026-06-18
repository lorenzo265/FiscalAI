# Frota de agentes — Re-engenharia Arkan (frontend)

Coloque esta pasta em `analista-fiscal-web/.claude/agents/`. Subagentes carregam no início da sessão
— se editar um arquivo, **reinicie a sessão** (ou crie via `/agents`, que aplica na hora).

A **sessão principal é o orquestrador** (lê `CLAUDE.md`); os agentes abaixo são os trabalhadores.
A coordenação acontece por arquivos: `CLAUDE.md` + contratos em `docs/` + `docs/HANDOFF.md`.

## Quem é quem

| Agente | Fase | Papel | Permissão | Modelo |
|---|---|---|---|---|
| `explorer` | — | Mapeia código antes de mexer (resumos) | read-only | haiku |
| `foundation` | 0 | Tokens (`globals.css`) + fontes (`layout.tsx`) | edit | opus |
| `design-system` | 1 | Primitivas `ui/*` + `shared/*` + `blueprint/*` + `lib/motion/*` + showcase | edit | opus |
| `shell` | 2 | Sidebar/topbar/transições + LenisProvider | edit | opus |
| `screen-implementer` | 3 | Reveste telas — **1 invocação por lote A–E** (em worktrees) | edit | sonnet |
| `motion-polish` | 4 | Motion premium + perf/a11y + dark mode | edit | opus |
| `reviewer` | gate | Roda os gates em todo PR (contexto fresco) | read-only | opus |

> **Frota expandida (Lote 1+):** além dos agentes de frontend acima, a equipe agora cobre backend e negócio — roster completo, ferramentas/MCPs e modos de execução em **`docs/time_arkan.md`**.

## Backend + gates (Lote 1)

| Agente | Papel | Permissão | Modelo |
|---|---|---|---|
| `backend-scout` | Mapeia o backend antes de mexer (resumos) | read-only | haiku |
| `backend-dev` | Implementa sprint/feature do PlanoBackend (TDD golden) | edit | sonnet |
| `fiscal-validator` | Roda golden + eval + mypy; parecer VERDE/VERMELHO | read-only | opus |
| `aliquota-smith` | Versiona alíquota (SCD): propõe migration+golden, **para p/ aprovação** | edit | opus |
| `backend-reviewer` | Gate dos 10 princípios no diff (contexto fresco) | read-only | opus |

Comandos: `/validar-fiscal [módulo]` · `/atualizar-aliquota [tributo] [ano]`.

## Backend — QA, infra, segurança + verificação visual (Lote 2)

| Agente | Papel | Permissão | Modelo |
|---|---|---|---|
| `migration-smith` | Migrations Alembic com RLS (2 fases) | edit | sonnet |
| `qa-integration` | Integração + RLS cross-tenant (Docker) | read-only | sonnet |
| `ci-engineer` | Pipeline, pre-commit, hooks | edit | sonnet |
| `security-auditor` | bandit, segredos, LGPD, RLS (propõe) | read-only | opus |
| `frontend-verifier` | Visual + console + a11y + E2E (browser) | read-only | sonnet |

Comandos: `/revisar-pr` · `/ci` · `/verificar-front`. Gates: `.pre-commit-config.yaml` + hook `command-guard.ps1` (freios). **Nota:** os agentes rodam via **PowerShell** (a Bash tool falha neste Windows).

## Business (Lote 3)

| Agente | Papel | Permissão | Modelo |
|---|---|---|---|
| `market-research` | Concorrência, ICP, pulse de mercado (com fonte) | web + write docs | opus |
| `pricing-cac-forecast` | Pricing, CAC/LTV, break-even, forecast MRR | write docs | opus |
| `compliance-legal-watch` | Vigia RFB/DOU/Reforma → tarefa p/ aliquota-smith | web + write docs | opus |
| `content-fiscal` | Conteúdo educacional p/ dono de PME | write docs | sonnet |
| `customer-success` | Churn, health score, onboarding (dados simulados) | write docs | sonnet |
| `product-analytics` | Adoção por segmento/coorte (dados simulados) | write docs | sonnet |

Comando: `/pulse-negocio`. Escrevem em `docs/negocio/` (write-back em `HANDOFF_NEGOCIO.md`). **Propõem; decisões de preço/produto/legislação são do humano.**

## Ordem (dependências)
`0 foundation` → `1 design-system` → `2 shell` (SERIAIS) → `3 screen-implementer` × lotes A–E
(PARALELO, 1 git worktree/branch cada) → `4 motion-polish`. O `reviewer` roda **antes de cada merge**;
o `explorer` é chamado sob demanda quando algo precisa ser mapeado.

> **Regra de worktree (lição da Fase 3):** um worktree só enxerga o que está **mergeado na sua base**.
> Rode `screen-implementer` em worktree **somente** quando o design-system (Fases 0–2 / tokens v2) já
> estiver na base; senão o lote não vê as primitivas e gera retrabalho — nesse caso, trabalhe no **tree
> principal**. Frentes que **não** dependem do design-system (conteúdo/traduções, backend) podem usar
> worktree de base atual sem problema.

## Como invocar (exemplos)
- "Use o subagente **foundation** para executar a Fase 0."
- "Use o **screen-implementer** no **lote B (Notas)**."
- "Use o **reviewer** para rodar o gate neste diff antes do merge."

> Pré-requisitos no repo: `CLAUDE.md` (raiz) e os contratos em `docs/`
> (`PLANO_REENGENHARIA_FRONTEND_ARKAN.md`, `arkan-visual-style-merge.md`, `arkan-motion-extraction.md`)
> + `docs/HANDOFF.md` (pode começar vazio).
