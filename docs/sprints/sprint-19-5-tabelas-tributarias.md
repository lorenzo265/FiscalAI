---
tags: [sprint, tabelas-tributarias, admin, scd, dou, llm, fase-3, concluida, extra]
fonte: "Decisão arquitetural pós-Sprint 18 (2026-05-25) — resolver pendências #9 e #37 sem migration recorrente"
status: concluida
fase: 3
ordem: "executou após [[sprints/sprint-19-performance]]"
estimativa_dias: 6-8
testes_estimados: +55
testes_final: 1821
testes_entregues: 105
pendencias_resolvidas: [9, 37]
concluida_em: 2026-05-27
---

# Sprint 19.5 — Painel admin de tabelas tributárias

> **Sprint extra**, análoga à [[sprint-15-advisor|15.5]] que entregou envio real
> WhatsApp. Substitui a abordagem atual de "criar migration nova toda vez que
> Portaria sair" por **endpoint admin + alerta proativo + scraper DOU
> opcional**. Resolve estruturalmente as pendências **#9** (INSS/IRRF/FGTS 2026)
> e **#37** (INSS 2024) e prepara base para outras vigências (Resolução CGSN,
> Lei IRRF, alíquotas ICMS por UF quando 27 SEFAZ publicarem).

## Contexto

A maioria das tabelas tributárias brasileiras **não tem API REST governamental
oficial** (auditoria 2026-05-25):

| Dado | API oficial | Como acompanhar hoje |
|---|---|---|
| INSS faixa | ❌ | Portaria MPS/MF anual em PDF no DOU |
| IRRF faixa | ❌ | Lei + RFB em PDF |
| FGTS alíquota | ❌ | Lei 8.036/1990 — fixo 8% |
| Simples Nacional (CGSN) | ❌ | Resolução CGSN em PDF |
| Presunção LP / IRPJ / CSLL | ❌ | Lei 9.249/1995 — fixo |
| ICMS por UF | ❌ | 27 SEFAZ cada com sua página |
| CBS / IBS | ❌ | Comitê Gestor IBS em formação |
| SELIC mensal | ✅ | BCB SGS — já usamos (Sprint 4) |
| Feriados nacionais | ✅ | Brasil API — já usamos (agenda) |
| CNPJ + CNAE + IBGE | ✅ | Brasil API — já usamos (onboarding) |

**Resultado:** atualização de tabela = humano lê PDF + agente cria migration.
Pendência #9 demonstra a fragilidade: já estamos em 2026-05 rodando com
tabela INSS 2025 — basta o agente esquecer e folha sai errada.

A Sprint 19.5 entrega **3 camadas em PRs separados**, cada uma com ROI
crescente, em ordem: admin posta → sistema alerta → LLM sugere.

## Objetivo

Tirar o agente Claude do caminho crítico de manutenção de tabelas
tributárias. **Contador admin** (humano com conhecimento fiscal real) passa a
postar nova vigência via API com JSON estruturado; sistema cuida do resto
(SCD, audit, alertas de vencimento, sugestões automáticas via LLM
opcional).

## Marco da sprint

- ⏳ Suite **+~55 testes** (estimativa: 30 + 15 + 10 por camada)
- ⏳ Princípios §8.1 RLS, §8.3 SCD, §8.4 golden, §8.5 citação, §8.6 re-check, §8.8 LLM não escreve fato, §8.10 logs cravados
- ⏳ Pendências #9 + #37 fechadas estruturalmente
- ⏳ Próxima após esta: [[sprints/sprint-20-piloto-lp|Sprint 20 — LP pronto pra venda]]

## Decisão de design

**Princípio inviolável que governa esta sprint:** §8.8 (LLM nunca escreve
fato). Mesmo na Camada 3 (LLM lendo DOU), o **admin humano comita** — o
sistema apenas **sugere** uma vigência pronta para ser aprovada com 1
clique. Nunca cria vigência tributária autonomamente.

**Re-uso máximo de infra existente:**

* Trigger PL/pgSQL `scd_close_previous_valid_to` (Fase 2 PR2) — fecha
  `valid_to` da vigência anterior automaticamente no `INSERT`.
* Role `tax_table_admin` (Fase 2 PR2) — `REVOKE UPDATE,DELETE FROM PUBLIC`
  em todas as 8 tabelas SCD.
* `app/modules/advisor/` (Sprint 15) — reusa pipeline de alerta + integração
  com digest WhatsApp.
* `app/shared/llm/` (Sprint 3) — reusa LLMClient + prompts versionados.
* `app/workers/` (Sprint 11 PR3) — reusa Celery beat schedule.

## PR1 — Camada 1: Endpoints admin de vigência (~3 dias)

Substitui "criar migration nova" por "POST com JSON da Portaria".

### Migration 0042

* `vigencia_tabela_log` (append-only audit cross-tenant):
  ```
  id UUID PK
  tipo_tabela VARCHAR(40) NOT NULL    -- inss|irrf|fgts|simples_nacional|presuncao_lp|icms_uf|cbs_ibs
  valid_from DATE NOT NULL
  fonte_norma TEXT NOT NULL           -- "Portaria MPS/MF 1/2026, DOU 2026-01-15 seção 1 página 42"
  payload_jsonb JSONB NOT NULL        -- snapshot do que foi postado (Decimal → str)
  usuario_admin_id UUID
  idempotency_key UUID UNIQUE         -- uuid5(tipo + valid_from + hash(payload)) → re-POST devolve mesmo log
  registros_criados INT NOT NULL      -- quantas linhas SCD foram criadas
  criado_em TIMESTAMPTZ DEFAULT now()
  ```
* CHECK em `tipo_tabela` aceitando os 7 tipos suportados.
* `GRANT INSERT, SELECT TO tax_table_admin` + `REVOKE UPDATE, DELETE FROM PUBLIC`.
* Sem RLS (operação cross-tenant de sistema, controlada por role).

### Novo módulo `app/modules/tabelas_admin/`

```
tabelas_admin/
├── __init__.py
├── schemas.py         # 7 schemas Pydantic v2 (1 por tipo)
├── validadores.py     # validações §8.6 puras + golden testable
├── repo.py            # VigenciaTabelaLogRepo + 7 repos SCD (re-uso dos existentes)
├── service.py         # TabelaAdminService — orquestra
└── router.py          # 9 endpoints
```

### Schemas Pydantic (1 por tipo)

* `VigenciaInssIn` — campo `faixas: list[FaixaInssIn]` com tipo (empregado/contribuinte_individual/domestico) + limite_superior + aliquota + valor_deducao
* `VigenciaIrrfIn` — `faixas: list[FaixaIrrfIn]` + `deducao_dependente`
* `VigenciaFgtsIn` — `aliquotas_por_vinculo: dict[vinculo, aliquota]`
* `VigenciaSimplesNacionalIn` — `anexo: AnexoEnum` + `faixas: list[FaixaSnIn]`
* `VigenciaPresuncaoLpIn` — `presuncoes_por_cnae: list[PresuncaoCnaeIn]` (CNAE prefix + percentuais IRPJ/CSLL)
* `VigenciaIcmsUfIn` — `aliquotas_por_uf: list[AliquotaIcmsUfIn]`
* `VigenciaCbsIbsIn` — `fase` + `regime` + `cnae_pattern` + alíquotas CBS/IBS

Todos com:
- `model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)`
- `valid_from: date` — primeiro dia do mês/ano
- `fonte_norma: str` (min 10 chars) — citação obrigatória da norma publicada
- `idempotency_key: UUID | None` — admin pode passar para retry idempotente

### Validações §8.6 (puras, golden-testable)

* **Faixas progressivas:** `limite[n] > limite[n-1]`.
* **Alíquotas em [0,1]:** `0 ≤ aliquota ≤ 1` (não aceita "7,5" — exige "0.075").
* **Vigência ≥ vigência atual ativa:** `valid_from > max(valid_from existente)`.
* **Salário mínimo de referência (INSS/IRRF):** primeira faixa deve cobrir o salário mínimo do ano (`limite_superior ≥ salario_minimo_ano(valid_from.year)`).
* **Sem gap nem overlap:** trigger `scd_close_previous_valid_to` já garante no DB, mas validamos antes para erro claro.
* **Soma de alíquotas plausíveis** (heurística): IRPJ presumido 8-32%, CSLL 9%, INSS 7,5-14%, IRRF 0-27,5%.

Cada validação levanta `VigenciaTributariaInvalida(422)` com mensagem específica.

### Endpoints REST

* `POST /v1/admin/tabelas/inss/vigencia` — body `VigenciaInssIn`, response `VigenciaTabelaLogOut`.
* `POST /v1/admin/tabelas/irrf/vigencia`
* `POST /v1/admin/tabelas/fgts/vigencia`
* `POST /v1/admin/tabelas/simples-nacional/vigencia`
* `POST /v1/admin/tabelas/presuncao-lp/vigencia`
* `POST /v1/admin/tabelas/icms-uf/vigencia`
* `POST /v1/admin/tabelas/cbs-ibs/vigencia`
* `GET /v1/admin/tabelas/{tipo}/historico?limit=50` — lista vigências postadas.
* `GET /v1/admin/tabelas/{tipo}/vigente?em=YYYY-MM-DD` — snapshot da vigência ativa.

Todos com `AdminSessionDep` (`SET LOCAL ROLE tax_table_admin` + valida token admin — pattern da Sprint 13 PR1 marketplace).

### Idempotência §8.9

* `idempotency_key = uuid5(NS_TABELA_ADMIN, f"{tipo}|{valid_from}|{sha256(payload_canonico)}")` — re-POST devolve mesmo log sem reescrever.
* Trigger SCD do DB faz o resto: `INSERT` na tabela tributária dispara `scd_close_previous_valid_to('chave_de_dominio')`.

### Exceções novas

* `VigenciaTributariaInvalida(422)` — validação §8.6 falhou.
* `VigenciaTributariaJaPostada(409)` — idempotency_key bate mas payload diverge (indicativo de erro do admin).
* `TipoTabelaDesconhecido(422)` — `tipo` fora dos 7 suportados.

### Resolve #9 e #37 imediatamente

* `POST /v1/admin/tabelas/inss/vigencia` com `valid_from=2026-01-15` + faixas da Portaria MPS/MF 1/2026 → tabela INSS 2026 entra sem migration.
* `POST .../inss/vigencia` com `valid_from=2024-01-01` + faixas retroativas da Portaria 2024 → seed retroativo de INSS 2024 (#37 fechada).

### Tests (~30)

1. POST INSS 2026 com 3 faixas progressivas válidas → 200 + trigger SCD fecha vigência 2025.
2. POST INSS com faixas não progressivas → 422 `VigenciaTributariaInvalida`.
3. POST INSS com alíquota > 1.0 → 422.
4. POST INSS com `valid_from` anterior à vigência ativa → 422.
5. POST INSS com `fonte_norma` < 10 chars → 422 Pydantic.
6. Idempotency_key duplicada com mesmo payload → 200 devolve log anterior.
7. Idempotency_key duplicada com payload diferente → 409.
8. POST sem auth admin → 401.
9. POST com auth de outro role → 403.
10-14. Idem para IRRF (5 testes).
15-18. Idem para FGTS, SN, Presunção LP (4 testes).
19-21. Idem para ICMS UF, CBS/IBS (3 testes).
22. GET historico ordena por valid_from desc.
23. GET vigente em data X retorna correta + 404 se sem vigência.
24-30. Validador puro (`tests/unit/tabelas_admin/test_validadores.py`) — golden para cada regra §8.6.

---

## PR2 — Camada 2: Worker Celery de alerta proativo (~1-2 dias)

Tira a responsabilidade do admin de **lembrar** que tabela mudou — sistema avisa.

### Migration 0043

* `alerta_admin` (operacional do sistema):
  ```
  id UUID PK
  tipo VARCHAR(40)              -- tabela_tributaria_vencida | tabela_proxima_vencer | vigencia_futura_proxima
  severidade VARCHAR(10)        -- info | aviso | critico
  titulo VARCHAR(255)
  descricao TEXT
  contexto_jsonb JSONB          -- {tipo_tabela: 'inss', ano_corrente: 2026, ano_vigencia: 2025, dias_desde: 165}
  idempotency_key UUID UNIQUE   -- uuid5(tipo + tipo_tabela + ano) → não duplica alerta no mesmo período
  resolvido_em TIMESTAMPTZ
  resolvido_por_usuario_id UUID
  criado_em TIMESTAMPTZ DEFAULT now()
  ```
* RLS desligado (admin-only, sem tenant).
* `GRANT SELECT, INSERT, UPDATE TO tax_table_admin`.

### Worker `tabelas.verificar_vigencias`

Beat schedule: daily 06:00 BRT em `app/workers/celery_app.py`.

Lógica por tipo de tabela crítica:

| Tabela | Critério |
|---|---|
| INSS | Se mês ≥ março e ano da vigência ativa < ano corrente → **crítico** (Portaria sai em janeiro) |
| IRRF | Idem (Lei publicada anualmente até fevereiro) |
| FGTS | Vigência > 10 anos sem atualização → **info** (Lei 8.036/1990 raríssima de mudar) |
| Simples Nacional | Vigência > 5 anos → **aviso** (Resolução CGSN pode ter sido atualizada) |
| Presunção LP | Vigência > 10 anos → **info** (Lei 9.249/1995 fixa) |
| ICMS UF | Por UF — alerta se vigência ativa não foi tocada em 2+ anos → **aviso** |
| CBS/IBS | Sempre conferir se há vigência futura ≤ 90 dias → **info** (cronograma LC 214) |

### Endpoints

* `GET /v1/admin/alertas?severidade=critico&resolvido=false` — lista alertas abertos.
* `POST /v1/admin/alertas/{id}/resolver` — marca resolvido (admin pós-POST da Camada 1).
* `POST /v1/admin/alertas/{id}/snooze?dias=30` — adia (raro, mas útil).

### Integração com AI Advisor (Sprint 15)

* Quando `severidade=critico`, o digest semanal `whatsapp.digest_advisor_semanal` (Sprint 15.5) inclui bullet:
  > ⚠ **Tabela INSS 2026 não atualizada** — Portaria MPS/MF de janeiro/2026 deve ter sido publicada. Última atualização: 2025-01-15. Acesse o painel admin: <link>
* Vai para um número específico do contador admin (não para PMEs — é alerta de sistema).
* Pendência: registrar destinatário do alerta admin nas settings.

### Resolução automática

* Quando Camada 1 recebe POST de nova vigência, dispara `tabelas_admin.resolver_alertas_relacionados(tipo_tabela, ano_valid_from)` que marca `resolvido_em` em todos os `alerta_admin` matching `contexto_jsonb.tipo_tabela == tipo && ano_corrente == ano`.

### Logs

* `tabelas.verificacao.iniciada` (1× por dia).
* `tabelas.verificacao.alerta_criado` (com tipo + severidade + ano).
* `tabelas.verificacao.concluida` (com contadores).

### Métricas Grafana

* `tabelas_alerta_total{tipo, severidade}` counter.
* `tabelas_vigencia_dias_desde_atualizacao{tipo_tabela}` gauge.

### Tests (~15)

1. Worker em 2026-03-15 com INSS vigência 2025-01-01 → cria alerta crítico.
2. Worker em 2026-01-10 (antes de março) com mesma vigência → não cria alerta (Portaria ainda pode estar saindo).
3. Worker idempotente: 2 runs no mesmo mês não criam 2 alertas.
4. POST Camada 1 nova vigência 2026 → marca alerta INSS 2026 como resolvido automaticamente.
5. Worker em 2027-01-01 sem POST de 2027 → alerta novo INSS 2027 (idempotency_key diferente).
6. FGTS última vigência 1990 + worker hoje → info (>10 anos).
7. Resolução CGSN > 5 anos → aviso.
8. CBS/IBS com vigência futura 60 dias → info.
9-12. Endpoints GET/POST alerta (listar, filtrar, resolver, snooze).
13-15. Integração com digest WhatsApp (mock do sender).

---

## PR3 — Camada 3: Scraper DOU + LLM extrai estrutura (~2-3 dias)

Tira a responsabilidade do admin de **traduzir PDF em JSON** — LLM faz a
extração, admin **só revisa e aprova**.

### Migration 0044

* `sugestao_vigencia_tabela` (operacional, pendente de aprovação):
  ```
  id UUID PK
  tipo_tabela VARCHAR(40)
  valid_from DATE
  payload_jsonb JSONB            -- estrutura idêntica ao body do POST Camada 1
  fonte_norma TEXT               -- preenchido pelo LLM com citação obrigatória
  fonte_dou_url TEXT             -- URL da matéria no DOU
  fonte_dou_pagina INT
  llm_modelo VARCHAR(50)         -- gemini-2.5-flash etc.
  llm_versao_prompt VARCHAR(50)  -- prompt versionado §8.5
  llm_confianca NUMERIC(3,2)     -- 0..1 confidence reportado pelo LLM
  recheck_passou BOOLEAN         -- §8.6 — re-check determinístico passou?
  recheck_observacoes JSONB      -- detalhes do re-check
  status VARCHAR(20)             -- pendente | aprovada | rejeitada | expirada
  aprovada_em TIMESTAMPTZ
  aprovada_por_usuario_id UUID
  vigencia_tabela_log_id UUID    -- FK do log Camada 1 quando aprovada
  criado_em TIMESTAMPTZ DEFAULT now()
  ```
* CHECK em `status` IN {pendente, aprovada, rejeitada, expirada}.
* `GRANT SELECT, INSERT, UPDATE TO tax_table_admin`.

### Worker `tabelas.varrer_dou_mensal`

Beat schedule: mensal dia 5 às 04:00 BRT.

Pipeline:

1. **Buscar matérias** — DOU tem API JSON pública: `https://www.in.gov.br/consulta?q=` com filtros. Buscar:
   - `q="Portaria MPS/MF" AND "INSS" AND ano:{ano}` — INSS
   - `q="Lei" AND "imposto de renda" AND "tabela progressiva"` — IRRF
   - `q="Resolução CGSN"` — Simples Nacional
   - **Fallback** se API DOU mudar: scraping HTML de `https://www.in.gov.br/leiturajornal`.

2. **Filtrar por publicação recente** — só matérias com `dataPublicacao` nos últimos 60 dias.

3. **Baixar PDF** — campo `urlPdf` do JSON. Cache local (S3/GCS quando #2 estiver pronta; bytea temporário enquanto isso).

4. **Extrair texto** — `pdfplumber` (puro Python, sem dependência de poppler).

5. **Passar para LLM Camada 3 (Gemini 2.5 Flash)** com prompt versionado:
   - `app/shared/llm/prompts/extrair_tabela_inss_v1.md` (e versões por tipo).
   - Prompt exige citação obrigatória (§8.5): cada faixa retornada precisa apontar página + linha do PDF.
   - Output em JSON estruturado matching `VigenciaInssIn`.

6. **Re-check determinístico §8.6** (novo arquivo `app/modules/tabelas_admin/recheck_llm.py`):
   - Reusa `validar_vigencia_inss` puro da Camada 1 PR1.
   - Adiciona checks específicos para extração:
     - Salário mínimo do ano referenciado bate com `salario_minimo_oficial(ano)`.
     - Soma de pesos das faixas plausível.
     - Tipos (empregado/CI/doméstico) presentes.
     - Cita pelo menos 3 strings literais do PDF (anti-alucinação).
   - Se algum check falha, marca `recheck_passou=false` e adiciona detalhe em `recheck_observacoes`.

7. **Criar sugestão** — `INSERT sugestao_vigencia_tabela(status='pendente')`. **Não cria vigência** — §8.8 cravado.

8. **Notificar admin** — gera `alerta_admin` (Camada 2) tipo `sugestao_vigencia_disponivel` severidade `aviso`.

### Endpoints

* `GET /v1/admin/sugestoes-vigencia?status=pendente`.
* `GET /v1/admin/sugestoes-vigencia/{id}` — detalhe + diff com vigência ativa.
* `POST /v1/admin/sugestoes-vigencia/{id}/aprovar` — chama Camada 1 com `payload_jsonb` como body + marca sugestão `aprovada` + link `vigencia_tabela_log_id`.
* `POST /v1/admin/sugestoes-vigencia/{id}/rejeitar?motivo=` — marca rejeitada.

### Princípios cravados na Camada 3

| § | Como |
|---|---|
| 8.5 Citação obrigatória LLM | Prompt exige citação literal de página + linha do PDF; sugestão sem citação é rejeitada pelo re-check |
| 8.6 Re-check determinístico pós-LLM | `recheck_llm.py` valida estrutura antes de criar sugestão; se falha, sugestão fica `status='pendente'` mas com flag `recheck_passou=false` que UI destaca em vermelho |
| 8.8 LLM nunca escreve fato | Sugestão é proposta; vigência só é criada quando admin chama `aprovar` |
| 8.10 Observabilidade | Cada extração tem trace Langfuse + log estruturado `tabelas.dou.extracao_iniciada/concluida/falhou` |

### Custo estimado

* Gemini 2.5 Flash: ~$0.30/M tokens input + $1.25/M output.
* Portaria INSS típica: 5 páginas PDF ≈ 10k tokens input + 500 tokens output (JSON estruturado).
* Custo por extração: ~R$ 0,02.
* Frequência: 4-6 publicações/ano para INSS + IRRF + CGSN.
* Custo anual: **<R$ 1**.

### Out-of-scope da Camada 3

* **Tabelas estaduais (ICMS UF)** — 27 SEFAZ cada com formato próprio. Volume e diversidade torna ROI baixo agora. Quando primeiro cliente migrar de UF não-mapeada, abrir PR dedicado.
* **Resolução CGSN** — extremamente rara (Resolução 140 vigente desde 2018). Admin posta manual quando publicada.
* **Tabela FGTS** — fixa 8% desde 1990. Não vale a pena automatizar.

### Tests (~10)

1. Mock do PDF "Portaria MPS/MF 1/2026" → LLM extrai → re-check passa → cria sugestão pendente.
2. Mock com faixas não progressivas → re-check rejeita → sugestão com `recheck_passou=false`.
3. Mock sem citação literal de página → re-check rejeita.
4. Mock com salário mínimo diferente do oficial → re-check rejeita.
5. POST aprovar sugestão chama Camada 1 + marca aprovada + linka log.
6. POST rejeitar marca rejeitada com motivo.
7. Worker varrer DOU 2 vezes no mesmo mês → idempotência (não duplica sugestão por `idempotency_key=uuid5(url_dou)`).
8. DOU API indisponível → worker loga erro mas não quebra (resiliência).
9. LLM retorna JSON inválido → re-check captura.
10. Sugestão sem aprovação > 60 dias → marca `expirada` automaticamente (limpeza).

---

## Princípios cravados (visão consolidada)

| § | Como aplicado na Sprint 19.5 |
|---|---|
| 8.1 RLS | `vigencia_tabela_log`, `alerta_admin`, `sugestao_vigencia_tabela` são admin-only (sem tenant) — `GRANT ... TO tax_table_admin` controla acesso |
| 8.2 Fatos imutáveis | `vigencia_tabela_log` é append-only com `REVOKE UPDATE,DELETE FROM PUBLIC` |
| 8.3 Decisões versionadas | Trigger SCD existente (Fase 2 PR2) fecha automaticamente `valid_to` da vigência anterior |
| 8.4 Golden tests | Validadores §8.6 puros + golden por tipo de tabela |
| 8.5 Citação obrigatória | Camada 1 exige `fonte_norma` ≥ 10 chars; Camada 3 LLM exige citação literal de página DOU |
| 8.6 Re-check determinístico | Pós-LLM da Camada 3 + pré-INSERT na Camada 1 (faixas progressivas, alíquotas em [0,1], salário mínimo) |
| 8.8 LLM nunca escreve fato | Camada 3 cria **sugestão** — humano admin aprova; sem auto-commit |
| 8.9 Idempotência | `idempotency_key=uuid5` em todas as 3 camadas — re-POST devolve recurso anterior |
| 8.10 Observabilidade | structlog + Langfuse traces + métricas Grafana para alertas + extração |
| 8.12 Out-of-scope declarado | ICMS UF + Resolução CGSN + FGTS explicitamente fora da Camada 3 |

## Pendências resolvidas estruturalmente

* **#9** `[temporal]` Tabela INSS/IRRF/FGTS 2026 — admin posta via Camada 1 (ou Camada 3 sugere e admin aprova). Sem migration nova nunca mais.
* **#37** `[temporal]` Tabela INSS 2024 retroativa — mesmo endpoint resolve, com `valid_from=2024-01-01`. Trigger SCD lida com o resto.

## Pendências novas que esta sprint introduz

* `[risco-deploy]` **Settings para webhook admin de alertas WhatsApp** — número do contador admin do sistema (não PME). Configurar em `app/config.py::settings.ADMIN_WHATSAPP_PHONE`.
* `[externo]` **DOU API estável** — se a API JSON do DOU mudar (ela é semi-pública sem SLA), worker Camada 3 quebra. Fallback HTML scraping documentado mas pode quebrar também.
* `[scope-cut]` **ICMS UF automático** — 27 SEFAZ cada uma com seu portal. Quando primeiro cliente migrar de UF sem cobertura, abrir PR dedicado.

## Out-of-scope explícito

❌ **API governamental REST** — não existe para tabelas tributárias que mudam (INSS, IRRF). Camada 3 (DOU + LLM) é o mais próximo possível.
❌ **Auto-aplicação sem revisão humana** — viola §8.8. Admin sempre comita.
❌ **Tabelas estaduais (ICMS UF)** na Camada 3 — só nas Camadas 1 e 2.
❌ **Integração com Integra Contador SERPRO** — ele expõe operações fiscais (PGDAS-D, certidões), não tabelas.

## Estimativa consolidada

| PR | Esforço | Migrations | Endpoints | Testes |
|---|---|---|---|---|
| PR1 — Painel admin | 3 dias | 0042 (vigencia_tabela_log) | 9 | +30 |
| PR2 — Worker alerta | 1-2 dias | 0043 (alerta_admin) | 3 | +15 |
| PR3 — DOU + LLM | 2-3 dias | 0044 (sugestao_vigencia_tabela) | 4 | +10 |
| **Total** | **6-8 dias** | **3 migrations** | **16 endpoints** | **+55 testes** |

## Cronograma de execução

```
[ Sprint 19 — Polish + load testing 1k empresas ]  ← termina primeiro
                                                  ↓
[ Sprint 19.5 — Tabelas tributárias ]             ← esta sprint
                                                  ↓
[ Sprint 20 — Lucro Presumido pronto pra venda ]
```

Sprint 19.5 **deve fechar antes da Sprint 20** porque o piloto pago precisa
de garantia de que as tabelas tributárias estarão atualizadas durante o
ano-calendário 2026/2027 — sem isso, cliente paga errado e abre incidente
no piloto.

## Referências

- Pendências: [[pendencias/tabela-inss-irrf-fgts-2026]] (#9), [[pendencias/tabela-inss-2024-retroativa]] (#37)
- Princípios: [[principios/03-scd-type-2]], [[principios/05-citacao-llm]], [[principios/06-recheck-deterministico]], [[principios/08-llm-nao-escreve-fatos]]
- Módulos relacionados: [[modulos/advisor]] (Sprint 15 — reusa pipeline de alerta), [[modulos/pessoal]] (consumidor de INSS/IRRF/FGTS)
- ADRs candidatos pós-implementação:
  - `decisoes/adr-0017-painel-admin-tabelas-tributarias.md` (decisão de não usar API governamental porque não existe)
  - `decisoes/adr-0018-llm-extracao-dou-com-recheck.md` (decisão de §8.8 preservado via sugestão-aprovação)
- Sprint anterior: [[sprints/sprint-19-performance]]
- Próxima sprint: [[sprints/sprint-20-piloto-lp]]
