---
tags: [sprint, cleanup, runbook, externos, fase-3, concluida, extra, fechamento]
fonte: "Trilha 100% — decisão pós-Sprint 19.5 (2026-05-27)"
status: concluida
fase: 3
testes_finais: 2012
delta_testes: +19
prs_concluidos: [1]
ordem: "executar após [[sprints/sprint-19-7-backlog-tecnico]]"
estimativa_dias: 10-12
testes_estimados: +60
pendencias_resolvidas: [12, 27, 29, 30, 32, 38]
pendencias_documentadas_como_externas: [19, 20, 21, 22, 23, 24]
marco: "100% das pendências conscientes fechadas ou documentadas como aguardando terceiro"
---

# Sprint 19.8 — Cleanup + runbook externos

> Terceira e última sprint da **trilha 100%**. Fecha os 6 scope-cuts
> restantes e transforma os 6 itens `[externo]` em runbooks de ativação
> documentados. Ao final desta sprint, **nenhuma pendência consciente
> está ativa sem trabalho técnico programado ou gate externo
> documentado**.
>
> Sprints da trilha:
> - [[sprint-19-6-housekeeping-pre-piloto|19.6]] — riscos críticos ✅
> - [[sprint-19-7-backlog-tecnico|19.7]] — backlog técnico ✅
> - **19.8** — cleanup + runbook externos (esta) → marco "100% fechado"

## Contexto

Pós-Sprint 19.7, restam:

- **6 scope-cuts técnicos** — casos mais raros ou que dependem de
  outras pendências já fechadas: #12 (folha intermitente), #27
  (EFD-Contribuições I/P), #29 (CT-e/MDF-e/DCE), #30 (EFD ICMS-IPI
  Bloco B/ISS), #32 (H010 inventário), #38 (Importador EFD G/H).
- **6 externos** — dependem de RFB / Comitê Gestor IBS / Focus
  publicarem regulamentação ou leiautes. Não vale "implementar agora
  e esperar" — vira código morto. Vira runbook: "quando X publicar,
  fazer Y" com checklist de PR pequeno.

**Princípio governante:** §8.11 (out-of-scope é declarado, não improvisado).
Cada externo tem uma rota explícita de ativação.

## Objetivo

Fechar 100% das pendências conscientes ativas. Marco mensurável:

- ✅ Suite **~2060 testes** (estimativa: +60 vs ~2000 da 19.7)
- ✅ mypy strict 0 erros
- ✅ 6 scope-cuts restantes fechados
- ✅ `docs/pendencias/runbook-ativacao-externos.md` criado com 6 entradas
- ✅ `log_agente.md` §"Pendências conscientes" — todas marcadas ✅ resolvidas
  OR ⏳ aguardando externo + link pro runbook
- ✅ **Marco "FiscalAI Backend pronto pra escala"** — green light pra Fase 4

## Marco da sprint

- ⏳ Suite +~60 testes
- ⏳ Princípios §8.11 out-of-scope, §8.12 transmissão consciente
- ⏳ Nenhuma pendência consciente ativa sem rota documentada
- ⏳ Próxima: [[sprints/sprint-20-piloto-lp|Sprint 20 — piloto LP]] (marco Fase 3)

## Estrutura — 3 PRs

### PR1 — Scope-cuts folha + EFD (~5 dias, +30 testes)

**#12 — Vínculo intermitente + horas trabalhadas**
- Sprint 10 PR1 só calcula salário fixo.
- Implementação: `EventoFolha` aceita `tipo='hora_extra'`/`adicional_noturno'`/
  `falta'` com `horas_quantidade` + `multiplicador` (1.5 hora extra 50%,
  2.0 100%, etc.).
- Esforço: ~2 dias.

**#27 — EFD-Contribuições blocos I e P**
- Bloco I: instituições financeiras (fora do nicho PME). Bloco P: PIS sobre
  folha (entidades imunes/isentas R$10k/mês).
- Implementação: blocos podem ser stubs simples (`IND_MOV='1'` vazio) com
  flag opt-in `EFD_CONTRIB_INCLUIR_BLOCO_I=false` / `_P=false` quando
  primeiro cliente do perfil aparecer. Documentar como entrar.
- Esforço: ~1 dia.

**#29 — CT-e/MDF-e/DCE no bloco D EFD**
- Sprint 17 deixa bloco D vazio.
- Implementação: parser CT-e (modelo 57) + MDF-e (modelo 58) + DCE (modelo
  65/68 conforme caso) + geração bloco D em ambos EFDs.
- Esforço: ~2 dias.

### PR2 — Scope-cuts SPED (~3 dias, +20 testes)

**#30 — EFD ICMS-IPI Bloco B (ISS RJ/SP)**
- Só RJ e SP exigem ISS escriturado dentro do EFD ICMS-IPI.
- Implementação: bloco B0/B100/B470 com ISS apurado + retenções.
- Esforço: ~1 dia.

**#32 — EFD ICMS-IPI H010 inventário anual**
- H010 = escrituração 31/12 com saldos por item.
- Implementação: relacionar `documento_fiscal_item` (Sprint 18 PR1) +
  estoque (depende de existência de módulo de estoque — sprint dedicada
  futura se não existir, ou stub bloco vazio com aviso).
- **Nota**: se módulo de estoque ainda não existir, gerar bloco vazio
  com `IND_MOV='1'` + warning estruturado.
- Esforço: ~1 dia.

**#38 — Importador EFD Bloco G/H**
- Depende de #31 (CIAP) e #32 (inventário) — ambas resolvidas em sprints
  anteriores. Aqui é só reverter o gerador (parser).
- Esforço: ~1 dia.

### PR3 — Runbooks externos (~2 dias, +10 testes)

Cria `docs/pendencias/runbook-ativacao-externos.md` documentando como
ativar cada externo quando o gate destravar. Para cada um: trigger,
trabalho técnico (estimativa), arquivos a alterar, testes a adicionar.

**#19 — Focus NFe CBS/IBS em NFS-e**
- Trigger: Focus documenta API CBS/IBS para todos os municípios.
- Trabalho: flip `FOCUS_NFSE_ENVIA_CBS_IBS=true` em `app/config.py`;
  ajustar `app/modules/notas/service.py` para preencher campos `vCBS`,
  `vIBS`, `cClassTrib` no payload Focus.
- Esforço esperado: ~1-2 dias quando ativar.

**#20 — Alíquotas IBS por UF/município**
- Trigger: Comitê Gestor IBS publica percentuais por UF/município.
- Trabalho: migration aditiva em `aliquota_cbs_ibs` (adicionar `uf
  VARCHAR(2)` + `municipio_ibge VARCHAR(7)`). `AliquotaCbsIbsRepo.
  _especificidade` (Sprint 14 PR1) já aceita mais um nível de score
  — só precisa do dado.
- Esforço esperado: ~1 dia + seed via painel admin (Sprint 19.5).

**#21 — Imposto Seletivo (IS)**
- Trigger: LC 214/2025 art. 9º §6º regulamentado.
- Trabalho: novo módulo `app/modules/imposto_seletivo/` (escopo de Fase 5
  do PlanoBackend).
- Esforço esperado: ~5-7 dias (módulo novo).

**#22 — Split payment real 2027**
- Trigger: BCB + PSPs (Stripe, Pagar.me, etc.) publicam fluxo.
- Trabalho: integração com PSPs para retenção na transação (Pix/cartão).
- Esforço esperado: ~7-10 dias (integração com PSPs é não-trivial).

**#23 — Bloco K SPED com CBS/IBS**
- Trigger: cliente industrial aparece no marketplace ou piloto.
- Trabalho: bloco K (controle de produção/estoque) + cálculo CBS/IBS
  por produto/item (não-agregado).
- Esforço esperado: ~5-7 dias (Fase 5 backlog).

**#24 — NFC-e/CT-e/MDF-e com CBS/IBS**
- Trigger: RFB publica leiautes finais para documentos não-NF-e.
- Trabalho: parser CBS/IBS por linha em NFC-e (modelo 65), CT-e (modelo
  57), MDF-e (modelo 58) — depende de #29.
- Esforço esperado: ~3-4 dias.

**Atualização do `log_agente.md`:**

Cada item externo passa de `[externo]` para `[externo-runbook]` linkando
pro `runbook-ativacao-externos.md` específico.

## Princípios cravados

| § | Como aplicado |
|---|---|
| 8.11 Out-of-scope declarado | Runbooks dos 6 externos documentam trigger + trabalho exato |
| 8.12 Transmissão consciente | #29 CT-e/MDF-e/DCE EFDs respeitam padrão "transmissão é ato cliente" |

## Pendências resolvidas

* **#12** Vínculo intermitente + horas → PR1
* **#27** EFD-Contribuições blocos I/P → PR1 (stubs com flag opt-in)
* **#29** CT-e/MDF-e/DCE bloco D → PR1
* **#30** EFD ICMS-IPI Bloco B (ISS RJ/SP) → PR2
* **#32** EFD ICMS-IPI H010 inventário → PR2
* **#38** Importador EFD bloco G/H → PR2

## Pendências documentadas como externas

* **#19** Focus NFe CBS/IBS → `runbook-ativacao-externos.md#19`
* **#20** Alíquotas IBS por UF/município → `runbook-ativacao-externos.md#20`
* **#21** Imposto Seletivo (IS) → `runbook-ativacao-externos.md#21`
* **#22** Split payment 2027 → `runbook-ativacao-externos.md#22`
* **#23** Bloco K SPED com CBS/IBS → `runbook-ativacao-externos.md#23`
* **#24** NFC-e/CT-e/MDF-e com CBS/IBS → `runbook-ativacao-externos.md#24`

## Estimativa consolidada

| PR | Esforço | Migrations | Endpoints | Testes |
|---|---|---|---|---|
| PR1 — Scope-cuts folha + EFD | 5d | 0049 (EventoFolha tipos) | (atualiza existentes) | +30 |
| PR2 — Scope-cuts SPED | 3d | — | (atualiza gerador) | +20 |
| PR3 — Runbooks externos | 2d | — | — | +10 (smoke runbook) |
| **Total** | **10-12 dias** | **1 migration** | (sem endpoints novos) | **+60 testes** |

## Marco final

Ao final desta sprint, **`log_agente.md` §"Pendências conscientes"
tem 0 itens ativos sem trabalho técnico programado ou gate externo
documentado**. Stats finais previstos:

- Suite: **~2060 testes** passando
- mypy strict: 0 erros, ~360 arquivos
- Pendências: 40 → 0 ativas (todas resolvidas ou documentadas)
- Trilha 100% fechada — green light pra Fase 4 (S21 hardening + S22 docs)

**Próxima sprint:** [[sprints/sprint-20-piloto-lp|Sprint 20 — piloto LP]]
(meta Fase 3: 200 pagantes, MRR R$40k+).

## Cronograma

```
[ Sprint 19.6 ✅ — Housekeeping pré-piloto ]
                ↓
[ Sprint 19.7 ✅ — Backlog técnico ]
                ↓
[ Sprint 19.8 — Cleanup + runbook externos ] ← esta sprint (marco 100%)
                ↓
[ Sprint 20 — Piloto LP pronto pra venda ]   ← marco Fase 3
                ↓
[ Sprint 21 — Hardening + segurança ]
                ↓
[ Sprint 22 — Documentação + handover ]
```

## Referências

- Pendências: `log_agente.md` §"Pendências conscientes" — 12 itens (6 scope-cuts + 6 externos)
- Princípios: [[principios/11-out-of-scope]], [[principios/12-transmissao-consciente]]
- Sprint anterior: [[sprints/sprint-19-7-backlog-tecnico]]
- Próxima sprint: `[[sprints/sprint-20-piloto-lp]]` (nota a criar)
- Documento criado nesta sprint: `docs/pendencias/runbook-ativacao-externos.md`
