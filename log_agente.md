# Log do Agente — Analista Fiscal Backend

**Última atualização:** 2026-05-20
**Agente:** claude-opus-4-7 (Sonnet 4-6 em sessões anteriores)
**Skill ativa:** `fiscalai-backend`
**Branch:** `main`
**Suite atual:** **996 testes passando**, 2 skipped (bcrypt >72b + eval_live)
**mypy strict:** ✅ 0 erros em 229 arquivos Python

---

## O que estamos construindo

Sistema fiscal-contábil multi-tenant para PMEs brasileiras (Simples Nacional + Lucro Presumido, faturamento R$200k–R$50M/ano). Stack: Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, PostgreSQL 16 com RLS, Celery 5.4+ (skeleton; ativa Sprint 11), Redis 7.4+.

A fonte de verdade absoluta é `C:\dev\Apresentação-Ideia\docs\PlanoBackend.md`. **Nunca tomar decisões de stack ou arquitetura sem consultar o Plano.**

---

## Estado atual — Sprints 1 a 9 ✅

### Fase 1 MVP (Sprints 0-6) — fechada
Marco §11.1 do Plano satisfeito: pipeline NFS-e + DAS + DEFIS + DASN + e-CAC monitor.

### Fase 2 (Sprints 7-9) — fechada parcialmente
Open Finance + conciliação + imobilizado/provisões + contabilidade completa concluídos. Faltam: pessoal (Sprint 10), LP+ICMS+EFD-Reinf (Sprint 11), relatórios DRE/Balanço/DFC (Sprint 12), marketplace contadores (Sprint 13).

### Histórico consolidado de PRs

| Sprint | PR | Tema | Testes finais |
|---|---|---|---|
| 1 | — | Auth multi-tenant + RLS | — |
| 2 | — | Ingestão NF-e + DAS SN | 63 |
| 3 | — | LLM (Ollama+Gemini) + eval suite 350 casos | 290 |
| 4 | — | RAG + agenda + multa/juros SELIC | 186 |
| 5 | — | WhatsApp + NFS-e (Focus NFe) + onboarding | 412 |
| 5-fix | 1+2 | 2 rodadas auditoria fiscal (16 bugs) | 449 |
| 6 | PR1 | SerproClient + OAuth + certidões CND/CRF/CNDT | 468 |
| 6 | PR2 | PGDAS-D transmissão + e-CAC monitor + classificador kw | 509 |
| 6 | PR3 | DEFIS + DASN-SIMEI + worker skeleton | 537 |
| 7 | PR1 | Pluggy client + connect token + items | 560 |
| 7 | PR2 | Sync contas/transações + webhook HMAC + worker | 593 |
| 7 | PR3 | Algoritmo conciliação banco × NF (golden) | 625 |
| 8 | PR1 | Imobilizado + depreciação linear (IN SRF 162/1998) | 654 |
| 8 | PR2 | Provisões trabalhistas (férias, 13º, INSS, FGTS) | 673 |
| 9 | PR1 | Plano de contas + partidas dobradas + plano referencial RFB | 706 |
| 9 | PR2 | Motor lançamentos automáticos NF/tx/depr/prov | 726 |
| 9 | PR3 | Balancete + diário + razão + encerramento mensal/anual | **741** |
| 10 | PR1 | Folha CLT + tabelas INSS/IRRF/FGTS SCD (vigência 2025) + golden tests | **784** |
| 10 | PR2 | 13º (1ª/2ª) + férias + 1/3 + abono + rescisão 5 modalidades + golden | **826** |
| 10 | PR3 | Sócio + pró-labore (INSS 11%) + distribuição lucros + eSocial skeleton 5 eventos | **860** |
| 11 | PR1 | Lucro Presumido completo (IRPJ tri + CSLL tri + PIS/Cofins mensais + SCD presunção) | **890** |
| 11 | PR2 | ICMS mensal por UF (SCD 27 estados) + EFD-Reinf R-4020 (IR 1,5% + CSRF 4,65%) | **917** |
| 11 | PR3 | DET + monitor RFB/Sintegra + parcelamentos + Celery beat schedule | **931** |
| 12 | PR1 | DRE estruturada (Lei 6.404 art. 187) + relatorio_gerado (snapshot imutável) | **941** |
| 12 | PR2 | Balanço Patrimonial (ATIVO=PASSIVO+PL) + DFC método indireto NBC TG 03 | **958** |
| 12 | PR3 | Indicadores (Liquidez/Endiv/Margens/ROA/ROE) + DRE auxiliar trimestral LP | **980** |
| Review | — | Review completa (5 atos) — ~30 achados em plano + código (ver `plans/cheeky-twirling-micali.md`) | — |
| Fase 1.1 | — | Plano: remoção de "LC 227/2026", "fdb-sped", "Ajuste SINIEF 2/2025" + correção de retenção 11→5 anos | — |
| Fase 1.2 | — | Plano: §7.7 vs §8.12 alinhados (SPED manual; PGDAS via procuração e-CAC + cert do escritório) + ADR 0014 escrito | — |
| Fase 1.3 | — | Plano §12: custos realistas (R$3k→R$17k a 100 pagantes; Status RFB R$900 explícito; pen test + Snyk incluídos); §12.4 margem refeita | — |
| Fase 1.4 | — | `calcula_das` v2: sublimite estadual (LC 123 art. 19) + teto federal (LC 123 art. 3º II) — levanta `EmpresaForaSimplesNacional` acima de R$4,8M | **+8 testes** |
| Fase 1.5 | — | `calcula_irpj` v2: IRRF a compensar (Lei 9.430 art. 64) → campos `irrf_consumido`, `irrf_saldo_credor`, `irpj_devido` | **+5 testes** |
| Fase 1.6 | — | `calcula_irpj` v2: quantização única no fim (alinha com PVA/DCTFWeb) | **+2 testes** |
| Fase 1.7 | — | Plano §5.8: DDL `consulta_marketplace` reforçado (idempotency_key, CHECK comissao<=valor, CHECK status, snapshot_versao, índice SLA) — pré-condição Sprint 13 | — |
| **Fase 1 total** | — | Suite **992 passing**, +12 testes vs review baseline; mypy strict 0 erros | **992** |
| Fase 2 PR1 | — | Migration 0024: `documento_fiscal` blindado — `superseded_by` + UNIQUE parcial `(empresa_id,chave) WHERE superseded_by IS NULL` + CHECK em `evento`/`cfop`/`cst` + REVOKE UPDATE/DELETE FROM PUBLIC. Backfill defensivo (supersedes inverso + normalização de CFOP/CST/evento inválidos → NULL). Princípios §8.2 + §8.9 deixam de ser prosa e viram constraint no DB. | **992** |
| Fase 2 PR2 | — | Migration 0025: 8 tabelas SCD blindadas — função PL/pgSQL `scd_close_previous_valid_to()` (SECURITY DEFINER) + trigger AFTER INSERT em 7 tabelas SCD com chaves de domínio explícitas (anexo/faixa, tipo/faixa, faixa, vinculo, categoria, grupo_atividade/cnae_pattern, uf). Role `tax_table_admin` criado + REVOKE UPDATE,DELETE FROM PUBLIC nas 8 tabelas (inclui `selic_mensal` append-only). Princípio §8.3 cravado no DB. | **992** |
| Fase 2 PR3 | — | Migration 0026: MV `rbt12_mensal(tenant_id, empresa_id, competencia, valor)` derivada de `documento_fiscal` (direcao=saida, status=autorizada, superseded_by IS NULL) com window ROWS 11 PRECEDING + UNIQUE INDEX + função `refresh_rbt12_mensal()` SECURITY DEFINER. `EmpresaRepo.rbt12_da_view()` (novo) + fiscal/service e LP/_resolver_presuncao agora leem da view com fallback para `empresa.faturamento_12m`. Celery beat: dia 2 às 6h. Drop da coluna fica para 0027. | **992** |
| Fase 2 PR4 | — | Redução de `Any` em contratos públicos: **144 → 13** ocorrências (alvo do plano era ≤30). Criado `app/shared/types.py` com `JsonObject = dict[str, Any]` (alias canônico para JSONB columns + payloads externos), `app/shared/integrations/serpro/types.py` com TypedDicts do envelope Integra Contador (`SerproRequest`, `SerproResponse`, `SerproParticipante`, `SerproPedidoDados`, `SerproMensagem`, `SerproDadosDeclaracao`). 35 arquivos atualizados em SERPRO/Pluggy/Focus NFe/LLM/eSocial/services. `NotasService` ganha `_FocusClient` Protocol. Eventos folha tipa `tuple[Empresa, Funcionario]` em vez de `tuple[Any, Any]`. As 13 ocorrências restantes são todas em helpers privados justificados (stubs Celery, lazy init `genai.Client`, helpers recursivos `_stringify` / `_detalhes_jsonb` com `noqa: ANN401` explícito). | **992** |
| Fase 2 PR5 | — | **Correção das 6 observações ⚠ da auditoria Sprints 1-3 (2026-05-20).** (1) Novo helper `app/shared/db/rls.py::set_tenant_id(session, tenant_id)` usa `SELECT set_config('app.tenant_id', :tid, true)` com bind param — elimina f-string em SQL nos 5 callsites (`deps.py`, `auth/service.py` ×2, `whatsapp/router.py`, `session_with_tenant`). Defense-in-depth: `verificar_token` já validava UUID, mas agora não há mais interpolação em qualquer caminho. (2) Novo teste `test_with_check_bloqueia_insert_cross_tenant` em `tests/integration/test_rls_isolation.py` — sessão com `tenant_id=A` tenta `INSERT INTO empresa (tenant_id=B, ...)` e espera `IntegrityError`/`ProgrammingError` do Postgres. Cobre o segundo lado da policy (WITH CHECK). (3) 3 ADRs novos: `0011-parser-xml-defusedxml-vs-nfelib.md` (Sprint 2), `0012-prompts-llm-versionados.md` (sistema de carregamento + bump explícito), `0013-celery-instalacao-opt-in.md` (stub fallback + cadência de ativação). (4) Novo módulo `app/shared/llm/prompts/` — carregador `get_prompt(nome)` com `@lru_cache`, dataclass `PromptVersionado(nome, versao, texto, path)`. Primeiro prompt versionado: `assistente_resposta_v1.md` (regras invioláveis de citação + tom dono de PME + out-of-scope). `app/modules/assistente/service.py` agora passa `system=get_prompt("assistente_resposta_v1").texto` no `LLMRequest`. 4 testes unit novos em `tests/unit/llm/test_prompts.py`. Migração dos demais prompts inline (whatsapp/intent, e_cac/classificador) rastreada no ADR 0012 como housekeeping. | **996** |

### Housekeeping
- 2026-05-17: 4 erros mypy strict pré-existentes corrigidos (types-redis 4.6 stub atrasado, Langfuse v2/v3 API divergente, celery_app placeholder importável).
- 2026-05-17: Celery beat schedule definido em `celery_app.py` (Sprint 11 PR3). Workers decorados com `@celery_app.task(name=...)`. Instalação real ainda opt-in (`poetry add celery[redis]`).
- 2026-05-18: Sprint 13 (marketplace) **pausada** até Fase 2 (hardening de schema) concluir. Decisão: bugs fiscais e contradições do plano corrigidos primeiro; schema da consulta_marketplace consolidado no §5.8 antes de qualquer DDL.
- 2026-05-19: Fase 2 PR1 entregue. Migration `0024_fase2_documento_fiscal_hardening.py` + `DocumentoFiscal` no `models.py` recebe `superseded_by` espelhando `supersedes`. Auditoria prévia: 0 callers fazem UPDATE/DELETE em `documento_fiscal` no app (só SELECT) — REVOKE é seguro. Validação do schema real exige `alembic upgrade head` com Docker up; mypy strict + pytest unit/eval seguem 992 green.
- 2026-05-19: Fase 2 PR2 entregue. Migration `0025_fase2_tabelas_scd_hardening.py` — função genérica `scd_close_previous_valid_to()` (SECURITY DEFINER, lê chave de domínio via TG_ARGV + `to_jsonb(NEW)`, fecha `valid_to` da vigência anterior com `IS NOT DISTINCT FROM` para suportar nullable como `cnae_pattern`). 7 triggers AFTER INSERT + REVOKE UPDATE,DELETE FROM PUBLIC em 8 tabelas (7 SCD + selic_mensal). Role `tax_table_admin` criado idempotentemente.
- 2026-05-19: Fase 2 PR3 entregue. Migration `0026_fase2_rbt12_materializada.py` + novo método `EmpresaRepo.rbt12_da_view(empresa_id, competencia)` + wire em `fiscal/service.py` (DAS) e `lucro_presumido/service.py` (presunção LP) com fallback para `empresa.faturamento_12m`. Task Celery `rbt12.refresh_mensal` (dia 2 às 6h) chama a função PL/pgSQL SECURITY DEFINER. Coluna `empresa.faturamento_12m` ainda existe — drop fica para uma migration 0027 separada (2ª fase do drop em 2 fases do plano). Suite mantém 992 passing; mypy 0 erros em 226 arquivos.
- 2026-05-19: Fase 2 PR4 entregue. **Any em contratos públicos: 144 → 13** (`grep -r ": Any\|dict\[str, Any\]" app/`). Novo `app/shared/types.py::JsonObject` e `app/shared/integrations/serpro/types.py` com TypedDicts. 35 arquivos atualizados: SERPRO/Pluggy/Focus NFe/LLM/Brasil API/Meta WhatsApp clients + eSocial payloads + services (declaracao_anual, open_finance, pgdas, certidoes, e_cac, notas, pessoal, lucro_presumido, relatorios, memoria, reinf, icms). `NotasService` ganha `_FocusClient` Protocol. As 13 restantes têm `noqa: ANN401` explícito ou são alias declarations / Celery stub / lazy init. Suite mantém 992 passing; mypy 0 erros em **228** arquivos.

---

## Estrutura do código

```
analista-fiscal-api/
├── alembic/versions/        # 15 migrations (0001-0015)
├── app/
│   ├── modules/             # 20 módulos de domínio (ver lista abaixo)
│   ├── shared/
│   │   ├── db/              # base, models, deps, rls
│   │   ├── auth/            # jwt + middleware
│   │   ├── llm/             # cliente unificado + eval + citação
│   │   ├── integrations/    # focus_nfe, serpro, pluggy, meta_whatsapp, brasil_api
│   │   ├── exceptions.py    # ~50 DomainError mapeadas para HTTP
│   │   └── logging.py
│   ├── workers/             # celery_app (skeleton) + 4 tasks placeholder
│   ├── config.py
│   └── main.py
└── tests/
    ├── unit/                # ~575 tests
    ├── eval/                # 166 casos LLM
    └── integration/         # requer Postgres+Redis (Docker)
```

### 28 módulos de domínio implementados

| Módulo | Sprint | Função |
|---|---|---|
| `auth` | 1 | Register/login JWT, multi-tenant via RLS |
| `empresa` | 1+5 | CRUD empresas + onboarding por CNPJ |
| `ingestao` | 2 | Parser NF-e 4.0 (defusedxml) + upload |
| `fiscal` | 2 | DAS Simples Nacional 5 anexos + Fator R |
| `multa_juros` | 4 | SELIC mora ordinária + denúncia espontânea CTN 138 |
| `agenda` | 4 | Calendário fiscal SN/MEI/LP + FGTS/eSocial/DIRF |
| `memoria` | 4 | Grafo + pgvector RAG (embeddings nomic) |
| `assistente` | 4 | Q&A com citação obrigatória + fallback marketplace |
| `notas` | 5 | NFS-e via Focus NFe + RPS sequencial |
| `whatsapp` | 5 | Meta Cloud API webhook + intent handlers |
| `certidoes` | 6 | CND federal (SERPRO) + CRF/CNDT (skeleton) |
| `pgdas` | 6 | Transmissão PGDAS-D via SERPRO |
| `e_cac` | 6 | Caixa postal RFB + classificador kw |
| `declaracao_anual` | 6 | DEFIS + DASN-SIMEI (geração + transmissão) |
| `open_finance` | 7 | Pluggy items + sync contas/transações + webhook |
| `conciliacao` | 7 | Match banco × NF (algoritmo versionado) |
| `imobilizado` | 8 | Bens + depreciação linear (IN SRF 162/1998) |
| `provisoes` | 8 | Provisões trabalhistas mensais |
| `contabil` | 9 | Plano de contas + lançamentos + balancete + encerramento |
| `pessoal` | 10 | Funcionário CLT + folha mensal + holerite + 13º + férias + rescisão + sócio + pró-labore + distribuição + eSocial skeleton |
| `lucro_presumido` | 11 | IRPJ + CSLL trimestrais + PIS/Cofins cumulativos mensais + SCD presunção por atividade |
| `icms` | 11 | ICMS mensal débito × crédito + SCD 27 UFs + alíquotas interestaduais (4/7/12%) |
| `reinf` | 11 | EFD-Reinf R-4020 — retenção PJ→PJ (IRRF 1,5% + CSRF 4,65%) com dispensa SN/MEI |
| `det` | 11 | Domicílio Eletrônico Trabalhista — caixa postal MTE (espelha `e_cac`) |
| `monitor_cadastral` | 11 | Snapshots RFB CNPJ + Sintegra IE/UF — append-only, mais recente + histórico |
| `parcelamentos` | 11 | Parcelamento ordinário Lei 10.522/2002 — cronograma + parcelas + cancelar |
| `relatorios` | 12 | DRE estruturada (PR1) + Balanço/DFC (PR2) + Indicadores/DRE-aux-LP (PR3) |

---

## Princípios invioláveis (§8 do Plano)

| § | Aplicação |
|---|---|
| 8.1 | RLS ativo em **todas** as 25+ tabelas de domínio (`SET LOCAL app.tenant_id`) |
| 8.2 | Fatos fiscais imutáveis: NF, apurações, lançamentos confirmados, depreciações, provisões — append-only |
| 8.3 | SCD Type 2 em `tabela_simples_faixa`, `tabela_depreciacao_rfb`, `selic_mensal`, `conta_contabil` |
| 8.4 | ~140 golden tests bloqueando regressão silenciosa (DAS, depreciação, provisão, conciliação, lançador, balancete, razão) |
| 8.5 | Citação obrigatória em LLM com validador determinístico (`validar_resposta`) |
| 8.6 | Re-check determinístico pós-LLM (extração de valores, CNPJs, datas via regex) |
| 8.7 | LGPD-first; cert e-CNPJ cifrado via pgcrypto; nunca persistimos credenciais Pluggy/SERPRO |
| 8.8 | LLM nunca escreve fatos — pipeline determinístico ingere/calcula/persiste |
| 8.9 | Idempotência em **todas** as integrações: Focus (uuid5 empresa+numero), SERPRO (X-Request-Tag), Pluggy (UNIQUE webhook_event_id + transaction_id), webhook Meta (HMAC), motor contábil (UNIQUE origem_tipo+origem_id) |
| 8.10 | Log estruturado (`structlog`) em cada chamada externa + apuração + lançamento + encerramento |
| 8.11 | Out-of-scope declarado: contencioso, holding, planejamento — encaminhamento marketplace |
| 8.12 | Transmissão é ato consciente: cliente assina termo no onboarding; geração separada de transmissão (DEFIS, DASN, PGDAS) |

---

## Onde paramos exatamente

**Sprint 12 PR3 fechada (2026-05-17). Sprint 12 inteira completa.** Indicadores + DRE auxiliar trimestral LP:
- 2 algoritmos puros golden-tested (22 testes novos): `calcula_indicadores` (11 índices clássicos: Liquidez Corrente/Seca/Geral, Endividamento Geral, Composição do Endividamento, Margem Bruta/EBITDA/Líquida, ROA, ROE, Giro do Ativo — divisões por zero retornam `None` para frontend mostrar "N/A") e `calcula_dre_aux_lp` (reconciliação trimestral cruzando apurações fiscais Sprint 11 com DRE contábil Sprint 12 PR1 — total por tributo, base presumida × contábil, diferença de receita, carga tributária efetiva).
- Service: `gerar_indicadores` reusa DRE + Balanço do mesmo período (sem nova migration); `gerar_dre_aux_lp` lista apurações do trimestre + converte cada `ApuracaoFiscal` ORM em input do algoritmo (helper `_to_apuracao_input` mapeia por tipo).
- `SaldosPeriodoRepo` ganha `apuracoes_do_trimestre` (lista todas as apurações no intervalo, ordenadas).
- 2 endpoints novos: `POST /v1/empresas/{eid}/relatorios/indicadores` (período), `POST .../dre-aux-lp` (ano+trimestre).
- **Sprint 12 completa**: DRE + Balanço + DFC + Indicadores + DRE auxiliar LP — 5 relatórios contábeis end-to-end usando o motor da Sprint 9 e as apurações fiscais da Sprint 11.

**Sprint 12 PR2 fechada (2026-05-17).** Balanço Patrimonial + DFC:
- 2 algoritmos puros golden-tested (17 testes novos): `calcula_balanco` (estrutura Lei 6.404/1976 art. 178 — Ativo Circ/Não Circ + Passivo Circ/Não Circ + PL; valida invariante ATIVO=PASSIVO+PL com flag `fecha` e `diferenca`) e `calcula_dfc` método indireto NBC TG 03 (Operacional: Lucro + não-caixa ± capital de giro; Investimento: aquisição/venda imobilizado; Financiamento: capital + empréstimos − distribuição; valida invariante saldo_inicial+variação=saldo_final).
- `SaldosPeriodoRepo` ganha 3 métodos: `saldos_posicao_em` (snapshot ativo/passivo/PL na data via subquery max(competencia)), `saldo_conta_codigo_em` (helper de 1 conta), `soma_movimento_codigo_periodo` (delta D-C signed pela natureza num intervalo).
- Service `gerar_balanco` consome saldos de posição; `gerar_dfc` reusa DRE do mesmo período para Lucro Líquido + deriva variações automaticamente de `saldo_conta_mes` para clientes/estoques/fornecedores/encargos/imobilizado/caixa (Caixa+Bancos = 1.1.1.01 + 1.1.1.02). Aporte/empréstimos/distribuição aceitam override no payload (MVP — plano contábil sem contas específicas).
- 2 endpoints novos: `POST /v1/empresas/{eid}/relatorios/balanco` (snapshot na `data_referencia`), `POST .../dfc` (período).

**Sprint 12 PR1 fechada (2026-05-17).** DRE estruturada:
- Migration 0022 cria `relatorio_gerado` (RLS) — tabela única que serve DRE/Balanço/DFC/Indicadores/DRE-aux-LP. Snapshot imutável: re-gerações criam nova linha com `superseded_by` apontando para a anterior (UNIQUE parcial onde `superseded_by IS NULL`).
- 1 algoritmo puro golden-tested (10 testes): `calcula_dre` estruturada Lei 6.404/1976 art. 187. Mapeia plano referencial RFB (4.x receitas, 5.x despesas) → Receita Bruta → Líquida → Lucro Bruto → EBITDA → EBIT → LAIR → Lucro Líquido. Match por prefixo com boundary de ponto (evita match indevido).
- Módulo `relatorios/` novo: `SaldosPeriodoRepo` agrega movimento das contas de resultado (4.x e 5.x) no período via `SaldoContaMes` (materializado na Sprint 9). IRPJ + CSLL vem de `apuracao_fiscal` (Sprint 11 PR1).
- 3 endpoints REST: `POST /v1/empresas/{eid}/relatorios/dre` (idempotente, com `forcar_regerar=true` para nova versão), `GET .../relatorios` (lista), `GET .../relatorios/{id}` (detalhe).
- 2 exceções de domínio novas: `RelatorioNaoEncontrado`, `SemDadosContabeis`.

**Sprint 11 PR3 fechada (2026-05-17). Sprint 11 inteira completa.** DET + monitor cadastral + parcelamentos + Celery beat:
- Migration 0021 cria 5 tabelas (todas RLS): `mensagem_det` (espelha pattern de `mensagem_e_cac`), `status_cadastral_rfb` (snapshot CNPJ RFB — append-only), `status_sintegra` (snapshot IE por UF — append-only), `parcelamento_fiscal` + `parcela_fiscal`.
- 1 algoritmo puro golden-tested (14 testes novos): `calcula_parcelamento` — Lei 10.522/2002 (até 60 parcelas, parcela mínima R$200 PJ / R$100 PF). Trata bordas de dia inexistente (31/jan → 28/29 de fev). PERT, PERT2 e modalidades especiais ficam para sprint futura.
- 3 módulos novos: `det/`, `monitor_cadastral/`, `parcelamentos/` — cada um com repo + service + router. DET marca lida automaticamente; monitor é append-only com `/atual` + `/historico`; parcelamento gera cronograma + permite cancelar.
- 4 exceções de domínio novas: `MensagemDetJaExiste`, `ParcelamentoInvalido`, `ParcelamentoNaoEncontrado`, `ParcelamentoJaCancelado`.
- 11 endpoints REST novos.
- **Celery beat schedule configurado** (`celery_app.py`): 4 tasks periódicas com cron (e-CAC 06:00 diário, Pluggy 07:00 diário, depreciação dia 1 às 03:00, provisão dia 28 às 23:00). Stub fallback mantido para que a suite rode sem Celery instalado — basta `poetry add celery[redis]` para ativar real (instrução documentada no docstring do módulo). 4 workers agora têm `@celery_app.task(name=..., acks_late=True, max_retries=3, queue='default')` — beat encontra pelo nome.

**Sprint 11 PR2 fechada (2026-05-17).** ICMS mensal + EFD-Reinf:
- Migration 0020 cria `aliquota_icms_uf` SCD (sem RLS — pública) com seed das 27 UFs vigente em 2025 (CONFAZ + leis estaduais; RJ com FECP 2%, BA com adicional saúde 1,5%) e `efd_reinf_evento` (RLS) com 15 tipos suportados (R-2010..R-9000), UNIQUE composto (empresa, tipo, referencia_id) para idempotência §8.9.
- 2 algoritmos puros golden-tested (27 testes novos):
  - `calcula_icms` mensal — débito × crédito + saldo credor anterior + ajustes (LC 87/1996). Helper `aliquota_interestadual` resolve Sul/Sudeste→N/NE/CO+ES (7%), outras combinações (12%), mercadoria importada (4% — Res. Senado 13/2012).
  - `calcula_retencao_pj_pj` — IRRF 1,5% (Lei 7.713/1988) + CSRF 4,65% (PIS 0,65% + Cofins 3% + CSLL 1% — Lei 10.833/2003). Dispensa automática de CSRF quando total < R$10 (IN RFB 459/2004). Tomador SN/MEI dispensado de toda retenção (LC 123/2006).
- 2 módulos novos: `app/modules/icms/` + `app/modules/reinf/`. ICMS reusa `apuracao_fiscal` tipo='icms' (Sprint 2). Reinf grava em `efd_reinf_evento` com payload R-4020 espelhando leiaute v2.1.2.
- 4 endpoints novos: `POST/GET /v1/empresas/{eid}/icms/...`, `POST/GET .../reinf/...`.
- 5 exceções de domínio novas: `UfNaoSuportada`, `EmpresaSemUf`, `ApuracaoIcmsJaExiste`, `EventoReinfJaExiste`, `RegimeIsentoRetencao`.

**Sprint 11 PR1 fechada (2026-05-17).** Lucro Presumido completo:
- Migration 0019 cria `presuncao_lucro_presumido` SCD (sem RLS — tabela pública) com seed de 12 linhas cobrindo 8 grupos (IN RFB 1.700/2017 art. 33): comercio_industria default (8%/12%), revenda_combustiveis (1,6%/12%), transporte_cargas (8%/12%), servicos_hospitalares (8%/12%), transporte_passageiros (16%/12%), servicos_gerais_pequenos (16%/12% — condicional fat. ≤ R$120k/ano), servicos_profissionais (32%/32% — CNAEs 69, 71, 73), intermediacao_negocios (32%/32% — CNAEs 70, 74, 82).
- 4 algoritmos puros golden-tested (30 testes novos):
  - `calcula_irpj` trimestral — 15% sobre base presumida + adicional 10% sobre o que exceder R$20.000 × meses (Lei 9.249/1995 art. 3º §1º). Aceita meses 1..3 para início de atividade.
  - `calcula_csll` trimestral — 9% sobre base presumida (Lei 7.689/1988).
  - `calcula_pis_cofins` — 0,65% PIS + 3% Cofins cumulativos mensais (Leis 9.715/1998 + 9.718/1998), com exclusões legais (vendas canceladas, descontos incondicionais, IPI destacado).
- Resolução por CNAE: `PresuncaoLpRepo.resolver_por_cnae` faz match por prefixo normalizado (sem pontos/traços), ordenando por `prioridade` ASC (menor número = mais específico). Default `comercio_industria` (prioridade 99) cobre o que não casa.
- Reusa `apuracao_fiscal` (Sprint 2 — tabela central) com tipos `irpj/csll/pis/cofins`. UNIQUE composto (empresa, competencia, tipo) já dá idempotência. Snapshot da presunção vigente em `faixas_usadas` JSONB.
- 6 endpoints REST: `POST /v1/empresas/{eid}/lp/{irpj|csll|pis|cofins}`, `GET .../lp/apuracoes`, `GET .../lp/presuncao` (diagnóstico — mostra qual grupo o sistema escolheu para o CNAE).
- 3 exceções de domínio novas: `PresuncaoNaoEncontrada`, `EmpresaForaDoRegimeLP`, `ApuracaoLPJaExiste`.

**Sprint 10 PR3 fechada (2026-05-17). Sprint 10 inteira completa.** Pró-labore + distribuição + eSocial:
- Migration 0018 cria 4 tabelas: `socio` (RLS), `prolabore_mensal` (RLS), `distribuicao_lucros` (RLS), `evento_esocial` (RLS). Constraints: distribuição com `valor_isento + valor_tributavel = valor`; pró-labore com `EXTRACT(DAY FROM competencia)=1`; eSocial com `tipo_evento IN (S-1200..S-2400)` + `status IN (preparado..cancelado)`. UNIQUE (sócio, competencia) para pró-labore e (empresa, tipo_evento, referencia_id) para eSocial — idempotência §8.9.
- 3 algoritmos puros golden-tested (34 testes novos):
  - `calcula_prolabore` — INSS plano simplificado 11% (Lei 9.876/1999, contribuinte individual) até teto SCD; IRRF mensal padrão; sem FGTS.
  - `calcula_distribuicao` — Lei 9.249/1995 art. 10: isento até `limite_isento_apurado` (input do contador/regime); excedente tributado como rendimento mensal IRRF. Aceita 4 bases: presunção LP, simples dentro do DAS, lucro contábil, MEI.
  - `esocial_payloads` — 5 geradores puros (S-1200/S-1210/S-2200/S-2299/S-2400) que produzem dicts JSON-safe espelhando 1:1 a estrutura XML do leiaute S-1.3. Mapas de vínculo (CLT=10, prazo_det=20, intermitente=11) e motivo rescisão (Tabela 19 eSocial).
- `socio_service.py` separado: `SocioService`, `ProlaboreService`, `DistribuicaoService`, `EsocialService`. EsocialService despacha por tipo: carrega referência (holerite/funcionario/evento_folha/socio) e monta payload via geradores puros.
- 5 exceções de domínio novas: `SocioNaoEncontrado`, `CpfSocioJaCadastrado`, `ProlaboreJaRegistrado`, `DistribuicaoInvalida`, `EventoESocialJaExiste`.
- 9 endpoints REST novos: `POST/GET /v1/empresas/{eid}/socios`, `POST/GET .../socios/{sid}/prolabore`, `POST/GET .../socios/{sid}/distribuicoes`, `POST/GET .../esocial/eventos`.
- Transmissão real ao eSocial (cert A1, assinatura ICP-Brasil) fica para sprint futura — eventos persistidos com `status='preparado'`.

**Sprint 10 PR2 fechada (2026-05-17).** Departamento Pessoal cobre os eventos pontuais:
- Migration 0017 cria `evento_folha` (RLS) com `tipo IN ('13_primeira','13_segunda','ferias','rescisao')` + JSONB `detalhes` com snapshot completo do cálculo (§8.3). UNIQUE parcial por tipo garante idempotência (§8.9): 13º por (func, parcela, ano), férias por (func, periodo_inicio), rescisão única por func.
- 3 algoritmos puros golden-tested (42 testes novos):
  - `calcula_13o` — 1ª parcela sem desconto; 2ª com INSS escalonado + IRRF exclusivo na fonte (Lei 8.134/1990 art. 16).
  - `calcula_ferias` — remuneração + 1/3 + abono pecuniário até 10 dias (isento — Lei 7.713/1988 art. 6º V).
  - `calcula_rescisao` — 5 modalidades CLT (sem_justa_causa, com_justa_causa, pedido_demissao, mutuo_acordo art. 484-A, termino_determinado). Aviso prévio Lei 12.506/2011 (30+3 por ano, máx 90). Multa FGTS 40/20/0% conforme tipo. Tributação por bloco (saldo + 13º separado; aviso indenizado + férias indenizadas isentos).
- `eventos_service.py` separado de `service.py` (coesão). Rescisão tem side-effect: marca funcionário como demitido (`data_demissao` + `ativo=false`) numa única transação.
- 4 endpoints novos: `POST /v1/empresas/{eid}/funcionarios/{fid}/13o`, `.../ferias`, `.../rescisao`, `GET .../eventos`.
- 4 exceções de domínio novas: `EventoFolhaJaExiste`, `ParametrosFolhaInvalidos`, `FuncionarioJaDemitido`, e reuso de `FuncionarioNaoEncontrado` / `TabelaTributariaAusente`.

**Sprint 10 PR1 fechada (2026-05-17).** Departamento Pessoal entregou o caminho feliz:
- Migration 0016 cria 6 tabelas: `funcionario` + `folha_mensal` + `holerite` (com RLS) e 3 SCD tributárias: `tabela_inss_faixa`, `tabela_irrf_faixa`, `tabela_fgts_aliquota`.
- Seeds carregam INSS empregado 2025 (Portaria MPS/MF 6/2025), INSS contribuinte individual (Lei 8.212/1991), IRRF mensal vigente fev/2024 (Lei 14.848/2024 + MP 1.171/2024) e FGTS 8% CLT/doméstico + 2% jovem aprendiz.
- 4 algoritmos puros Decimal-safe golden-tested:
  - `calcular_inss_empregado` — escalonado por faixa, com flag `teto_aplicado`.
  - `calcular_irrf_mensal` — dedução INSS + dependentes, encontra faixa.
  - `calcular_fgts` — encargo do empregador (não desconto).
  - `calcular_holerite` — orquestrador (INSS → IRRF que depende dele → FGTS → líquido).
- Endpoints: `POST /v1/empresas/{id}/funcionarios`, `GET /v1/empresas/{id}/funcionarios`, `POST /v1/empresas/{id}/folhas/{aaaa-mm}/fechar` (idempotente), `GET /v1/empresas/{id}/folhas`, `GET /v1/empresas/{id}/folhas/{aaaa-mm}/holerites`.
- Folha fechada vira fato imutável (§8.2): segunda chamada `/fechar` retorna 409 `FolhaJaFechada`.
- 43 testes novos (4 arquivos golden: `test_calcula_inss`, `test_calcula_irrf`, `test_calcula_fgts`, `test_calcula_holerite`). Cobertura: bordas (zero, negativo, vazia), intra-faixa, teto, dependentes, determinismo.

Sprint 9 PR3 (anterior). Contabilidade end-to-end pronta: plano hierárquico, lançamentos com partidas dobradas (CHECK D=C no DB), motor automático para NF/transação/depreciação/provisão, balancete + diário + razão, encerramento mensal (trava lançamentos + materializa `saldo_conta_mes`) e anual (apuração que zera receita/despesa contra "3.9.01 Resultado do Exercício").

Critério Fase 2 §1533 **satisfeito**: depreciação e provisões agora batem com balancete via motor automático (Sprint 9 PR2) + materialização do encerramento (Sprint 9 PR3).

---

## Próximos passos — Roadmap

### Sprint 10 — Pessoal completo (em andamento)

Plano §1477. **3 PRs:**

**PR1 — Folha de pagamento + tabelas tributárias ✅ FECHADO (2026-05-17):**
Ver "Onde paramos exatamente" acima. Sprint 10 PR1 entregue: cadastro funcionário CLT, folha mensal, holerite, 3 algoritmos puros golden-tested (INSS escalonado + IRRF + FGTS), 3 tabelas SCD com seed vigente.

**PR2 — 13º + férias + 1/3 + rescisão completa ✅ FECHADO (2026-05-17):**
Ver "Onde paramos exatamente". Migration 0017 + 3 algoritmos puros + 42 testes golden + 4 endpoints REST.

**PR3 — Pró-labore + distribuição de lucros + eSocial ✅ FECHADO (2026-05-17):**
Migration 0018 (4 tabelas) + 3 algoritmos puros golden-tested + 5 geradores eSocial skeleton + 9 endpoints. Sprint 10 inteira completa — pessoal end-to-end pronto para 5 empresas demo em piloto.

**Próximo (Sprint 11):**
- `calcular_13o` (1ª parcela novembro, 2ª dezembro com desconto INSS+IRRF)
- `calcular_ferias` (saldo dias + 1/3 + adicional noturno se aplicável)
- `calcular_rescisao` (verbas + aviso prévio trabalhado/indenizado + FGTS rescisório 40% + GRRF)
- Integra com módulo `provisoes` (Sprint 8) consumindo provisões acumuladas

**PR3 — Pró-labore + distribuição de lucros + eSocial:**
- `calcular_prolabore` (INSS 11% + IRRF tabela mensal)
- `calcular_distribuicao_lucros` (limites por regime: SN sem teto enquanto dentro DAS, LP até presunção)
- Geradores skeleton eSocial S-1200/S-1210/S-2200/S-2299/S-2400

### Sprint 11 — LP + ICMS mensal + Compliance v2

**PR1 — Lucro Presumido completo ✅ FECHADO (2026-05-17):**
Ver "Onde paramos exatamente" acima. Migration 0019 + 4 algoritmos puros + 30 testes + 6 endpoints REST.

**PR2 — ICMS mensal + EFD-Reinf ✅ FECHADO (2026-05-17):**
Ver "Onde paramos exatamente". Migration 0020 + 2 algoritmos puros + 27 testes + 4 endpoints REST + 2 módulos novos (icms, reinf).

**PR3 — Celery beat + DET + Sintegra + parcelamentos ✅ FECHADO (2026-05-17):**
Migration 0021 + 1 algoritmo puro + 14 testes + 11 endpoints + 3 módulos novos (det, monitor_cadastral, parcelamentos) + Celery beat schedule completo (4 tasks periódicas; instalação opt-in via `poetry add celery[redis]`).

### Sprint 12 — Relatórios

- DRE, Balanço Patrimonial, DFC, Indicadores
- DRE auxiliar trimestral LP

### Sprint 13 — Marketplace de contadores parceiros

- Tabelas `contador_parceiro`, `consulta_marketplace`
- Fluxo de matching para casos out-of-scope (contencioso, holding)
- Pagamento Pix/cartão + dashboard parceiro

### Sprints 14-22 — Fase 3 e 4

- 14: Reforma Tributária CBS/IBS
- 15: AI Advisor proativo (weekly digest WhatsApp + anomaly detection)
- 16: SPED ECD + ECF
- 17: EFD-Contribuições + EFD ICMS-IPI
- 18: Migração de escritório antigo (importador SPED 12 meses)
- 19: Performance + load testing 1k empresas
- 20: LP completo pronto-pra-venda (10 empresas piloto)
- 21: Pen test + bug bounty
- 22: Docs operacionais

---

## Pendências conscientes (acumuladas)

Não bloqueiam Sprint 10, mas voltarão como housekeeping/integration:

1. **Celery não instalado** — Sprint 11 PR3 configurou o beat schedule e marcou workers com `@celery_app.task`. Instalação real do pacote (`poetry add celery[redis]`) + start de `worker -Q default` e `beat` fica para deploy de infra. Corpos das tasks (`sync_e_cac_empresa` etc.) ainda são stubs — implementação completa (sessão isolada com SET LOCAL + chamada a service) entra em sprint futura ou no PR de produção.
2. **Storage S3/GCS de PDFs** — recibos SERPRO (PGDAS, DEFIS, certidões), DANFSE Focus, holerite (Sprint 10). Hoje só calculamos `storage_key`. Infra fica para deploy.
3. **CRF (Caixa) + CNDT (TST)** — Sprint 6 PR1 marca como `processando` (skeleton). Scraping fica para Sprint 11 ou Sprint 13.
4. **Webhook Pluggy → sync inline** — hoje só persiste `pluggy_webhook_event`. Cross-tenant routing exige role admin (SECURITY DEFINER) — Sprint 11 quando Celery rodar com worker admin.
5. **NF entrada com classificação inteligente** — motor contábil joga em "5.1.99 Outras Despesas — A Classificar". Categorização por CFOP/NCM via LLM fica para Sprint 11+ (módulo "ai_advisor" do roadmap).
6. **Conciliação consumir match para refinar lançamento** — hoje transação CREDIT sem match vai em "4.9.99 Outras Receitas". Quando há match com NF, ideal é creditar Clientes (baixa de duplicata). Iteração futura.
7. **Bloqueio explícito de lançamento em mês encerrado** — service de criação manual não verifica `saldo_conta_mes.status='fechado'`. Hoje só o DB CHECK em status do lançamento bloqueia. Refinar no Sprint 10.
8. **Encerramento anual reabrir contas de resultado em janeiro** — o lançamento de apuração zera dezembro, mas em janeiro do ano seguinte as contas devem começar com saldo 0. Lógica de "abertura" do exercício novo pode entrar na Sprint 10 ou 12.
9. **Tabela INSS/IRRF/FGTS 2026 oficial pendente** — Sprint 10 PR1 seedou valores vigentes em 2025 (Portaria MPS/MF 6/2025 + Lei 14.848/2024 IRRF). Quando a Portaria 2026 for publicada, basta `INSERT` de novas linhas SCD com `valid_from='2026-XX-XX'` e `UPDATE` fechando o `valid_to` das antigas — sem alterar histórico (§8.3).
10. **Lançamento contábil automático da folha** — Sprint 10 PR1 calcula totais mas não cria lançamento em "5.1.02 Despesa com Pessoal" / "2.1.2.01 Salários a Pagar" / "2.1.3.01 INSS a Recolher" / "2.1.3.02 FGTS a Recolher" / "2.1.3.03 IRRF a Recolher". Plano referencial RFB já tem essas contas (Sprint 9 PR1). Integração com motor contábil fica para Sprint 10 PR2 ou Sprint 11.
11. **Holerite PDF** — `storage_key` é NULL no Sprint 10 PR1. Geração de PDF (placeholder) entra junto com S3/GCS infra na Sprint 11 ou Sprint 19.
12. **Vínculo intermitente + horas trabalhadas** — Sprint 10 PR1 só calcula salário fixo. Eventos variáveis (horas extras, adicionais, faltas) entram na PR2.
13. **eSocial transmissão real** — Sprint 10 PR3 gera apenas o payload JSON (`evento_esocial.status='preparado'`). Implementação da geração XML, assinatura ICP-Brasil com cert A1 e envio à API do eSocial fica para Sprint 11 ou posterior (segue padrão de "transmissão é ato consciente" §8.12 — pode ser opt-in pelo cliente).
14. **S-2400 uso adaptado** — leiaute oficial S-2400 é "Cadastro Beneficiário Ente Público" (RPPS). Sprint 10 PR3 usa para registrar sócios como beneficiários de pró-labore (codCateg 701). Em produção, esse evento deve ser revisto: provavelmente S-1005 (estabelecimentos) ou S-2300 (TSV inicial) seria mais correto.
15. **`limite_isento_apurado` da distribuição** — Sprint 10 PR3 aceita como input. Cálculo automático a partir da presunção/balancete entra na Sprint 11 (LP) e Sprint 12 (relatórios).

---

## Como rodar localmente

```powershell
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api

# Suite unitária + eval
poetry run python -m pytest tests/unit tests/eval

# mypy strict completo
poetry run python -m mypy app/

# Integração (requer Docker rodando)
docker compose up -d
poetry run alembic upgrade head
poetry run python -m pytest tests/integration
```

PATH necessário porque o Device Guard da máquina bloqueia `poetry.exe` direto — usar `poetry run python -m <ferramenta>`.

---

## Dicas críticas para o próximo agente

1. **Leia o Plano antes de qualquer coisa** — `docs/PlanoBackend.md`. Seção §1477 detalha Sprint 10.
2. **Convenção de exceções:** tudo herda `DomainError` em `app/shared/exceptions.py`. Não definir inline em services.
3. **Convenção de algoritmo:** sempre versionar (`ALGORITMO_VERSAO`) e cobrir com golden tests. Imports no topo do módulo (nunca `__import__()` inline).
4. **Idempotência:** todo motor automático precisa de UNIQUE `(origem_tipo, origem_id)` ou similar. Padrão usado em 6 módulos hoje.
5. **Cuidado com Sprint 10 — tabelas INSS/IRRF/FGTS 2026:** verificar valores oficiais vigentes (Portaria Interministerial MPS/MF 6/2026 para INSS; última tabela IRRF mensal RFB).
6. **PathContas referencial:** ao gerar lançamento auto na Sprint 10, mapear "Salários a Pagar" (`2.1.2.01`), "INSS a Recolher" (`2.1.3.01`), "FGTS a Recolher" (`2.1.3.02`), "Despesa com Pessoal" (`5.1.02`). Já existem no `plano_referencial.py`.
7. **Integração com `provisoes`:** quando folha é fechada, a provisão acumulada (Sprint 8) deve ser **baixada** (D Provisão / C INSS/FGTS a recolher quando recolhe efetivamente). Iteração futura.
