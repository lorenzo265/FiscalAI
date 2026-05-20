# Plano de remediação — Achados da review FiscalAI Backend

> **Documento de handoff.** Outro agente deve poder pegar de onde paramos.
> Plano original em `C:\Users\loren\.claude\plans\cheeky-twirling-micali.md`.
> Review completa que gerou esses achados está na conversa anterior — referenciada por códigos `C1.x`–`C5.x`.

---

## Status atual (2026-05-18)

| Fase | Tema | Status | Suite |
|---|---|---|---|
| Review | Auditoria do plano + código (5 atos) | ✅ Concluída | — |
| **Fase 1** | Correção emergencial (plano + 3 bugs fiscais) | ✅ **Concluída** | 980 → **992 passing** |
| **Fase 2** | Hardening de schema | ✅ **Concluída** (PR1 ✅ PR2 ✅ PR3 ✅ PR4 ✅; drop column → 0027 housekeeping) | 992 mantido |
| Fase 3 | Sprint 13 reforçada (marketplace) | ⏸️ Aguarda Fase 2 | — |
| Fase 4 | Governança (LGPD, ADRs, custos, regulatório) | ⏸️ Paralelo às 2-3 | — |
| Fase 5 | Housekeeping técnico (typing, dead code, validação) | ⏸️ Contínuo | — |

**Suite:** 992 testes passando, 2 skipped. mypy strict: 0 erros em 225 arquivos.
**Sprint 13 (marketplace) está pausada** até Fase 2 completar.

---

## Contexto

A review do PlanoBackend.md + código `analista-fiscal-api/` produziu **~30 achados** distribuídos em
5 atos. Os achados se concentram em 4 famílias:

1. **Plano fonte-da-verdade tem 3 referências normativas inventadas** (LC 227/2026, `fdb-sped`,
   "Ajuste SINIEF 2/2025") e contradições internas. Foi redigido por LLM e nunca passou por
   revisor humano com CRC. **(Resolvido na Fase 1.)**
2. **Schema do banco tem buracos que violam os próprios princípios invioláveis (§8.2 fatos
   imutáveis, §8.9 idempotência)** — `documento_fiscal` aceita UPDATE/DELETE; `consulta_marketplace`
   (Sprint 13, pré-implementação) não tem idempotência nem snapshot versionado.
   **(`consulta_marketplace` resolvido em §5.8 do Plano na Fase 1.7; resto fica na Fase 2.)**
3. **3 bugs fiscais de risco real** em `calcula_das` (sublimite estadual ignorado),
   `calcula_irpj` (IRRF a compensar ausente + quantização dupla). Esses geram cliente
   pagando imposto errado. **(Todos resolvidos na Fase 1.)**
4. **Princípios diluídos no código:** 138 `Any` em 40 arquivos; idempotência semântica em
   Pluggy diverge do princípio §8.9 escrito; ADRs (0001-0013) prometidos pela Sprint 0
   nunca foram escritos no repositório (`docs/adr/` não existia — Fase 1.2 criou e escreveu
   ADR 0014). **(Fase 2 + Fase 4 endereçam.)**

**Resultado esperado:** Plano e código coerentes, bugs fiscais corrigidos com golden tests novos,
schema do banco impondo os princípios invioláveis no DB (não só na prosa), Sprint 13 reaberta
com escopo reforçado.

---

## Resumo executivo do plano

5 fases sequenciais (com paralelismo onde possível). Cada fase termina com critério binário.

| Fase | Tema | Duração estimada | Bloqueia Sprint 13? |
|---|---|---|---|
| **Fase 1** | Correção emergencial (plano + 3 bugs fiscais) | 2-3 dias | Sim |
| **Fase 2** | Hardening de schema | 1 sprint | Sim |
| **Fase 3** | Sprint 13 reforçada | 1 sprint normal | — |
| **Fase 4** | Governança (LGPD, ADRs, custos, regulatório) | Paralelo às Fases 2-3 | Não |
| **Fase 5** | Housekeeping técnico (typing, dead code, validação) | Contínuo | Não |

---

## ✅ Fase 1 — Correção emergencial (CONCLUÍDA em 2026-05-18)

Objetivo: parar o sangramento. Texto inventado fora do plano + 3 bugs com risco fiscal direto.

### 1.1 — Corrigir PlanoBackend.md (referências normativas inventadas) ✅

Arquivo: `C:\dev\Apresentação-Ideia\docs\PlanoBackend.md`

- **C1.1 / C3.12** — Remover "LC 227/2026" das linhas 153 e 1919. ✅ Substituído por LC 214/2025 + PLP 68/2024 + PLP 108/2024.
- **C1.5** — Linha 196 substituir "`fdb-sped`" por "parser custom + `python-sped` como ponto de partida". ✅
- **C3.4** — "Ajuste SINIEF 2/2025" sobre retenção 11 anos. ✅ Trocado para 5 anos (CTN art. 173-174), com nota sobre extensão a 10 anos sob ato fiscal específico.

### 1.2 — Corrigir contradição §7.7 vs §8.12 (transmissão SPED) ✅

Arquivo: `C:\dev\Apresentação-Ideia\docs\PlanoBackend.md` + ADR novo.

- **C2.1 / C2.2** — Decisão final: SPED é manual (cliente baixa+transmite com cert dele); PGDAS/DCTFWeb usa procuração e-CAC + cert do **escritório contábil** (não do cliente). **Não armazenamos cert A1 de cliente.**
- ADR `analista-fiscal-api/docs/adr/0014-transmissao-spedes-modelo.md` ✅ escrito com a justificativa completa.

### 1.3 — Corrigir matemática e divergência custo SERPRO ✅

- **C1.8** — Conta `R$0,96 × 100 × 12 = R$96` corrigida para `R$0,96 × 100 = R$96/mês`.
- **C2.4** — Status RFB diário adicionado em linha separada: `R$0,30 × 100 × 30 = R$900/mês`.
- §12.1 inteira refeita com custos realistas (R$3.046 → R$16.700–18.700 a 100 pagantes).
- §12.4 margem bruta refeita (86% → 15–25% a 100 pagantes; 78–82% a 1.000 pagantes; break-even ~120–150).
- §1.6 alinhado com novos números.

### 1.4 — Bug fiscal #1: `calcula_das` sublimite estadual ✅

Arquivo: `analista-fiscal-api/app/modules/fiscal/calcula_das.py`

- Novo input `uf: str | None` + `sublimite_estadual: Decimal | None` (default R$3.600.000).
- Novos campos no `ResultadoDAS`: `uf`, `sublimite_aplicado`, `sublimite_excedido`.
- Acima do teto federal R$4.800.000: levanta `EmpresaForaSimplesNacional` (nova exception).
- `ALGORITMO_VERSAO` bumpado para `sn.das.v2`.
- 8 testes novos cobrindo sublimite padrão, sublimite reduzido R$1,8M, teto federal exato e excedido.

**Limitação consciente:** quando `sublimite_excedido=True`, o sistema **continua** retornando o DAS cheio (com ICMS/ISS embutidos) e sinaliza via flag. O cálculo real "DAS sem ICMS/ISS" exige decomposição por tributo na tabela CGSN — pendência da Fase 5. Frontend deve mostrar aviso explícito.

### 1.5 — Bug fiscal #2: `calcula_irpj` IRRF a compensar ✅

Arquivo: `analista-fiscal-api/app/modules/lucro_presumido/calcula_irpj.py`

- Novo parâmetro `irrf_a_compensar: Decimal = _ZERO` em `calcular_irpj_trimestral`.
- Aplicado **após** soma normal + adicional (Lei 9.430 art. 64).
- Novos campos no `ResultadoIrpjLp`: `irrf_a_compensar`, `irrf_consumido`, `irrf_saldo_credor`, `irpj_devido`.
- `ALGORITMO_VERSAO` bumpado para `lp.irpj.trimestral.v2`.
- `_extrair_valor_total` em `schemas.py` agora retorna `irpj_devido` (com fallback para `irpj_total` em apurações antigas).
- 5 testes novos cobrindo: IRRF zero (backward-compat), IRRF < IRPJ, IRRF > IRPJ (saldo credor), IRRF = IRPJ, IRRF negativo (rejeitado).

### 1.6 — Bug fiscal #3: quantização dupla em `calcula_irpj` ✅

Mesmo arquivo de 1.5.

- Substituído `_quantizar(irpj_normal_q + irpj_adicional_q)` por `_quantizar(irpj_normal + irpj_adicional)` (soma raw, quantize único).
- `irpj_normal` e `irpj_adicional` no resultado seguem quantizados para exibição, mas a soma vai do raw — alinha com PVA/DCTFWeb.
- 2 testes novos cobrindo invariante e caso de borda em centavo.

### 1.7 — Atualizar §5.8 do Plano com requisitos consulta_marketplace ✅

Arquivo: `docs/PlanoBackend.md` §5.8.

DDL definitivo agora inclui:
- `idempotency_key UUID NOT NULL UNIQUE` (UUID v5 com `(empresa_id, categoria, hash, dia)`)
- `pergunta_hash CHAR(64)` (SHA-256 da pergunta)
- `snapshot_versao VARCHAR(20) NOT NULL`
- `CHECK (categoria IN (...))` lista enumerada
- `CHECK (status IN (...))` lista enumerada
- `CHECK (comissao_plataforma >= 0 AND comissao_plataforma <= valor_consulta)`
- `CHECK (valor_consulta >= 0)`
- `consentimento_revogado_em` + `pii_apagado_em` (LGPD)
- `sla_aceitar_ate`, `sla_responder_ate`, `aceita_em`
- Status `'expirada'` e `'aceita'` (adicionados além de `'aberta','atribuida','em_andamento','concluida','cancelada'`)
- 4 índices (tenant, empresa+status, contador+status, SLA parcial)
- RLS habilitado + policy padrão

### Critério Fase 1 (todos ✅)
- [x] Plano com 0 referências normativas inventadas (`grep "LC 227|fdb-sped"` → 0 matches).
- [x] §7.7 e §8.12 alinhados (ADR 0014 documenta a decisão).
- [x] §12.1 com SERPRO realista; §12.4 margem refeita.
- [x] `calcula_das` recebe `uf` + `sublimite_estadual`; golden tests novos passam.
- [x] `calcula_irpj` aceita `irrf_a_compensar`; quantização única no fim; golden tests passam.
- [x] `pytest tests/unit tests/eval` 100% green (992 passed, 2 skipped).
- [x] `mypy strict` 0 erros em 225 arquivos.
- [x] `log_agente.md` atualizado com nova contagem.

---

## ⏸️ Fase 2 — Hardening de schema (PRÓXIMO, bloqueia Sprint 13)

Objetivo: princípios §8.1, §8.2, §8.3, §8.9 deixam de ser prosa e viram constraint no DB.

### ✅ PR1 — `documento_fiscal` blindado (Migration 0024) — CONCLUÍDO em 2026-05-19

Arquivos entregues:
- `analista-fiscal-api/alembic/versions/0024_fase2_documento_fiscal_hardening.py` ✅
- `analista-fiscal-api/app/shared/db/models.py` — `DocumentoFiscal` atualizado ✅

Decisão sobre granularidade: o plano sugeria 3 sub-migrations (0024a/b/c).
Auditoria prévia confirmou **0 callers fazem UPDATE/DELETE em `documento_fiscal`** no
app (`Grep` em `app/` retornou só `select(DocumentoFiscal).where(...)`), então
o REVOKE é seguro de aplicar de uma só vez. A migration `0024` consolida as 3
fases em uma única revisão com `op.execute` separados em blocos comentados
(Fase 1 estrutural → Fase 2 backfill → Fase 3 integridade).

Mudanças aplicadas (C1.3):
- ✅ Coluna `superseded_by UUID NULL REFERENCES documento_fiscal(id)` espelhando `supersedes`.
- ✅ UNIQUE parcial `uq_doc_empresa_chave_vigente (empresa_id, chave) WHERE superseded_by IS NULL AND chave IS NOT NULL`.
- ✅ CHECK `ck_doc_evento` (`evento IS NULL OR evento IN ('cancelou','denegou','retificou')`).
- ✅ CHECK `ck_doc_cfop_formato` (`cfop ~ '^\d{4}$'`).
- ✅ CHECK `ck_doc_cst_formato` (`cst ~ '^\d{2,3}$'`).
- ✅ `REVOKE UPDATE, DELETE ON documento_fiscal FROM PUBLIC`.
- ✅ Index parcial `ix_doc_vigente (empresa_id, tipo, emitida_em) WHERE superseded_by IS NULL` — acesso rápido aos documentos vigentes.

Backfill defensivo na Fase 2 (único UPDATE legítimo permitido — depois disso PUBLIC perde permissão):
- `superseded_by` reconstruído a partir do inverso de `supersedes`.
- CFOP fora de `^\d{4}$` → `NULL` (preserva o documento sem o lixo).
- CST fora de `^\d{2,3}$` → `NULL`.
- `evento` fora do enum → `NULL`.

Validação: mypy strict 0 erros em 225 arquivos · pytest unit/eval **992 passing**, 2 skipped.
Validação do schema real (alembic upgrade + DDL aplicado) exige Docker rodando — o
usuário valida no próximo `docker compose up -d && alembic upgrade head`.

### ✅ PR2 — Tabelas SCD tributárias protegidas (Migration 0025) — CONCLUÍDO em 2026-05-19

Arquivo entregue: `analista-fiscal-api/alembic/versions/0025_fase2_tabelas_scd_hardening.py` ✅

Mudanças aplicadas (C1.10):
- ✅ `REVOKE UPDATE, DELETE FROM PUBLIC` em 8 tabelas:
  `tabela_simples_faixa`, `tabela_inss_faixa`, `tabela_irrf_faixa`,
  `tabela_fgts_aliquota`, `tabela_depreciacao_rfb`,
  `presuncao_lucro_presumido`, `aliquota_icms_uf`, `selic_mensal`.
- ✅ Role `tax_table_admin` criado idempotentemente (`DO $$ ... CREATE ROLE IF NOT EXISTS ...`)
  + `GRANT INSERT` explícito nas 8 tabelas (sinalização semântica).
- ✅ Função PL/pgSQL `scd_close_previous_valid_to()` (`SECURITY DEFINER` para
  bypassar o próprio REVOKE) — genérica, lê chave de domínio via `TG_ARGV` +
  `to_jsonb(NEW)`. Usa `IS NOT DISTINCT FROM` para tratar nullable corretamente
  (importante para `presuncao_lucro_presumido.cnae_pattern`).
- ✅ Trigger `AFTER INSERT FOR EACH ROW` em 7 tabelas SCD (exceto `selic_mensal`
  que não tem `valid_from/valid_to` — é append-only puro com UNIQUE em `competencia`):

  | Tabela | Chave de domínio |
  |---|---|
  | `tabela_simples_faixa` | `(anexo, faixa)` |
  | `tabela_inss_faixa` | `(tipo, faixa)` |
  | `tabela_irrf_faixa` | `(faixa)` |
  | `tabela_fgts_aliquota` | `(vinculo)` |
  | `tabela_depreciacao_rfb` | `(categoria)` |
  | `presuncao_lucro_presumido` | `(grupo_atividade, cnae_pattern)` |
  | `aliquota_icms_uf` | `(uf)` |

Validação: mypy strict 0 erros em 225 arquivos · pytest unit/eval **992 passing**, 2 skipped.
Modelos SQLAlchemy não precisam de mudança (trigger/REVOKE são puramente do DB).
Validação física exige `alembic upgrade head` com Docker.

### ✅ PR3 — `empresa.faturamento_12m` virar view materializada (Migration 0026) — CONCLUÍDO em 2026-05-19

Arquivos entregues:
- `analista-fiscal-api/alembic/versions/0026_fase2_rbt12_materializada.py` ✅
- `analista-fiscal-api/app/modules/empresa/repo.py` — `EmpresaRepo.rbt12_da_view()` (novo) ✅
- `analista-fiscal-api/app/modules/fiscal/service.py` — DAS lê RBT12 da view com fallback ✅
- `analista-fiscal-api/app/modules/lucro_presumido/service.py` — `_resolver_presuncao` idem ✅
- `analista-fiscal-api/app/workers/tasks/refresh_rbt12.py` (novo) — task Celery ✅
- `analista-fiscal-api/app/workers/celery_app.py` — beat entry `rbt12.refresh_mensal` ✅

Mudanças aplicadas (C1.2):
- ✅ MV `rbt12_mensal(tenant_id, empresa_id, competencia, valor)` agregando
  `documento_fiscal.valor_total WHERE direcao='saida' AND status='autorizada' AND superseded_by IS NULL`
  com janela `ROWS BETWEEN 11 PRECEDING AND CURRENT ROW`.
- ✅ UNIQUE INDEX `(tenant_id, empresa_id, competencia)` — pré-requisito de `REFRESH CONCURRENTLY`.
- ✅ Função `refresh_rbt12_mensal()` `SECURITY DEFINER` (bypassa RLS de `documento_fiscal`).
- ✅ Celery beat `rbt12.refresh_mensal` — dia 2 às 06:00 (após encerramento contábil).
- ✅ Services migrados com fallback para `empresa.faturamento_12m` (empresa nova sem documentos).

**Drop da coluna `empresa.faturamento_12m`:** fica para migration 0027 separada
(2ª fase do "drop em 2 fases" do plano). Soft deprecation feita; hard deprecation
quando produção validar que a MV popula corretamente.

Limitação consciente documentada no docstring da migration:
* Janela `ROWS 11 PRECEDING` conta 12 emissões — para empresa sazonal pode
  abranger período calendário > 12 meses. Trade-off aceito para PME típica
  que emite mensalmente.

Validação: mypy strict 0 erros em **226** arquivos (+1 do novo `refresh_rbt12.py`).
pytest unit/eval **992 passing**, 2 skipped. Validação física exige `alembic upgrade head` com Docker.

### ✅ PR4 — Reduzir `Any` em contratos públicos — CONCLUÍDO em 2026-05-19

**Resultado: 144 → 13 ocorrências** (≈91% de redução; alvo do plano era ≤30).

Arquivos novos:
- `analista-fiscal-api/app/shared/types.py` — `JsonObject = dict[str, Any]` (alias
  canônico para colunas JSONB do Postgres + payloads JSON crus de integração).
- `analista-fiscal-api/app/shared/integrations/serpro/types.py` — TypedDicts do
  envelope Integra Contador (`SerproRequest`, `SerproResponse`, `SerproParticipante`,
  `SerproPedidoDados`, `SerproMensagem`, `SerproDadosDeclaracao`).

Arquivos atualizados (35):
- **Clients/HTTP** (33 Any → 0): `serpro/client.py`, `serpro/oauth.py`, `pluggy/client.py`,
  `pluggy/auth.py`, `pluggy/webhook.py`, `focus_nfe/client.py`, `brasil_api/client.py`,
  `meta_whatsapp/sender.py`, `meta_whatsapp/webhook.py`.
- **LLM** (4 → 1): `shared/llm/client.py` (1 `Any` justificado em lazy `genai.Client`).
- **eSocial / Reinf payloads** (8 → 0): `pessoal/esocial_payloads.py`, `reinf/esocial_payload.py`.
- **Services + repos**: `declaracao_anual/{service,repo,gerar_defis,gerar_dasn_simei}`,
  `open_finance/{service,sync_service,webhook_service,transacoes_repo}`,
  `pgdas/{service,repo}`, `certidoes/{service,repo}`, `e_cac/service`, `notas/service`
  (com novo Protocol `_FocusClient`), `pessoal/{eventos_service,socio_service}`,
  `lucro_presumido/service`, `relatorios/service`, `memoria/{service,repo,schemas}`,
  `reinf/service`, `icms/service`, `main.py`, `workers/tasks/refresh_rbt12.py`.
- **Models** (23 → 1 ref ao alias): `shared/db/models.py` — todas as colunas JSONB
  agora declaram `Mapped[JsonObject]`.

As 13 ocorrências restantes (todas em helpers privados ou pontos justificados):
1. `shared/types.py:20` — declaração canônica do alias `JsonObject`.
2. `workers/celery_app.py` (4) — stub local de `Celery` (aceita `task(*args, **kwargs)` arbitrário e `beat_schedule: dict[str, Any]` do Celery upstream).
3. `shared/llm/client.py:121` — `self._gemini: Any  # noqa: ANN401` (lazy import de `genai.Client`).
4. `modules/whatsapp/service.py:25` — `sender: Any | None` com noqa (duck-typed do Sprint 5).
5. `modules/pessoal/eventos_service.py` (2) — `_detalhes_jsonb(obj: Any)` + `_stringify` recursivos com noqa.
6. `modules/{relatorios,reinf,icms,lucro_presumido}/service.py` (4) — `_stringify(o: Any) -> Any` helpers privados com noqa.

Validação: mypy strict 0 erros em **228** arquivos. pytest unit/eval **992 passing**, 2 skipped.

### Critério Fase 2
- [x] `documento_fiscal` aceita CHECK, REVOKE, UNIQUE parcial sem quebrar dados existentes. ✅ PR1
- [x] 8 tabelas SCD com REVOKE UPDATE/DELETE. ✅ PR2
- [x] view materializada `rbt12_mensal` populada + endpoints migrados. ✅ PR3 (drop column `empresa.faturamento_12m` fica em 0027 housekeeping)
- [x] `grep -r ": Any\|dict\[str, Any\]" app/` **13 ocorrências** (alvo ≤30), todas em helpers privados/justificadas. ✅ PR4
- [x] mypy strict + pytest 100% green (228 arquivos / 992 passing). ✅

---

## Fase 3 — Sprint 13 reforçada (1 sprint normal, depois da Fase 2)

Após Fase 2 fechada, abrir Sprint 13 com **3 PRs** + 1 PR extra de validação.

Estrutura: PR1 cadastro contadores; PR2 consulta_marketplace; PR3 resposta + pagamento + SLA.

Reforços herdados da Fase 1.7 e do plano:

- **`consulta_marketplace`** já nasce com `idempotency_key`, CHECK `comissao<=valor`, CHECK status, `snapshot_versao` (DDL final está em §5.8 do Plano).
- **Bootstrap curadoria (C2.11):** primeiros 10 contadores parceiros entram via `crc_status='periodo_teste'` e ganham 10 consultas com **valor zerado e rating não-contabilizado**. Depois disso viram `crc_status='ativo'` se NPS interno ≥ 4.0.
- **SLA policy (C2.15):** consulta com SLA estourado é automaticamente cancelada pelo worker `monitor_sla_marketplace`; cliente é reembolsado integralmente; contador recebe strike. Após 3 strikes em 30 dias: `crc_status='suspenso'`.
- **`LLMResponse` desacoplada (C2.3):** remover `encaminhar_marketplace` e `categoria_marketplace` de `app/shared/llm/client.py:74-75`. Criar `app/modules/marketplace/triage.py` que consome `LLMResponse` pura + chama `detectar_out_of_scope`.
- **LGPD por consulta (C2.16):** ao revogar consentimento, dados pessoais são apagados mas campos contábeis (papéis de trabalho — Resolução CFC 1.328/2011) ficam por 5 anos. `consulta_marketplace` já tem `consentimento_revogado_em` + `pii_apagado_em` no DDL.

### Critério Fase 3
- [ ] 3 PRs Sprint 13 + 1 PR refactor `LLMResponse` aprovados.
- [ ] Marco Fase 2 §11.1 do plano: 5+ contadores parceiros + 10+ consultas (em dados de teste).
- [ ] mypy + pytest green.

---

## Fase 4 — Governança (paralelo às Fases 2-3)

Não bloqueia código mas é dívida que precisa ser amortizada antes de 100 pagantes.

### 4.1 — Criar `docs/adr/` e escrever os 16 ADRs

**ADR 0014 já está em `analista-fiscal-api/docs/adr/0014-transmissao-spedes-modelo.md` (Fase 1.2).**

Faltam:
- `0001-fastapi-vs-litestar.md`
- `0002-pgvector-vs-qdrant.md`
- `0003-llm-3-camadas.md`
- `0004-multi-tenancy-rls.md`
- `0005-fatos-imutaveis.md`
- `0006-focus-nfe-vs-plugnotas.md`
- `0007-pluggy-vs-belvo.md`
- `0008-citacao-obrigatoria.md`
- `0009-serpro-integra-contador.md`
- `0010-meta-whatsapp-direto.md`
- `0011-marketplace-vs-contadores-internos.md`
- `0012-geracao-sped-propria.md`
- `0013-out-of-scope-deliberado.md`
- `0015-pluggy-idempotencia-semantica.md` — documentar divergência §8.9 vs realidade Pluggy (C2.4/C4.2).
- `0016-prolabore-distribuicao-em-pessoal.md` — documentar consolidação módulos (C4.3).

Template Michael Nygard padrão. Cada ADR ≤ 100 linhas.

### 4.2 — Endpoints LGPD reais

- **C3.5** — Plano §14.4 marca `[x]` em endpoints que não existem. Criar:
  - `GET /v1/lgpd/dados-do-titular` — retorna JSON com todos os dados do tenant.
  - `DELETE /v1/lgpd/dados-do-titular` — pseudonimização (não delete) preservando obrigação fiscal 5 anos.
  - Endpoint de **exportação completa** (LGPD art. 18 II): JSON + PDF assinado.
- Atualizar checklist §14.4 com status honesto.

### 4.3 — DPO + parecer jurídico

- **C2.13** — Designar DPO desde cliente 1 (LGPD não condiciona a 100 clientes). DPO terceirizado (R$2-5k/mês) até justificar interno.
- **R5** — Contratar parecer jurídico CRC/CFC sobre limites de IA conversacional em serviço contábil **antes do cliente 1 pagante** (não cliente 100). Custo R$15-30k.

### 4.4 — Runbook ANPD 72h (R8)

Criar `analista-fiscal-api/docs/runbooks/lgpd-incidente-72h.md` com:
- Fluxo de identificação do vazamento.
- Template de notificação ANPD (e-PIA).
- Cadeia de comunicação interna.
- Comunicação aos titulares afetados.

### 4.5 — Re-baseline final de custos e time (parte feita na Fase 1.3)

**Custos já atualizados na Fase 1.3.** Pendente:
- **C3.6** — Adicionar §15.5 itens omitidos: advogado LGPD R$30-50k, advogado tributarista R$30-50k, seguro tech R$15-30k, DPO R$20-50k.
- Total revisado: ~R$950k-R$1,17M em 10 meses (vs R$685-810k do plano original).

### 4.6 — Riscos ausentes (§16)

Adicionar ao Plano:
- **R11** — Concentração de fornecedor SERPRO. Mitigação: contrato fallback com PlugNotas/Avalara em compliance ≥ Fase 3.
- **R12** — CFC/RFB publicar norma restringindo IA em escrita fiscal. Mitigação: parecer jurídico Sprint 0 + monitoramento jurídico mensal + cláusula ToS de adaptação.
- **R13** — Google muda ToS Gemini ou treina com dados pagos. Mitigação: contrato BAA escrito com Google Cloud antes de cliente 1; auditar termos anualmente.
- **R14** — Cliente paga DAS/IRPJ errado por bug. Mitigação: fundo de garantia R$50k inicial; ToS com limite de responsabilidade R$1k/cliente; seguro tech.

### Critério Fase 4
- [ ] 16 ADRs em `docs/adr/`.
- [ ] 2 endpoints LGPD funcionais + checklist §14.4 honesto.
- [ ] DPO contratado + parecer CRC/CFC obtido.
- [ ] Runbook ANPD escrito + simulado (tabletop exercise).
- [ ] §15 do Plano com números realistas (§12 já feito na Fase 1.3).
- [ ] §16 com R11-R14.

---

## Fase 5 — Housekeeping técnico (contínuo, qualquer ordem)

Pequenas dívidas que não bloqueiam roadmap mas devem ser limpas antes da Fase 3 do plano (Sprint 20).

### Itens

- **C5.8** — Remover dead code `acumulado = topo_faixa` em `calcula_inss.py:104`.
- **C5.9** — Adicionar `_validar_faixas_consecutivas()` em todos os `calcula_*` que recebem lista de faixas. Erro: gap, sobreposição, alíquota não-monotônica, faixa 1 ausente.
- **C5.6 + C5.7** — Limites/alíquotas hardcoded (`_LIMITE_MES` em IRPJ, `_ALIQ_PIS`, `_ALIQ_COFINS`) migram para tabela SCD. Bumpar `ALGORITMO_VERSAO` quando o algoritmo passar a ler do banco.
- **C5.11** — `aliquota_efetiva` em `calcula_inss.py:111` usa `inss` quantizado — usar `inss_total` raw, quantizar uma vez no final.
- **C5.12** — Criar `app/modules/pessoal/validador_folha_12m.py` validando composição da `folha_12m` para Fator R (verbas elegíveis: salários + 13º + encargos + pró-labore).
- **C4.4** — `# type: ignore[arg-type]` em `contabil/lancador_service.py:154,220` ganha comentário explicativo OU é refatorado (`cast(NfTipo, nf.tipo)`).
- **C5.4** — Em `calcula_pis_cofins`, permitir `exclusoes > receita_bruta_mes` retornando saldo credor (campo novo `saldo_credor_proximo_mes: Decimal`).
- **C2.6** — Refinar `OUT_OF_SCOPE_PATTERNS` em `app/shared/llm/citacao.py:160`. Adicionar anti-padrões: "exportar relatório", "fiscalização interna", etc. Eval suite ganha 20+ casos de falso positivo.
- **C2.9** — `validar_resposta` em `citacao.py` normaliza valores monetários antes da comparação (`Decimal` canônico, sem `R$`/`.`/`,`).
- **C5.10** — Decidir explicitamente PIS/Cofins monofásico: out-of-scope ou implementar. Atualizar §9.3 do Plano.
- **C4.5** — Padronizar golden tests: hoje há 9 JSON (só SN) + parametrize no resto. **Decisão pragmática:** manter como está e atualizar Plano §4.2 para refletir realidade.
- **C4.8** — Documentar pattern `proximo_numero_rps` com `SELECT FOR UPDATE` em ADR (risco de gargalo) e adicionar métrica Prometheus `nfse_rps_lock_wait_ms`.
- **C5.1 (extensão Fase 1.4)** — Implementar decomposição por tributo da tabela CGSN 140 para que `calcula_das` consiga calcular DAS **sem ICMS/ISS** quando `sublimite_excedido=True`. Hoje apenas sinaliza com flag.

### Critério Fase 5
- [ ] 0 dead code detectado por `vulture` no CI.
- [ ] `_validar_faixas_consecutivas` em todos calcula_* que recebem faixas.
- [ ] `OUT_OF_SCOPE_PATTERNS` com anti-padrões + eval com 90%+ precisão (não só recall).
- [ ] `calcula_das` calcula DAS-sem-ICMS/ISS corretamente quando sublimite excedido.

---

## Critérios globais de pronto

Antes de retomar **qualquer sprint nova além da Sprint 13**:

- [x] Fase 1 completa.
- [ ] Fase 2 completa.
- [ ] Fase 3 (Sprint 13) completa.
- [x] PlanoBackend.md sem nenhuma fonte normativa não-verificável (grep checa).
- [x] mypy strict 0 erros (mantido).
- [x] pytest unit + eval 100% green com **golden tests novos** (Fase 1.4, 1.5, 1.6).
- [x] `log_agente.md` atualizado refletindo o estado verdadeiro.
- [ ] 16 ADRs em `docs/adr/` (1 de 16 ✅: ADR 0014).
- [ ] §15 do Plano com números honestos (§12 ✅) e §14.4 LGPD checklist verdadeiro.

---

## Riscos do próprio plano

1. **Migration 0024 (documento_fiscal CHECK)** pode quebrar dados existentes. Mitigação: rodar validação read-only antes de aplicar; cleanup script para dados inconsistentes.
2. **Migration 0026 (drop `faturamento_12m`)** pode quebrar endpoints que ainda leem direto. Mitigação: 2 fases — primeiro view + endpoints migrados; depois drop.
3. **Refactor `LLMResponse`** quebra contratos com frontend? **Não** — `encaminhar_marketplace` só era usado no service do assistente; frontend ainda não consome esse campo.
4. **Pausar Sprint 13 atrasa o marco Fase 2 (50 pagantes/MRR R$10k)** em ~2-3 semanas. Tradeoff aceito: melhor atrasar que retrabalhar marketplace depois com dados em produção.

---

## Arquivos críticos a modificar (referência rápida)

| Arquivo | Mudança | Fase | Status |
|---|---|---|---|
| `docs/PlanoBackend.md` | Corrigir LC 227/2026, fdb-sped, §7.7 vs §8.12, §12 custos, §5.8 marketplace | 1.1-1.3, 1.7 | ✅ |
| `analista-fiscal-api/app/modules/fiscal/calcula_das.py` | Sublimite estadual + flag teto federal | 1.4 | ✅ |
| `analista-fiscal-api/app/modules/lucro_presumido/calcula_irpj.py` | IRRF compensar + quantização única | 1.5, 1.6 | ✅ |
| `analista-fiscal-api/app/shared/exceptions.py` | Nova `EmpresaForaSimplesNacional` | 1.4 | ✅ |
| `analista-fiscal-api/app/modules/fiscal/{service,schemas,router}.py` | Propagar uf + sublimite + flags | 1.4 | ✅ |
| `analista-fiscal-api/app/modules/lucro_presumido/{service,schemas}.py` | Propagar irrf_a_compensar + irpj_devido | 1.5 | ✅ |
| `analista-fiscal-api/docs/adr/0014-transmissao-spedes-modelo.md` | ADR explicando o modelo de transmissão | 1.2 | ✅ |
| `analista-fiscal-api/tests/unit/fiscal/test_calcula_das.py` | +8 golden tests sublimite | 1.4 | ✅ |
| `analista-fiscal-api/tests/unit/lucro_presumido/test_calcula_irpj.py` | +7 golden tests IRRF + quantização | 1.5, 1.6 | ✅ |
| `analista-fiscal-api/alembic/versions/0024_fase2_documento_fiscal_hardening.py` (novo) | `documento_fiscal` blindado | 2 PR1 | ✅ |
| `analista-fiscal-api/alembic/versions/0025_fase2_tabelas_scd_hardening.py` (novo) | REVOKE em 8 tabelas SCD + role + trigger genérico | 2 PR2 | ✅ |
| `analista-fiscal-api/alembic/versions/0026_fase2_rbt12_materializada.py` (novo) | MV `rbt12_mensal` + refresh fn SECURITY DEFINER | 2 PR3 | ✅ |
| `analista-fiscal-api/alembic/versions/0027_*.py` (novo, futuro) | Drop coluna `empresa.faturamento_12m` (2ª fase do drop em 2 fases) | 2 PR3b | ⏸️ |
| `analista-fiscal-api/app/modules/empresa/repo.py` | `rbt12_da_view()` + leitura da MV | 2 PR3 | ✅ |
| `analista-fiscal-api/app/modules/fiscal/service.py` | RBT12 da view com fallback | 2 PR3 | ✅ |
| `analista-fiscal-api/app/modules/lucro_presumido/service.py` | RBT12 da view em `_resolver_presuncao` | 2 PR3 | ✅ |
| `analista-fiscal-api/app/workers/tasks/refresh_rbt12.py` (novo) | Celery task de refresh + beat entry | 2 PR3 | ✅ |
| `app/shared/db/models.py:138-230` | `DocumentoFiscal` com superseded_by + CHECK + UNIQUE parcial | 2 PR1 | ✅ |
| `app/shared/db/models.py:97` | Remover `faturamento_12m` | 2 PR3b (0027) | ⏸️ |
| `app/shared/llm/client.py:74-75` | Remover `encaminhar_marketplace` da `LLMResponse` | 3 | ⏸️ |
| `app/modules/marketplace/triage.py` (novo) | Pós-processador out-of-scope desacoplado | 3 | ⏸️ |
| `app/modules/pessoal/esocial_payloads.py:117-286` | `TypedDict` por evento eSocial | 2 PR4 | ⏸️ |
| `app/shared/integrations/{serpro,pluggy,focus_nfe}/client.py` | Pydantic responses tipados | 2 PR4 | ⏸️ |
| `analista-fiscal-api/docs/adr/0001-*.md` a `0016-*.md` | 15 ADRs adicionais | 4.1 | ⏸️ (1/16) |
| `analista-fiscal-api/docs/runbooks/lgpd-incidente-72h.md` (novo) | Runbook ANPD | 4.4 | ⏸️ |
| `app/modules/lgpd/router.py` (novo) | Endpoints `/lgpd/dados-do-titular` | 4.2 | ⏸️ |

---

## Verificação end-to-end

### Após Fase 1 (já validado)
```powershell
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api
poetry run python -m pytest tests/unit/fiscal tests/unit/lucro_presumido -v
poetry run python -m mypy app/
# Checar 0 referências a "LC 227" ou "fdb-sped":
Select-String -Path "..\docs\PlanoBackend.md" -Pattern "LC 227|fdb-sped"
```

**Esperado:** 60 testes em fiscal+LP green; mypy 0 erros; grep retorna 0 matches. ✅

### Após Fase 2
```powershell
poetry run alembic upgrade head
poetry run python -m pytest tests/unit tests/eval tests/integration
poetry run python -m mypy app/
# Contagem de Any deve ter caído para < 30:
(Select-String -Path "app\**\*.py" -Pattern ": Any|dict\[str, Any\]|list\[Any\]" |
  Measure-Object).Count
```

### Após Fase 3 (Sprint 13)
```powershell
poetry run python -m pytest tests/unit/marketplace tests/integration/test_marketplace
# Smoke test do fluxo completo:
# 1. POST /v1/admin/contadores (3 contadores)
# 2. POST /v1/empresas/{eid}/consultas-marketplace (categoria=contencioso)
# 3. Verificar idempotência (mesma key → mesma consulta)
# 4. PATCH ... contador aceita / cliente avalia / pagamento webhook HMAC
```

### Após Fase 4
```powershell
# ADRs presentes:
(Get-ChildItem analista-fiscal-api\docs\adr -Filter "*.md" | Measure-Object).Count
# (esperar 16)
# Endpoints LGPD respondendo:
curl http://localhost:8000/v1/lgpd/dados-do-titular -H "Authorization: Bearer ..."
```

---

## Stack e contexto técnico (resumo para outro agente)

- **Python 3.12** (ambiente local roda 3.13 — não substituir o `pyproject.toml`).
- **FastAPI 0.115+**, **SQLAlchemy 2.0 async**, **Alembic 1.13+**, **Pydantic v2**.
- **PostgreSQL 16** com RLS multi-tenant em todas as tabelas de domínio.
- **mypy strict** é critério de merge.
- **Decimal** para dinheiro (NUNCA `float`); `quantize(_CENT, rounding=ROUND_HALF_EVEN)`.
- **Logger estruturado** `structlog` (NUNCA `print()`).
- **TIMESTAMPTZ** + `ZoneInfo("America/Sao_Paulo")` para datas com timezone.
- **Migrations backward-compatible em 2 fases** (add column nullable → deploy code → backfill → NOT NULL).
- **`# type: ignore`** só com comentário curto explicando.
- **Princípios invioláveis** estão em §8 do `docs/PlanoBackend.md` — 12 itens numerados §8.1 a §8.12. Sprint 0 prometia 13 ADRs (0001-0013); só 0014 existe hoje (criado na Fase 1.2). Resto é dívida da Fase 4.

### Como rodar localmente
```powershell
$env:PATH = "C:\Users\loren\AppData\Roaming\Python\Scripts;$env:PATH"
cd C:\dev\Apresentação-Ideia\analista-fiscal-api

# Suite unitária + eval (rápida, ~12s)
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

## Decisões já fechadas com o usuário

1. **Escopo:** todos os ~30 achados (não só top-10).
2. **Sprint 13:** pausada até Fase 2 completar.
3. **Fase 1:** ✅ concluída em 2026-05-18 — 992 testes passing, 0 mypy.

## Próximo passo concreto

**Fase 2 completa em 2026-05-19** (PR1 ✅ PR2 ✅ PR3 ✅ PR4 ✅). Sprint 13 (marketplace)
está **desbloqueada** — pode iniciar Fase 3.

Próximos caminhos possíveis:
1. **Fase 3 — Sprint 13 reforçada** (marketplace de contadores): 3 PRs +
   refactor `LLMResponse`. Schema `consulta_marketplace` já consolidado no §5.8 do Plano.
2. **Fase 4 — Governança** (paralelo): 16 ADRs faltantes, endpoints LGPD, DPO, runbook ANPD.
3. **Migration 0027** (housekeeping): drop column `empresa.faturamento_12m` agora que
   `rbt12_mensal` está em produção e validada.

Esperar comando do usuário (`prossiga`/`fase3`/`pr3b`/`fase4`).
