---
tags: [sprint, migracao, importador, sped, ecd, ecf, efd, csv, fase-3, concluida]
fonte: "[[PlanoBackend]] §11 Sprint 18"
status: concluida
fase: 3
marco: "Fase 3 em andamento (S14 → S20: 200 pagantes + MRR R$40k+)"
testes_final: 1698
concluida_em: 2026-05-25
---

# Sprint 18 — Migração de escritório antigo

> Quarta sprint da Fase 3 (após [[sprints/sprint-15-advisor]] e
> [[sprints/sprint-16-sped]] / [[sprints/sprint-17-efd]]). Habilita
> onboarding de PMEs trazidas de outro escritório contábil, importando
> 12 meses de histórico SPED + fallback CSV.

## Objetivo

Sem importador histórico, o vendedor não consegue mostrar dashboard cheio no
dia 1 e o piloto pago da Sprint 20 (10 empresas LP pronto-pra-venda) trava.
A Sprint 18 entrega **importador inverso** dos geradores SPED das Sprints
16–17 (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI) + importador de planilha
CSV (balancete + razão) para escritórios sem SPED completo.

## Marco da sprint

- ✅ Suite **1698 testes** passando (1604 baseline + 94 desta sprint), 2 skipped
- ✅ mypy strict 0 erros em 308 arquivos
- ✅ Princípios §8.1, §8.2, §8.4, §8.6, §8.8, §8.9, §8.10, §8.12 cravados
- ✅ 2 pendências históricas resolvidas: #8 (reabertura janeiro) + #26 (granularidade NF)
- ✅ Sprint 18 fechada. Próxima: [[sprints/sprint-19-performance]]

## Decisão de design

**ECD** (lançamentos contábeis) entra **completa** no nosso motor — cada
``LancamentoEcdParseado`` vira ``LancamentoCandidato`` com
`origem_tipo='importacao'` e é persistido via ``LancadorService._persistir``
reusado da Sprint 9 PR2 (idempotente via UNIQUE parcial em
`(origem_tipo, origem_id)`).

**ECF, EFD-Contribuições (M200/M600) e EFD ICMS-IPI (E110)** ficam como
**snapshot read-only** em ``lote_importacao.resumo_jsonb`` — não recriamos
apurações declaradas pelo escritório antigo. O front compara
"declarado × recalculado por nós" depois que rodarmos nossas próprias
apurações (Sprint 11) em cima dos lançamentos importados.

**Documentos fiscais** (C100/C170 + A100/A170) viram ``documento_fiscal``
+ ``documento_fiscal_item`` (granularidade da Sprint 18 PR1). Cross-check
por chave NF: se a NF já foi ingerida via XML pela Sprint 2 (`uq_doc_empresa_chave_vigente`),
não duplica — registra warning no lote.

**CSV** é fallback — escritórios sem SPED completo. Balancete vira snapshot;
razão gera ``LancamentoCandidato``. Encoding UTF-8 ou Latin-1 com BOM
(Excel BR); separador `;` ou `,` detectado por sniffer; decimal vírgula
ou ponto.

## PRs

### PR1 — Fundação (2026-05-25, [[../log_agente#sprint-18-pr1]])
- Migration 0040: `documento_fiscal_item` + `lote_importacao` +
  estende `ck_lanc_origem_tipo` com `'importacao'`.
- Parser NF-e estendido (`NFeData.itens` com `<det>` granular).
- `IngestaoService` persiste itens em batch via cascade.
- `EncerramentoService.abrir_exercicio(ano)` (pendência #8 resolvida).
- Endpoint `POST /v1/empresas/{eid}/contabil/exercicio/{ano}/abrir`.
- Suite +13 = 1617.

### PR2 — Importador SPED contábil (2026-05-25)
- Módulo novo `app/modules/migracao/`.
- `parser_ecd.py` (`migracao.ecd.v1`) — round-trip do gerador Sprint 16 PR1.
- `parser_ecf.py` (`migracao.ecf.v1`) — snapshot LP (P200/P300 trimestral).
- `MigracaoService.importar_sped_ecd/ecf` com hash SHA-256 idempotente,
  validação CNPJ/período, lookup conta com cache anti-N+1, integração com
  `LancadorService._persistir`.
- 4 endpoints REST (`upload ECD`, `upload ECF`, `lote/{id}`, `lotes`).
- 4 exceções: `SpedInvalido`, `EmpresaCnpjDivergente`,
  `PeriodoForaCobertura`, `VigenciaScdAusente`.
- Suite +27 = 1644.

### PR3 — Importador SPED fiscal + CSV + docs (2026-05-25)
- `parser_efd_contribuicoes.py` + `parser_efd_icms_ipi.py` — round-trip dos
  geradores Sprint 17. Cria `documento_fiscal` + `documento_fiscal_item`
  granular agora que PR1 entregou a tabela. Cross-check chave NF-e.
- `parser_csv.py` — balancete (snapshot) + razão (lançamentos), Pydantic v2
  validando cada linha, detecção de chave NF-e 44 dígitos no histórico.
- `MigracaoService` ganha 4 métodos novos: `importar_sped_efd_contribuicoes`,
  `importar_sped_efd_icms_ipi`, `importar_csv_balancete`, `importar_csv_razao`.
- 4 endpoints REST novos.
- Runbook `migracao-escritorio-antigo.md`.
- Notas Obsidian (esta + `modulos/migracao.md`).
- Suite +27 → ~1671 (+ ajustes finais → 1698).

## Princípios cravados

| § | Como aplicado |
|---|---|
| 8.1 RLS multi-tenant | Tabelas novas (`documento_fiscal_item`, `lote_importacao`) com RLS + policy de tenant; sessão de upload faz `SET LOCAL app.tenant_id` antes de qualquer operação |
| 8.2 Fatos imutáveis | `arquivo_sped` importado herda `supersedes`/`superseded_by`; reimport de hash diferente marca anterior como superseded; cross-check de chave NF-e impede duplicar `documento_fiscal` |
| 8.4 Golden tests | Round-trip `gerar_XXX → parse_XXX` valida cada parser (ECD, ECF, EFD-Contribuições, EFD ICMS-IPI); fixtures CSV inline |
| 8.6 Re-check determinístico | Validação CNPJ contra `Empresa.cnpj`, 9999 contra total real, débitos==créditos por lançamento ECD, conta em I250 ∈ I050 |
| 8.8 LLM nunca escreve fatos | 100% determinístico — split, Decimal, regex, Pydantic |
| 8.9 Idempotência | Hash SHA-256 → `lote_importacao` único por `(empresa, hash)`; `origem_id = uuid5(arquivo_sped + lançamento)` no `lancamento_contabil`; UNIQUE parcial `uq_doc_empresa_chave_vigente` |
| 8.10 Observabilidade | `migracao.lote.iniciado/concluido/reaproveitado` em structlog com contagens |
| 8.12 Transmissão é ato consciente | Importador NÃO transmite nada — apenas reconstrói o histórico já transmitido pelo escritório antigo |

## Out-of-scope (pendências para próxima sprint)

- **Bloco G/H/Y do SPED** — EFD ICMS-IPI sem CIAP (G), inventário (H), nem
  Y540 detalhado. Importação fica em ([[pendencias/efd-bloco-g-h]] futuro).
- **Lookup do emitente NF via 0150** — hoje usamos `cnpj_emitente="00000000000000"`
  placeholder. Em PR de seguimento, casamos `COD_PART` em C100 com o
  registro `0150` para extrair CNPJ real do participante.
- **Workers Celery beat para importação em background** — uploads grandes
  (>50MB) ficam síncronos por enquanto. Ativar quando pendência #1
  (Celery instalado) sair.
- **Migration 0041 com seed retroativo INSS 2024** — Sprint 18 PR2 valida
  período ≥ 2024-01-01, mas tabela INSS só tem vigência a partir de
  2025-01-01. Se cliente importar folha 2024, cálculo será errado.
  Resolução: PR pequeno seedando Portaria MPS/MF 2024.

## Referências cruzadas

- Plano: [[PlanoBackend]] §11 Sprint 18
- Princípios: [[principios/02-fatos-imutaveis]], [[principios/09-idempotencia]]
- ADRs relevantes: [[decisoes/adr-001-postgres-rls]]
- Módulo: [[modulos/migracao]]
- Runbook: [[runbooks/migracao-escritorio-antigo]]
- Pendências resolvidas: [[pendencias/abertura-exercicio-janeiro]] (#8), [[pendencias/granularidade-item-nfe]] (#26)
