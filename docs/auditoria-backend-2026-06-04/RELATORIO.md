---
titulo: Auditoria Profunda Backend — analista-fiscal-api
data: 2026-06-04
metodo: 6 revisores de contexto fresco (lotes A–F), rubrica = 12 princípios invioláveis + convenções
estado_repo: Sprint 20 · 34 módulos · 52 migrations · ~46k LOC
veredito: saúde forte; 13 defeitos reais + ~10 defense-in-depth; vários bloqueadores de piloto pago
---

# Auditoria Profunda — Backend (2026-06-04)

> Varredura de **recall** dividida em 6 lotes, cada um auditado por um revisor de contexto fresco
> contra os 12 princípios invioláveis (`docs/principios/01-12`) + convenções de `CLAUDE.md`.
> Cortes de escopo conscientes (stubs documentados em `log_agente.md`) **não** foram contados como
> achados — só defeitos reais e line-citáveis.

## Veredito geral

Zero `float` em caminho monetário. Zero alíquota fiscal hardcoded (tudo via SCD `valid_from/valid_to`).
RLS íntegro em **todos** os caminhos autenticados verificados (`get_session` aplica `SET LOCAL ROLE
fiscal_app` + `app.tenant_id`; tabelas core com `FORCE RLS` + `WITH CHECK`). Disciplina
`Decimal`/`ROUND_HALF_EVEN`, idempotência (UNIQUE/`uuid5`) e partidas dobradas balanceadas
consistentes. Os defeitos são **pontuais, não sistêmicos**.

## Findings ranqueados

### 🔴 Bloqueadores de piloto pago / go-live

| # | Sev | Local | Defeito | Princípio |
|---|---|---|---|---|
| 1 | risco-regulatório | `sped/compartilhado.py:150` | **Registro 9990 off-by-one** — `total_bloco_9 = 9001 + n×9900 + 1`, esquece a linha do **9999**. Afeta os 4 tipos (ECD/ECF/EFD-Contrib/EFD-ICMS-IPI). PVA valida QTD_LIN_9 estritamente → **rejeita todo arquivo gerado**. Parser só valida 9999 → golden round-trips ficam verdes e escondem o bug. | leiaute |
| 2 | security | `config.py:80-83,318-325` | `JWT_SECRET` placeholder (commitado no repo) **não barrado em prod**. `_fail_fast_em_prod` só checa DATABASE/REDIS. Subir sem env → tokens assinados com segredo público → forja de `tid` → **takeover cross-tenant total**. | §8.7 / sec |
| 3 | lgpd | `logging.py:21-40` | **Sem processador de redação de PII.** Cadeia structlog não tem scrub. CLAUDE.md afirma "CNPJ/CPF/email redacted antes de Loki" — **falso**; depende 100% de disciplina de call-site. Docstring de `perf.py:18-19` reforça a premissa falsa. | §8.7 |
| 4 | risco-regulatório | `llm/client.py:220,274` | `LLMClient` retorna `citacoes=[]` **hardcoded** em ambos caminhos (Ollama+Gemini); nunca parseia `[ID]`. Cascata: `validar_resposta` itera lista vazia (vacuamente verdadeira) e **não exige ≥1 citação** → afirmação fiscal **sem citação** é aceita. §8.5 "citação obrigatória" é vazio na prática. | §8.5/§8.6 |

### 🟠 Dinheiro errado / regulatório

| # | Sev | Local | Defeito | Princípio |
|---|---|---|---|---|
| 5 | risco-regulatório | `pessoal/eventos_service.py:434` (+`calcula_ferias.py`) | **Férias gozadas não recolhem FGTS 8%.** `calcula_ferias` não modela FGTS; evento grava `fgts_empregador=_ZERO`. FGTS incide sobre férias gozadas + 1/3 (Lei 8.036/90 art.15). Subdeclara GFIP/FGTS (~R$213 p/ salário R$3k, 20 dias). | folha |
| 6 | risco-regulatório | `pessoal/eventos_service.py:378,404` (+`calcula_13o.py`) | **13º não recolhe FGTS.** Ambas parcelas gravam `_ZERO`. A *provisão* mensal já acumula `fgts_13` → provisão ≠ realização. | folha |
| 7 | bug | `sped/efd/gerador_contribuicoes.py:734-745` | M200/M600 gravam apurado nos campos **não-cumulativos** (`VL_TOT_CONT_NC_*`) mesmo no regime cumulativo (`COD_INC_TRIB="2"`). PVA cruza 0110×M200 → erro de coerência / glosa. | leiaute |
| 8 | bug | `sped/efd/gerador_icms_ipi.py:570-573` | E110 `VL_SLD_APURADO` recebe `valor_icms_a_recolher` (duplica campo 13) e ignora saldo credor. Mês com créditos>débitos → PVA recalcula e acusa inconsistência aritmética. | leiaute |
| 9 | risco-cliente | `relatorios/service.py:284-289` + `repo.py:166-174` | **DFC N+1 explosivo.** `_soma_saldos_codigos` ×12, cada código chama `saldo_conta_codigo_em` → roda `saldos_posicao_em` inteiro. ~22 full-scans por relatório. Valor correto, mas degrada sob carga. | perf/N+1 |

### 🟡 Bug / authz / rastreabilidade

| # | Sev | Local | Defeito | Princípio |
|---|---|---|---|---|
| 10 | bug | `marketplace/service.py:263-297` + `router.py:294` | `avaliar` grava `rating_cliente` + recalcula rating do `ContadorParceiro` (pool global sem RLS) e dá `commit()`; **só depois** o router compara `empresa_id` e levanta 404. Usuário com 2 empresas do mesmo tenant avalia consulta da empresa B via path da A; a rejeição não desfaz a escrita. | §8.1/authz |
| 11 | security | `marketplace/router.py:432-448` | Webhook de pagamento **sem HMAC**, em `WebhookSessionDep` (superuser, **bypassa RLS**). Qualquer um que poste um `provider_externo_id` válido marca cobrança como paga cross-tenant. Stub consciente, mas já plugado → bloqueador de prod. | §8.9/sec |
| 12 | bug | `multa_juros/calcula_selic.py` | **Único `calcula_*.py` do repo sem `ALGORITMO_VERSAO`** nem campo de versão em `ResultadoMora`/`SimularMoraOut`. Valores de mora não-auditáveis quando a metodologia mudar. | §8.4 |
| 13 | bug | `parcelamentos/calcula_parcelamento.py:113-137` | Parcela base replicada idêntica → soma diverge da dívida consolidada (333.33×3=999.99; 142.86×7=1000.02). Nenhum teste valida `sum==divida`. | money |

### ⚪ Defense-in-depth / cleanup (entram no PR6 / PR2)

| Local | Item | Sev |
|---|---|---|
| `serpro/client.py:289`, `pluggy/client.py:196`, `serpro/oauth.py:120`, `pluggy/auth.py:123` | Corpo de erro de upstream loga CNPJ cru (`resp.text[:300]`) | lgpd |
| `meta_whatsapp/webhook.py:9-22` | `verificar_assinatura_meta` não rejeita `app_secret`/`signature` vazios (Pluggy rejeita) | bug |
| `multa_juros/schemas.py:9` | `SimularMoraIn` sem `ConfigDict(extra="forbid")` | cleanup |
| `multa_juros/service.py:59-85` | `except ValueError` largo mascara causa como "SELIC insuficiente" | cleanup |
| `provisoes/calcula_provisao.py:109-113` | Linha de férias: `aliquota` não reconcilia com `valor_provisao` (1/12 vs 1/12×4/3) | cleanup |
| `imobilizado/calcula_depreciacao.py:127-132` | Heurística de última parcela via divisão do acumulado — frágil | cleanup |
| `storage/backend.py:75-78` | Path-traversal: só `replace("..","_")`, sem `resolve()`+`is_relative_to` | security |
| `middleware/rate_limit.py:230-254` | Chave por `tid` não-verificado → DoS dirigido por tenant | cleanup |
| `sped/ecd/router.py:71` | Download ECD legado não checa `tipo` (cross-tipo same-tenant) | cleanup |
| `meta_whatsapp/sender.py` | `enviar_texto` sem retry (resposta ao cliente perdida em blip 5xx) | cleanup |

### Risco estrutural latente (documentar, não corrigir agora)

`db/deps.py:46-55` — `SET LOCAL ROLE` + `set_config('app.tenant_id', ..., is_local:=true)` são
**transação-scoped**. Benigno hoje (services do escopo verificado fazem `commit()` como última
operação). Mas um service futuro que faça `commit()` e **depois** rode outra query de domínio na
mesma sessão perde o GUC + role → query como superuser sem tenant → **bypass de RLS** (em tabelas
só `ENABLE`; `FORCE` não afeta superuser). Mitigação recomendada: re-aplicar `SET LOCAL` num hook
`after_commit`, ou proibir multi-commit por request, + teste de regressão. → `docs/pendencias/`.

---

## Sumários de saúde por lote

### Lote A — Cálculo fiscal (fiscal, multa_juros, lucro_presumido, icms, pgdas, declaracao_anual, reforma, reinf, det, parcelamentos)
Boa saúde. `calcula_das.py` exemplar (SCD via `FaixaDAS`, ROUND_HALF_EVEN, teto/sublimite, multi-anexo).
LP/ICMS/reforma/reinf/pgdas/DEFIS limpos — alíquotas 100% SCD, `OBSERVACAO_ESTIMATIVA` obrigatória na
reforma (§8.12), idempotência por IntegrityError/uuid5. Defeitos concentrados em **multa_juros**
(sem `ALGORITMO_VERSAO`, sem `extra="forbid"`, catch largo) + **parcelamentos** (centavos). Nenhum
risco-regulatório/LGPD grave.

### Lote B — Pessoal & Contábil (pessoal, contabil, imobilizado, provisoes)
Núcleo excelente: disciplina Decimal/ROUND_HALF_EVEN impecável, faixas SCD sem hardcode, partidas
dobradas sempre balanceadas (folha de 6 partidas fecha), idempotência via UNIQUE(origem_tipo,origem_id),
bloqueio de mês encerrado, classificacao_ncm com re-check (§8.6) + citação (§8.5). Risco material =
**FGTS do empregador não recolhido em férias gozadas e 13º** (calc não modela; eventos gravam zero;
provisão prevê mas realização some). Demais achados (aliquota férias na provisão, heurística de
depreciação) são auditabilidade/robustez.

### Lote C — SPED & Migração (sped, migracao)
Arquitetura sólida: parsers robustos e simétricos aos geradores (bounds-check, latin-1/utf-8, CRLF),
idempotência (hash + uuid5 + supersede), RLS/imutabilidade/Decimal respeitados, round-trips golden
cobrindo a maioria dos campos. Risco dominante = **9990 off-by-one em todos os arquivos** (PVA rejeita
tudo; escapou porque parser só valida 9999). M200/M600 (regime cumulativo) e E110 (saldo credor)
merecem coerência fiscal antes de transmissão real. CSV estorno e fix do field-21 `VL_PIS_RET` corretos.

### Lote D — Integrações & LLM (shared/integrations, shared/llm, assistente, memoria, whatsapp, ingestao, notas, open_finance, conciliacao, certidoes, e_cac, monitor_cadastral, agenda)
Bom estado: idempotência rigorosa (chaves determinísticas, dedup de webhook, UPSERT), Decimal
impecável em conciliação/open-finance, retry bounded + timeouts em todos os clients, embeddings
Ollama-only (PII nunca vai ao Gemini), zero segredo em log. Achado dominante e de maior alavancagem:
**`LLMClient` nunca extrai citações** → §8.5 vazio no assistente. Re-check (§8.6) funciona mas só
morde quando há literal numérico. Secundários: HMAC Meta sem guard próprio; corpo de erro upstream
loga CNPJ.

### Lote E — Plataforma multi-tenant (shared/db, auth, crypto, cache, middleware, storage, idempotency, logging, types; auth, empresa; workers)
**Invariante RLS se mantém em todos os caminhos autenticados verificados.** `get_session` aplica role
+ tenant antes de qualquer query; tabelas core com `FORCE RLS` + `WITH CHECK` (108 ocorrências RLS em
29 migrations); marketplace dual-GUC/role segregado; JWT com alg pinado, sem `alg=none`; bcrypt cost
12 constant-time; xmldsig fail-closed; cache keys sem PII. Ações imediatas **não** são furos de RLS e
sim LGPD/secrets: **(1) sem redação de PII no `logging.py`** e **(2) `JWT_SECRET` placeholder não
barrado em prod**. Vigiar o acoplamento `SET LOCAL`↔`commit()` (latente).

### Lote F — Admin/Advisor/Marketplace/Relatórios (tabelas_admin, advisor, marketplace, relatorios)
Princípios bem aplicados: SCD/idempotência de `tabelas_admin` (uuid5 + payload-compare + REVOKE
UPDATE/DELETE), advisor com separação fato-vs-LLM correta (anomalia = z-score determinístico; LLM só
redige digest com citação), relatorios Decimal-disciplinado com `_divide`→None em denom zero.
Cross-tenant entre tenants distintos contido por `FORCE RLS` em `consulta_marketplace`. Riscos: **DFC
N+1** (perf), **validação de empresa pós-commit no `avaliar`** (same-tenant cross-empresa), **webhook
de pagamento sem HMAC em sessão privilegiada** (bloqueador de prod).

---

## Plano de remediação

Ver `../../C:\Users\loren\.claude\plans\abundant-jingling-truffle.md` (plano aprovado). 6 PRs:
PR1 SPED leiaute · PR2 Segurança/LGPD · PR3 Folha FGTS · PR4 LLM citação · PR5 Marketplace ·
PR6 Cálculo/robustez+defense-in-depth. Execução orquestrada: 1 agente Sonnet por PR, write-back em
`HANDOFF.md`.
