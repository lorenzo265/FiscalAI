---
tags: [modulo, migracao, importador, sped, ecd, ecf, efd, csv, fase-3]
fonte: "app/modules/migracao/"
sprint_origem: 18
status: ativo
---

# Módulo `migracao`

> Bounded context da **migração de escritório antigo** — importador SPED
> histórico (12 meses) + planilha CSV. Habilita onboarding de PME trazida
> de outro escritório com dashboard cheio no dia 1.

## Propósito

Pipeline determinístico que lê arquivos SPED/CSV entregues pelo escritório
anterior e reconstrói o grafo contábil-fiscal da empresa no nosso sistema:

* **SPED ECD** → `lancamento_contabil(origem_tipo='importacao')` completo.
* **SPED ECF** → snapshot read-only das apurações IRPJ/CSLL trimestrais.
* **SPED EFD-Contribuições** → `documento_fiscal` + `documento_fiscal_item`
  (NF-e + NFS-e) + snapshot M200/M600.
* **SPED EFD ICMS-IPI** → `documento_fiscal` + `documento_fiscal_item` + snapshot E110.
* **CSV balancete** → snapshot em `resumo_jsonb`.
* **CSV razão** → `lancamento_contabil(origem_tipo='importacao')`.

## Estrutura

```
app/modules/migracao/
├── __init__.py                   # docstring com princípios cravados
├── parser_ecd.py                 # ALGORITMO_VERSAO=migracao.ecd.v1
├── parser_ecf.py                 # ALGORITMO_VERSAO=migracao.ecf.v1
├── parser_efd_contribuicoes.py   # ALGORITMO_VERSAO=migracao.efd_contribuicoes.v1
├── parser_efd_icms_ipi.py        # ALGORITMO_VERSAO=migracao.efd_icms_ipi.v1
├── parser_csv.py                 # ALGORITMO_VERSAO=migracao.csv.v1
├── repo.py                       # LoteImportacaoRepo
├── service.py                    # MigracaoService — orquestra
├── schemas.py                    # Pydantic v2 (LoteImportacaoOut + FonteLote + StatusLote)
└── router.py                     # 8 endpoints REST
```

## Endpoints REST

| Verb | Path | Sprint |
|------|------|--------|
| POST | `/v1/empresas/{eid}/migracao/sped/ecd/upload` | 18 PR2 |
| POST | `/v1/empresas/{eid}/migracao/sped/ecf/upload` | 18 PR2 |
| POST | `/v1/empresas/{eid}/migracao/sped/efd-contribuicoes/upload` | 18 PR3 |
| POST | `/v1/empresas/{eid}/migracao/sped/efd-icms-ipi/upload` | 18 PR3 |
| POST | `/v1/empresas/{eid}/migracao/csv/balancete/upload` | 18 PR3 |
| POST | `/v1/empresas/{eid}/migracao/csv/razao/upload` | 18 PR3 |
| GET  | `/v1/empresas/{eid}/migracao/lote/{lote_id}` | 18 PR2 |
| GET  | `/v1/empresas/{eid}/migracao/lotes` | 18 PR2 |

## Modelo de dados

* **`lote_importacao`** (migration 0040) — auditoria de cada upload.
  Idempotência por hash via UNIQUE parcial
  `(empresa_id, hash_arquivo) WHERE status='concluido'`.
* **`documento_fiscal_item`** (migration 0040) — granularidade por linha
  de NF (pendência #26 resolvida).
* **`arquivo_sped`** (reusada da Sprint 16 PR1) — guarda o `.txt` SPED
  importado com `algoritmo_versao='migracao.XXX.v1'`.

## Idempotência (§8.9)

3 níveis:

1. **Nível arquivo:** hash SHA-256 → se já existe `lote_importacao` concluído
   para `(empresa, hash)`, devolve lote anterior sem reprocessar.
2. **Nível lançamento contábil:** `origem_id = uuid5(NS_MIGRACAO_LANC, arquivo_sped_id|numero)`
   + UNIQUE parcial `uq_lanc_origem` no `lancamento_contabil` (Sprint 9 PR1).
3. **Nível documento fiscal:** cross-check pela chave NF-e —
   `uq_doc_empresa_chave_vigente` impede duplicar. Quando documento já existe,
   registra warning em `lote.erros_jsonb` em vez de duplicar.

## Validações §8.6 (re-check determinístico)

* CNPJ do registro 0000 deve bater com `Empresa.cnpj` → `EmpresaCnpjDivergente` (422).
* Período ≥ 2024-01-01 → `PeriodoForaCobertura` (422 — corte arbitrário).
* 9999 do SPED deve declarar total real de linhas.
* Lançamentos ECD: débitos == créditos == valor_total declarado.
* Partidas referenciam contas existentes em I050.

## Exceções de domínio

| Classe | HTTP | Quando |
|---|---|---|
| `SpedInvalido` | 422 | Parser falhou (CNPJ inválido, 9999 ausente, débitos ≠ créditos, conta órfã) |
| `EmpresaCnpjDivergente` | 422 | CNPJ do 0000 ≠ `Empresa.cnpj` |
| `PeriodoForaCobertura` | 422 | Período do SPED anterior a 2024-01-01 |
| `VigenciaScdAusente` | 422 | Reservada — usada no futuro quando importar EFD cruzar com SCD ausente |
| `LoteImportacaoNaoEncontrado` | 404 | GET de lote inexistente / cross-empresa |

## Princípios cravados

* §8.1 RLS — toda escrita dentro de `SET LOCAL app.tenant_id`.
* §8.2 Fatos imutáveis — `arquivo_sped` com `supersedes`/`superseded_by`;
  documentos importados respeitam `uq_doc_empresa_chave_vigente`.
* §8.4 Golden tests — round-trip `gerar_XXX → parse_XXX` em todos os 4 parsers SPED.
* §8.6 Re-check — CNPJ + período + 9999 + débito/crédito.
* §8.8 LLM nunca escreve fato — pipeline 100% determinístico.
* §8.9 Idempotência tripla (arquivo, lançamento, documento).
* §8.10 `migracao.lote.iniciado/concluido/reaproveitado` em structlog + Langfuse.
* §8.12 Importador NÃO transmite — apenas reconstrói histórico.

## Limites conhecidos (out-of-scope)

* **Lookup do emitente NF via 0150** — placeholder `"00000000000000"`. Refinar
  quando primeiro cliente reclamar.
* **Bloco G (CIAP)** e **bloco H (inventário)** EFD ICMS-IPI — ficam vazios
  na importação. Pendências #31, #32.
* **Workers Celery beat para upload assíncrono >50MB** — síncronos por enquanto.
* **Importação cross-ano (DRE comparativo)** — pendência #8 resolvida pela
  PR1 (`abrir_exercicio` transporta saldos), mas reconciliação automática
  do balancete importado vs nosso recálculo fica para PR de seguimento.
* **Bloco D (CT-e / MDF-e)** — não importado. Pendência #29.

## Referências

* Sprint origem: [[sprints/sprint-18-migracao]]
* Geradores reversos: [[modulos/sped]]
* Idempotência: [[principios/09-idempotencia]]
* Runbook: [[runbooks/migracao-escritorio-antigo]]
