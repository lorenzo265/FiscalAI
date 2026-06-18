# 🧠 Vault Analista Fiscal — Knowledge Graph

Ponto de entrada do vault. Use a barra lateral do Obsidian ou clique nos links abaixo.

> Abrir grafo: `Ctrl+G` (ou ícone de grafo na barra lateral).

---

## 🧭 Ferramentas do vault

- [[roadmap]] — evolução do projeto: as 23 sprints, status e onde estamos.
- [[dashboard]] — painéis vivos (Dataview): pendências, módulos, sprints, ADRs.
- [[review-checklist]] — rubrica de auto-review de PR derivada dos 12 princípios.
- [[deploy]] — mapeamento operacional pra subir o sistema (settings, integrações, gates `hard`/`soft`, pendências `[risco-deploy]`).
- [[time_arkan]] — a **frota de agentes** (devs + business): roster, ferramentas/MCPs, gates e modos de execução.

---

## 📋 Fontes de verdade

- [[Plano]] — Plano do frontend (Next.js + Dexie + TanStack Query)
- [[PlanoBackend]] — Plano do backend (FastAPI + Postgres + Redis). **Sprints 0-12 concluídas**, próxima Sprint 13.

---

## 🏛️ Princípios invioláveis (§8 do PlanoBackend)

1. [[principios/01-rls-multi-tenant|RLS multi-tenant]]
2. [[principios/02-fatos-imutaveis|Fatos fiscais imutáveis]]
3. [[principios/03-scd-type-2|Decisões versionadas (SCD Type 2)]]
4. [[principios/04-golden-tests|Golden tests bloqueando merge]]
5. [[principios/05-citacao-llm|Citação obrigatória em LLM]]
6. [[principios/06-recheck-deterministico|Re-check determinístico pós-LLM]]
7. [[principios/07-lgpd-first|LGPD-first]]
8. [[principios/08-llm-nao-escreve-fatos|LLM nunca escreve fatos]]
9. [[principios/09-idempotencia|Idempotência em integrações]]
10. [[principios/10-observabilidade|Observabilidade obrigatória]]

Bônus (§8.11–8.12):

- [[principios/11-out-of-scope|11 — Out-of-scope é declarado, não improvisado]]
- [[principios/12-transmissao-consciente|12 — Transmissão ao Fisco é ato consciente do cliente]]

---

## 🚀 Sprints

- **Status completo das 23 sprints → [[roadmap]]** (Sprints 0-12 ✅, 13 próxima)
- Próxima: [[sprints/sprint-13-marketplace|Sprint 13 — Marketplace de Contadores]]
- Meta Fase 2: 50 pagantes + MRR R$10k

---

## 📦 Módulos do backend (28 bounded contexts)

Cada módulo vive em `analista-fiscal-api/app/modules/<nome>/`.

- [[modulos/fiscal|fiscal]] — cálculo DAS, anexos
- [[modulos/pessoal|pessoal]] — folha, INSS, IRRF, FGTS
- [[modulos/conciliacao|conciliacao]] — Open Finance + Pluggy
- [[modulos/lucro-presumido|lucro_presumido]] — IRPJ/CSLL trimestral
- [[modulos/relatorios|relatorios]] — Sprint 12
- [[modulos/reforma|reforma]] — CBS/IBS informacional (Sprint 14)
- [[modulos/sped|sped]] — geração ECD/ECF/EFD-Contribuições/EFD ICMS-IPI (Sprint 16+)
- (criar notas conforme for tocando cada módulo)

---

## ⚠️ Pendências conscientes

Lista completa em `log_agente.md`. Replicar como notas individuais facilita o grafo:

- [[pendencias/celery-instalacao]]
- [[pendencias/storage-s3]]
- [[pendencias/crf-cndt-scraping]]
- [[pendencias/webhook-pluggy-sync]]
- [[pendencias/nf-entrada-classificacao]]
- [[pendencias/tabelas-2026-oficiais]]
- [[pendencias/folha-lancamento-contabil]]
- [[pendencias/esocial-transmissao]]
- [[pendencias/sintegra-scraping]]

---

## 📚 Decisões arquiteturais (ADRs)

- [[decisoes/adr-001-postgres-rls]] — porque Postgres + RLS em vez de schemas por tenant
- [[decisoes/adr-002-llm-citacao]] — porque toda resposta LLM precisa citar
- (adicionar conforme decidir)

---

## 🔧 Stack cravada (não substituir)

Python 3.12 · FastAPI 0.115+ · SQLAlchemy 2.0 async · Postgres 16 + pgvector ·
Redis 7.4 · Celery 5.4 · Gemini 2.5 (cloud) · Ollama + Gemma 3 4B (local) ·
pytest + golden suite + eval suite.

**Anti-stack:** ❌ LangChain · ❌ Litestar · ❌ MongoDB · ❌ Claude/GPT em prod ·
❌ `float` em dinheiro · ❌ `Any` em contrato público.

---

## 🤖 Para agentes Claude lendo este vault

1. Comece pelo `CLAUDE.md` da raiz do repo.
2. Leia `log_agente.md` para estado atual.
3. Use [[PlanoBackend]] como source of truth.
4. Não invente notas — se uma referência `[[x]]` não existir, ela é uma **pendência de documentação**, não um arquivo a ser criado sem confirmação.
5. Para trabalhar **via frota de subagentes** (validação fiscal, alíquota, gates, business), veja [[time_arkan]] — o orquestrador encadeia os agentes; você não chama um por um.
