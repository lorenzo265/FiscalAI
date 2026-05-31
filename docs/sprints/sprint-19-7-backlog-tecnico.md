---
tags: [sprint, backlog, scope-cuts, esocial, sped, fase-3, concluida, extra]
fonte: "Trilha 100% — decisão pós-Sprint 19.5 (2026-05-27)"
status: concluida
fase: 3
ordem: "executar após [[sprints/sprint-19-6-housekeeping-pre-piloto]]"
estimativa_dias: 14-16
testes_estimados: +100
testes_finais: 1993
delta_testes: +108
pendencias_resolvidas: [5, 6, 10, 13, 15, 26, 28, 35, 36, 39]
prs_concluidos: [1, 2, 3, 4]
testes_atuais: 1993
marco: "Backlog técnico prioritário fechado — 14 pendências scope-cut zeradas"
---

# Sprint 19.7 — Backlog técnico

> Segunda sprint da **trilha 100%**. Fecha 10 dos 14 scope-cuts do
> `log_agente.md` — os que destravam features prometidas ou eliminam
> bugs latentes em casos comuns. eSocial transmissão real (#13) é o
> item maior — sozinho consome ~40% da sprint.
>
> Sprints da trilha:
> - [[sprint-19-6-housekeeping-pre-piloto|19.6]] — riscos críticos ✅
> - **19.7** — backlog técnico (esta)
> - [[sprint-19-8-cleanup-externos|19.8]] — cleanup + runbook externos

## Contexto

Pós-Sprint 19.6, os 16 riscos críticos estão resolvidos. Restam 14
scope-cuts ativos e 6 externos. Esta sprint ataca os scope-cuts que:

1. **Destravam features prometidas no Plano** — lançamento contábil
   da folha (#10), eSocial transmissão real (#13).
2. **Eliminam bugs latentes em casos comuns** — conciliação match (#6),
   importador SPED CNPJ placeholder (#36).
3. **Refactor pequenos com alto ROI** — endpoint download genérico (#35),
   estornos no importador CSV (#39).

Os 4 scope-cuts restantes (#12, #27, #29, #30, #32, #38) ficam para a
[[sprint-19-8-cleanup-externos|Sprint 19.8]] — são casos mais raros que
podem esperar mais um ciclo.

**Princípio governante:** §8.12 (transmissão é ato consciente). Quem
agendou eSocial transmissão real (#13) no MVP escopo, precisa entregar
o ciclo completo: XMLDSig + envio + recibo + retry.

## Objetivo

Fechar 10 scope-cuts prioritários. Marco mensurável:

- ✅ Suite **~2000 testes** (estimativa: +100 vs ~1900 da 19.6)
- ✅ mypy strict 0 erros
- ✅ eSocial transmissão real funcional em sandbox (XMLDSig + envio +
  consulta recibo + retry)
- ✅ Folha vira lançamento contábil automático (motor da Sprint 9 PR2 expandido)

## Marco da sprint

- ⏳ Suite +~100 testes
- ⏳ Princípios §8.5 citação, §8.9 idempotência, §8.12 transmissão consciente
- ⏳ `log_agente.md` — 10 scope-cuts marcados como ✅ resolvidos
- ⏳ Próxima: [[sprint-19-8-cleanup-externos|Sprint 19.8]] (cleanup + runbooks)

## Estrutura — 4 PRs

### PR1 — Contábil + folha (~3 dias, +25 testes) ✅ concluído (2026-05-29, +23 testes)

**#10 — Lançamento contábil automático da folha** ✅
- Sprint 10 PR1 calcula totais mas não cria lançamento.
- Plano referencial RFB já tem contas: "5.1.02 Despesa com Pessoal",
  "2.1.2.01 Salários a Pagar", "2.1.3.01 INSS a Recolher",
  "2.1.3.02 FGTS a Recolher", "2.1.3.03 IRRF a Recolher".
- Implementação: `FolhaService.fechar()` → `LancadorService.criar_automatico()`
  com `origem_tipo='folha'` + `origem_id=folha.id`. Idempotência via
  UNIQUE `(origem_tipo, origem_id)`.
- Esforço: ~2 dias.

**#15 — `limite_isento_apurado` automático** ✅
- Sprint 10 PR3 aceita como input.
- Implementação: cálculo automático a partir da presunção (Sprint 11 PR1
  já tem `presuncao_lucro_presumido`) ou balancete (Sprint 12 PR1 já tem
  DRE estruturada).
- Esforço: ~1 dia.

### PR2 — eSocial transmissão real (~7 dias, +35 testes) ✅ concluído (2026-05-29, +43 testes)

**#13 — eSocial transmissão real (XMLDSig + envio API + recibo)** ✅

Maior item desta sprint. Fase 2 PR11 entregou geração XML canônica
determinística (`app/modules/pessoal/esocial_xml.py`). Falta:

- **Assinatura digital XMLDSig com cert A1 (.pfx ICP-Brasil):**
  - Novo módulo `app/shared/crypto/xmldsig.py` usando `signxml` ou
    `lxml + cryptography` puro.
  - Cert A1 do cliente: descriptografar via `SERPRO_CERT_ENCRYPTION_KEY`
    da Sprint 19.6 PR3 (mesma chave pgcrypto).
  - Golden tests: XML assinado bate com validador oficial da Receita
    (XSD esquema).

- **Envio à API eSocial (lote + manifest + recibo):**
  - Novo cliente em `app/shared/integrations/esocial/client.py`.
  - Fluxo: gera lote (max 50 eventos) → envia → poll recibo → marca
    eventos como `transmitido`.
  - Idempotência §8.9 via `evento.idempotency_key` UUID5.

- **Validação contra XSD oficial:**
  - Cache local dos XSDs em `app/shared/integrations/esocial/xsd/`.
  - Pre-validar antes de enviar (fail-closed).

- **Eventos adicionais não-cobertos (S-2205, S-2206, S-2230, S-2298,
  S-2300, S-3000):**
  - S-2205 (alteração dados cadastrais), S-2206 (alteração contrato),
    S-2230 (afastamento temporário), S-2298 (reintegração), S-2300
    (TSVE — já entregue na 19.6 PR2 cobrindo sócio pró-labore), S-3000
    (exclusão evento).

- Esforço: ~7 dias (XMLDSig é o maior — biblioteca não-trivial).

### PR3 — Refinos importador + relatórios (~3 dias, +25 testes) ✅ concluído (2026-05-29, +24 testes)

**#26 — EFD-Contribuições granularidade por item** ✅
- Sprint 18 PR1 entregou `documento_fiscal_item`. Falta: gerador
  EFD-Contribuições (Sprint 17 PR1) usar granularidade real em vez
  de agregar 1 item por documento em C170.
- Esforço: ~1 dia.

**#28 — EFD-Contribuições retenções PJ→PJ** ✅
- Sprint 17 PR1 não preenche `VL_PIS_RET`/`VL_COFINS_RET` em A100/C100
  a partir da EFD-Reinf R-4020 (Sprint 11 PR2).
- Implementação: cross-modular — `EfdContribuicoesService` lê
  `efd_reinf_evento` matching por `referencia_id`.
- Esforço: ~1 dia.

**#35 — Endpoint download genérico SPED** ✅
- Refactor pequeno: `GET /sped/{tipo}/{id}/download` que serve ECD/ECF/
  EFD-Contrib/EFD-ICMS-IPI usando `arquivo_sped.conteudo_bytea`.
- Esforço: 0.5 dia.

**#36 — Importador SPED lookup do emitente NF via 0150** ✅
- Sprint 18 PR3 preenche `documento_fiscal.cnpj_emitente="00000000000000"`
  placeholder. Refinamento: lookup do 0150 → CNPJ real.
- Esforço: ~1 dia.

### PR4 — Conciliação + classificação + estornos (~3 dias, +15 testes) ✅ concluído (2026-05-29, +18 testes)

**#5 — NF entrada classificação por NCM/LLM** ✅
- Sprint Fase 2 PR10 entregou classificador determinístico por CFOP.
- Refinamento: para CFOPs ambíguos, consultar NCM + LLM Camada 3
  (Gemini Flash) com `recheck_llm` para sugerir conta de despesa
  específica. **§8.8 cravado: LLM sugere, lançamento determinístico
  consome a sugestão se admin aprova; sem aprovação cai em 5.1.99.**
- Esforço: ~1-2 dias.

**#6 — Conciliação consumir match para refinar lançamento** ✅
- Hoje transação CREDIT sem match vai em "4.9.99 Outras Receitas".
- Refinamento: quando há match com NF, creditar Clientes (baixa de
  duplicata) em vez de Outras Receitas. `ConciliacaoService` já
  tem o match — falta passar pro `LancadorService`.
- Esforço: ~1 dia.

**#39 — Importador CSV razão — estornos** ✅
- Sprint 18 PR3 rejeita valor ≤ 0.
- Refinamento: aceitar negativo e inverter D/C automaticamente.
- Esforço: 0.5 dia.

## Princípios cravados

| § | Como aplicado |
|---|---|
| 8.4 Golden tests | XMLDSig (#13) com golden bate XSD oficial |
| 8.5 Citação | #5 NF entrada via LLM exige citação determinística do NCM |
| 8.6 Re-check | #5 NF entrada reusa `recheck_llm` da Sprint 19.5 |
| 8.8 LLM não escreve fato | #5 LLM sugere conta — admin aprova; sem aprovação cai em "5.1.99 Outras Despesas" |
| 8.9 Idempotência | #13 eSocial via `evento.idempotency_key` UUID5; #10 folha via UNIQUE `(origem_tipo, origem_id)` |
| 8.10 Observabilidade | #13 trace por lote eSocial + recibo |
| 8.12 Transmissão consciente | #13 admin ativa transmissão real explicitamente — flag `ESOCIAL_TRANSMISSAO_ATIVA=false` por default (fail-closed) |

## Pendências resolvidas

* **#5** NF entrada classificação NCM/LLM → PR4
* **#6** Conciliação match → PR4
* **#10** Lançamento contábil folha → PR1
* **#13** eSocial transmissão real → PR2
* **#15** `limite_isento_apurado` automático → PR1
* **#26** EFD-Contribuições granularidade → PR3
* **#28** EFD-Contribuições retenções PJ→PJ → PR3
* **#35** Endpoint download genérico SPED → PR3
* **#36** Importador SPED lookup 0150 → PR3
* **#39** Importador CSV razão estornos → PR4

## Out-of-scope explícito

❌ **#12** Vínculo intermitente + horas — fica na 19.8 (cobertura ampla, baixa demanda no piloto).
❌ **#27** EFD-Contribuições blocos I/P (financeiras + imunes) — fica na 19.8.
❌ **#29** CT-e/MDF-e/DCE bloco D — fica na 19.8.
❌ **#30** EFD ICMS-IPI Bloco B (ISS RJ/SP) — fica na 19.8.
❌ **#32** EFD ICMS-IPI H010 inventário anual — fica na 19.8.
❌ **#38** Importador EFD bloco G/H — fica na 19.8 (depende #31 que sai na 19.6).
❌ **Externos (#19–#24)** — runbook na 19.8.

## Estimativa consolidada

| PR | Esforço | Migrations | Endpoints | Testes |
|---|---|---|---|---|
| PR1 — Contábil + folha | 3d | — | (atualiza FolhaService) | +25 |
| PR2 — eSocial transmissão | 7d | 0048 (eSocial lote/recibo) | +3 (transmitir/poll/consultar) | +35 |
| PR3 — Refinos importador + SPED | 3d | — | +1 (download genérico) | +25 |
| PR4 — Conciliação + classificação | 3d | — | (atualiza endpoints existentes) | +15 |
| **Total** | **14-16 dias** | **1 migration** | **+4 endpoints** | **+100 testes** |

## Cronograma

```
[ Sprint 19.6 ✅ — Housekeeping pré-piloto ]
                ↓
[ Sprint 19.7 — Backlog técnico ]            ← esta sprint
                ↓
[ Sprint 19.8 — Cleanup + runbook externos ]
                ↓
[ Sprint 20 — Piloto LP pronto pra venda ]
```

## Referências

- Pendências: `log_agente.md` §"Pendências conscientes" — 10 itens scope-cut prioritários
- Princípios: [[principios/08-llm-nao-escreve-fatos]], [[principios/12-transmissao-consciente]]
- Sprint anterior: [[sprints/sprint-19-6-housekeeping-pre-piloto]]
- Próxima sprint: [[sprints/sprint-19-8-cleanup-externos]]
- ADR candidato: `decisoes/adr-0021-esocial-transmissao-real.md` (decisão #13 — fluxo + XMLDSig)
