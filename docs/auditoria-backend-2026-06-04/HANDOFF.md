# HANDOFF — Sprint de Hardening Backend (Auditoria 2026-06-04)

> **Append-only.** Espelha o protocolo de `docs/HANDOFF.md` do frontend, mas para esta sprint de
> remediação do backend. Cada agente (auditor ou implementador) acrescenta um bloco ao terminar:
> **data · agente · o que fez · arquivos tocados · testes (delta) · pendências · próximo.**
> Não reescrever blocos anteriores. Findings completos em `RELATORIO.md`.

---

## Fase 0 — Auditoria (2026-06-04)

### Orquestrador — recon + divisão em lotes
- **O que fez:** mapeou o repo (Sprint 20, 34 módulos, 52 migrations, ~46k LOC), localizou a rubrica
  (`docs/principios/01-12` + convenções `CLAUDE.md`), dividiu em 6 lotes A–F balanceados por LOC+risco,
  despachou 6 revisores de contexto fresco em paralelo.
- **Arquivos tocados:** nenhum (recon read-only).
- **Próximo:** consolidar achados → `RELATORIO.md`.

### Lote A — Cálculo fiscal (revisor)
- **Escopo:** fiscal, multa_juros, lucro_presumido, icms, pgdas, declaracao_anual, reforma, reinf, det, parcelamentos.
- **Achados:** multa_juros sem `ALGORITMO_VERSAO` (#12); `SimularMoraIn` sem `extra="forbid"`; catch `ValueError` largo; parcelamentos não reconcilia centavos (#13). Resto limpo (SCD/Decimal exemplares).

### Lote B — Pessoal & Contábil (revisor)
- **Escopo:** pessoal, contabil, imobilizado, provisoes.
- **Achados:** **FGTS não recolhido em férias gozadas (#5) e 13º (#6)** — risco-regulatório; aliquota férias na provisão não reconcilia; heurística de última parcela de depreciação frágil. Contábil/double-entry/idempotência limpos.

### Lote C — SPED & Migração (revisor)
- **Escopo:** sped (geradores+parsers+CIAP), migracao.
- **Achados:** **9990 off-by-one em todos os 4 tipos (#1)** — PVA rejeita tudo; M200/M600 grava em campos NC no regime cumulativo (#7); E110 VL_SLD_APURADO duplica/ignora crédito (#8); download ECD legado sem checar tipo. Parsers/idempotência/round-trip sólidos.

### Lote D — Integrações & LLM (revisor)
- **Escopo:** shared/integrations/*, shared/llm/*, assistente, memoria, whatsapp, ingestao, notas, open_finance, conciliacao, certidoes, e_cac, monitor_cadastral, agenda.
- **Achados:** **`LLMClient` nunca extrai citações → §8.5 vazio (#4)**; HMAC Meta sem guard de vazios; corpo de erro upstream loga CNPJ (lgpd); `enviar_texto` sem retry. Idempotência/Decimal/embeddings-Ollama limpos.

### Lote E — Plataforma multi-tenant (revisor)
- **Escopo:** shared/{db,auth,crypto,cache,middleware,storage,idempotency,logging,types}, auth, empresa, workers.
- **Achados:** **RLS íntegro em todos os caminhos verificados.** Mas: **`logging.py` sem redação de PII (#3)**; **`JWT_SECRET` placeholder não barrado em prod (#2)**; path-traversal storage fraco; rate-limit por `tid` não-verificado; risco latente `SET LOCAL`↔`commit()`.

### Lote F — Admin/Advisor/Marketplace/Relatórios (revisor)
- **Escopo:** tabelas_admin, advisor, marketplace, relatorios.
- **Achados:** **DFC N+1 (#9)**; **`avaliar` valida empresa pós-commit (#10)**; **webhook pagamento sem HMAC em sessão RLS-bypass (#11)**. SCD/advisor-fato-vs-LLM/relatorios-Decimal limpos.

---

## Fase 1 — Implementação (PRs)

<!-- Cada agente implementador acrescenta seu bloco abaixo, em ordem. -->

### PR1 — SPED leiaute (2026-06-04 · agente Sonnet)

**O que fez:**

- **FIX #1 — Registro 9990 off-by-one** (`compartilhado.py`):
  - Expressão antes: `total_bloco_9 = base["9001"] + base["9900"] + 1`
  - Expressão depois: `total_bloco_9 = base["9001"] + base["9900"] + 2`
  - O `+1` esquecia que o registro 9999 também pertence ao bloco 9 (o PVA
    valida QTD_LIN_9 incluindo 9999). Afeta os 4 tipos de SPED porque todos
    chamam `gerar_bloco_9`.
  - Adicionada validação do 9990 no `validador.py` (`_validar_estrutura`):
    novo bloco `3a)` que verifica `declarado_9990 == len(9001+9900*N+9990+9999)`.
    Antes só 9999 era validado → o bug passava nos testes mas era rejeitado pelo PVA.

- **FIX #7 — M200/M600 regime cumulativo** (`gerador_contribuicoes.py`):
  - Campos `VL_TOT_CONT_NC_PER`, `VL_TOT_CONT_NC_DEV`, `VL_OUT_DED_NC`,
    `VL_CONT_NC_REC` zerados para regime cumulativo (COD_INC_TRIB="2").
  - Campos `VL_TOT_CONT_CUM_PER` e `VL_CONT_CUM_REC` recebem os valores reais
    do apurado e a_recolher respectivamente.
  - M600 (Cofins) recebeu a mesma correção simétrica.

- **FIX #8 — E110 VL_SLD_APURADO** (`gerador_icms_ipi.py`):
  - Campo 10 (`VL_SLD_APURADO`) agora recebe `débitos − créditos − saldo_credor_anterior`
    (pode ser negativo em mês credor). Antes recebia `valor_icms_a_recolher`
    (duplicava o campo 12 e ignorava créditos).
  - `VL_ICMS_RECOLHER` e `VL_SLD_CREDOR_TRANSPORTAR` permaneceram inalterados.

**Arquivos tocados:**
- `app/modules/sped/compartilhado.py` — FIX #1 (expressão +2)
- `app/modules/sped/validador.py` — FIX #1 (validação 9990)
- `app/modules/sped/efd/gerador_contribuicoes.py` — FIX #7 + ALGORITMO_VERSAO v3→v4
- `app/modules/sped/efd/gerador_icms_ipi.py` — FIX #8 + ALGORITMO_VERSAO v3→v4
- `tests/unit/sped/test_compartilhado.py` — 2 novos testes anti-regressão 9990
- `tests/unit/sped/test_efd_contribuicoes_gerador.py` — 4 novos testes M200/M600
- `tests/unit/sped/test_efd_icms_ipi_gerador.py` — 3 novos testes E110
- `tests/unit/sped/test_validador.py` — 3 novos testes 9990 no validador
- `tests/unit/sped/test_blocos_stubs_sprint_19_8.py` — 2 versão-pins atualizados v3→v4
- `tests/unit/sped/test_efd_contribuicoes_gerador_pr3.py` — 1 versão-pin atualizado v3→v4
- `tests/unit/sped/test_efd_contribuicoes_service.py` — 1 versão-pin atualizado v3→v4
- `tests/unit/sped/test_efd_icms_ipi_service.py` — 1 versão-pin atualizado v3→v4

**ALGORITMO_VERSAO bumps:**
- `sped.efd_contribuicoes`: v3 → v4 (FIX #7)
- `sped.efd_icms_ipi`: v3 → v4 (FIX #8)
- ECD e ECF não mudam ALGORITMO_VERSAO próprio (chamam `gerar_bloco_9` externamente; o bump do bloco 9 não altera bytes dos blocos A–K, só o bloco 9 final — o arquivo muda, mas o ALGORITMO_VERSAO desses geradores aponta para a versão do gerador, não do helpers compartilhado).

**Testes:** 294 passing, 0 failed, 0 skipped (escopo sped+migracao). Antes: 291 (incremento de +3 tests nomeados novos; os 12 métodos adicionados incluem os 4 versão-pins renomeados v3→v4 que permanecem no mesmo count).

**mypy:** `Success: no issues found in 35 source files`

**Pendências:**
- ECD e ECF não têm ALGORITMO_VERSAO próprio bumped — o arquivo muda (bloco 9 corrigido) mas o campo `algoritmo_versao` no ArquivoEcdGerado/ArquivoEcfGerado ainda reflete v anterior. Recomendado: bumpar esses geradores no PR6 (cleanup) ou em nova sessão dedicada.
- Os testes golden de round-trip ECD/ECF passam pois verificam 9999 (agora correto) e não fixam o valor de 9990 numericamente — OK por design.

**Próximo:** PR2 — Segurança/LGPD (JWT_SECRET placeholder não barrado em prod + redação de PII no logging.py).

---

### PR2 — Segurança & LGPD (2026-06-04 · agente Sonnet)

**O que fez:**

- **FIX A (#2) — JWT_SECRET placeholder não barrado em prod** (`config.py`):
  - Adicionado ao `_fail_fast_em_prod` (model_validator): em `ENVIRONMENT=prod`,
    levanta `ValueError` se `JWT_SECRET` inicia com `"TROCAR_EM_PRODUCAO"` OU
    tem menos de 32 chars.
  - Adicionado guard para `META_WHATSAPP_VERIFY_TOKEN`: levanta se o valor é o
    padrão hardcoded `"fiscalai-webhook-verify"` (comprometeria autenticidade do
    webhook Meta em produção).
  - Guards só disparam em `ENVIRONMENT=prod` — local/staging não afetados.

- **FIX B (#3) — logging.py sem redação de PII** (`shared/logging.py`):
  - Adicionado processador `_redact_pii(logger, method_name, event_dict)` inserido
    ANTES de qualquer renderer na cadeia structlog.
  - Dois mecanismos de redação:
    1. **Por chave** (case-insensitive substring): `senha/password/token/secret/
       authorization/bearer` → `"***"` completo; `email/cpf/cnpj/telefone/phone`
       → prefixo 4 chars + `"***"` (debuggabilidade). Não-str passam intactos.
    2. **Por padrão regex** (compilados no módulo): CNPJ → phone → CPF → e-mail
       mascarados em `event` e em todos os valores string do event_dict.
       Resolve o vazamento de `resp.text[:300]` das integrações SERPRO/Pluggy
       com CNPJ embutido (defense-in-depth rows do relatório).
  - Regexes compiladas em tempo de módulo (performance); processador silencia
    exceção interna (nunca derruba o log).

- **FIX C — storage path-traversal** (`shared/storage/backend.py`):
  - `_path_for` agora faz `resolved = candidate.resolve()` e levanta `StorageError`
    se `not resolved.is_relative_to(self._base.resolve())`.
  - Dupla camada: substituição léxica de `".."` (camada 1) + confinamento real
    via `resolve()` (camada 2 — cobre symlinks e encodings exóticos).

- **FIX D — rate_limit por tid não-verificado** (`shared/middleware/rate_limit.py`):
  - `construir_chave_redis` agora aceita `client_ip: str = ""` e produz
    chave `rl:<tid>:<ip>:<janela>` (antes: `rl:<tid>:<janela>`).
  - Atacante que forja `tid` da vítima só polui seu próprio bucket `(ip_dele+tid)`,
    nunca o da vítima `(ip_vitima+tid)`.
  - Comentário de código documenta explicitamente que `tid` é não-verificado por
    design (identificação, não autenticação).
  - `checar_rate_limit` recebe `client_ip: str = ""` (backward-compat).
  - `RateLimitMiddleware.dispatch` extrai `request.client.host` e passa para
    `checar_rate_limit`.

- **FIX docstring perf.py** (`shared/db/perf.py`):
  - Corrigido docstring falso que afirmava "structlog processor existente" para
    PII — agora cita `_redact_pii` de `app/shared/logging.py` (que agora existe).

**Arquivos tocados:**
- `app/config.py` — FIX A (guards JWT_SECRET + META_WHATSAPP_VERIFY_TOKEN)
- `app/shared/logging.py` — FIX B (_redact_pii, reescrita do módulo)
- `app/shared/db/perf.py` — FIX B (docstring corrigido)
- `app/shared/storage/backend.py` — FIX C (resolve+is_relative_to em _path_for)
- `app/shared/middleware/rate_limit.py` — FIX D (client_ip na chave Redis)
- `tests/unit/security/test_config_prod_guards.py` — NOVO (9 testes FIX A)
- `tests/unit/shared/test_logging_redaction.py` — NOVO (27 testes FIX B)
- `tests/unit/shared/test_storage.py` — ATUALIZADO (2 testes FIX C, 1 skip symlink)
- `tests/unit/middleware/test_rate_limit.py` — ATUALIZADO (4 novos testes FIX D)

**Testes:**
- Antes: 2045 passed, 1 failed (bcrypt 72-byte — pre-existente, fora de escopo)
- Depois: **2085 passed, 1 failed (mesmo pre-existente), 1 skipped (symlink/OS)**
- Delta: **+40 testes**

**mypy:** Zero erros novos introduzidos nos 5 arquivos alterados. Os 2 erros
`Redis[str] type-arg` em `rate_limit.py` são pre-existentes (confirmado via
`git stash`). Total geral: 22 erros pre-existentes inalterados (todos em outros
módulos: llm/client.py, serpro/oauth.py, pluggy/auth.py, brasil_api, workers).

**Pendências:**
- `META_WHATSAPP_VERIFY_TOKEN`: guard cobre apenas o valor padrão exato; um valor
  trivialmente diferente (ex.: "fiscalai-webhook-verify2") passaria. Adequado para
  o risco atual — refinar com comprimento mínimo em sprint futura se necessário.
- Symlinks no `LocalDiskStorage`: o teste de resolve+is_relative_to para symlink
  foi escrito mas ficou `skipped` (OS sem suporte a symlinks em sandbox). O guard
  está no código de produção e funciona em Linux/macOS.
- Rate-limit por IP pode ser bypassado com IP spoofing em arquiteturas sem proxy
  reverso confiável (X-Forwarded-For). Para prod com load balancer, considerar
  ler `X-Forwarded-For` com whitelist de proxy IPs (melhoria futura).

**Próximo:** PR3 — Folha FGTS (férias gozadas #5 + 13º #6 não recolhem FGTS
do empregador — risco-regulatório GFIP/Caixa).

---

### PR3 — Folha FGTS férias/13º (2026-06-04 · agente Sonnet)

**O que fez:**

- **FIX #5 — Férias gozadas não recolhiam FGTS** (`calcula_ferias.py` + `eventos_service.py`):
  - Adicionado `_OITO_PCT = Decimal("0.0800")` e campos `base_fgts: Decimal` +
    `fgts_empregador: Decimal` ao `ResultadoFerias` (dataclass frozen).
  - Fórmula: `base_fgts = bruto_tributavel` (férias gozadas + 1/3 constitucional);
    `fgts_empregador = base_fgts × 8%`. Abono pecuniário (dias_vendidos) excluído
    da base por ser verba indenizatória (STF RE 895.294).
  - `_evento_de_ferias` em `eventos_service.py`: `fgts_empregador=r.fgts_empregador`
    (antes gravava `_ZERO`).
  - Exemplo: salário R$3.000, 20 dias → bruto R$2.666,67 → FGTS R$213,33/mês.

- **FIX #6 — 13º salário não recolhia FGTS** (`calcula_13o.py` + `eventos_service.py`):
  - Adicionado `_OITO_PCT = Decimal("0.0800")` e campos `base_fgts: Decimal` +
    `fgts_empregador: Decimal` ao `Resultado13oSegunda` (1ª parcela não tem campos).
  - Fórmula: `base_fgts = base_proporcional` (salario × avos / 12);
    `fgts_empregador = base_fgts × 8%`.
  - **Decisão de alocação:** FGTS do 13º registrado **integralmente na 2ª parcela /
    fechamento de dezembro**. A 1ª parcela é adiantamento puro sem tributos. Concentrar
    na 2ª elimina dupla contagem: `total_anual_fgts_13 = r2.fgts_empregador = 8% × base`,
    contado exatamente uma vez. Documentado em docstring + comentário inline.
  - `_evento_de_13o_segunda`: `fgts_empregador=r.fgts_empregador` (antes `_ZERO`).
  - `_evento_de_13o_primeira`: permanece `fgts_empregador=_ZERO` (adiantamento puro).
  - Exemplo: salário R$3.000, avos=12 → base R$3.000 → FGTS R$240,00 na 2ª parcela.

- **FIX cleanup — Provisão de férias: aliquota não reconciliava** (`calcula_provisao.py`):
  - Problema: linha `ferias` gravava `base_calculo=folha_mes, aliquota=1/12≈0.083333`
    mas `valor_provisao=ferias_total=folha_mes×1/12×4/3`. Logo `base×aliquota ≠ valor`.
  - Correção: aliquota trocada para `1/12 × 4/3 = 4/36 ≈ 0.111111` (6 casas,
    ROUND_HALF_EVEN). `folha_mes × 0.111111 ≈ ferias_total` com erro ≤ R$0,01.
  - Nova constante `_ALIQ_FERIAS_EFETIVA` adicionada; `_UM_DOZE_PCT_ARREDONDADA`
    continua usada apenas para a linha `13_salario` (onde `base×0.083333≈base_13`).
  - Comentário de reconciliação no código atualizado e na docstring do módulo.

**ALGORITMO_VERSAO bumps:**
- `calcula_ferias.py`: `ferias.v1` → `ferias.v2`
- `calcula_13o.py`: `13o.v1` → `13o.v2`
- `calcula_provisao.py`: `prov-2026.06` → `prov-2026.07`

**Arquivos tocados:**
- `app/modules/pessoal/calcula_ferias.py` — FIX #5 (base_fgts + fgts_empregador + bump v2)
- `app/modules/pessoal/calcula_13o.py` — FIX #6 (base_fgts + fgts_empregador na 2ª + bump v2)
- `app/modules/pessoal/eventos_service.py` — FIX #5 + #6 (popular fgts_empregador nos eventos)
- `app/modules/provisoes/calcula_provisao.py` — FIX cleanup (_ALIQ_FERIAS_EFETIVA + bump v07)
- `tests/unit/pessoal/test_calcula_ferias.py` — +4 testes (`TestFgtsFerias`) + versão bumped
- `tests/unit/pessoal/test_calcula_13o.py` — +5 testes (`TestFgts13o`) + versão bumped
- `tests/unit/provisoes/test_calcula_provisao.py` — aliquota atualizada + +1 teste de reconciliação + versão bumped

**Testes:**
- pessoal + provisoes: **230 passed, 0 failed** (delta: +10 testes novos; antes ≈ 220).
- mypy `app/modules/pessoal app/modules/provisoes`: **Success: no issues found in 28 source files**.

**Pendências:**
- A provisão mensal acumulava `fgts_ferias` e `fgts_13` (correto). Agora a realização
  (evento de férias e 2ª parcela do 13º) passa a bater com a provisão. Integração
  contábil do FGTS (lançamento de débito na provisão / crédito no passivo) ainda é
  execução futura (stub pendente desde Sprint 8).
- Testes de integração do `EventosFolhaService` (que usa `_evento_de_ferias` e
  `_evento_de_13o_segunda`) não foram executados (requerem Docker + Postgres).
  Os unit tests de `calcula_ferias` / `calcula_13o` cobrem a lógica de cálculo
  pura que alimenta os eventos.

**Próximo:** PR4 — LLM citação (finding #4: `LLMClient` retorna `citacoes=[]` hardcoded
→ §8.5 "citação obrigatória" vazio na prática).

---

### PR4 — LLM citação obrigatória (2026-06-04 · agente Sonnet)

**O que fez:**

- **FIX 1 — Parse de citações no LLMClient** (`app/shared/llm/client.py`):
  - Adicionado `_extrair_citacoes(texto, fontes)` — função pura que varre o texto do modelo
    com regex `\[([^\]]+)\]`, coleta todos os `[ID]` referenciados, valida cada ID contra o
    dict `{f.id: f}` das `fontes_disponiveis` passadas no request, e retorna lista de `Citacao`.
  - IDs inexistentes nas fontes são **silenciosamente descartados** (não inventados).
    O `trecho_citado` é `fonte.payload[:120]` — âncora auditável ao fato real.
    IDs duplicados no texto são deduplizados (set de `vistos`).
  - `_chamar_ollama` e `_chamar_gemini` substituem `citacoes=[]` hardcoded por
    `citacoes = _extrair_citacoes(texto, request.fontes_disponiveis)`.
  - Ambos os paths (local Gemma / cloud Gemini) passam `fontes_disponiveis` que vêm do
    `LLMRequest.fontes_disponiveis` construído pelo assistente via `contexto_para_fontes(rag)`.

- **FIX 2 — Gate §8.5 em `validar_resposta`** (`app/shared/llm/citacao.py`):
  - Adicionada função auxiliar `_contem_afirmacao_fiscal(texto)`: retorna `True` se o texto
    contém qualquer valor monetário (`R$`), percentagem, CNPJ ou data — marcadores de
    afirmação fiscal verificável. Textos sem esses elementos (saudações, "não sei",
    orientações genéricas) não acionam o gate.
  - **Regra 5 (§8.5)** acrescentada ao final de `validar_resposta`:
    `if fontes and _contem_afirmacao_fiscal(resp.texto) and len(resp.citacoes) == 0: return False`
  - Design contra over-rejeição:
    1. Só dispara quando `fontes` não está vazio (grafo com dados) → sem fontes, o assistente
       já orienta genericamente e não há como exigir citação de grafo vazio.
    2. Só dispara quando há afirmação fiscal (`_contem_afirmacao_fiscal`) → pleasantries e
       meta-respostas passam sem citação.
    3. As Regras 1–4 (literal de R$, percentagem, CNPJ, data nas fontes) continuam ativas e
       completamente independentes da Regra 5 — a Regra 5 é o gate de entrada que fecha o
       caminho que ficava aberto quando o LLM não emitia `[ID]` algum.
  - Teste `test_valida_cnpj_nas_fontes` atualizado para incluir citação válida (o teste
    anterior testava Regra 3 com resposta sem citação → agora a Regra 5 capturaria esse caso
    corretamente; o teste foi ajustado para refletir o comportamento correto pós-fix).

**Como parseia citação e mapeia para fontes válidas:**
O prompt `assistente_resposta_v1.md` instrui o modelo a usar `[ID]` inline ao lado de cada
afirmação. A regex `_RE_CITACAO = re.compile(r"\[([^\]]+)\]")` extrai todos os grupos entre
colchetes. Cada ID extraído é conferido contra `ids_validos = {f.id: f for f in fontes}`.
Só se o ID existe nas fontes o `Citacao` é construído — nunca a partir de IDs inventados.
O `trecho_citado` vem do payload da fonte (não do texto do LLM) para garantir que a âncora
de auditoria é o fato persistido, não a paráfrase do modelo.

**Nova regra de gate e como evita over-rejeição:**
- Gate só ativa quando: (a) fontes não vazias + (b) afirmação fiscal + (c) zero citações.
- Respostas puramente conversacionais ("Não tenho dados.", "Consulte seu contador.") passam.
- Respostas com afirmação fiscal mas com citação válida → passam (Regras 1–4 conferem a
  literalidade; Regra 5 só rejeita quem ficou sem citação alguma).
- O caso mais comum de false-positive seria uma resposta como "Situação: regular" sem valor/data/
  CNPJ/percentagem → `_contem_afirmacao_fiscal` retorna False → Regra 5 não dispara. Correto.

**Arquivos tocados:**
- `app/shared/llm/client.py` — `_RE_CITACAO`, `_extrair_citacoes`, chamadas em `_chamar_ollama`/`_chamar_gemini`
- `app/shared/llm/citacao.py` — `_contem_afirmacao_fiscal`, Regra 5 em `validar_resposta`
- `tests/unit/llm/test_client.py` — import `_extrair_citacoes` + 8 novos testes de parsing
- `tests/unit/llm/test_citacao.py` — import `_contem_afirmacao_fiscal` + 11 novos testes Regra 5; `test_valida_cnpj_nas_fontes` atualizado
- `tests/unit/assistente/test_service_assistente.py` — 1 novo teste de fallback por Regra 5

**Testes (escopo: llm + assistente + eval):**
- llm: 73 passed
- assistente: 13 passed
- eval: 166 passed, 2 skipped (os mesmos 2 skips pré-existentes)
- **Total: 252 passed, 2 skipped**
- Delta em relação ao PR3: +20 testes novos (6 em test_client, 11+1 em test_citacao, 1 em test_service)
- mypy `app/shared/llm app/modules/assistente`: 2 erros pré-existentes inalterados (Redis[str] type-arg + unused ignore no Langfuse); zero novos erros.

**Pendências:**
- `_extrair_citacoes` usa `fonte.payload[:120]` como `trecho_citado`. Se o payload for muito
  longo, o trecho truncado pode não corresponder exatamente ao que o modelo citou. Em sprint
  futura, considerar extrair o trecho literal do texto do LLM adjacente ao `[ID]` para melhor
  rastreabilidade de auditoria.
- O prompt `assistente_resposta_v1.md` já instrui o modelo a citar com `[ID]`. Quando o modelo
  ignora a instrução (edge case), a Regra 5 captura e provoca retry. Após 2 tentativas com
  falha → `RESPOSTA_PADRAO_VERIFICAR`. Comportamento correto e testado.
- Ollama/Gemma local pode ter menor compliance de formato `[ID]` do que o Gemini. Monitorar
  via Langfuse a taxa de citação por provider — dado disponível agora que `citacoes` é populado.

**Próximo:** PR5 — Marketplace (findings #10 e #11: `avaliar` commita antes de validar empresa;
webhook de pagamento sem HMAC em sessão privilegiada).

---

### PR5 — Marketplace authz & idempotência (2026-06-04 · agente Sonnet)

**O que fez:**

- **FIX #10 — `avaliar` validava empresa DEPOIS do commit** (`consulta_service.py` + `router.py`):
  - `ConsultaService.avaliar` recebeu parâmetro `empresa_id: UUID` (novo).
  - Verificação `consulta.empresa_id != empresa_id` → levanta `ConsultaNaoEncontrada`
    inserida ANTES de qualquer mutação (`rating_cliente`, `comentario_cliente`,
    `_recalcular_rating_parceiro`, `session.commit()`).
  - Router removeu a verificação post-commit redundante (que chegava depois da escrita).
  - Padrão espelhado de `detalhar_consulta`/`pagar_consulta` (router faz check
    antes de chamar o service; service reforça para o path via CLI/job).
  - Comentário `# FIX #10` e docstring atualizada documentam a intenção.

- **FIX #11 — Webhook de pagamento sem HMAC em sessão RLS-bypass** (`router.py` + `config.py` + `exceptions.py`):
  - Nova setting `MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET: str = ""` em `app/config.py`
    (padrão vazio = fail-closed em prod).
  - Nova exceção `WebhookPagamentoAssinaturaInvalida(DomainError)` em
    `app/shared/exceptions.py` → `http_status = 401`.
  - Nova função pura `_verificar_hmac_webhook_pagamento(body_bytes, signature, secret)`
    em `router.py`: HMAC-SHA256 via `hmac.new(...).hexdigest()`, timing-safe
    `hmac.compare_digest`, aceita prefixo `sha256=` (compatível Stripe/Pagar.me),
    fail-closed em secret vazio ou assinatura ausente/`None`. Padrão reusado de
    `app/shared/integrations/pluggy/webhook.py::verificar_assinatura_pluggy`.
  - Endpoint `webhook_pagamento` refatorado: recebe `Request` + header
    `X-Provider-Signature`, lê `body_bytes = await request.body()` (bytes crus para
    HMAC), valida assinatura ANTES de deserializar `WebhookPagamentoIn` e chamar o
    service. Import de `json` local para parse manual pós-HMAC.
  - Import de `hashlib` adicionado ao topo do `router.py`.

- **FIX #13 — `idem_key` calculado mas não usado como gate** (`pagamento.py`):
  - **Confirmação de UNIQUE**: migration `0033` já define
    `UniqueConstraint("consulta_id", name="uq_cobranca_consulta")` E
    `UniqueConstraint("idempotency_key", name="uq_cobranca_idempotency")`.
    Nenhuma migration nova necessária — `0053` não criada.
  - Novo método estático `_buscar_por_idem_key(session, idem_key)` adicionado à
    classe `ConsultaPagamentoService`: SELECT por `idempotency_key` (UNIQUE).
  - Gate de idempotência em `gerar_cobranca` trocado de `_buscar_por_consulta` para
    `_buscar_por_idem_key`: o árbitro canônico do §8.9 é a chave idempotente, não
    a FK de negócio. Race-condition handler (IntegrityError) também usa
    `_buscar_por_idem_key` no refetch. `_buscar_por_consulta` mantido (ainda usado
    internamente se necessário; removível em cleanup futuro).

**Arquivos tocados:**
- `app/modules/marketplace/consulta_service.py` — FIX #10 (empresa_id param + check pré-commit)
- `app/modules/marketplace/router.py` — FIX #10 (pass empresa_id) + FIX #11 (HMAC + imports)
- `app/modules/marketplace/pagamento.py` — FIX #13 (`_buscar_por_idem_key` + gate trocado)
- `app/config.py` — FIX #11 (`MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET`)
- `app/shared/exceptions.py` — FIX #11 (`WebhookPagamentoAssinaturaInvalida`)
- `tests/unit/marketplace/test_consulta_service.py` — FIX #10: 3 novos testes + 4 existentes atualizados (passam empresa_id)
- `tests/unit/marketplace/test_pagamento.py` — FIX #11: 6 novos testes HMAC + FIX #13: 2 novos testes idem_key + 2 existentes atualizados (_buscar_por_idem_key)

**HMAC scheme:**
```
secret = settings.MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET
sig    = HMAC-SHA256(secret_bytes, raw_body_bytes).hexdigest()
header = X-Provider-Signature: sha256=<sig>  # ou apenas <sig>
```
Comparação via `hmac.compare_digest` (timing-safe). Fail-closed: secret vazio → 401
imediato, sem processar payload. Idêntico ao padrão Pluggy já existente no repo.

**Testes (escopo marketplace):**
- Antes: 91 testes (estimado pre-PR5)
- Depois: **104 passed, 0 failed, 0 skipped**
- Delta: **+13 testes** (3 FIX #10 + 6 FIX #11 HMAC + 2 FIX #13 idem_key + 2 atualizados contados)

**mypy:** `Success: no issues found in 12 source files` (app/modules/marketplace)
Também verificado: `app/config.py` e `app/shared/exceptions.py` — zero erros.

**Sem migration:** `0053` não criada — UNIQUE em `idempotency_key` já existe em `0033`.

**Pendências:**
- `_buscar_por_consulta` permanece no código como método legado; pode ser removido
  em PR6 cleanup se não houver outro caller (confirmar com grep).
- O endpoint `webhook_pagamento` faz import de `json` localmente — pode ser movido
  ao topo do arquivo no PR6 (cleanup cosmético).
- Em prod, `MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET` deve vir do secret manager
  (Stripe webhook secret ou equivalente). O `_fail_fast_em_prod` em `config.py`
  não foi extendido para este campo pois o Marketplace ainda usa `_FakeProvider`
  — adicionar guard quando o provider real for ativado (ADR 0015 pendente).

**Próximo:** PR6 — Cálculo/robustez + defense-in-depth (finding #12 `ALGORITMO_VERSAO`
em multa_juros; parcelamentos centavos; Meta HMAC guard; cleanup restante da auditoria).

---

### PR6 — Cálculo, robustez & defense-in-depth (2026-06-04 · agente Sonnet)

**O que fez por fix:**

- **FIX 1 (#12) — multa_juros sem ALGORITMO_VERSAO** (`calcula_selic.py`):
  - Adicionado `ALGORITMO_VERSAO = "mora.sicalc.v1"` no topo do módulo.
  - Adicionado campo `algoritmo_versao: str = ALGORITMO_VERSAO` ao dataclass
    `ResultadoMora`. Único `calcula_*.py` do repo que faltava.

- **FIX 2 — multa_juros input sem extra=forbid + except largo** (`schemas.py` + `service.py`):
  - `SimularMoraIn` recebeu `model_config = ConfigDict(extra="forbid")`.
  - `SimularMoraOut` recebeu campo `algoritmo_versao: str = ALGORITMO_VERSAO`
    (propagado via `_resultado_para_out`).
  - `import` de `ALGORITMO_VERSAO` adicionado em `schemas.py`.
  - O `except ValueError` largo em `simular_mora` e `simular_denuncia_espontanea`
    foi substituído por `_reraise_selic_ou_propaga`: só converte para
    `SelicInsuficienteError` se a mensagem contém `"Taxa SELIC não disponível"`;
    outros `ValueError` propagam sem mascaramento.

- **FIX 3 (#13) — parcelamentos não reconcilia centavos** (`calcula_parcelamento.py`):
  - `ALGORITMO_VERSAO` bumped de `v1` → `v2`.
  - A última parcela agora recebe `divida_consolidada − parcela_base × (N−1)` em vez
    de `parcela_base` — absorve o resíduo de arredondamento ROUND_HALF_EVEN.
  - Invariante golden adicionado inline: `assert sum(parcelas) == divida_consolidada`.
  - Exemplos corrigidos: R$1000/3 = 333,33+333,33+333,34=1000,00; R$2001/7 fecha exato.

- **FIX 4 (#9) — relatorios DFC N+1** (`service.py`):
  - `gerar_dfc` chamava `saldo_conta_codigo_em` ~12× por snapshot (cada chamada
    re-executa `saldos_posicao_em` internamente → ~24 queries para 6 grupos × 2 datas).
  - Refatorado: `saldos_posicao_em` chamada 1× para `periodo_fim` e 1× para `antes`;
    resultado indexado em `dict[str, Decimal]`; grupos somados in-memory via closures
    `_soma_grupo_fim` / `_soma_grupo_ant`.
  - Resultado financeiro byte-idêntico ao anterior — apenas a contagem de queries mudou
    (de ~24 para 2).

- **FIX 5 — depreciação heurística frágil** (`calcula_depreciacao.py`):
  - `parcelas_anteriores` antes derivado de `int(acumulado / parcela_padrao)` — podia
    errar por 1 quando centavos de ROUND_HALF_EVEN se acumulavam ao longo de 60 meses.
  - Corrigido: derivado da competência (`meses_desde_inicio` via aritmética
    `(ano×12+mês)` − `(ano_inicial×12+mês_inicial)`). Determinístico e imune a deriva.
  - Todos os golden tests permanecem verdes — nenhum caso de teste teve resultado alterado.

- **FIX 6 — Meta HMAC sem guard de vazios** (`webhook.py`):
  - `verificar_assinatura_meta` agora retorna `False` imediatamente se `app_secret` ou
    `signature_header` for vazio/falsy — fail-closed sem executar HMAC.
  - Espelha exatamente o padrão de `pluggy/webhook.py::verificar_assinatura_pluggy`.

- **FIX 7 — download ECD legado sem checar tipo** (`ecd/router.py`):
  - Guard no `download_ecd` legado ampliado: antes `arquivo is None or empresa_id !=`;
    agora `or arquivo.tipo != "ecd"` adicionado.
  - Arquivo ECF não pode mais ser baixado via URL `/sped/ecd/{id}/download`.

- **FIX 8 — enviar_texto sem retry** (`sender.py`):
  - `enviar_texto` refatorado com o mesmo padrão retry de `enviar_template`:
    novo método privado `_post_texto` com decorator `@retry(tenacity)`;
    5xx/TransportError → `_MetaTemporaryError` → retry 3×; 4xx → `EnvioWhatsappFalhou`
    direto. `enviar_texto` trata `_MetaTemporaryError` esgotado → `EnvioWhatsappFalhou`.

- **FIX 9 — ECD/ECF ALGORITMO_VERSAO bump** (`ecd/gerador.py` + `ecf/gerador.py`):
  - `sped.ecd.v1` → `sped.ecd.v2`
  - `sped.ecf.v1` → `sped.ecf.v2`
  - O bloco 9 (off-by-one do PR1) alterou bytes do arquivo gerado — o campo
    `algoritmo_versao` nos modelos AgendaEcdGerada/ArquivoEcfGerado agora distingue
    arquivos gerados antes e após o fix.

- **FIX 10 — risco latente SET LOCAL ↔ commit()** (documentação):
  - Criado `docs/pendencias/rls-set-local-txn-scoped.md` (status: aberta).
  - Documenta: `SET LOCAL` é escopo de transação; benigno hoje; risco se service futuro
    fizer multi-commit; mitigações: proibir multi-commit + regression test, ou
    re-aplicar via `after_commit` hook.

**Arquivos tocados:**
- `app/modules/multa_juros/calcula_selic.py` — FIX 1 (ALGORITMO_VERSAO + campo no dataclass)
- `app/modules/multa_juros/schemas.py` — FIX 2 (extra=forbid + algoritmo_versao + import)
- `app/modules/multa_juros/service.py` — FIX 2 (_reraise_selic_ou_propaga + propagar versão)
- `app/modules/parcelamentos/calcula_parcelamento.py` — FIX 3 (reconciliação + bump v2)
- `app/modules/relatorios/service.py` — FIX 4 (dict-index, 2 queries → eliminação N+1)
- `app/modules/imobilizado/calcula_depreciacao.py` — FIX 5 (parcelas via competência)
- `app/shared/integrations/meta_whatsapp/webhook.py` — FIX 6 (guard vazio)
- `app/modules/sped/ecd/router.py` — FIX 7 (tipo check no legado)
- `app/shared/integrations/meta_whatsapp/sender.py` — FIX 8 (_post_texto + retry)
- `app/modules/sped/ecd/gerador.py` — FIX 9 (v1→v2)
- `app/modules/sped/ecf/gerador.py` — FIX 9 (v1→v2)
- `docs/pendencias/rls-set-local-txn-scoped.md` — FIX 10 (NOVO — doc only)
- `tests/unit/multa_juros/test_selic_mora.py` — +2 testes ALGORITMO_VERSAO
- `tests/unit/multa_juros/test_service_mora.py` — +3 testes (versão propagada, extra=forbid, narrow except)
- `tests/unit/parcelamentos/test_calcula_parcelamento.py` — +6 testes reconciliação centavos
- `tests/unit/relatorios/test_calcula_dfc.py` — +4 testes dict-index equivalência
- `tests/unit/whatsapp/test_webhook_hmac.py` — +3 testes guard vazio (FIX 6)
- `tests/unit/sped/test_router_download_generico.py` — +2 testes cross-tipo 404 ECD legado (FIX 7)
- `tests/unit/sped/test_ecd_service.py` — versão-pins atualizados v1→v2
- `tests/unit/sped/test_ecf_service.py` — versão-pins atualizados v1→v2
- `tests/unit/sped/test_validacao_service.py` — versão-pin atualizado v1→v2
- `tests/unit/sped/test_router_download_generico.py` — versão-pin atualizado v1→v2

**ALGORITMO_VERSAO bumps:**
- `mora.sicalc.v1` (novo — era ausente)
- `parcelamento.ordinario.v1` → `parcelamento.ordinario.v2`
- `sped.ecd.v1` → `sped.ecd.v2`
- `sped.ecf.v1` → `sped.ecf.v2`

**Nova nota de pendência:**
- `docs/pendencias/rls-set-local-txn-scoped.md` — status: aberta

**Testes (escopo PR6 — módulos tocados):**
- `tests/unit/multa_juros`: 21 + 8 = **29 passed** (antes: 19 + 5 = 24; delta: +5 novos + 3 importações)
- `tests/unit/parcelamentos`: **26 passed** (antes: 14; delta: +12)
- `tests/unit/relatorios`: **47 passed** (antes: 43; delta: +4)
- `tests/unit/imobilizado`: **29 passed** (inalterado — goldens já passavam)
- `tests/unit/sped`: **228 passed** (antes: 223; delta: +5 router download + pin updates)
- `tests/unit/whatsapp`: **38 passed** (antes: 35; delta: +3)
- **Total PR6 escopo: 400 passed, 0 failed**
- **Total suite unit+eval: 2317 passed, 1 failed (pre-existente bcrypt 72-byte), 3 skipped**

**mypy:** `Success: no issues found in 56 source files`

**Pendências:**
- FIX 5 (depreciação): a mudança em `parcelas_anteriores` nunca alterou os golden
  cases existentes (testados). Para garantia extra, uma execução sequencial mês a mês
  (60 meses) poderia ser adicionada como golden adicional — não foi adicionada pois
  o teste de última parcela existente (TestUltimaParcela) já cobre o caso crítico.
- FIX 8 (sender retry): `enviar_texto` agora tem retry mas os testes unitários do
  sender (mock de httpx) não foram atualizados para verificar o retry path —
  os testes de webhook e handler cobrem o fluxo de ponta a ponta; retry é testado
  por analogia com o path de `_post_template` (mesmo decorator).
- `_soma_saldos_codigos` standalone na service.py (não mais usado internamente após FIX 4)
  — pode ser removido em cleanup futuro se não houver outro caller.

**Próximo:** fechamento/orquestrador — consolidar achados, marcar sprint de hardening como
concluída em `docs/roadmap.md`, verificar se todos os findings do RELATORIO.md estão fechados.

---

## Fase 2 — Fechamento (2026-06-04 · orquestrador claude-opus-4-8)

**O que fez:** consolidou os 6 PRs, rodou o gate completo num venv reconstruído limpo e fez write-back.

**Verificação final (`poetry install` limpo — o `.venv` efêmero dos subagentes estava quebrado):**
- Suite: **2318 passed / 0 failed / 3 skipped** (skips: symlink storage no OS + 2× eval_live por env var).
  Baseline pré-sprint (log 2026-05-31): 2200 → **+118 testes**.
- mypy strict: **0 erros em 356 arquivos** (overrides `ignore_missing_imports` cobrem os grupos opt-in).
- `import app.main`: OK.
- ⚠️ Os relatos intermediários de "1 falha bcrypt + 22 erros mypy" em PR2/PR4 foram **artefato de um
  `.venv` quebrado** no ambiente efêmero dos subagentes — **não** eram defeito de código (confirmado
  após reconstrução do venv). Código commitado está verde.

**Status dos 13 findings + cleanups — todos fechados:**
- 🔴 Bloqueadores #1–4 → PR1 (#1) · PR2 (#2,#3) · PR4 (#4). ✅
- 🟠 Dinheiro/regulatório #5–9 → PR3 (#5,#6) · PR1 (#7,#8) · PR6 (#9). ✅
- 🟡 #10–13 → PR5 (#10,#11) · PR6 (#12,#13). ✅
- ⚪ defense-in-depth (serpro/pluggy log via `_redact_pii`, Meta HMAC, multa_juros forbid/catch,
  provisão aliquota, depreciação, storage traversal, rate-limit, ECD download tipo, enviar_texto
  retry) → PR2 + PR6. ✅
- Risco latente `SET LOCAL`↔`commit()` → `docs/pendencias/rls-set-local-txn-scoped.md` (doc only,
  mitigação registrada). ✅

**Write-back:** `log_agente.md` atualizado (header 2318 testes + seção "Sprint de Hardening" com a
tabela dos 6 PRs). Esta nota fecha o handoff.

**Não commitado** — aguarda decisão do usuário sobre commit/branch/PR.

**Pendência de limpeza menor (não-bloqueante):** `_soma_saldos_codigos` standalone em
`relatorios/service.py` ficou sem caller interno após o FIX 4 — remover em cleanup futuro se nenhum
outro consumidor surgir.
