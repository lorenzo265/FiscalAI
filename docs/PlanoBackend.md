# Plano de Backend — Analista Fiscal (v2.0)

**Audiência:** Dev senior de backend (Python, distributed systems, fiscal/financial domain).
**Versão:** 2.0 — 2026-05-10
**Status:** Pronto para Sprint 0.
**Frontend:** `analista-fiscal-web` (Next.js 15) em ~70% — ver `RELATORIO_ANALISE_FISCALAI_MAIN.md`.

> **v2.0 consolida duas rodadas de auditoria de cobertura.** Substitui integralmente a v1.0. Adicionados 16 itens críticos (Tier 1 + rodada 2): ECD/ECF/EFD-Contribuições/EFD ICMS-IPI, imobilizado + depreciação, provisões trabalhistas, EFD-Reinf, DET, DEFIS, rescisão completa, ICMS apurado mensal, Sintegra/IE, multa/juros, distribuição de lucros, pró-labore, monitor RFB. Marketplace de contadores parceiros adicionado como estratégia para os 15-25% que não devem entrar no produto.

> **Cravado**: stack, arquitetura, princípios e fases foram decididos com base em pesquisa de mercado de 2026. Não inventar substituições. Onde houver dúvida, perguntar — não improvisar.

---

## Sumário

1. [Resumo executivo](#1-resumo-executivo)
2. [Pesquisa de mercado — fundamentação](#2-pesquisa-de-mercado--fundamentação)
3. [Tech stack final (cravado)](#3-tech-stack-final-cravado)
4. [Arquitetura macro](#4-arquitetura-macro)
5. [Modelagem de dados](#5-modelagem-de-dados)
6. [Camada de IA — híbrida 3-níveis](#6-camada-de-ia--híbrida-3-níveis)
7. [Integrações externas](#7-integrações-externas)
8. [Princípios invioláveis](#8-princípios-invioláveis)
9. [Cobertura realista e out-of-scope deliberado](#9-cobertura-realista-e-out-of-scope-deliberado)
10. [Marketplace de contadores parceiros](#10-marketplace-de-contadores-parceiros)
11. [Roadmap — 22 sprints](#11-roadmap--22-sprints)
12. [Custos operacionais](#12-custos-operacionais-mensais)
13. [DevOps e infraestrutura](#13-devops-e-infraestrutura)
14. [Observabilidade e segurança](#14-observabilidade-e-segurança)
15. [Time mínimo](#15-time-mínimo-recomendado)
16. [Riscos e mitigação](#16-riscos-e-mitigação)
17. [Métricas de sucesso](#17-métricas-de-sucesso)
18. [Apêndices](#18-apêndices)

---

## 1. Resumo executivo

### 1.1 O que o backend faz

Sistema fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido, faturamento R$200k–R$50M/ano), com:

**Ingestão e operação fiscal:**
- Ingestão automática de NF-e/NFS-e/NFC-e (SEFAZ + ADN nacional + IMAP + Manifesto Destinatário)
- Cálculo determinístico de DAS, IRPJ, CSLL, PIS, Cofins, ISS, ICMS (golden tests obrigatórios)
- Apuração mensal automática + transmissão de PGDAS-D / DCTFWeb / DCTF mensal / EFD-Reinf via SERPRO
- **Geração SPED**: ECD anual, ECF anual, EFD-Contribuições mensal, EFD ICMS-IPI mensal
- DEFIS anual (SN) + DASN-SIMEI (MEI)
- Cálculo de multa/juros (denúncia espontânea via SELIC acumulada)
- Reforma Tributária 2026+: cálculo informacional CBS/IBS; suporte a campos IBSCBS em DFe; pronto para split payment 2027

**Calendário, alertas e compliance:**
- Calendário fiscal por regime + alertas multi-canal (WhatsApp + email + in-app)
- Monitor e-CAC + DTE federal + DET trabalhista
- Monitor cadastral RFB (status: ativo/suspenso/inapto/baixado) — diário
- Monitor Sintegra / regularidade IE estadual
- Certidões automáticas (CND federal + CRF + CNDT)
- Parcelamentos (simulador + monitor de adimplência)

**Contábil e patrimonial:**
- Plano de contas hierárquico + código ECD
- Motor de lançamentos automáticos (NF → razão, banco → razão, folha → razão)
- Imobilizado + depreciação automática (IN SRF 162/1998)
- Provisões trabalhistas (férias, 13º, INSS s/ férias) calculadas mensalmente
- Balancete, DRE, Balanço, DFC, Indicadores
- Encerramento de período mensal e anual

**Folha e departamento pessoal:**
- Cálculo completo de folha (INSS, IRRF, FGTS) com tabelas 2026
- 13º salário (1ª e 2ª parcelas)
- Férias + 1/3 constitucional
- Rescisão completa (verbas, aviso prévio trabalhado/indenizado, FGTS rescisório 40%, GRRF)
- Pró-labore com INSS 11% + IRRF
- Distribuição de lucros com limites de presunção (SN/LP/LR)
- eSocial S-1xxx (mensal), S-2xxx (admissão/rescisão), S-3xxx (exclusão)
- EFD-Reinf (retenções PJ → PJ)
- FGTS Digital

**Tesouraria e Open Finance:**
- Pluggy primário (Belvo backup) com regulação BCB
- Conciliação bancária automática (match banco × NF)
- Contas a pagar / receber
- Fluxo de caixa diário

**IA conversacional:**
- Assistente WhatsApp + in-app com memória persistente por empresa
- Citação obrigatória de fatos (validador de re-check)
- Três camadas: determinística (70%) + LLM local Gemma 3 4B (20%) + LLM cloud Gemini Flash (10%)

**Marketplace de contadores parceiros (Sprint 13+):**
- Encaminhamento estruturado dos 15-25% out-of-scope para contadores/advogados parceiros
- Comissão de 20-30% sobre consultas
- Categorias: contencioso fiscal, holding/sucessão, operações fiscais complexas, planejamento tributário

### 1.2 Premissa central

**LLM nunca escreve fatos no banco.** Pipeline determinístico ingere/calcula/persiste; LLM lê, sintetiza e cita IDs verificáveis. Esta é a única defesa contra alucinação em valores fiscais (risco crítico: cliente paga imposto errado e processa).

### 1.3 Estratégia de cobertura

| Camada | Tempo do contador | Cobertura plano | Como cobrimos |
|---|---|---|---|
| Rotina mensal | ~60% do tempo | **~95%** | Backend completo |
| Eventos pontuais + anuais | ~25% | **~75%** | Backend cobre maioria; alguns out-of-scope |
| Consultoria operacional | ~10% | **~50%** | Assistente IA + simuladores |
| Contencioso fiscal | ~3% | **15%** (deliberado) | Marketplace de parceiros |
| Eventos societários | ~2% | **0%** (deliberado) | Marketplace de parceiros |

**Cobertura ponderada: ~80% do trabalho do contador da PME-alvo.** Os 20% que sobram **não devem entrar no produto** — viram receita extra via marketplace.

### 1.4 Cronograma

- **MVP Simples Nacional para venda:** Sprint 6 (14 semanas)
- **Lucro Presumido completo + SPED:** Sprint 20 (40 semanas)
- **Produto completo PME-alvo:** Sprint 22 (44 semanas / 10 meses)
- **Marketplace de contadores ativo:** Sprint 13 (depois dos primeiros 50 pagantes)

### 1.5 Time mínimo

- 1 senior backend (100%)
- 1 mid backend (100%) — entra na Sprint 5
- 1 mid backend extra (100%) — entra na Sprint 12 para Fase 2
- 1 contador consultor com CRC ativo (30%) — desde Sprint 0
- 1 DevOps (20% compartilhado) — desde Sprint 0
- 1 frontend (50%) — desde Sprint 4 para integrações

### 1.6 Custo operacional estimado (números revisados — ver §12.1)

| Volume | Custo total/mês | Custo/empresa |
|---|---|---|
| 100 empresas pagantes | R$16.700–18.700 | R$170–190 |
| 500 empresas pagantes | R$35.000–45.000 | R$70–90 |
| 1.000 empresas pagantes | R$55.000–70.000 | R$55–70 |

Com pricing R$149–R$499/mês, margem bruta cresce com escala: **15–25% a 100 pagantes → 78–82% a 1.000+ pagantes**. Break-even por volta de 120–150 pagantes. A versão anterior do plano publicava R$30/empresa e margem 80%+ desde o início — números otimistas que mascaravam Status RFB SERPRO, AWS Multi-AZ e overhead de observabilidade self-hosted.

---

## 2. Pesquisa de mercado — fundamentação

Toda decisão deste plano vem de dados reais coletados em maio de 2026. Resumo das fontes que pesarão nas decisões:

### 2.1 Integrações brasileiras

| Serviço | Status 2026 | Decisão | Fonte |
|---|---|---|---|
| **SERPRO Integra Contador** | Plataforma oficial RFB+SERPRO. 27 serviços em 7 APIs (PGDAS-D, DCTFWeb, DARF, DAS, e-CAC, Procurações, Sicalc, MIT). Custo: ~R$0,96 por emissão completa de guia (3 chamadas). Requer certificado e-CNPJ. | **Adotar como camada federal** | SERPRO oficial |
| **Focus NFe** | API REST para todos os DFe (NF-e/NFS-e/NFC-e/CT-e/MDF-e/MD-e/NFCom/DCe). 1.200+ municípios integrados; novos municípios em 15 dias por taxa fixa de R$199. Sem contrato mínimo, sem setup. | **Adotar como camada NF-e/NFS-e** | Focus NFe oficial |
| **Nuvem Fiscal** | **Será desativada em 31/07/2026.** Não usar. | **Descartado** | Aviso oficial Nuvem Fiscal |
| **PlugNotas** (TecnoSpeed) | Alternativa forte, equipe especializada em DFe, evolução dos componentes Delphi para REST moderna. | **Backup de Focus NFe** | NFe.io blog |
| **Pluggy** | Iniciadora de Pagamento autorizada pelo BCB (CNPJ 37.943.755/0001-30). Open Finance regulado. Foco developer-first. | **Adotar como Open Finance primário** | Pluggy oficial |
| **Belvo** | API LATAM, +90% bancos via Open Finance. Lançou solução oficial regulada em 2025 com BACEN. Já tem 60+ instituições + 30 OB regulado. | **Adotar como Open Finance backup** | Belvo / FF News |
| **NFS-e Nacional ADN** | Obrigatória desde 01/01/2026 — todos contribuintes. Cronograma escalonado: nov/2025 (autônomos), dez/2025 (Simples), jan/2026 (demais). Municípios que não aderirem perdem transferências voluntárias. | **Suportar desde dia 1** | Receita Federal + TecnoSpeed |
| **Reforma Tributária CBS/IBS** | LC 214/2025 vigente. PLP 68/2024 e PLP 108/2024 em tramitação para completar o arcabouço infralegal. 2026 = ano informativo (alíquotas teste 0,9% CBS + 0,1% IBS, sem recolhimento). Cronograma de destaque obrigatório em DFe e início de cobrança real **sujeito a alteração** — conferir via newsletter de compliance fiscal antes de cada release. Split payment previsto para 2027+. | **Calcular CBS/IBS desde 2026 como informacional; preparar split payment; tratar cronograma como variável (SCD)** | Min. Fazenda + LC 214/2025 |
| **WhatsApp Business Cloud API** | Per-message desde 01/07/2025. Brasil: utility ~$0.008, marketing $0.0625, service = grátis dentro de 24h após msg do cliente. Click-to-WhatsApp ad = 72h grátis. | **Adotar via Meta Cloud API direto (BSP só se sobrar tempo)** | Meta + Spur + MessageCentral |

### 2.2 LLMs — estado da arte e custo

| Modelo | Preço (input/output por 1M tok) | Quando usar | Fonte |
|---|---|---|---|
| **Gemini 2.5 Flash Lite** | $0.10 / $0.40 | Classificação de intent WhatsApp, extração estruturada simples | pricepertoken |
| **Gemini 2.5 Flash** | $0.30 / $2.50 (cache hit: $0.03 = −90%) | Síntese final de resposta, raciocínio sobre intimações | Google AI / pricepertoken |
| **Gemini 2.5 Pro** | $1.25 / $10.00 | Reservar para análise de SPED/ECF (raro, alto valor) | MetaCTO |
| **Gemma 3 4B local (Ollama)** | Grátis, ~3GB VRAM | Backup offline, intent simples, extração com baixa criticidade | localaimaster + Contabo |
| **Qwen 3 4B local (Ollama)** | Grátis, ~5GB VRAM | Alternativa se Gemma 3 falhar em PT-BR fiscal | codersera + localaimaster |
| **Claude / OpenAI** | Caro demais para volume | NÃO usar em produção | — |

**Decisão:** Gemini Flash Lite + Gemini Flash são primários. Gemma 3 4B local é fallback offline e privacy-first. Cache de prompts é obrigatório (reduz 90% do custo Gemini).

### 2.3 Stack Python

**FastAPI** continua a escolha padrão para greenfield em 2026 (4,5M downloads/dia, OpenAI/Anthropic/Microsoft em produção). Litestar é tecnicamente superior em performance bruta, mas tem ecossistema menor e maior risco de hiring. Para um produto fiscal com múltiplas integrações maduras, FastAPI vence.

### 2.4 Vector database

**pgvector** é a escolha pragmática até ~5M vetores. Nosso caso (RAG por empresa, ~1k–10k fatos por empresa × ~5k empresas) cabe em pgvector com `pgvectorscale`. Migrar para Qdrant só se latência p99 virar problema.

---

## 3. Tech stack final (cravado)

> Não substituir. Decisões dependem umas das outras (ex: Pydantic v2 ↔ FastAPI ↔ SQLAlchemy 2.0 ↔ Alembic).

### 3.1 Runtime e linguagem

| Camada | Tecnologia | Versão | Justificativa |
|---|---|---|---|
| Linguagem | Python | `3.12` | Performance > 3.11; tipo `Self`; pattern matching maduro |
| Framework | FastAPI | `0.115+` | Async-first, OpenAPI auto, ecossistema maduro |
| ORM | SQLAlchemy | `2.0` async | `Mapped[]`, sintaxe moderna, async first-class |
| Migrations | Alembic | `1.13+` | Versionamento de schema |
| Validation | Pydantic | `v2` | Compatibilidade FastAPI + SQLAlchemy; espelho do Zod no frontend |
| HTTP client | httpx | `0.27+` | Async, mantido pelo time da Starlette |
| Workers | Celery | `5.4+` | Maturidade > Dramatiq; RabbitMQ ou Redis broker |
| Scheduler | Celery Beat | `5.4+` | Apuração mensal, sync diário SEFAZ, renovação certidões |
| Testes | pytest + pytest-asyncio | latest | `pytest-cov` para coverage |
| **Geração SPED** | **Parser custom** (eventualmente fork de `python-sped` — Sergio Garcia — como ponto de partida) | — | Para ECD/ECF/EFD-Contribuições/EFD ICMS-IPI. Layouts oficiais do SPED são versionados pela RFB e devem ser tratados como SCD (mudam por ato COTEPE/ICMS e por publicação anual). |

### 3.2 Banco de dados

| Item | Tecnologia | Versão | Justificativa |
|---|---|---|---|
| Banco principal | PostgreSQL | `16` | RLS nativo, JSONB, particionamento, pgcrypto |
| Vector search | pgvector | `0.7+` | Suficiente até 5M vetores |
| Vector tuning | pgvectorscale | `0.4+` | StreamingDiskANN para >2M vetores |
| Cache + queue | Redis | `7.4+` | Sessions, rate limiting, Celery broker |

### 3.3 IA e ML

| Camada | Tecnologia | Quando |
|---|---|---|
| LLM cloud primário | Gemini 2.5 Flash via `google-genai` | Síntese, raciocínio, análise intimação |
| LLM cloud econômico | Gemini 2.5 Flash Lite via `google-genai` | Intent, extração simples |
| LLM local | Ollama + Gemma 3 4B Q4_K_M | Backup, privacy-first, dados sensíveis |
| Embeddings | `nomic-embed-text` via Ollama | 768-dim, grátis, bom em PT-BR |
| Eval | promptfoo (CLI) + custom golden suite | CI bloqueia merge se eval falhar |

### 3.4 Integrações brasileiras

| Domínio | Provider | Backup |
|---|---|---|
| NF-e/NFS-e/NFC-e/CT-e | Focus NFe | PlugNotas |
| RFB / Simples / DCTFWeb / e-CAC / DET | SERPRO Integra Contador | Scraping fallback (último recurso) |
| Open Finance | Pluggy | Belvo |
| WhatsApp | Meta Cloud API direto | Twilio (escala) |
| Email IMAP | aioimaplib | — |
| OCR | Tesseract via pytesseract (Google Vision como upgrade) | — |
| Parser XML NF-e | `nfelib` | parser custom como fallback |
| Certificados A1 | `cryptography` + pkcs12 | — |

### 3.5 Infraestrutura

| Camada | Tecnologia | Notas |
|---|---|---|
| Container | Docker + docker-compose (dev) / Kubernetes (prod) | Helm charts |
| Cloud | AWS São Paulo (sa-east-1) ou GCP southamerica-east1 | LGPD: dados em território nacional |
| Object storage | S3 ou GCS | XMLs, PDFs, certificados criptografados, **SPED files** |
| CDN | CloudFront / Cloud CDN | Frontend e DANFEs públicas |
| Secrets | AWS Secrets Manager / GCP Secret Manager | Certificados A1, API keys |
| Observability | Langfuse self-hosted (LLM) + Grafana + Loki + Tempo (infra) | LGPD: dados no BR |
| Error tracking | Sentry self-hosted (BR) | LGPD |
| CI/CD | GitHub Actions | Lint, testes, golden suite, deploy |

### 3.6 O que NÃO usar (anti-padrões)

- ❌ **Litestar no MVP** — risco de hiring/ecossistema
- ❌ **MongoDB / DynamoDB** — fiscal exige ACID + relacional + RLS
- ❌ **Pinecone / Qdrant** no MVP — pgvector basta
- ❌ **LangChain / LangGraph** no MVP — abstração excessiva, dificulta debug
- ❌ **Claude / GPT em produção** — caro demais
- ❌ **Free tier Gemini com dados reais** — viola LGPD
- ❌ **Nuvem Fiscal** — desativada em 31/07/2026
- ❌ **Hardcoded de tabelas tributárias** — SCD Type 2 obrigatório
- ❌ **HSM real no MVP** — pgcrypto + KMS basta até enterprise

---

## 4. Arquitetura macro

### 4.1 Visão de alto nível

```
                        ┌─────────────────────────────┐
                        │   Frontend (Next.js 15)     │
                        │   analista-fiscal-web       │
                        └──────────────┬──────────────┘
                                       │ HTTPS + JWT
                                       ▼
              ┌────────────────────────────────────────────┐
              │       API Gateway (FastAPI + Uvicorn)      │
              │       /v1/* — REST + OpenAPI auto          │
              │       Auth, rate limit, RLS context        │
              └─────┬───────────┬───────────┬──────────────┘
                    │           │           │
        ┌───────────▼─┐  ┌──────▼──────┐  ┌─▼────────────────┐
        │  Domain     │  │  Domain     │  │  Domain          │
        │  Modules    │  │  Modules    │  │  Modules         │
        │  (fiscal,   │  │  (notas,    │  │  (compliance,    │
        │  contábil,  │  │  ingestão,  │  │  pessoal,        │
        │  sped)      │  │  sped)      │  │  marketplace)    │
        └─────┬───────┘  └──────┬──────┘  └─┬────────────────┘
              │                 │           │
              └─────────────────┼───────────┘
                                ▼
              ┌────────────────────────────────────────────┐
              │  Shared Layer                              │
              │  ├── db (SQLAlchemy + RLS helpers)         │
              │  ├── llm (Gemini + Ollama unificado)       │
              │  ├── auth (JWT + tenant context)           │
              │  ├── crypto (pgcrypto + KMS)               │
              │  ├── audit (immutable trail)               │
              │  ├── sped (geradores ECD/ECF/EFD)          │
              │  └── integrations (Focus, SERPRO, Pluggy)  │
              └────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
       ┌────────────┐  ┌─────────────┐  ┌──────────────┐
       │ Postgres 16│  │ Redis 7     │  │ Object       │
       │ + RLS      │  │ Cache+Queue │  │ Storage (S3) │
       │ + pgvector │  │             │  │              │
       │ + pgcrypto │  │             │  │ XMLs/PDFs    │
       └────────────┘  └──────┬──────┘  │ SPED files   │
                              │         └──────────────┘
                              ▼
              ┌────────────────────────────────────────────┐
              │  Celery Workers (heterogêneos)             │
              │  ├── ingestao    (XML, IMAP, OCR)          │
              │  ├── apuracao    (cálculo mensal)          │
              │  ├── sync        (SEFAZ, e-CAC, Open Fin.) │
              │  ├── sped        (geração ECD/ECF/EFD)     │
              │  ├── notificacao (WhatsApp, email)         │
              │  └── ai          (LLM batch jobs)          │
              └────────────────────────────────────────────┘
```

### 4.2 Estrutura de pastas

```
analista-fiscal-api/
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── README.md
├── PLANO_BACKEND.md          # este arquivo
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── app/
│   ├── main.py               # FastAPI entrypoint
│   ├── config.py             # Settings via pydantic-settings
│   │
│   ├── modules/              # Domain-driven, um módulo por bounded context
│   │   ├── auth/             # Login, JWT, tenant context
│   │   ├── empresa/          # CNPJ, regime, perfil — Sprint 1
│   │   ├── ingestao/         # XML NF-e, IMAP, OCR — Sprint 1+2
│   │   ├── fiscal/           # DAS, IRPJ, CSLL, PIS, Cofins, ICMS — Sprint 2+3+10+11
│   │   ├── notas/            # Emissão NF-e/NFS-e via Focus — Sprint 5
│   │   ├── imobilizado/      # Ativos + depreciação — Sprint 8 (NOVO)
│   │   ├── provisoes/        # Provisões trabalhistas — Sprint 8 (NOVO)
│   │   ├── contabil/         # Plano de contas, lançamentos — Sprint 9
│   │   ├── controles/        # Open Finance, conciliação — Sprint 7
│   │   ├── pessoal/          # eSocial, folha, rescisão — Sprint 10-11
│   │   ├── prolabore/        # Pró-labore + INSS + IRRF — Sprint 10 (NOVO)
│   │   ├── distribuicao/     # Distribuição de lucros — Sprint 11 (NOVO)
│   │   ├── relatorios/       # DRE, Balanço, DFC — Sprint 12
│   │   ├── sped/             # ECD, ECF, EFD-Contribuições, EFD ICMS-IPI — Sprint 16-18 (NOVO)
│   │   ├── compliance/       # e-CAC, DET, certidões, RFB status — Sprint 6+11+13
│   │   ├── multa_juros/      # Cálculo SELIC + denúncia espontânea — Sprint 4 (NOVO)
│   │   ├── agenda/           # Calendário fiscal — Sprint 4
│   │   ├── reforma/          # CBS/IBS — Sprint 14
│   │   ├── memoria/          # Grafo + RAG — Sprint 4
│   │   ├── assistente/       # AI Q&A com citação — Sprint 4
│   │   ├── whatsapp/         # Meta Cloud API + handlers — Sprint 5
│   │   └── marketplace/      # Contadores parceiros — Sprint 13 (NOVO)
│   │
│   ├── shared/
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── models.py     # Modelos centrais (tenant, empresa, usuario)
│   │   │   ├── deps.py       # get_db, get_tenant_context
│   │   │   └── rls.py        # Helpers de RLS
│   │   ├── auth/
│   │   │   ├── jwt.py
│   │   │   ├── middleware.py
│   │   │   └── permissions.py
│   │   ├── llm/
│   │   │   ├── client.py
│   │   │   ├── prompts.py
│   │   │   ├── eval.py
│   │   │   └── citacao.py
│   │   ├── crypto/
│   │   │   ├── pgcrypto.py
│   │   │   └── kms.py
│   │   ├── audit/
│   │   │   └── trail.py
│   │   ├── sped/             # NOVO
│   │   │   ├── ecd_generator.py
│   │   │   ├── ecf_generator.py
│   │   │   ├── efd_contribuicoes.py
│   │   │   ├── efd_icms_ipi.py
│   │   │   └── validador.py
│   │   ├── integrations/
│   │   │   ├── focus_nfe/
│   │   │   ├── serpro/
│   │   │   ├── pluggy/
│   │   │   ├── belvo/
│   │   │   ├── meta_whatsapp/
│   │   │   ├── receita_federal/
│   │   │   └── sintegra/     # NOVO
│   │   ├── tax_tables/       # NOVO
│   │   │   ├── inss.py
│   │   │   ├── irrf.py
│   │   │   ├── fgts.py
│   │   │   ├── simples_nacional.py
│   │   │   ├── presumido_presuncao.py
│   │   │   └── selic.py
│   │   ├── exceptions.py
│   │   └── config.py
│   │
│   └── workers/
│       ├── celery_app.py
│       └── tasks/
│           ├── ingestao_imap.py
│           ├── apuracao_mensal.py
│           ├── sync_sefaz.py
│           ├── sync_ecac.py
│           ├── sync_det.py             # NOVO
│           ├── sync_rfb_status.py      # NOVO
│           ├── sync_sintegra.py        # NOVO
│           ├── geracao_sped.py         # NOVO
│           ├── notificacao_whatsapp.py
│           ├── renovacao_certidoes.py
│           ├── depreciacao_mensal.py   # NOVO
│           ├── provisao_mensal.py      # NOVO
│           └── ai_batch.py
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── fiscal/
│   │   │   ├── test_calcula_das.py        # 30+ casos golden
│   │   │   ├── test_calcula_presumido.py
│   │   │   ├── test_icms_mensal.py        # NOVO
│   │   │   └── test_fator_r.py
│   │   ├── pessoal/
│   │   │   ├── test_inss.py
│   │   │   ├── test_irrf.py
│   │   │   ├── test_fgts.py
│   │   │   ├── test_rescisao.py           # NOVO
│   │   │   ├── test_13o.py                # NOVO
│   │   │   ├── test_ferias.py             # NOVO
│   │   │   └── test_prolabore.py          # NOVO
│   │   ├── imobilizado/                   # NOVO
│   │   │   └── test_depreciacao.py
│   │   ├── provisoes/                     # NOVO
│   │   │   └── test_provisoes_trabalhistas.py
│   │   ├── multa_juros/                   # NOVO
│   │   │   └── test_selic_mora.py
│   │   ├── sped/                          # NOVO
│   │   │   ├── test_ecd_blocos.py
│   │   │   ├── test_ecf_blocos.py
│   │   │   └── test_efd_contribuicoes.py
│   │   └── notas/
│   │       ├── test_chave_nfe.py
│   │       └── test_xml_nfe.py
│   ├── integration/
│   │   ├── test_focus_nfe_sandbox.py
│   │   ├── test_serpro_sandbox.py
│   │   └── test_pluggy_sandbox.py
│   ├── e2e/
│   │   ├── test_onboarding.py
│   │   ├── test_emissao_nfe.py
│   │   ├── test_apuracao_simples.py
│   │   └── test_geracao_ecd.py            # NOVO
│   ├── golden/
│   │   ├── simples_nacional/
│   │   ├── lucro_presumido/
│   │   ├── reforma_tributaria/
│   │   ├── icms_mensal/                   # NOVO
│   │   ├── rescisao/                      # NOVO
│   │   ├── sped_ecd/                      # NOVO
│   │   └── sped_ecf/                      # NOVO
│   └── eval/
│       ├── intent_classification.jsonl
│       ├── extracao_estruturada.jsonl
│       ├── citacao_obrigatoria.jsonl
│       └── encaminhamento_marketplace.jsonl  # NOVO
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.beat
│   ├── k8s/
│   │   ├── helm-chart/
│   │   └── manifests/
│   ├── terraform/
│   │   ├── aws/
│   │   └── gcp/
│   └── scripts/
│       ├── seed_dev.py
│       ├── load_golden_tests.py
│       ├── migrate_tax_tables.py
│       └── seed_marketplace.py            # NOVO
│
└── docs/
    ├── adr/                              # Architecture Decision Records
    │   ├── 0001-fastapi-vs-litestar.md
    │   ├── 0002-pgvector-vs-qdrant.md
    │   ├── 0003-llm-3-camadas.md
    │   ├── 0004-multi-tenancy-rls.md
    │   ├── 0005-fatos-imutaveis.md
    │   ├── 0006-focus-nfe-vs-plugnotas.md
    │   ├── 0007-pluggy-vs-belvo.md
    │   ├── 0008-citacao-obrigatoria.md
    │   ├── 0009-serpro-integra-contador.md
    │   ├── 0010-meta-whatsapp-direto.md
    │   ├── 0011-marketplace-vs-contadores-internos.md  # NOVO
    │   ├── 0012-geracao-sped-propria.md                # NOVO
    │   └── 0013-out-of-scope-deliberado.md             # NOVO
    ├── sprints/
    │   ├── sprint-00.md
    │   └── ...
    ├── api/                              # OpenAPI gerado + custom
    └── runbooks/                         # Incident response, deploy, etc.
```

### 4.3 Camadas conceituais

**Camada 1 — Determinística (Python puro, ~70% do produto):**
- Cálculo DAS Simples Nacional (5 anexos, 6 faixas, Fator R)
- Cálculo Lucro Presumido (IRPJ trimestral, CSLL, PIS cumulativo, Cofins cumulativo, ISS, ICMS mensal)
- Cálculo de rescisão (verbas, aviso, FGTS, GRRF)
- Cálculo de 13º e férias
- Cálculo de pró-labore + INSS 11% + IRRF
- Distribuição de lucros (regras por regime)
- Multa e juros (SELIC acumulada)
- Depreciação automática (linear, IN SRF 162/1998)
- Provisões trabalhistas mensais
- Parsing XML NF-e (`nfelib`) → grafo
- Validação CFOP/CST/NCM contra tabela versionada
- Conciliação bancária por regras
- **Geração SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI)** — todos os blocos
- Geração XML/PDF (DANFE, holerite, DAS, DARF)
- Cálculo CBS/IBS (informacional 2026)

**Camada 2 — LLM local (Gemma 3 4B via Ollama, ~20% do produto):**
- Classificação de intent WhatsApp (PT-BR fiscal)
- Extração estruturada simples (foto de boleto/recibo → JSON)
- Categorização de lançamentos bancários
- **Detecção de pergunta out-of-scope** (encaminhar marketplace)

**Camada 3 — LLM cloud (Gemini 2.5 Flash, ~10% do produto):**
- Síntese final de resposta (WhatsApp + dashboard)
- Análise de intimações e-CAC / DET
- Raciocínio sobre decisões tributárias
- Cache de prompts obrigatório (90% redução de custo)

**Regra inviolável:** LLM **nunca** escreve fatos no banco. Pipeline determinístico ingere; LLM lê e cita IDs.

---

## 5. Modelagem de dados

### 5.1 Schemas core (Sprint 1)

```sql
-- Tenant: dono da conta (escritório contábil ou empresa direta)
CREATE TABLE tenant (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome VARCHAR(255) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  ativo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE usuario (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  email VARCHAR(255) NOT NULL,
  senha_hash VARCHAR(255) NOT NULL,  -- bcrypt cost 12+
  nome VARCHAR(255) NOT NULL,
  ativo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_id, email)
);

CREATE TABLE empresa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  cnpj VARCHAR(14) NOT NULL,
  razao_social VARCHAR(255) NOT NULL,
  nome_fantasia VARCHAR(255),
  regime_tributario VARCHAR(50) NOT NULL CHECK (
    regime_tributario IN ('mei','simples_nacional','lucro_presumido','lucro_real')
  ),
  perfil_ui VARCHAR(50) NOT NULL CHECK (
    perfil_ui IN ('mei','sn_sem_funcionarios','sn_com_funcionarios','lucro_presumido','lucro_real')
  ),
  anexo_simples CHAR(1) CHECK (anexo_simples IN ('I','II','III','IV','V')),
  cnae_principal VARCHAR(10),
  municipio VARCHAR(100),
  uf CHAR(2),
  ie VARCHAR(20),
  im VARCHAR(20),
  faturamento_12m NUMERIC(14,2),
  -- Status cadastral (NOVO)
  status_rfb VARCHAR(20) DEFAULT 'ativa',  -- ativa, suspensa, inapta, baixada
  status_rfb_atualizado_em TIMESTAMPTZ,
  status_sintegra VARCHAR(20),             -- regular, irregular, sem_ie
  status_sintegra_atualizado_em TIMESTAMPTZ,
  ativa BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_id, cnpj)
);

CREATE INDEX ix_empresa_tenant ON empresa(tenant_id);
CREATE INDEX ix_empresa_cnpj ON empresa(cnpj);
CREATE INDEX ix_empresa_perfil ON empresa(tenant_id, perfil_ui);

ALTER TABLE empresa ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON empresa
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

### 5.2 Documentos fiscais (Sprint 2+5)

```sql
CREATE TABLE documento_fiscal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenant(id),
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  tipo VARCHAR(20) NOT NULL CHECK (
    tipo IN ('nfe','nfse','nfce','cte','mdfe','nfcom','dce')
  ),
  direcao VARCHAR(10) NOT NULL CHECK (direcao IN ('saida','entrada')),
  chave VARCHAR(44),
  numero VARCHAR(20) NOT NULL,
  serie VARCHAR(10) NOT NULL,
  status VARCHAR(20) NOT NULL,
  emitida_em TIMESTAMPTZ NOT NULL,
  cnpj_emitente VARCHAR(14) NOT NULL,
  cnpj_destinatario VARCHAR(14),
  valor_total NUMERIC(14,2) NOT NULL,
  valor_impostos NUMERIC(14,2),
  -- Detalhamento de impostos para SPED (NOVO)
  valor_icms NUMERIC(14,2),
  valor_ipi NUMERIC(14,2),
  valor_pis NUMERIC(14,2),
  valor_cofins NUMERIC(14,2),
  valor_iss NUMERIC(14,2),
  cfop VARCHAR(4),
  cst VARCHAR(3),
  ncm VARCHAR(8),
  -- Reforma Tributária 2026+
  valor_cbs NUMERIC(14,2),
  valor_ibs NUMERIC(14,2),
  cclasstrib VARCHAR(20),
  -- Storage
  xml_storage_key VARCHAR(500),
  pdf_storage_key VARCHAR(500),
  natureza_operacao VARCHAR(255),
  regime_emitente VARCHAR(50),
  -- Imutabilidade
  versao INT NOT NULL DEFAULT 1,
  supersedes UUID REFERENCES documento_fiscal(id),
  evento VARCHAR(50),
  -- Audit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  ingested_via VARCHAR(50)
);

CREATE INDEX ix_doc_chave ON documento_fiscal(chave);
CREATE INDEX ix_doc_empresa_tipo ON documento_fiscal(empresa_id, tipo, direcao);
CREATE INDEX ix_doc_emitida ON documento_fiscal(empresa_id, emitida_em DESC);

ALTER TABLE documento_fiscal ENABLE ROW LEVEL SECURITY;
```

### 5.3 Imobilizado e depreciação (Sprint 8 — NOVO)

```sql
CREATE TABLE bem_imobilizado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  descricao VARCHAR(255) NOT NULL,
  categoria VARCHAR(50) NOT NULL,         -- imovel, veiculo, maquina, computador, movel
  data_aquisicao DATE NOT NULL,
  valor_aquisicao NUMERIC(14,2) NOT NULL,
  documento_fiscal_id UUID REFERENCES documento_fiscal(id),
  conta_contabil_id UUID,                 -- referência conta_contabil
  taxa_depreciacao_anual NUMERIC(6,4),   -- ex: 0.10 = 10% a.a.
  metodo_depreciacao VARCHAR(20) DEFAULT 'linear',
  vida_util_meses INT,
  valor_residual NUMERIC(14,2) DEFAULT 0,
  data_baixa DATE,
  motivo_baixa VARCHAR(255),
  ativo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE depreciacao_mensal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  bem_id UUID NOT NULL REFERENCES bem_imobilizado(id),
  competencia DATE NOT NULL,
  valor_depreciado NUMERIC(14,2) NOT NULL,
  valor_acumulado NUMERIC(14,2) NOT NULL,
  saldo_contabil NUMERIC(14,2) NOT NULL,
  lancamento_contabil_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (bem_id, competencia)
);
```

### 5.4 Provisões trabalhistas (Sprint 8 — NOVO)

```sql
CREATE TABLE provisao_mensal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  funcionario_id UUID,                    -- NULL para provisão agregada
  competencia DATE NOT NULL,
  tipo VARCHAR(30) NOT NULL CHECK (
    tipo IN ('ferias','13_salario','inss_ferias','inss_13','fgts_ferias','fgts_13')
  ),
  base_calculo NUMERIC(14,2) NOT NULL,
  aliquota NUMERIC(6,4) NOT NULL,
  valor_provisao NUMERIC(14,2) NOT NULL,
  lancamento_contabil_id UUID,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_provisao_empresa_comp ON provisao_mensal(empresa_id, competencia, tipo);
```

### 5.5 Tabelas tributárias versionadas (SCD Type 2)

```sql
-- Faixas Simples Nacional
CREATE TABLE tabela_simples_faixa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  anexo CHAR(1) NOT NULL CHECK (anexo IN ('I','II','III','IV','V')),
  faixa INT NOT NULL CHECK (faixa BETWEEN 1 AND 6),
  rbt12_ate NUMERIC(14,2) NOT NULL,
  aliquota_nominal NUMERIC(6,4) NOT NULL,
  parcela_deduzir NUMERIC(14,2) NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE,
  fonte VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SELIC acumulada (NOVO)
CREATE TABLE selic_mensal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competencia DATE NOT NULL UNIQUE,        -- 1º dia do mês
  taxa_mensal NUMERIC(6,4) NOT NULL,       -- ex: 0.0085 = 0.85%
  fonte VARCHAR(255) DEFAULT 'BACEN',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de depreciação RFB (NOVO)
CREATE TABLE tabela_depreciacao_rfb (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  categoria VARCHAR(100) NOT NULL,         -- "móveis", "veículos", "computadores"
  taxa_anual NUMERIC(6,4) NOT NULL,
  vida_util_anos INT NOT NULL,
  fonte VARCHAR(255) NOT NULL,             -- 'IN SRF 162/1998 anexo I'
  valid_from DATE NOT NULL,
  valid_to DATE
);

-- Percentuais de presunção Lucro Presumido por CNAE (NOVO)
CREATE TABLE presuncao_lucro_presumido (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  grupo_atividade VARCHAR(100) NOT NULL,
  cnae_pattern VARCHAR(20),                -- pattern para match (regex ou prefixo)
  percentual_irpj NUMERIC(6,4) NOT NULL,   -- 0.08, 0.16, 0.32
  percentual_csll NUMERIC(6,4) NOT NULL,   -- 0.12 ou 0.32
  fonte VARCHAR(255) NOT NULL,             -- 'IN RFB 1.700/2017 art. 33'
  valid_from DATE NOT NULL,
  valid_to DATE
);

-- Histórico de cálculos
CREATE TABLE apuracao_fiscal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  competencia DATE NOT NULL,
  tipo VARCHAR(30) NOT NULL CHECK (
    tipo IN ('das','irpj','csll','pis','cofins','iss','icms','dctf','efd_contrib')
  ),
  regime VARCHAR(50) NOT NULL,
  input_jsonb JSONB NOT NULL,
  output_jsonb JSONB NOT NULL,
  faixas_usadas JSONB NOT NULL,
  algoritmo_versao VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL,
  transmitido_em TIMESTAMPTZ,
  pago_em DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (empresa_id, competencia, tipo)
);
```

### 5.6 SPED files (NOVO — Sprint 16-18)

```sql
CREATE TABLE arquivo_sped (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  tipo VARCHAR(30) NOT NULL CHECK (
    tipo IN ('ecd','ecf','efd_contribuicoes','efd_icms_ipi')
  ),
  periodo_inicio DATE NOT NULL,
  periodo_fim DATE NOT NULL,
  storage_key VARCHAR(500) NOT NULL,       -- S3 key do arquivo .txt SPED
  hash_arquivo VARCHAR(64) NOT NULL,       -- SHA-256 para integridade
  recibo_transmissao VARCHAR(100),         -- número do recibo ReceitaNet
  status VARCHAR(20) NOT NULL,             -- gerado, validado, transmitido, aceito, rejeitado
  validacao_jsonb JSONB,                   -- erros/warnings da validação local
  algoritmo_versao VARCHAR(20) NOT NULL,
  gerado_por_usuario_id UUID,
  gerado_em TIMESTAMPTZ DEFAULT NOW(),
  transmitido_em TIMESTAMPTZ
);

CREATE INDEX ix_sped_empresa_periodo ON arquivo_sped(empresa_id, tipo, periodo_inicio);
```

### 5.7 Pró-labore e distribuição de lucros (NOVO)

```sql
CREATE TABLE prolabore_mensal (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  socio_id UUID NOT NULL,                  -- FK para socio
  competencia DATE NOT NULL,
  valor_bruto NUMERIC(14,2) NOT NULL,
  inss_socio NUMERIC(14,2) NOT NULL,       -- 11% até teto
  irrf NUMERIC(14,2) NOT NULL,
  valor_liquido NUMERIC(14,2) NOT NULL,
  evento_esocial_id UUID,                  -- referência S-1200
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE distribuicao_lucros (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  socio_id UUID NOT NULL,
  data_distribuicao DATE NOT NULL,
  valor NUMERIC(14,2) NOT NULL,
  limite_isento_apurado NUMERIC(14,2) NOT NULL,  -- baseado na presunção
  valor_isento NUMERIC(14,2) NOT NULL,
  valor_tributavel NUMERIC(14,2) DEFAULT 0,
  irrf_retido NUMERIC(14,2) DEFAULT 0,
  base_calculo_referencia VARCHAR(100) NOT NULL,  -- 'presuncao_lp', 'lucro_contabil', 'simples'
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.8 Marketplace de contadores (NOVO — Sprint 13)

```sql
CREATE TABLE contador_parceiro (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nome VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  telefone VARCHAR(20) NOT NULL,
  cpf VARCHAR(11),
  cnpj VARCHAR(14),
  crc_numero VARCHAR(20) NOT NULL,
  crc_uf CHAR(2) NOT NULL,
  crc_status VARCHAR(20) DEFAULT 'ativo',   -- ativo, suspenso, baixado
  especialidades JSONB NOT NULL,            -- ['tributario','trabalhista','societario','contencioso']
  uf_atuacao JSONB,                         -- ['SP', 'RJ', ...]
  rating_medio NUMERIC(3,2),
  total_consultas INT DEFAULT 0,
  taxa_resposta_horas INT,
  sla_resposta_horas INT DEFAULT 24,
  oab_numero VARCHAR(20),                   -- caso seja também advogado
  ativo BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE consulta_marketplace (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  usuario_id UUID NOT NULL,
  contador_id UUID REFERENCES contador_parceiro(id),
  categoria VARCHAR(50) NOT NULL CHECK (categoria IN (
    'consulta_rapida','analise_intimacao_simples','analise_intimacao_complexa',
    'parecer_tecnico','peticao_administrativa','defesa_auto',
    'planejamento_tributario','holding','sucessao'
  )),
  pergunta TEXT NOT NULL,
  pergunta_hash CHAR(64) NOT NULL,           -- SHA-256(empresa_id || categoria || pergunta)
  contexto_empresa_jsonb JSONB NOT NULL,
  snapshot_versao VARCHAR(20) NOT NULL,      -- versão do schema do contexto (ex: 'v1')
  consentimento_compartilhamento BOOLEAN NOT NULL,
  consentimento_revogado_em TIMESTAMPTZ,     -- LGPD: cliente pode revogar
  pii_apagado_em TIMESTAMPTZ,                -- LGPD: timestamp da pseudonimização
  status VARCHAR(20) NOT NULL CHECK (status IN (
    'aberta','atribuida','aceita','em_andamento','concluida','cancelada','expirada'
  )),
  valor_consulta NUMERIC(14,2) NOT NULL CHECK (valor_consulta >= 0),
  comissao_plataforma NUMERIC(14,2) NOT NULL CHECK (
    comissao_plataforma >= 0 AND comissao_plataforma <= valor_consulta
  ),
  resposta_resumo TEXT,
  arquivos_anexos JSONB,
  rating_cliente INT CHECK (rating_cliente IS NULL OR rating_cliente BETWEEN 1 AND 5),
  comentario_cliente TEXT,
  idempotency_key UUID NOT NULL UNIQUE,      -- §8.9 — uuid5(NAMESPACE, "empresa|categoria|hash|dia")
  sla_aceitar_ate TIMESTAMPTZ NOT NULL,
  sla_responder_ate TIMESTAMPTZ NOT NULL,
  aberta_em TIMESTAMPTZ DEFAULT NOW(),
  aceita_em TIMESTAMPTZ,
  respondida_em TIMESTAMPTZ,
  paga_em TIMESTAMPTZ
);

CREATE INDEX ix_consulta_mkt_tenant ON consulta_marketplace(tenant_id);
CREATE INDEX ix_consulta_mkt_empresa_status ON consulta_marketplace(empresa_id, status);
CREATE INDEX ix_consulta_mkt_contador_status ON consulta_marketplace(contador_id, status);
CREATE INDEX ix_consulta_mkt_sla ON consulta_marketplace(status, sla_responder_ate)
  WHERE status IN ('aberta','atribuida','aceita','em_andamento');

ALTER TABLE consulta_marketplace ENABLE ROW LEVEL SECURITY;
CREATE POLICY consulta_mkt_tenant ON consulta_marketplace
  USING (tenant_id = current_setting('app.tenant_id')::UUID);
-- Contador parceiro vê suas consultas via role/policy separada (não fica em ``app.tenant_id``).

```

### 5.9 Memória + grafo + vetores (Sprint 4)

```sql
CREATE TABLE memoria_node (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL REFERENCES empresa(id),
  tipo VARCHAR(50) NOT NULL,
  rotulo VARCHAR(255) NOT NULL,
  atributos JSONB NOT NULL DEFAULT '{}',
  fonte_id UUID,
  fonte_tipo VARCHAR(50),
  embedding VECTOR(768),
  imutavel BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ix_memoria_node_empresa ON memoria_node(empresa_id, tipo);
CREATE INDEX ix_memoria_node_emb ON memoria_node USING hnsw (embedding vector_cosine_ops);

CREATE TABLE memoria_edge (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  empresa_id UUID NOT NULL,
  origem_id UUID NOT NULL REFERENCES memoria_node(id),
  destino_id UUID NOT NULL REFERENCES memoria_node(id),
  tipo VARCHAR(50) NOT NULL,
  atributos JSONB NOT NULL DEFAULT '{}',
  valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.10 Audit trail

```sql
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID,
  usuario_id UUID,
  empresa_id UUID,
  acao VARCHAR(100) NOT NULL,
  recurso_tipo VARCHAR(50),
  recurso_id UUID,
  payload_jsonb JSONB,
  ip_origem INET,
  user_agent TEXT,
  ocorrido_em TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (ocorrido_em);

REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;
```

### 5.11 Princípios da modelagem

1. **Tudo tem `tenant_id`.** RLS Postgres ativo.
2. **Fatos imutáveis.** NF cancelada = nova linha com `evento='cancelou'`.
3. **Cálculos versionados.** `algoritmo_versao` muda quando fórmula muda.
4. **Tabelas tributárias com SCD Type 2.** `valid_from`/`valid_to`.
5. **Audit trail append-only.** Particionado por mês, retenção 5 anos (lei fiscal).
6. **Snapshots de input/output em apurações.** Auditoria reproduz cálculo idêntico.
7. **Storage object para XMLs/PDFs/SPED.** Postgres só guarda metadata + chave.

---

## 6. Camada de IA — híbrida 3-níveis

### 6.1 LLMClient unificado

```python
# app/shared/llm/client.py
from enum import Enum
from typing import Protocol
from decimal import Decimal
from pydantic import BaseModel

class LLMProvider(Enum):
    OLLAMA_GEMMA_3_4B = "ollama-gemma3-4b"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_PRO = "gemini-2.5-pro"

class LLMRequest(BaseModel):
    prompt: str
    system: str | None = None
    response_schema: type[BaseModel] | None = None
    cache_key: str | None = None
    temperature: float = 0.0
    fontes_disponiveis: list[FonteFato] = []

class LLMResponse(BaseModel):
    texto: str
    citacoes: list[Citacao]
    tokens_input: int
    tokens_output: int
    tokens_cached: int
    custo_usd: Decimal
    provider: LLMProvider
    latencia_ms: int
    encaminhar_marketplace: bool = False  # NOVO
    categoria_marketplace: str | None = None  # NOVO

class LLMClient:
    async def chamar(
        self,
        request: LLMRequest,
        provider: LLMProvider,
    ) -> LLMResponse:
        """Despacha para Ollama ou Gemini, registra em Langfuse, valida citação."""
```

### 6.2 Política de roteamento

| Caso de uso | Provider primário | Fallback | Justificativa |
|---|---|---|---|
| Intent WhatsApp ("quanto eu pago de DAS?") | Gemini Flash Lite | Gemma 3 4B local | Volume alto, pergunta simples |
| Extração estruturada (foto de boleto → JSON) | Gemma 3 4B local (privacy) | Gemini Flash Lite | Dados sensíveis |
| Síntese de resposta com fatos do grafo | Gemini Flash | Gemini Flash Lite | Qualidade na linguagem |
| Análise de intimação e-CAC / DET | Gemini Flash | Gemini Pro | Texto não-estruturado complexo |
| Categorização lançamento bancário | Gemma 3 4B local (privacy) | Gemini Flash Lite | Dados sensíveis em massa |
| Decisão tributária complexa | Gemini Pro | Gemini Flash | Caso de alto valor, raro |
| **Detecção out-of-scope (encaminhar marketplace)** | **Gemma 3 4B local** | **Gemini Flash Lite** | **Decisão crítica de produto (NOVO)** |

### 6.3 Detecção de pergunta out-of-scope (NOVO)

```python
# app/shared/llm/citacao.py
from app.modules.marketplace.categorias import CATEGORIAS_MARKETPLACE

OUT_OF_SCOPE_PATTERNS = {
    'contencioso_fiscal': [
        'auto de infração', 'recurso administrativo', 'defesa fiscal',
        'CARF', 'DRJ', 'fiscalização', 'mandado de segurança',
    ],
    'societario': [
        'holding', 'sucessão', 'sócio entrando', 'sócio saindo',
        'alteração contratual', 'cisão', 'fusão', 'incorporação',
    ],
    'planejamento_tributario': [
        'reduzir imposto', 'planejamento tributário',
        'aproveitar incentivo', 'regime especial',
    ],
    'operacoes_complexas': [
        'importação', 'exportação', 'drawback',
        'zona franca', 'ICMS-ST', 'substituição tributária',
    ],
}

async def detectar_out_of_scope(pergunta: str) -> tuple[bool, str | None]:
    """
    Retorna (True, categoria) se pergunta deve ser encaminhada ao marketplace.
    Usa Gemma 3 4B local + match contra padrões.
    """
```

### 6.4 Cache de prompts (obrigatório)

- Cache de **system prompt** (fiscal expert + regras de citação): TTL 7 dias
- Cache de **contexto da empresa** (CNPJ, regime, último mês): TTL 1 hora
- Cache de **fatos de grafo** retornados por RAG: TTL 5 minutos

### 6.5 Eval suite (barreira de merge)

```
tests/eval/
├── intent_classification.jsonl       # 100+ casos
├── extracao_estruturada.jsonl        # 100+ casos
├── citacao_obrigatoria.jsonl         # 50+ casos
├── alucinacao_valor.jsonl            # 50+ casos
└── encaminhamento_marketplace.jsonl  # 50+ casos (NOVO)
```

**CI bloqueia merge se:**
- Intent accuracy < 95%
- Extração F1 < 90%
- Citação válida = 100% (não negociável)
- Alucinação de valor monetário = 0% (zero tolerância)
- Encaminhamento marketplace accuracy > 90% (NOVO)

### 6.6 Re-check determinístico pós-LLM

```python
async def validar_resposta(resp: LLMResponse, fontes: list[FonteFato]) -> bool:
    # 1. Toda citação aponta para um ID válido em fontes?
    for cit in resp.citacoes:
        if cit.fato_id not in {f.id for f in fontes}:
            return False
    
    # 2. Todo valor monetário no texto aparece literalmente em alguma fonte?
    valores_no_texto = extrair_valores_monetarios(resp.texto)
    for valor in valores_no_texto:
        if not any(valor in f.payload for f in fontes):
            return False
    
    # 3. Toda data, CNPJ, CPF idem
    return True
```

---

## 7. Integrações externas

### 7.1 SERPRO Integra Contador

**Serviços usados:**
- PGDAS-D (Simples Nacional)
- DCTFWeb (regime normal)
- DCTF mensal (Lucro Presumido)
- DARF/DAS (emissão de guias)
- e-CAC (caixa postal, situação fiscal)
- DET (caixa postal trabalhista — NOVO)
- Procurações eletrônicas
- Sicalc
- MIT

**Custo:** ~R$0,96/empresa/mês média.

### 7.2 Focus NFe (NF-e/NFS-e/NFC-e/CT-e)

**Por que Focus e não Nuvem Fiscal:** Nuvem Fiscal será desativada em 31/07/2026. Focus tem 1.200+ municípios, suporta NFS-e ADN nacional, R$199 fixo por novo município.

**Emissão e recepção:**
- Saída: POST `/v2/nfse?ref={idempotency_key}` (assíncrono ou síncrono dependendo do município)
- Recepção: GET `/v2/nfes_recebidas?cnpj=...` para manifesto destinatário
- Webhook para callbacks de autorização

### 7.3 Pluggy (Open Finance)

**Primário** developer-first, regulado pelo BCB, ITP autorizada.
**Belvo** como backup com mesmo padrão de integração.

### 7.4 Meta WhatsApp Cloud API

**Direto, sem BSP** no MVP. Custos Brasil 2026:
- Service (resposta a msg do cliente em <24h): GRÁTIS
- Utility template (lembrete DAS, alerta certidão): ~$0.008/msg
- Marketing template: $0.0625/msg (não usaremos)
- Click-to-WhatsApp ad: 72h grátis (oportunidade de aquisição)

### 7.5 Receita Federal (consulta CNPJ + status)

**MVP:** BrasilAPI com cache 30 dias.
**Sprint 11:** Status RFB diário via SERPRO Integra Contador (incluído na assinatura).

### 7.6 Sintegra estadual (NOVO — Sprint 11)

**Sem API unificada nacional.** Estratégia:
- Web scraping por estado (RJ, SP têm sistemas próprios)
- Cache 7 dias
- Alerta se passar de "regular" para "irregular"

**Risco:** scraping pode quebrar quando estado muda layout. Mitigação: alertas + retry manual.

### 7.7 ReceitaNet (transmissão SPED — NOVO — Sprint 16-18)

**SPED Contábil (ECD), SPED Fiscal-Contábil (ECF), EFD-Contribuições, EFD ICMS-IPI:**
- Geração do arquivo .txt no formato oficial
- Validação local (sintática + amarrações)
- Cliente baixa o arquivo e transmite via PVA ou ReceitaNet
- **Nunca transmitimos SPED automaticamente** — requer certificado A1 + ação consciente do cliente (LGPD + responsabilidade legal). Não armazenamos certificado A1 do cliente para SPED. Ver ADR 0014.

**PGDAS-D, DCTFWeb, DCTF mensal (apurações via SERPRO Integra Contador):**
- Modelo distinto do SPED: o SERPRO Integra Contador opera com **certificado do escritório contábil (não do cliente)** + procuração eletrônica e-CAC formal outorgada pelo cliente
- A "transmissão automática" possível aqui é: a) cliente outorga procuração eletrônica no e-CAC ao CNPJ do escritório; b) escritório (= nosso tenant) usa seu próprio cert A1 + token SERPRO para transmitir em nome do cliente; c) audit trail amarra quem solicitou + cert usado + recibo SERPRO
- **Não armazenamos certificado A1 do cliente em nenhum fluxo.** Ver ADR 0014.

### 7.8 Resumo de integrações

| Domínio | Provider primário | Backup | Custo estimado |
|---|---|---|---|
| Federal (Simples, DCTFWeb, DET) | SERPRO Integra Contador | Scraping | R$0,96/empresa/mês |
| NF-e/NFS-e | Focus NFe | PlugNotas | R$0,30–R$1,00/NF |
| Open Finance | Pluggy | Belvo | R$200–500/mês fixo + por conta |
| WhatsApp | Meta Cloud API direto | Twilio | $0.008/msg utility |
| Email IMAP | aioimaplib | — | grátis |
| OCR boletos | Tesseract local | Google Vision | grátis (local) |
| CNPJ lookup | BrasilAPI | SERPRO | grátis |
| Sintegra | Scraping por estado | — | grátis (custo dev) |
| ReceitaNet/SPED | Cliente transmite | — | grátis |

---

## 8. Princípios invioláveis

### 8.1 Multi-tenancy ativa desde o dia 1
- Toda tabela de domínio tem `tenant_id NOT NULL`
- RLS Postgres ativo em **todas** essas tabelas
- Middleware FastAPI injeta `app.tenant_id` a cada request
- Testes de integração validam isolamento
- **Não desativar RLS "temporariamente"** — sempre via `SET LOCAL`

### 8.2 Fatos fiscais imutáveis
- Documentos não são deletados. Cancelamento = nova linha com `evento='cancelou'`
- Apurações antigas não recalculam ao mudar fórmula
- Audit log particionado é append-only

### 8.3 Decisões versionadas (SCD Type 2)
- Toda alíquota tem `valid_from` / `valid_to`
- Cálculos históricos usam tabela vigente na data
- Migrações de tabelas tributárias geram nova versão, nunca substituem

### 8.4 Golden tests como barreira de merge
- `tests/golden/simples_nacional/` — 30+ casos
- `tests/golden/lucro_presumido/` — IRPJ + CSLL + PIS + Cofins + ICMS + ISS
- `tests/golden/folha/` — INSS + IRRF + FGTS + 13º + férias + rescisão
- `tests/golden/sped_ecd/` — validação ECD contra ReceitaNet
- `tests/golden/sped_ecf/` — idem ECF
- CI bloqueia merge se golden falhar

### 8.5 Citação obrigatória em LLM
- Toda resposta de LLM passa por validador
- Falha → reject + retry; segunda falha → resposta padrão ou encaminhar marketplace

### 8.6 Re-check determinístico pós-LLM
- Valores monetários, datas, CNPJs/CPFs: literalidade verificada via regex

### 8.7 LGPD-first
- AES-256 em repouso (pgcrypto + KMS)
- TLS 1.3 em trânsito
- Logs por titular (audit_log particionado)
- Endpoints `/lgpd/exportar` e `/lgpd/excluir`
- Retenção 5 anos
- Dados em território nacional
- Consentimento versionado em onboarding
- DPO designado obrigatório quando passar de 100 clientes
- **Compartilhamento com contador parceiro requer consentimento explícito por consulta** (NOVO)

### 8.8 LLM nunca escreve fatos
- Pipeline determinístico ingere, calcula, persiste
- LLM só lê grafo + apurações, sintetiza, cita IDs

### 8.9 Idempotência em integrações externas
- Toda chamada a Focus NFe / SERPRO / Pluggy usa `idempotency_key`
- Em retry: mesma key → mesmo resultado

### 8.10 Observabilidade obrigatória
- Cada chamada LLM em Langfuse (prompt + resposta + custo + latência)
- Cada chamada SERPRO/Focus/Pluggy em Tempo (traces)
- Cada erro em Sentry self-hosted
- Métricas no Grafana

### 8.11 Out-of-scope é declarado, não improvisado (NOVO)
- Tier 3 (contencioso, holding, planejamento avançado) **nunca** entra no produto
- Assistente IA detecta e encaminha ao marketplace, **nunca tenta responder**
- ToS explicita os limites
- ADR 0013 documenta cada categoria out-of-scope com justificativa

### 8.12 Transmissão de obrigações ao Fisco é ato consciente do cliente (NOVO)
- **SPED (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI):** sistema **gera** o arquivo `.txt` no formato oficial, **valida** localmente, **mostra** erros e amarrações inconsistentes. Cliente ou contador **baixa o arquivo e transmite** via PVA/ReceitaNet com o certificado A1 **dele próprio**. **Não armazenamos certificado A1 do cliente.**
- **PGDAS-D, DCTFWeb, DCTF mensal (via SERPRO Integra Contador):** transmissão delegada pelo modelo oficial — cliente outorga procuração eletrônica e-CAC ao CNPJ do escritório, e o escritório (nosso tenant) usa seu próprio cert A1 + token SERPRO para transmitir. **O certificado armazenado criptografado é o do escritório, nunca o do cliente.**
- Em todos os casos: cliente assina termo no onboarding autorizando o uso da procuração e-CAC; audit trail registra usuário + IP + recibo SERPRO + timestamp.
- Decisão e justificativa completas em ADR 0014 (`docs/adr/0014-transmissao-spedes-modelo.md`).

---

## 9. Cobertura realista e out-of-scope deliberado

### 9.1 Cobertura ponderada

| Camada | Tempo do contador | Cobertura plano | Status |
|---|---|---|---|
| Rotina mensal | ~60% | **~95%** | Plano cobre |
| Eventos pontuais + anuais | ~25% | **~75%** | Plano cobre maioria |
| Consultoria operacional | ~10% | **~50%** | Plano + assistente IA cobrem |
| Contencioso fiscal | ~3% | **~15%** | **Out-of-scope deliberado → marketplace** |
| Eventos societários | ~2% | **0%** | **Out-of-scope deliberado → marketplace** |

**Cobertura ponderada: ~80%** do trabalho do contador da PME-alvo.

### 9.2 O que o plano cobre completamente

**Rotina mensal:**
- Ingestão de XML NF (IMAP + manifesto)
- Conciliação bancária (Pluggy + match automático)
- Folha de pagamento (INSS + IRRF + FGTS 2026)
- Depreciação mensal automática (IN SRF 162/1998)
- Provisões trabalhistas mensais (férias + 13º + INSS s/ férias)
- Apuração DAS Simples Nacional (5 anexos + Fator R)
- Apuração IRPJ + CSLL trimestral Lucro Presumido (8 grupos de presunção)
- Apuração PIS + Cofins cumulativo mensal LP
- Apuração ICMS mensal (com SCD por UF)
- Apuração ISS mensal (municípios não-ADN)
- Transmissão PGDAS-D, DCTFWeb, DCTF mensal, EFD-Reinf
- eSocial S-1xxx, S-2xxx, S-3xxx
- Emissão DAS, DARF, guias
- Renovação certidões (CND, CRF, CNDT)
- Monitor caixa postal e-CAC + DET
- Monitor cadastral RFB + Sintegra
- Cálculo de multa/juros (SELIC)

**Eventos anuais:**
- DEFIS (SN) até 31/março
- ECD até 31/maio (geração + validação + cliente transmite)
- ECF até 31/julho
- DASN-SIMEI (MEI) — via parceria opt-in

**Eventos pontuais:**
- Admissão de funcionário (wizard + eSocial)
- Rescisão completa (verbas + aviso + FGTS + GRRF)
- 13º (1ª/2ª parcela) + férias + 1/3
- Pró-labore (cálculo + INSS + IRRF + S-1200)
- Distribuição de lucros (regras por regime)
- Migração de regime tributário (simulador + execução)
- Compra de imóvel/veículo (cadastro bem + depreciação automática)

### 9.3 O que NUNCA entra no produto (out-of-scope deliberado)

**Contencioso fiscal e tributário:**
- Defesa em auto de infração → advogado tributarista
- Recurso administrativo (DRJ, CARF) → advogado tributarista
- Mandado de segurança → advogado tributarista
- Análise complexa de intimação → contador especialista
- Negociação com Receita / SEFAZ / Município → contador especialista
- PER/DCOMP (compensação) → contador tributário
- Restituição de tributo pago a maior → contador

**Eventos societários:**
- Constituição de empresa (Redesim) → contador + Junta
- Alteração contratual → advogado + Junta
- Mudança de endereço (Junta) → contador
- Mudança de CNAE → contador
- Entrada/saída de sócio → advogado societário
- Cisão / fusão / incorporação → advogado societário
- Holding patrimonial → advogado societário + tributário
- Sucessão familiar → advogado sucessório
- Encerramento de empresa (distrato) → contador + advogado + Junta

**Planejamento tributário complexo:**
- Reorganização societária para redução fiscal → consultor tributário
- Aproveitamento de incentivos fiscais específicos → consultor
- Regime especial (RECAP, REPETRO, etc) → consultor especialista
- Decisão de abrir filial em outro estado → consultor

**Operações fiscais complexas:**
- ICMS-ST avançado (cadeia produtiva) → contador ICMS
- Importação (II, ICMS importação, PIS/Cofins importação, IPI) → despachante + contador
- Exportação (DUE, drawback, RECOF) → despachante + contador
- Operações triangulares → contador especialista
- Bloco K (inventário SPED) → contador industrial

**Lucro Real:**
- Apuração ajustada via LALUR → contador especialista
- PIS/Cofins não-cumulativo com créditos → contador
- Transferência de preços → tributarista internacional

**Setores específicos não cobertos (sem ROI no MVP):**
- Construção civil (CEI/CNO, INSS retido 11%, EFD-Reinf complexa)
- Saúde (DMED, profissionais PF, retenções)
- Agronegócio (FUNRURAL, IN 1700 art. 251)
- Comércio exterior (DI, DUE)
- Indústria pesada (IPI, Bloco K, custos indiretos)
- Imobiliário (DOI, DIMOB, RET, SCP)
- Energia/telecom (NFCom específica)
- Marketplaces (responsabilidade solidária + split payment)
- Cooperativas (regime próprio)
- Entidades sem fins lucrativos (imunidade)
- Empregador doméstico (eSocial Doméstico)

**Pessoa física:**
- DIRPF dos sócios — produtos especializados existem
- IRPF pessoa física em geral

### 9.4 Estratégia para o que sai

Para os out-of-scope, **marketplace de contadores parceiros** (§ 10) resolve. Para os setores não cobertos, **roadmap futuro de verticais** (Fase 5+).

---

## 10. Marketplace de contadores parceiros

### 10.1 Por que marketplace e não contadores internos

| Modelo | Margem | Escalabilidade | Risco regulatório |
|---|---|---|---|
| Contadores internos (Contabilizei) | <40% | Linear (1 contador / N clientes) | Alto (RFB pode auditar) |
| **Marketplace de parceiros** | **80%+** | **Não-linear** | **Baixo (parceiros são autônomos)** |

### 10.2 Fluxo do marketplace

```
1. Cliente pergunta algo no WhatsApp ou dashboard
   ↓
2. LLM classifica intent
   ↓
3. Se intent ∈ out_of_scope_categorias:
   - Resposta: "Esse caso merece um contador especialista. Posso te conectar?"
   - Mostra 3 parceiros melhor avaliados na categoria + UF
   - Cliente escolhe + confirma compartilhamento de dados
   ↓
4. Sistema cria consulta_marketplace com:
   - Categoria
   - Pergunta
   - Snapshot de contexto da empresa (anonymized se cliente preferir)
   - Valor base (R$80-R$2.500 dependendo da categoria)
   ↓
5. Contador parceiro recebe notificação (email + WhatsApp + dashboard)
   - SLA 24h para aceitar
   - SLA 72h para responder
   ↓
6. Contador responde dentro do app (texto + arquivos)
   ↓
7. Cliente recebe resposta + avalia (1-5 estrelas)
   ↓
8. Pagamento: cliente paga via Pix/cartão; plataforma retém 20-30%
```

### 10.3 Categorias e pricing

| Categoria | Preço base | Comissão plataforma | SLA |
|---|---|---|---|
| Consulta rápida (15 min WhatsApp) | R$80–R$150 | 30% | 24h |
| Análise de intimação simples | R$200–R$400 | 25% | 48h |
| Análise de intimação complexa | R$500–R$1.000 | 25% | 72h |
| Parecer técnico (escrito) | R$800–R$1.500 | 20% | 5 dias |
| Petição administrativa | R$1.500–R$3.000 | 20% | 7 dias |
| Defesa de auto de infração | R$2.500+ | 20% | 14 dias |
| Planejamento tributário | R$1.500–R$5.000 | 20% | 14 dias |
| Holding patrimonial | R$3.000–R$15.000 | 15% | 30 dias |
| Sucessão familiar | R$3.000–R$10.000 | 15% | 30 dias |

### 10.4 Curadoria de parceiros

**Critérios mínimos:**
- CRC ativo (validação automática mensal)
- OAB ativa para casos jurídicos
- 3+ anos de experiência na categoria
- Avaliação ≥4.0 nas primeiras 10 consultas (período de teste)
- SLA de resposta cumprido em ≥90% dos casos
- Sem reclamações graves em ouvidoria

**Desligamento automático:**
- Avaliação cai abaixo de 3.5 em 30 dias
- SLA descumprido 3 vezes seguidas
- 2 reclamações graves no trimestre

### 10.5 Receita estimada

| Cenário | Pagantes | Consultas/mês | Ticket médio | MRR adicional |
|---|---|---|---|---|
| Conservador | 100 | 30 (30% dos pagantes 1×/quarter) | R$300 | R$2.250 (25% comissão) |
| Realista | 500 | 200 | R$400 | R$20.000 |
| Otimista | 1.000 | 500 | R$500 | R$62.500 |

**Receita extra estimada: +15-25% sobre MRR de assinatura.**

### 10.6 LGPD e segurança

- Consentimento **explícito por consulta** (não global)
- Cliente vê **exatamente** o que será compartilhado
- Anonização opcional (CPFs/CNPJs redactados)
- Contador parceiro assina NDA + cláusula LGPD
- Audit trail de tudo
- Direito de revogação a qualquer momento (apaga dados do parceiro em 30 dias)

---

## 11. Roadmap — 22 sprints

> Cada sprint = 2 semanas. Total: 44 semanas (~10 meses).

### Fase 1 — MVP Fiscal Simples Nacional (Sprints 0–6, 14 semanas)

| Sprint | Tema | Entregáveis |
|---|---|---|
| **0** | Setup | Repo, Docker Compose, Postgres+Redis+Ollama subindo, FastAPI hello, CI no GitHub Actions, ADRs 0001-0013 escritos |
| **1** | Fundação multi-tenant | Schemas tenant/usuario/empresa, RLS ativo, JWT, endpoints `POST /auth/register`, `POST /auth/login`, testes isolamento |
| **2** | Ingestão XML + DAS | Parser `nfelib`, ingestão upload + IMAP, calculadora DAS SN com 5 anexos + Fator R + RBT12, golden tests bloqueando merge |
| **3** | Camada IA + eval suite | LLMClient unificado, Ollama + Gemma 3 + Gemini Flash Lite, cache de prompts, eval suite 100+ casos, CI roda eval |
| **4** | RAG + memória + agenda + multa/juros | Grafo `memoria_node/edge` com pgvector, embeddings nomic, endpoint `/assistente/perguntar` com citação, calendário fiscal, **cálculo SELIC acumulada para denúncia espontânea** |
| **5** | WhatsApp + emissão NFS-e + onboarding | Meta Cloud API webhook, onboarding por CNPJ → derivar regime, emissão NFS-e via Focus NFe |
| **6** | Compliance v1 + SERPRO + DEFIS | Integra Contador OAuth, PGDAS-D transmissão, e-CAC monitor, certidões CND/CRF/CNDT, **DEFIS geração**, **DASN-SIMEI opt-in**. **Marco Fase 1: 5 empresas demo emitindo NFS-e e pagando DAS.** |

### Fase 2 — Expansão para produto pago (Sprints 7–13, 14 semanas)

| Sprint | Tema | Entregáveis |
|---|---|---|
| **7** | Open Finance + conciliação | Pluggy widget integration, sync transações, algoritmo match banco × NF |
| **8** | **Imobilizado + provisões trabalhistas** | Cadastro de bens, **depreciação automática mensal (IN SRF 162/1998)**, **provisões mensais (férias, 13º, INSS s/ férias)** |
| **9** | Contábil completo | Plano de contas hierárquico + código ECD, motor de lançamentos automáticos, balancete + diário + razão + encerramento |
| **10** | Pessoal completo | Folha com tabelas 2026, holerite PDF, **rescisão completa (verbas + aviso + FGTS + GRRF)**, **13º (1ª/2ª) + férias + 1/3**, **pró-labore (INSS 11% + IRRF)**, eSocial S-1xxx/2xxx/3xxx |
| **11** | Lucro Presumido + ICMS mensal + compliance v2 | Calculadora LP (IRPJ + CSLL + PIS + Cofins), **ICMS apurado mensal**, **EFD-Reinf**, **DET trabalhista**, **monitor RFB cadastral + Sintegra**, classificador intimações via LLM, parcelamentos, **distribuição de lucros** |
| **12** | Relatórios | DRE, Balanço, DFC, Indicadores, DRE auxiliar trimestral LP |
| **13** | **Marketplace de contadores** + primeiros pagantes | Tabelas `contador_parceiro` + `consulta_marketplace`, fluxo de matching, pagamento via Pix/cartão, dashboard do parceiro. **Marco Fase 2: 50 empresas pagantes, MRR R$10k+.** |

### Fase 3 — SPED + Reforma + escala (Sprints 14–20, 14 semanas)

| Sprint | Tema | Entregáveis |
|---|---|---|
| **14** | Reforma Tributária | Cálculo CBS/IBS informacional 2026, suporte campos IBSCBS em NF-e/NFS-e, simulador impacto da Reforma |
| **15** | AI Advisor proativo | Weekly digest WhatsApp, anomaly detection ("seu PIS subiu 40%"), sugestões otimização (Fator R → mudar Anexo) |
| **16** | **SPED ECD + ECF** | Gerador ECD (blocos 0, I, J, 9), gerador ECF (todos os blocos), validador local, golden tests contra ReceitaNet |
| **17** | **EFD-Contribuições + EFD ICMS-IPI** | Gerador EFD-Contribuições mensal, gerador EFD ICMS-IPI mensal, validador local, golden tests |
| **18** | Migração de escritório antigo | Importador SPED 12 meses para reconstruir grafo histórico, importador planilha CSV de movimento |
| **19** | Polish + escala | Performance tuning, cache layers, load testing 1k empresas, bundle onboarding self-service |
| **20** | Lucro Presumido completo pronto pra venda | Validação end-to-end com 10 empresas LP piloto, ajustes finais. **Marco Fase 3: 200 pagantes, MRR R$40k+.** |

### Fase 4 — Lapidação (Sprints 21–22, 4 semanas)

| Sprint | Tema | Entregáveis |
|---|---|---|
| **21** | Hardening + segurança | Pen test externo, fix de findings, bug bounty público, hardening WAF |
| **22** | Documentação + handover | Runbooks operacionais completos, docs de onboarding de novos devs, ADRs revisados, OpenAPI público |

### Fase 5 — Backlog (não-MVP)

- Split payment 2027 (quando regulamentação técnica final sair)
- Bloco K (indústria SPED ICMS-IPI)
- NFC-e + integração PDV (Stone, Cielo, Getnet) — vertical Varejo
- CT-e + MDF-e completo — vertical Transporte
- Marketplaces e split payment 2027+
- Vertical Construção Civil (CEI/CNO, INSS retido)
- Vertical Saúde (DMED, retenções)
- Vertical Agronegócio (FUNRURAL)
- API pública para escritórios contábeis whitelabel
- Mobile app nativo (React Native)
- Integrações ERP (Omie, Conta Azul, Bling)
- Multi-empresa por tenant (escritório com 50 clientes)

### 11.1 Critérios de conclusão por fase

**Fase 1 (Sprint 6):**
- [ ] 5 empresas demo emitindo NFS-e via Focus NFe
- [ ] 100% acerto golden tests Simples Nacional
- [ ] DEFIS gerada para 5 empresas
- [ ] <30s latência resposta WhatsApp p95
- [ ] <2% taxa de alucinação LLM
- [ ] 0 violações de RLS detectadas
- [ ] 100% citação válida em respostas LLM

**Fase 2 (Sprint 13):**
- [ ] 50 empresas pagantes
- [ ] MRR R$10k+
- [ ] Churn mensal <5%
- [ ] Onboarding <2h
- [ ] CAC <R$500
- [ ] Depreciação e provisões batendo com balancete
- [ ] Pelo menos 10 consultas processadas no marketplace
- [ ] Pelo menos 5 contadores parceiros ativos

**Fase 3 (Sprint 20):**
- [ ] 200 pagantes
- [ ] MRR R$40k+
- [ ] NPS ≥40
- [ ] ECD gerada e validada contra ReceitaNet para 10 empresas LP
- [ ] ECF gerada e validada
- [ ] CBS/IBS informacional para 100% das empresas

**Fase 4 (Sprint 22):**
- [ ] Pen test sem findings críticos
- [ ] Runbooks completos
- [ ] OpenAPI público
- [ ] Sistema pronto para 1.000+ pagantes

---

## 12. Custos operacionais (mensais)

### 12.1 Estimativa para 100 empresas pagantes ativas

| Item | Cálculo | Custo BRL |
|---|---|---|
| AWS sa-east-1 | RDS Multi-AZ (db.r6g.large) + EKS multi-AZ + S3 + CloudFront + NAT | R$4.000–6.000 |
| SERPRO Integra Contador — apurações | R$0,96 × 100 transmissões/mês | R$96 |
| SERPRO Integra Contador — status RFB diário | R$0,30 × 100 empresas × 30 dias | R$900 |
| Focus NFe | Plano + ~3.000 NFs/mês | R$700 |
| Pluggy | ~200 contas conectadas | R$500 |
| Meta WhatsApp | ~10 utility/empresa/mês × 100 × $0.008 × R$5 | R$40 |
| Gemini API | Cache hit 80%, ~500k tokens/empresa/mês | R$300 |
| Sentry self-hosted | VM dedicada + storage de eventos + Postgres | R$300–500 |
| Langfuse self-hosted | VM dedicada + Postgres | R$250–400 |
| Snyk + Trivy (security scan) | Licença time | R$1.500 |
| Pen test trimestral (rateado) | R$25k × 4/ano ÷ 12 | R$8.000 |
| Domínio + SSL | Let's Encrypt | R$0 |
| Backups | S3 Glacier + cross-region | R$200 |
| **Total realista** | | **R$16.700–18.700** |

Custo unitário realista para 100 empresas pagantes: **~R$170–190/empresa**.

> ⚠️ A versão anterior deste plano publicava R$3.046 total / R$30 por empresa, subestimando:
> a) AWS Multi-AZ em sa-east-1 (3-5× maior que t3.medium dev);
> b) Status RFB SERPRO **não está incluído** na assinatura — é cobrado à parte (R$0,30/consulta);
> c) Sentry/Langfuse self-hosted exigem VM + Postgres dedicados;
> d) Pen test trimestral e licenças de security scan estavam ausentes.
> Pricing R$149–R$499 continua viável, mas a margem bruta cai de 86% para ~30–40% nesta faixa.
> Margem volta a 80%+ apenas a partir de ~500 pagantes (economia de escala em AWS + diluição de overhead).

### 12.2 Receita estimada por tier

| Tier | Mensalidade | Cobertura |
|---|---|---|
| **MEI** | R$49 | Funcionalidades básicas; muito DAS-SIMEI fixo |
| **Simples Nacional Essentials** | R$149 | Tudo do Fase 1 + ICMS por nota |
| **Simples Nacional Pro** | R$249 | + folha + eSocial + contábil + relatórios |
| **Lucro Presumido** | R$349–R$499 | Tudo + SPED ECD/ECF + EFD-Contribuições + EFD ICMS-IPI |

### 12.3 Receita extra do marketplace

- Conservador: +R$2.250/mês com 100 pagantes
- Realista: +R$20.000/mês com 500 pagantes
- Otimista: +R$62.500/mês com 1.000 pagantes

### 12.4 Margem bruta (refeita com custos realistas — ver §12.1)

| Cenário | Receita | Custos | Margem |
|---|---|---|---|
| 100 pagantes × R$200 médio + R$2.250 marketplace | R$22.250 | R$16.700–18.700 | **15–25%** |
| 500 pagantes × R$200 + R$20.000 marketplace | R$120.000 | R$35.000–45.000 | **62–71%** |
| 1.000 pagantes × R$250 + R$62.500 marketplace | R$312.500 | R$55.000–70.000 | **78–82%** |

> A margem bruta histórica anunciada (86–95%) usava custos subestimados.
> Com números realistas, o break-even ocorre por volta de **120–150 pagantes**, não de 1 pagante.
> Pricing precisa subir ou volume precisa crescer mais rápido para fechar o Marco Fase 2 (50 pagantes, MRR R$10k) com margem positiva — provavelmente exige pricing médio R$249+ (acima do R$200 da tabela).

---

## 13. DevOps e infraestrutura

### 13.1 Ambientes

```
local        → Docker Compose (Postgres, Redis, Ollama)
dev          → AWS sa-east-1, EC2 t3.medium x2, RDS db.t3.medium
staging      → AWS sa-east-1, mesmo size, dados anonimizados de prod
production   → AWS sa-east-1, EKS multi-AZ, RDS Multi-AZ, Read Replica
```

### 13.2 Deploy

- GitHub Actions: lint (ruff) → mypy → testes unit/integration → golden suite → eval suite → build Docker → push ECR → kubectl rollout
- Blue-green em produção via Kubernetes
- Migrations Alembic backward-compatible (2 fases: code primeiro, migration depois)
- Feature flags via `posthog-python` ou `flagsmith` self-hosted

### 13.3 Backup e DR

- RDS automated backup: 30 dias, point-in-time recovery
- Cross-region replication para us-east-1 (DR)
- S3 versioning + lifecycle (XMLs por **5 anos** — CTN art. 173-174, decadência/prescrição quinquenal; estender para 10 anos quando houver fato gerador específico que dispare prescrição decenal cumulativa, p.ex. débito não declarado)
- Restore drill: trimestral
- **SPED gerados: retenção 5 anos no S3 Standard-IA, depois Glacier; extensão para 10 anos sob ato fiscal específico**

### 13.4 Disponibilidade

- SLA alvo: 99,5% (~3h6min downtime/mês)
- Health checks por módulo
- Circuit breakers em integrações externas (`tenacity`)
- Filas com dead-letter para retries falhos

---

## 14. Observabilidade e segurança

### 14.1 Stack

```
Logs       → Loki + Promtail
Métricas   → Prometheus + Grafana
Traces     → Tempo + OpenTelemetry SDK Python
LLM        → Langfuse self-hosted (LGPD: dados no BR)
Errors     → Sentry self-hosted
Alertas    → AlertManager → Slack + PagerDuty
```

### 14.2 Métricas-chave (SLI/SLO)

| Métrica | SLO | Onde |
|---|---|---|
| API latency p99 | <500ms | Grafana |
| Apuração mensal success rate | >99,5% | Grafana |
| LLM citação válida | =100% | Langfuse |
| LLM custo/empresa/mês | <R$3 | Grafana |
| Sync SEFAZ failures | <1%/dia | Grafana |
| RLS violations detected | =0 | Sentry |
| Marketplace SLA cumprido | >90% | Grafana |
| SPED validação local sem erros | >95% | Grafana |

### 14.3 Segurança

**Pré-deploy:**
- `bandit` + `safety` no CI
- Snyk scan dependencies
- Trivy scan Docker images

**Runtime:**
- WAF na frente do API gateway
- Rate limiting por tenant: 1000 req/hora padrão, 100 em endpoints sensíveis
- DDoS protection: CloudFlare
- Secrets em KMS/Secrets Manager

**Auditoria:**
- Trilha imutável (audit_log particionado)
- Trilha de toda chamada LLM
- Pen test trimestral por terceiro (a partir de Fase 2)

### 14.4 LGPD checklist

- [x] Criptografia em repouso (AES-256 via pgcrypto + KMS)
- [x] TLS 1.3 em trânsito
- [x] Dados em território nacional
- [x] Logs por titular acessíveis
- [x] Endpoint exportação (`GET /lgpd/dados-do-titular`)
- [x] Endpoint exclusão (`DELETE /lgpd/dados-do-titular`)
- [x] Consentimento versionado no onboarding
- [x] DPO designado quando passar de 100 clientes
- [x] Política de retenção: 5 anos pós-cancelamento (fiscal)
- [x] Termo de uso revisado por advogado LGPD
- [x] Free tier Gemini proibido com dados reais
- [x] **Compartilhamento com contador parceiro: consentimento explícito por consulta**

---

## 15. Time mínimo recomendado

### 15.1 Fase 1 (Sprints 0–6, 14 semanas)

| Função | Dedicação | Salário/mês |
|---|---|---|
| Tech Lead / Senior Backend | 100% | R$20-25k |
| Mid Backend | 100% (a partir Sprint 5) | R$12-15k |
| Contador / Product consultor | 30% | R$5k |
| DevOps (compartilhado) | 20% | R$3k |
| Frontend (manutenção FiscalAI) | 50% | R$8k |

**Custo Fase 1:** ~R$48-56k/mês × 3,5 meses = **R$170-200k**

### 15.2 Fase 2 (Sprints 7–13, 14 semanas)

Adicionar:
- 1 Mid Backend extra (módulos paralelos): R$13k/mês

**Custo Fase 2:** ~R$60-70k/mês × 3,5 meses = **R$210-245k**

### 15.3 Fase 3 (Sprints 14–20, 14 semanas)

- Manter time da Fase 2
- Adicionar 1 QA específico para SPED + golden tests: R$10k/mês (50%)

**Custo Fase 3:** ~R$65-75k/mês × 3,5 meses = **R$230-260k**

### 15.4 Fase 4 (Sprints 21–22, 4 semanas)

- Pen test externo: R$25-40k (one-shot)

### 15.5 Total estimado MVP-to-production

**~R$660-770k em salários + R$25-40k pen test = R$685-810k em 10 meses.**

### 15.6 Não contratar antes da hora

- ❌ ML Engineer dedicado — Gemini API + golden tests bastam até Fase 5
- ❌ Data Engineer — Postgres + Celery resolve até 1.000 empresas
- ❌ Mobile dev — React Native só na Fase 5+
- ❌ Customer Success — só depois dos primeiros 50 pagantes
- ❌ Contador interno full-time — marketplace resolve

---

## 16. Riscos e mitigação

### R1 — Alucinação em valor fiscal (CRÍTICO)
**Cenário:** sistema responde "DAS R$2.340" no WhatsApp, valor real é R$2.430. Cliente paga errado, recebe multa, processa.
**Mitigação:**
- Valor monetário **sempre** vem da Camada 1 determinística
- LLM nunca gera valor — apenas cita valor calculado
- Re-check verifica literalidade
- Eval suite com 50+ casos de "tentativa de alucinação"
- Eval roda em CI a cada PR
**Alerta precoce:** Langfuse alerta se taxa de citação válida cair abaixo de 99,9%

### R2 — SERPRO Integra Contador throttling (ALTO)
**Cenário:** API limita volume. PGDAS-D não transmite no dia 20.
**Mitigação:**
- Testar volume no sandbox na Sprint 2
- Cache agressivo (situação fiscal 24h, dados cadastrais 30 dias)
- Distribuir transmissão ao longo do mês
- Scraping fallback (último recurso, com disclaimer ao cliente)
- Monitor de SLA SERPRO no Grafana

### R3 — Custo Gemini escalando (MÉDIO)
**Cenário:** cada conversa estoura 10k tokens, margem cai pra <50%.
**Mitigação:**
- Prompt caching obrigatório (90% redução)
- Budget alert em $100/mês inicial
- Migrar perguntas simples para Gemma 3 4B local
- Comprimir contexto

### R4 — Qualidade Gemma 3 4B em PT-BR fiscal (MÉDIO)
**Cenário:** classificação <90%, extração quebra.
**Mitigação:**
- Benchmark na Sprint 3
- Se <90%, migrar para Qwen 3 4B
- Fallback Gemini Flash Lite (custa mais, mantém qualidade)

### R5 — Regulatório CFC/CRC (BAIXO no MVP, ALTO na escala)
**Cenário:** CRC interpreta IA conversacional como "consultoria privativa".
**Mitigação:**
- Posicionar como "software de apoio"
- Disclaimers em toda resposta sensível
- **Marketplace de contadores parceiros com CRC ativo** (cobre o tier 3)
- Parecer jurídico antes de 100 clientes

### R6 — Meta muda política WhatsApp (BAIXO)
**Cenário:** Meta altera pricing/terms.
**Mitigação:**
- Arquitetura multi-canal desde dia 1 (interface abstrata)
- Monitorar políticas Meta mensalmente

### R7 — Reforma Tributária mudanças regulatórias (MÉDIO)
**Cenário:** Lei nova muda alíquota teste ou cronograma split payment.
**Mitigação:**
- Tabelas tributárias com SCD Type 2
- Newsletter compliance fiscal monitorada semanalmente
- Engenheiro on-call para emergências
- Cláusula contratual: "alíquotas atualizadas conforme legislação"

### R8 — Vazamento de dados fiscais (CRÍTICO)
**Cenário:** atacante explora SQL injection ou IDOR.
**Mitigação:**
- RLS Postgres ativo (não confiar só na lógica)
- Pen test trimestral
- WAF com regras OWASP Top 10
- Bug bounty público (Fase 4)
- Cobertura testes de isolamento >95%
- Criptografia em repouso de PII

### R9 — Contador parceiro responde mal e processa a plataforma (MÉDIO — NOVO)
**Cenário:** parceiro dá conselho errado, cliente é multado, processa a plataforma e o contador.
**Mitigação:**
- ToS do marketplace explicita: plataforma é facilitadora, não responsável técnica
- Contador assina termo: responsabilidade técnica é dele
- Seguro de responsabilidade civil obrigatório para parceiros (a partir de Fase 3)
- Avaliação 1-5 + sistema de descredenciamento automático
- Ouvidoria com resposta em 48h

### R10 — Geração SPED incorreta (CRÍTICO — NOVO)
**Cenário:** ECD/ECF gerada com erro de amarração, cliente é multado.
**Mitigação:**
- Golden tests bloqueando merge para todos os blocos
- Validador local antes de cliente baixar
- Sandbox de validação contra PVA da Receita
- ADR 0012 documenta cada decisão de geração
- Disclaimer: "Validar antes de transmitir; em caso de dúvida, consultar contador parceiro"

---

## 17. Métricas de sucesso

### 17.1 Técnicas

- Code coverage: >85% backend
- Golden tests passando: 100%
- Eval suite passando: 100%
- API latency p99: <500ms
- Build time: <8 min
- Deploy frequency: pelo menos diário em dev
- MTTR: <30 min

### 17.2 Produto

- Onboarding completion rate: >80%
- Time to first value: <2h
- WhatsApp DAU/MAU: >40%
- NPS: >40 (Fase 2), >50 (Fase 3)
- Marketplace conversion rate: >5% das perguntas out-of-scope
- Marketplace rating médio: >4.0

### 17.3 Negócio

- Pagantes: 50 (Fase 2), 200 (Fase 3), 1.000 (Fase 5)
- MRR: R$10k (Fase 2), R$40k (Fase 3), R$200k (Fase 5)
- Churn mensal: <5%
- CAC: <R$500
- LTV/CAC: >3
- Marketplace receita: 15-25% sobre MRR de assinatura

---

## 18. Apêndices

### 18.1 ADRs a escrever na Sprint 0

| ADR | Tema |
|---|---|
| 0001 | FastAPI vs Litestar |
| 0002 | pgvector vs Qdrant |
| 0003 | LLM 3-camadas |
| 0004 | Multi-tenancy via RLS |
| 0005 | Fatos imutáveis |
| 0006 | Focus NFe vs PlugNotas |
| 0007 | Pluggy vs Belvo |
| 0008 | Citação obrigatória |
| 0009 | SERPRO Integra Contador |
| 0010 | Meta WhatsApp direto |
| **0011** | **Marketplace vs contadores internos** |
| **0012** | **Geração SPED própria (não Sage/Domínio)** |
| **0013** | **Out-of-scope deliberado (categorias e justificativas)** |

### 18.2 Glossário (rápido onboarding)

| Termo | Significado |
|---|---|
| DAS | Documento de Arrecadação do Simples |
| DARF | Documento de Arrecadação de Receitas Federais |
| DCTFWeb | Declaração de Débitos e Créditos Tributários Federais (Web) |
| PGDAS-D | Programa Gerador do DAS — declaração mensal SN |
| DEFIS | Declaração anual socioeconômica do SN |
| DASN-SIMEI | Declaração anual MEI |
| ECD | Escrituração Contábil Digital (anual) |
| ECF | Escrituração Contábil Fiscal (anual) |
| EFD-Contribuições | Apuração mensal PIS/Cofins (LP/LR) |
| EFD ICMS-IPI | Apuração mensal ICMS/IPI |
| EFD-Reinf | Retenções (PJ → PJ, etc) |
| NFS-e ADN | NFS-e Padrão Nacional, ambiente de dados nacional |
| CBS | Contribuição sobre Bens e Serviços (federal, substitui PIS+Cofins) |
| IBS | Imposto sobre Bens e Serviços (estadual+municipal, substitui ICMS+ISS) |
| IS | Imposto Seletivo (bens nocivos) |
| CFOP | Código Fiscal de Operações e Prestações |
| CST/CSOSN | Código de Situação Tributária |
| NCM | Nomenclatura Comum do Mercosul |
| e-CAC | Centro Virtual de Atendimento ao Contribuinte (caixa postal RFB) |
| DTE | Domicílio Tributário Eletrônico |
| DET | Domicílio Eletrônico Trabalhista |
| eSocial | Sistema unificado de obrigações trabalhistas |
| SPED | Sistema Público de Escrituração Digital |
| Fator R | Razão folha/receita — define Anexo III ou V no SN |
| RBT12 | Receita Bruta dos últimos 12 meses |
| Integra Contador | API oficial SERPRO+RFB |
| Sintegra | Sistema Integrado de Informações sobre Operações Interestaduais |
| Certificado A1 | Arquivo .pfx, 1 ano de validade, para SEFAZ |
| GRRF | Guia de Recolhimento Rescisório do FGTS |

### 18.3 Referências

**Fiscal:**
- LC 123/2006 (Simples Nacional)
- LC 214/2025 (Reforma Tributária — lei base CBS/IBS)
- PLP 68/2024 + PLP 108/2024 (em tramitação — Comitê Gestor IBS e regras complementares; conferir vigência atual antes de citar como norma)
- IN RFB 1.700/2017 (Lucro Presumido)
- IN SRF 162/1998 (depreciação)
- Resolução CGSN 140/2018 (Fator R)
- Ato COTEPE/ICMS 9/2008 (ECD)
- IN RFB 2.004/2021 (ECF)
- CTN art. 173-174 (decadência e prescrição — retenção de documentos fiscais)

**Técnico:**
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- pgvector: https://github.com/pgvector/pgvector
- Pydantic v2: https://docs.pydantic.dev/latest/
- SERPRO Integra Contador: https://apicenter.estaleiro.serpro.gov.br/
- Focus NFe: https://focusnfe.com.br/doc/
- Pluggy: https://docs.pluggy.ai/
- Meta WhatsApp Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api

**Arquitetura:**
- Building Microservices, Sam Newman (2nd ed)
- Designing Data-Intensive Applications, Martin Kleppmann
- Database Internals, Alex Petrov

### 18.4 Próximos passos imediatos

**Esta semana (pré-Sprint 0):**
1. Aprovar este plano v2.0 formalmente
2. Provisionar contas:
   - AWS sa-east-1 ou GCP southamerica-east1
   - SERPRO Integra Contador (Loja SERPRO)
   - Focus NFe sandbox
   - Pluggy sandbox
   - Meta Business + WhatsApp Cloud API sandbox
   - Google Gemini API key (tier pago obrigatório)
3. Criar repositório `analista-fiscal-api` com este `PLANO_BACKEND.md` na raiz
4. Designar Tech Lead
5. Agendar kickoff com consultor contador (CRC ativo)
6. **Iniciar conversa com 5-10 contadores potenciais parceiros do marketplace** (validação informal)

**Sprint 0 (semana 1):**
1. Setup repo + Docker Compose
2. ADRs 0001 a 0013
3. CI básico no GitHub Actions
4. README com `docker compose up`

**Não começar Sprint 1 sem todos os itens da Sprint 0 ✅.**

---

## Mudanças da v1.0 → v2.0

### Adições críticas (Tier 1)
- ✅ ECD anual (SPED Contábil) — Sprint 16
- ✅ ECF anual (SPED Fiscal-Contábil) — Sprint 16
- ✅ EFD-Contribuições mensal — Sprint 17
- ✅ EFD ICMS-IPI mensal — Sprint 17
- ✅ DEFIS — Sprint 6
- ✅ DASN-SIMEI opt-in — Sprint 6
- ✅ Imobilizado + depreciação automática — Sprint 8
- ✅ Provisões trabalhistas — Sprint 8
- ✅ Cálculo rescisório completo (verbas + aviso + FGTS + GRRF) — Sprint 10
- ✅ 13º + férias + 1/3 — Sprint 10
- ✅ Pró-labore + INSS 11% + IRRF — Sprint 10
- ✅ Distribuição de lucros (regras por regime) — Sprint 11
- ✅ ICMS apurado mensal — Sprint 11
- ✅ EFD-Reinf — Sprint 11
- ✅ DET trabalhista — Sprint 11
- ✅ Monitor status RFB diário — Sprint 11
- ✅ Monitor Sintegra estadual — Sprint 11
- ✅ Cálculo multa/juros (SELIC) — Sprint 4

### Novas decisões estratégicas
- ✅ Marketplace de contadores parceiros (Sprint 13) — substitui contadores internos
- ✅ Categorias out-of-scope deliberadas e documentadas (ADR 0013)
- ✅ Transmissão de SPED ao Fisco é ato consciente do cliente (princípio 8.12)

### Crescimento do escopo
- Sprints: 16 → **22** (+6 sprints, +12 semanas)
- Tempo total: 32 → **44 semanas** (10 meses)
- Custo team: R$485k → **R$685-810k**
- Cobertura: 75% → **~80% ponderado** (95% rotina mensal)

### Pontos NÃO mudados
- Stack técnico cravado (Python 3.12 + FastAPI + Postgres 16 + Gemini + Ollama)
- Princípios invioláveis (multi-tenancy, fatos imutáveis, citação obrigatória, LGPD-first)
- Integrações primárias (Focus NFe, SERPRO, Pluggy, Meta WhatsApp)
- Modelo de custo operacional (~R$30/empresa/mês unitário)

---

*Plano v2.0 gerado por Claude — skill `analista-fiscal-br`, modo [ARCHITECTURE] consolidado. Pesquisa de mercado conduzida em maio de 2026. Auditoria de cobertura em 2 rodadas. Decisões cravadas baseadas em dados, não opinião. Tom técnico, sem suavizar.*]