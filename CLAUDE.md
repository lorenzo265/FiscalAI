# CLAUDE.md — Analista Fiscal (FiscalAI)

Instruções para agentes Claude trabalhando neste repositório. Leia este arquivo PRIMEIRO em qualquer sessão nova.

---

## O que é este projeto

Sistema fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido, faturamento R$200k–R$50M/ano). Dois sub-projetos:

- **`analista-fiscal-api/`** — Backend (FastAPI + Postgres + Redis). Source of truth: `docs/PlanoBackend.md`.
- **`analista-fiscal-web/`** — Frontend (Next.js 15 + React 19 + Tailwind v4 + shadcn/ui). **Em re-engenharia de design** (rebrand do app → **Arkan**; identidade "Instrumento"). Escopo de produto: `analista-fiscal-web/Plano.md`. Re-engenharia/design: seção «Frontend — Re-engenharia Arkan» (abaixo) + `docs/PLANO_REENGENHARIA_FRONTEND_ARKAN.md`.

Dois workstreams ativos: **backend** (sprints 0–22 concluídas — roadmap completo, ver «Estado atual») e **frontend** (re-engenharia de design "Arkan", agora em identidade v2 "Arkan Claro" — ver seção própria).

---

## Antes de começar qualquer trabalho

1. **Ativar a skill apropriada:**
   - Backend → `fiscalai-backend`
   - Frontend (código de feature) → `fiscalai-frontend`
   - Frontend (design / identidade visual / motion) → `frontend-design-architect`
   - Domínio fiscal sem código → `analista-fiscal-br`

   > **Roteamento:** se a tarefa é **frontend/design (Arkan)**, pule para a seção «Frontend — Re-engenharia Arkan» e leia `docs/HANDOFF.md` — não o fluxo backend (`log_agente.md` / `PlanoBackend.md`) abaixo.

2. **Ler `log_agente.md`** (na raiz do repo) — histórico de PRs, contagem de testes, pendências conscientes, onde paramos exatamente.

3. **Ler `docs/PlanoBackend.md`** para a sprint atual — o Plano é fonte de verdade absoluta. Nunca substituir stack, pular sprint ou adicionar escopo sem documentar.

4. **Consultar `docs/README.md`** — hub do knowledge graph (Obsidian vault). Contém wikilinks `[[ ]]` para princípios, sprints, módulos, ADRs e pendências. Use como mapa de navegação rápido. Se uma nota referenciada (`[[x]]`) ainda não existir, ela é uma **pendência de documentação** — não criar sem confirmar com o usuário.

5. **Frota de agentes (devs + business)** — a equipe de subagentes que executa validação fiscal, atualização de alíquota, gates e tarefas de negócio está definida em `docs/time_arkan.md` + `.claude/agents/`. O orquestrador encadeia os agentes (você não chama um por um); freios em ações irreversíveis. Ver `docs/time_arkan.md` §12 (modos de execução).

---

## Estado atual (2026-06-06)

- **Sprints 0–22 concluídas (roadmap completo).** 2520 testes passando, 3 skipped. mypy strict ✅ em 357 arquivos. bandit ✅ 0 issues.
- **56 migrations Alembic** com RLS multi-tenant em todas as tabelas de domínio.
- **33 módulos** em `app/modules/`. Estrutura: cada módulo = `models.py` (raros — geralmente em `shared/db/models.py`), `repo.py`, `service.py`, `router.py`, `schemas.py` + arquivos `calcula_*.py` puros.
- **Branch:** `hardening-fiscal-2026-06`. **Aberto e acionável:** #9 — tabelas INSS/IRRF/FGTS 2026 (aguarda valores oficiais da Portaria MPS/MF 2026; fluxo `/atualizar-aliquota`, para em aprovação).

---

## Stack cravada (não substituir)

| Camada | Tech | Versão |
|---|---|---|
| Linguagem | Python | 3.12 |
| API | FastAPI | 0.115+ |
| ORM | SQLAlchemy 2.0 async | + asyncpg |
| Migrations | Alembic | 1.13+ |
| Validation | Pydantic | v2 |
| DB | PostgreSQL | 16 (RLS, JSONB, pgcrypto) |
| Vector | pgvector | 0.7+ |
| Cache/queue | Redis | 7.4+ |
| Worker | Celery | 5.4+ (instalação opt-in; beat schedule já configurado) |
| LLM cloud | Gemini 2.5 Flash/Pro | via `google-genai` |
| LLM local | Ollama + Gemma 3 4B | privacy-first |
| Embeddings | `nomic-embed-text` | via Ollama, 768-dim |
| Tests | pytest + pytest-asyncio | + golden suite + eval suite |
| Obs | Langfuse, Sentry, Grafana, Tempo, Loki | self-hosted |

**Anti-stack:** ❌ Litestar, MongoDB, LangChain, Claude/GPT em prod, Nuvem Fiscal, Pinecone, HSM real, hardcode de tabela tributária, `float` para dinheiro, `Any` em contratos públicos, `print()` em vez de logger estruturado.

---

## Comandos comuns

```powershell
# PATH necessário (Device Guard bloqueia poetry.exe direto)
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api

# Suite unitária + eval (rápida, ~7s)
poetry run python -m pytest tests/unit tests/eval

# mypy strict completo
poetry run python -m mypy app/

# Suite de um módulo só (durante TDD)
poetry run python -m pytest tests/unit/pessoal --tb=short

# Integração (requer Docker rodando)
docker compose up -d
poetry run alembic upgrade head
poetry run python -m pytest tests/integration

# Servir API local
poetry run uvicorn app.main:app --reload
```

---

## 10 princípios invioláveis (§8 do Plano)

1. **RLS multi-tenant** ativo em toda tabela de domínio (`SET LOCAL app.tenant_id` na sessão).
2. **Fatos fiscais imutáveis** — cancelamento gera nova linha com `supersedes` ou `superseded_by`.
3. **Decisões versionadas (SCD Type 2)** — toda alíquota tem `valid_from`/`valid_to`.
4. **Golden tests** bloqueando merge — barreira anti-regressão em todo cálculo fiscal.
5. **Citação obrigatória em LLM** — resposta sem citação válida é rejeitada.
6. **Re-check determinístico pós-LLM** — valores monetários, datas, CNPJs conferidos via regex.
7. **LGPD-first** — AES-256 em repouso, TLS 1.3, dados em sa-east-1.
8. **LLM nunca escreve fatos** — pipeline determinístico ingere/calcula/persiste.
9. **Idempotência** em integrações externas — `idempotency_key` em todo POST a Focus/SERPRO/Pluggy.
10. **Observabilidade obrigatória** — Langfuse, Tempo, Sentry, Grafana.

Bônus (§8.11–8.12):
- **Out-of-scope é declarado**, não improvisado (contencioso/holding → marketplace, nunca tentar responder).
- **Transmissão é ato consciente** do cliente — sistema gera SPED + valida + cliente baixa + transmite com cert dele.

---

## Convenções de código (mecânicas)

### Padrão de módulo (`app/modules/<nome>/`)

```
__init__.py        # docstring explicando o bounded context
calcula_<x>.py     # algoritmo puro Decimal-safe, golden-tested, ALGORITMO_VERSAO
repo.py            # async + selectinload explícito, sem N+1
schemas.py         # Pydantic v2 com ConfigDict(extra="forbid") em inputs
service.py         # orquestra; aceita repo por DI
router.py          # thin: valida → service → response_model
```

### Tipagem (mypy strict)

- Zero `Any` / `dict[str, Any]` em contratos públicos.
- `Decimal` para dinheiro (NUNCA `float`), `TIMESTAMPTZ` para tempo, `UUID` para IDs.
- `from __future__ import annotations` em todo arquivo com type hints.
- Imports sempre absolutos a partir de `app.`.

### Money discipline

```python
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
getcontext().prec = 28
valor = (receita * Decimal("0.073")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
```

Persiste em `NUMERIC(14,2)` no Postgres. Nunca `FLOAT`.

### Datas

```python
from datetime import datetime
from zoneinfo import ZoneInfo
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))  # SEMPRE aware
```

### Logging

```python
import structlog
log = structlog.get_logger(__name__)
log.info("evento.acao", empresa_id=str(empresa.id), valor=str(decimal))  # Decimal → str
```

CNPJ/CPF/email redacted antes de chegar em Loki.

### Migration backward-compatible (2 fases)

1. Adicionar coluna nullable + deploy code que popula.
2. NOT NULL + deploy final.

Migration que cria tabela já inclui RLS policy:

```python
_RLS_USING = "NULLIF(current_setting('app.tenant_id', TRUE), '')::uuid = tenant_id"
op.execute("ALTER TABLE x ENABLE ROW LEVEL SECURITY")
op.execute(f"CREATE POLICY x_tenant ON x USING ({_RLS_USING})")
```

---

## Estrutura do código (resumo)

```
analista-fiscal-api/
├── alembic/versions/        # 56 migrations (RLS por tabela de domínio)
├── app/
│   ├── modules/             # 33 bounded contexts
│   │   ├── auth, empresa, ingestao                            (Sprints 1-2)
│   │   ├── fiscal, multa_juros                                 (Sprints 2-4)
│   │   ├── llm-related: assistente, memoria                    (Sprint 4)
│   │   ├── agenda                                              (Sprint 4)
│   │   ├── notas, whatsapp                                     (Sprint 5)
│   │   ├── certidoes, pgdas, e_cac, declaracao_anual           (Sprint 6)
│   │   ├── open_finance, conciliacao                           (Sprint 7)
│   │   ├── imobilizado, provisoes                              (Sprint 8)
│   │   ├── contabil                                            (Sprint 9)
│   │   ├── pessoal                                             (Sprint 10)
│   │   ├── lucro_presumido, icms, reinf, det,
│   │   │   monitor_cadastral, parcelamentos                    (Sprint 11)
│   │   ├── relatorios                                          (Sprint 12)
│   │   └── reforma, sped, tabelas_admin, advisor,
│   │       marketplace, migracao                               (Sprints 13-22)
│   ├── shared/
│   │   ├── db/models.py     # ~50 models SQLAlchemy 2.0 (Mapped[])
│   │   ├── db/deps.py       # get_session com SET LOCAL RLS
│   │   ├── exceptions.py    # ~60 DomainError mapeadas para HTTP
│   │   ├── llm/             # cliente unificado + eval + citação
│   │   ├── integrations/    # focus_nfe, serpro, pluggy, brasil_api, meta_whatsapp
│   │   └── logging.py
│   ├── workers/             # Celery app + 4 tasks (skeleton + beat schedule)
│   ├── config.py, main.py
└── tests/
    ├── unit/                # golden por módulo (maior parte da suite)
    ├── eval/                # 166 casos LLM
    └── integration/         # requer Postgres+Redis (Docker)
```

---

## Padrão de PR (cadência observada)

Cada sprint vira tipicamente 3 PRs. PR pattern:

1. **Migration** Alembic com RLS + seed (se SCD).
2. **Modelo(s)** SQLAlchemy em `app/shared/db/models.py`.
3. **Exceções** de domínio em `app/shared/exceptions.py`.
4. **Algoritmo(s) puro(s)** `calcula_*.py` com `ALGORITMO_VERSAO` + golden tests.
5. **Repo + Service + Schemas + Router** no módulo.
6. Plugar router no `app/main.py`.
7. Rodar **pytest + mypy** (zero erros é critério de merge).
8. **Atualizar `log_agente.md`** com a contagem nova e descrição do que entrou.

Convenção de mensagens de log: contagem final cresce 10-40 testes por PR. Suite atual: 2520 (a contagem corrente vive no `log_agente.md`).

---

## Pendências conscientes (não esquecer)

Estão documentadas em `log_agente.md` seção "Pendências conscientes". Resumo:

1. **Celery instalação** — workers têm beat schedule mas pacote é opt-in (`poetry add celery[redis]`).
2. **Storage S3/GCS** — recibos SERPRO, DANFSE, holerite PDF: hoje só calculamos `storage_key`.
3. **CRF/CNDT scraping** — Sprint 6 PR1 marca como `processando` (placeholder).
4. **Webhook Pluggy → sync inline** — só persiste evento; cross-tenant routing exige Celery + role admin.
5. **NF entrada com classificação inteligente** — vai pra "5.1.99 Outras Despesas — A Classificar". Categorização por CFOP/NCM via LLM em sprint futura.
6. **Bloqueio explícito de lançamento em mês encerrado** — confiar no DB CHECK; refinar no service.
7. **Tabelas INSS/IRRF/FGTS 2026 oficiais** — seed atual é 2025 (Portaria 6/2025). Quando 2026 sair, nova linha SCD.
8. **Lançamento contábil automático da folha** — totais calculados, lançamento em "5.1.02"/"2.1.2.01" etc. fica para Sprint 11+.
9. **eSocial transmissão real** — payload JSON pronto; XML + ICP-Brasil + envio fica para sprint futura.
10. **Limite isento da distribuição automático** — hoje vem como input do contador.
11. **Sintegra/RFB scraping real** — endpoints aceitam snapshot manual; sync automático no Celery.

---

## O que NUNCA fazer

- ❌ Adicionar dependência banida (LangChain, Litestar, MongoDB, etc.).
- ❌ Pular sprint do Plano.
- ❌ Usar `float` em qualquer cálculo monetário.
- ❌ Hardcoded de alíquota — sempre SCD Type 2.
- ❌ LLM gravando fatos diretamente (princípio §8.8).
- ❌ Sessão SQLAlchemy sem `SET LOCAL app.tenant_id` (princípio §8.1).
- ❌ Endpoint sem golden test cobrindo o cálculo (princípio §8.4).
- ❌ `Any` em contrato público de service/router.
- ❌ Commit sem rodar `pytest` + `mypy` antes.
- ❌ Modificar tabela tributária seedada — sempre INSERT nova vigência.

---

## Onde encontrar coisas específicas

| O que | Onde |
|---|---|
| Próxima sprint a executar | `log_agente.md` seção "Roadmap" |
| Estrutura de uma sprint específica | `docs/PlanoBackend.md` §9 (roadmap detalhado) |
| Princípios invioláveis | `docs/PlanoBackend.md` §8 |
| Modelo de dados | `docs/PlanoBackend.md` §5 + `app/shared/db/models.py` |
| Padrão de teste golden | `tests/unit/fiscal/test_calcula_das.py` (canônico) ou `tests/unit/pessoal/*` (mais recente) |
| Padrão de migration RLS | `alembic/versions/0013_sprint8_provisoes_trabalhistas.py` |
| Padrão de service + idempotência | `app/modules/provisoes/service.py` |
| Padrão de algoritmo puro | `app/modules/pessoal/calcula_inss.py` ou `app/modules/lucro_presumido/calcula_irpj.py` |
| Plano referencial de contas (Sprint 9) | `app/modules/contabil/plano_referencial.py` |
| Equipe de agentes (devs + business) | `docs/time_arkan.md` + `.claude/agents/*.md` |

---

## Protocolo Obsidian + Claude Code (vault `docs/`)

O vault `docs/` é a **memória de longo prazo** e a **camada de invariantes** do projeto. Notas atômicas linkadas em `principios/`, `modulos/`, `sprints/`, `decisoes/`, `pendencias/`. Hub: `docs/README.md`. O grafo é para o humano navegar; o agente lê os `.md` como texto. O ganho de qualidade vem de **priming antes** + **auto-review depois** + **write-back sempre**.

### 1. Antes de codar — priming dirigido

Não despejar o `PlanoBackend.md` inteiro. Puxar só as notas relevantes ao alvo. Regra por tipo de tarefa:

| Vai mexer em… | Ler antes |
|---|---|
| Qualquer módulo | `docs/modulos/<nome>.md` + princípios que ele cita |
| Cálculo fiscal (`calcula_*.py`) | `principios/03-scd-type-2` + `principios/04-golden-tests` + nota do módulo |
| Algo com LLM | `principios/05-citacao-llm` + `06-recheck-deterministico` + `08-llm-nao-escreve-fatos` |
| Integração externa | `principios/09-idempotencia` + pendência relacionada |
| Migration / tabela nova | `principios/01-rls-multi-tenant` + `decisoes/adr-001-postgres-rls` |
| Nova sprint | `docs/roadmap.md` (onde estamos) + `sprints/sprint-<n>-*.md` (refinar como spec antes de implementar) |

Antes de alterar um módulo, **checar os backlinks** da nota dele (o que depende dele) para medir o raio de impacto.

### 2. Durante — princípios como guardrail

Os 12 princípios em `docs/principios/` são checklist de merge. Usar `docs/review-checklist.md` como rubrica de auto-review do diff **antes** de declarar o PR pronto. Violação de princípio bloqueia merge tanto quanto teste vermelho.

### 3. Depois — write-back obrigatório (não pedir confirmação)

Ao fechar um PR, além de `log_agente.md`:

- Pendência resolvida → editar a nota em `docs/pendencias/` para `status: resolvida` (não deletar — manter histórico).
- Decisão arquitetural nova → criar `docs/decisoes/adr-XXX-*.md`.
- Módulo novo / sprint concluída → criar/atualizar a nota correspondente + linkar no `docs/README.md`.
- Nunca criar nota referenciada por `[[x]]` inexistente sem confirmar — link vermelho é **pendência de documentação**, não tarefa silenciosa.

**Ao concluir uma SPRINT inteira** (todos os PRs fechados, `pytest` + `mypy` verdes), marcar a evolução em `docs/roadmap.md` — sem pedir confirmação:

1. Status da sprint na tabela do roadmap → ✅ e coluna **Testes** = contagem final.
2. Frontmatter do `roadmap.md`: atualizar `sprints_concluidas`, `testes_atuais`, `atualizado` (data de hoje).
3. Se houver nota em `docs/sprints/`, marcar `status: concluida` no frontmatter dela.
4. Promover a próxima sprint para 🔜 (e `status: proxima` na nota dela, se existir).

Atalho que executa esse write-back: comando `/fechar-sprint` (`.claude/commands/fechar-sprint.md`).

**Vault desatualizado é pior que vault nenhum** — o agente confia nele. Manter sincronizado com o código é parte do Definition of Done.

---

## Frontend — Re-engenharia "Arkan" (Instrumento)

> **Workstream de design ATIVO.** Agente de frontend/design: leia **esta seção + `docs/HANDOFF.md`** antes de tudo. O app está sendo **rebatizado "Arkan"** (empresa: Arkan Fiscal Technologies) e revestido com uma identidade nova. **A arquitetura e as funções ficam; muda a pele.**

### Energia-alvo
*O instrumento de precisão, agora leve na mão* — identidade **v2 "Arkan Claro"** (Instrumento × Apple). Séria, exata, calma, lindamente desenhada: papel quente + tinta + **um verde** (marca = saúde fiscal), **um número-herói** em mono no centro de cada tela, **respiro** (≤3 blocos acima da dobra), tipografia editorial (**Fraunces só em momentos-marca** + **mono em todo dado**) e motion premium (springs, count-up). A camada técnica de **blueprint** (crop marks, "Fig.", régua) **recua para assinatura rara** — telas de detalhe, confirmações, PDF — **não** é mais a moldura de todo painel. **Nunca** dark/neon nem o look genérico de IA. → contrato completo e tokens em **`docs/arkan-claro-identidade-v2.md`** (estilo §2, componente §3, gates §5), que **vence sobre a v1** "Instrumento".

### Fontes de verdade (em `docs/`)
| Arquivo | É o contrato de… |
|---|---|
| `docs/PLANO_PRODUCTION_READY.md` | **plano-mãe** (12 sprints até o lançamento; funde fiscal + UX + identidade v2) |
| `docs/arkan-claro-identidade-v2.md` | **identidade v2 "Arkan Claro"** (recalibra os tokens v1 para clareza Apple; vence sobre o estilo v1) |
| `docs/plano-experiencia-ux-v2.md` | **sequência única de PRs do front** (funde a auditoria UX × as fases D0–D6 da v2) |
| `docs/PLANO_REENGENHARIA_FRONTEND_ARKAN.md` | plano v1: fases, frota, invariantes, gates |
| `docs/arkan-visual-style-merge.md` | estilo v1 (tokens, linguagem de componente) — **recalibrado pela v2** |
| `docs/arkan-motion-extraction.md` | motion v1 (Lenis + Framer, receitas de reveal) |
| `docs/HANDOFF.md` | livro de passagem entre agentes (append-only) |

(O `analista-fiscal-web/Plano.md` segue como fonte de **escopo de produto/feature**.)

### Princípio: re-vestir, não re-arquitetar
Stack (Next 15 + React 19 + Tailwind v4 + shadcn) é boa e **fica**. O tema é dirigido por tokens no `src/app/globals.css` (bloco `@theme`): **trocar tokens + revestir primitivas propaga por todo o app**. A paleta atual é o dark/neon "copiado do fiscalai_v4.html" — é o que estamos descartando.

### Contrato de código (não divergir)
- **Importar do design-system; NUNCA reinventar tokens/primitivas** no escopo de uma tela.
- Camadas-contrato construídas **primeiro** e consumidas por todos:
  `globals.css` (`@theme`) · fontes em `layout.tsx` (**Fraunces + Hanken Grotesk + Spline Sans Mono** via `next/font`) · `components/ui/*` + `components/shared/*` revestidos · `components/blueprint/*` (`Framed`, `CropMarks`, `Fig`, `Ruler`, `BlueprintSchematic`, `Carimbo`) · `lib/motion/*` (variants, `LenisProvider`, hooks).

### Gates anti-AI-slop (todo PR de tela)
Gates **v2** (de `docs/arkan-claro-identidade-v2.md §5` — vencem sobre a v1):
**Reprova** com: tudo-sans sem a serifa nos momentos-marca; dado em fonte proporcional (não-mono); 2º acento de cor; botão-pílula ou radius grande em controle; sombra suave difusa como profundidade (aqui profundidade = material translúcido/plano); ícone em quadradinho lavado; saudação "Olá, fulano 👋"; **mais de 3 blocos acima da dobra**; **painel comum com crop marks** (inflação da assinatura).
**Aprova** com: 1 pergunta respondida em 5s; **1 número-herói** (mono 56–72px); 1 ação primária; respiro ≥ escala; **mono em todo dado**; verde só onde significa saúde/ação. Regra-mãe: **detalhe no craft, calma no conteúdo.**

### Invariantes de função (não quebrar ao revestir)
Toda rota e item de navegação acessível; hooks (`use-*`), providers (Query/Empresa/Auth), Dexie/mock e lógica fiscal **inalterados**; wizards mantêm passos + validação (RHF+Zod); DANFE/PDF/QR/barcode funcionando; charts (Recharts) re-tematizados com os **mesmos dados**; status sempre **cor + ícone + palavra**; **nunca** expor CFOP/CST/NCM crus ao dono de PME — traduzir.

### Motion
Lenis (scroll suave) + Framer Motion (já instalado). Só animar `transform/opacity/clip-path/filter`. Honrar `prefers-reduced-motion`. 60fps em mobile. Orçamento: **1 entrada + 1 signature por tela**.

### Estratégia multi-agente (Claude Code)
O **repositório é o barramento.** Subagentes têm contexto próprio e só devolvem o resultado final; o único canal pai→subagente é o prompt. Coordenação por **arquivos**, não por chat:
- esta `CLAUDE.md` (constituição) + os contratos em `docs/` + `.claude/agents/*.md` (a frota) + `docs/HANDOFF.md`.
- **Fases:** `0` tokens → `1` design-system → `2` shell (**seriais**) → `3` telas A–E (**paralelo**, 1 git worktree/branch por domínio) → `4` polish. Default = orquestrador + subagentes (barato); *agent teams* só para negociar conflito.
- **Revisor de contexto fresco** roda os gates + invariantes em **todo PR antes do merge** (maior alavancagem contra deriva de design).
- Roster em `.claude/agents/`: `explorer` (read-only), `foundation`, `design-system`, `shell`, `screen-implementer` (invocado 1× por lote A–E, em worktree próprio), `motion-polish`, `reviewer` (read-only). A sessão principal é o **orquestrador** (lê esta `CLAUDE.md`).
- Tela **Notas** = gabarito de ouro que as outras imitam.

### Protocolo HANDOFF (`docs/HANDOFF.md`) — write-back obrigatório
Append-only. Ao terminar **qualquer etapa**, o agente registra, sem pedir confirmação:
**data · agente · o que fez · arquivos tocados · pendências · próximo agente.**
É assim que a frota se coordena sem custo de mensagens diretas (espelha o espírito do `log_agente.md` do backend, mas para o frontend).

### Frontend — NUNCA
- ❌ Reinventar tokens/primitivas no escopo de uma tela (use o design-system).
- ❌ Introduzir os "tells" de slop (pílula, card flutuando, sombra suave genérica, tudo sans).
- ❌ Quebrar uma função ao trocar a pele (ver Invariantes).
- ❌ Animar `width/height/top/left` em motion frequente.
- ❌ Voltar ao dark/neon do `fiscalai_v4` ou hardcodar cor fora do `@theme`.

---

## Comunicação com o usuário

- Mensagens em português.
- Tom técnico direto, sem firulas.
- Status final de cada PR sempre inclui: contagem de testes, erros de mypy, e o que entrou.
- Após cada PR, atualizar `log_agente.md` (não pedir confirmação).
- Sugerir próximo PR no final, mas esperar `prossiga`/`pr3`/etc. para começar.