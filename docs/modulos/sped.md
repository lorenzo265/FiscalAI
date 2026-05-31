---
tags: [modulo, sped, ecd, ecf, geracao-fiscal]
fonte: "[[PlanoBackend]] §5.6 + §7.7 + §11 (Sprints 16-17)"
sprint_origem: "16"
path: "analista-fiscal-api/app/modules/sped/"
status: em-andamento
---

# Módulo `sped`

> Bounded context da geração e validação de arquivos SPED (Sistema Público de Escrituração Digital). Fonte: [[PlanoBackend]] §5.6 (modelo `arquivo_sped`) + §7.7 (transmissão) + §11 (Sprints 16-17).

## Cobertura por sprint

| Sprint | PR | Entrega |
|---|---|---|
| 16 | PR1 | **ECD** — Escrituração Contábil Digital anual (blocos 0/I/J/9). ✅ |
| 16 | PR2 | **ECF** — Escrituração Contábil Fiscal anual (Lucro Presumido). ✅ |
| 16 | PR3 | **Validador local** + workers beat anuais + endpoints listar/validar. ✅ |
| 17 | — | **EFD-Contribuições** + **EFD ICMS-IPI** mensais. ⏳ |

## Responsabilidade

Gerar o arquivo `.txt` no formato pipe-delimited oficial publicado pela RFB, calcular SHA-256 do conteúdo, persistir snapshot imutável em `arquivo_sped` e expor endpoint de download. **NUNCA transmite ao Fisco** ([[principios/12-transmissao-ato-consciente]]) — o cliente baixa o `.txt` e envia via PVA/ReceitaNet com certificado A1 próprio.

## Arquitetura

```
app/modules/sped/
├── compartilhado.py            # helpers puros: linha(), escapar, formatar_decimal,
│                               # formatar_data, gerar_bloco_9 (auto-referência),
│                               # calcular_hash_sha256, montar_arquivo (latin-1)
├── ecd/                        # Escrituração Contábil Digital ✅
│   ├── gerador.py              # ALGORITMO_VERSAO=sped.ecd.v1 — blocos 0/I/J/9
│   ├── repo.py                 # ContabilParaEcdRepo + ArquivoSpedRepo
│   ├── service.py              # EcdService.gerar — orquestração + idempotência
│   ├── schemas.py              # Pydantic v2
│   └── router.py               # POST /sped/ecd + GET .../download
├── ecf/                        # Escrituração Contábil Fiscal Lucro Presumido ✅
│   ├── gerador.py              # ALGORITMO_VERSAO=sped.ecf.v1 — 17 blocos (0..9 + Y)
│   ├── repo.py                 # ApuracoesLpParaEcfRepo + SaldosTrimestreParaEcfRepo
│   │                           # + EcdVinculadaRepo (C040 hash da ECD do ano)
│   ├── service.py              # EcfService.gerar — LP-only, idempotência §8.9
│   ├── schemas.py              # Reusa ArquivoSpedOut da PR1
│   └── router.py               # POST /sped/ecf + GET .../download
├── validador.py                # VALIDADOR_VERSAO=sped.validador.v1 ✅
│                               # estruturais + amarrações ECD/ECF
├── validacao_service.py        # SpedValidacaoService — persist + transit status
└── router.py                   # GET /sped (listar) + POST .../validar
```

## Princípios aplicados

- [[principios/02-fatos-imutaveis]] — `arquivo_sped` é snapshot append-only via `supersedes`/`superseded_by`; REVOKE UPDATE,DELETE FROM PUBLIC.
- [[principios/03-scd-type-2]] — `algoritmo_versao` bumpado junto com a versão do leiaute publicada pela RFB (ADE Cofis).
- [[principios/04-golden-tests]] — testes de estrutura por bloco (registros obrigatórios + contagens do 9900 consistentes) bloqueiam regressão.
- [[principios/08-llm-nao-escreve-fatos]] — gerador 100% determinístico; LLM nunca participa.
- [[principios/09-idempotencia]] — UNIQUE parcial DB-level em `(empresa, tipo, periodo_inicio, periodo_fim) WHERE superseded_by IS NULL` + check no service (`SpedJaGerado` 409 sem `forcar`).
- [[principios/10-observabilidade]] — log estruturado `sped.ecd.gerado` com hash, tamanho, total_linhas; SHA-256 persistido para integridade pós-download.
- [[principios/12-transmissao-ato-consciente]] — geração só. Transmissão é ato consciente do cliente. ADR [[adr/0014-pgdas-procuracao-eletronica-vs-cert-cliente]] cobre o porquê de não armazenar cert A1 do cliente.

## Layouts implementados

### ECD v10 (Sprint 16 PR1)

Fundamento normativo: IN RFB 2.003/2021 + ADE Cofis 64/2024 (leiaute v10 vigente desde 2024).

**Blocos cobertos:**

| Bloco | Registros | Conteúdo |
|---|---|---|
| 0 | 0000, 0001, 0030, 0990 | Abertura + identificação + dados cadastrais |
| I | I001, I010, I012, I030, I050, I051, I150, I155, I200, I250, I350, I355, I990 | Plano de contas + mapeamento referencial RFB + saldos periódicos + lançamentos + saldo de resultado pré-encerramento |
| J | J001, J005, J100, J150, J990 | Demonstrações: Balanço Patrimonial + DRE |
| 9 | 9001, 9900, 9990, 9999 | Totalizadores (`gerar_bloco_9` resolve a auto-referência circular: cada 9900 conta a si mesmo + 9990/9999) |

**Pré-condições validadas no gerador:**

- CNPJ 14 dígitos numéricos
- `codigo_municipio_ibge` 7 dígitos
- `fim_exercicio >= inicio_exercicio`
- `tipo_escrituracao ∈ {G, R, A, B, Z}`
- Cada lançamento com `débitos == créditos == valor_total`
- Toda partida/saldo periódico referencia conta existente em I050

**Validações que aceitamos como `SemDadosParaSped(422)` no service:**

- Plano de contas vazio
- Nenhum lançamento confirmado/encerrado no ano
- Empresa sem `codigo_municipio_ibge` populado

**Regime rejeitado**: MEI (`EmpresaNaoElegivelEcd 422`) — LC 123/2006 art. 18-A §13 (dispensa).

### ECF v10 (Sprint 16 PR2)

Fundamento normativo: IN RFB 2.004/2021 + ADE Cofis 51/2024 (leiaute v10).

**17 blocos emitidos em ordem fixa**: `0 → C → E → J → K → L → M → N → P → Q → T → U → V → W → X → Y → 9`. Blocos vazios em LP emitem apenas `X001` (com `IND_DAD='1'`) + `X990` (totalizador = 2).

**Blocos com dados (LP):**

| Bloco | Registros | Conteúdo |
|---|---|---|
| 0 | 0000, 0001, 0010, 0020, 0030, 0990 | Abertura + identificação tributária + parâmetros LP/trimestral |
| C | C001, C040 (condicional), C990 | Vinculação a ECD do mesmo ano (hash + recibo) |
| J | J001, J050, J051, J990 | Plano de contas final + mapeamento referencial RFB |
| K | K001, K030, K155, K990 | Saldos contábeis por período trimestral |
| P (núcleo) | P001, P010, P030, P100, P130, P200, P300, P400, P500, P990 | Apuração Lucro Presumido — IRPJ + CSLL trimestrais |
| Y | Y001, Y540, (Y600), Y990 | Discriminação receita por atividade + sócios (futuro) |
| 9 | 9001, 9900, 9990, 9999 | Totalizadores |

**P200 (IRPJ trimestral)** carrega: `base_total_irpj | limite_adicional | irpj_normal | irpj_adicional | irpj_total | irrf_consumido | irpj_devido`. Valores vêm direto do `IrpjLpSnapshot` (Sprint 11 PR1 estendida nesta PR2).

**P300 (CSLL trimestral)** carrega: `receita_bruta | percentual_presuncao | base_presumida | outras_adicoes | base_total | csll_devida`.

**Pré-condições no service:**

- Empresa Lucro Presumido (MEI/SN/Real → `EmpresaNaoElegivelEcd 422`).
- 4 apurações IRPJ + 4 CSLL trimestrais já registradas em `apuracao_fiscal`.
- Plano de contas vigente em 31/12 com pelo menos 1 conta.
- `codigo_municipio_ibge` populado.

**Out-of-scope** (Fase 5):

- Lucro Real (blocos M/N/L completos)
- Lucro Arbitrado (Q detalhado)
- Imunes/isentas (T detalhado)
- PJ exterior (U detalhado)
- Y600 sócios (depende de join com módulo `socio`)
- Y570 DCTF (depende de outros módulos)

## Endpoints

### `POST /v1/empresas/{eid}/sped/ecd`

Gera ECD anual. Idempotente §8.9: 409 `SpedJaGerado` quando já existe ativo e `forcar=false`. Com `forcar=true`, cria nova versão e marca a anterior como `superseded_by`.

```http
POST /v1/empresas/{eid}/sped/ecd
{
  "ano": 2025,
  "forcar": false
}
```

Resposta 201 com `ArquivoSpedOut` (id + hash + tamanho + status).

### `GET /v1/empresas/{eid}/sped/ecd/{sped_id}/download`

Devolve `Response(application/octet-stream)` com:
- `Content-Disposition: attachment; filename="sped_ecd_YYYYMMDD-YYYYMMDD.txt"`
- `X-Sped-Hash: <SHA-256>` (cliente compara antes de transmitir)
- `X-Sped-Algoritmo-Versao: sped.ecd.v1`

### `POST /v1/empresas/{eid}/sped/ecf`

Gera ECF anual LP. Idempotente §8.9. Requer 4 apurações IRPJ + 4 CSLL trimestrais já existentes.

```http
POST /v1/empresas/{eid}/sped/ecf
{
  "ano": 2025,
  "forcar": false
}
```

### `GET /v1/empresas/{eid}/sped/ecf/{sped_id}/download`

Devolve `application/octet-stream` com `X-Sped-Hash` + filename `sped_ecf_YYYYMMDD-YYYYMMDD.txt`. **Defesa em profundidade**: 404 se `arquivo.tipo != 'ecf'` (impede confundir download ECD/ECF).

### `GET /v1/empresas/{eid}/sped`

Lista arquivos SPED da empresa. Filtros: `tipo` (ecd|ecf|efd_contribuicoes|efd_icms_ipi), `somente_ativos` (default true), `limite` (1..500). Esconde versões com `superseded_by != null` por default.

### `POST /v1/empresas/{eid}/sped/{tipo}/{sped_id}/validar`

Executa o validador local (`VALIDADOR_VERSAO="sped.validador.v1"`) no conteúdo persistido, atualiza `validacao_jsonb` com `{ok, total_erros, total_warnings, erros[], warnings[]}` e transita `status='gerado' → 'validado'` se zero erros. **Sempre 200** — erros são parte do payload, não exceção HTTP. Cliente inspeciona `ok` para decidir transmissão.

## Workers Celery beat (PR3)

Beat schedule em `app/workers/celery_app.py`:

| Task | Cron | Cobertura |
|---|---|---|
| `sped.gerar_ecd_anual` | 03/abril 04:00 BR | Todas empresas LP + SN ativas — ECD do ano anterior |
| `sped.gerar_ecf_anual` | 03/junho 04:00 BR | Empresas LP ativas — ECF do ano anterior |

Datas escolhidas ~30 dias antes do prazo legal (último dia útil de maio/julho respectivamente). Idempotente: empresas que já têm versão ativa são absorvidas como `empresas_ja_gerada` (não-erro). Resilientes — falha em uma empresa não aborta as demais. Rodam como superuser fiscal (bypass RLS — operação cross-tenant). Ativação aguarda `poetry add celery[redis]` ([[pendencias/celery-instalacao]]).

## Pendências conscientes

- [[pendencias/sped-storage-s3-gcs]] — conteúdo do `.txt` em `BYTEA` provisório. Limite prático Postgres ~1GB; PME fica em 5-50MB. Migração para S3/GCS quando vier o gatilho de escala (>1k empresas ativas) ou quando entrar Sprint 18 (importação de SPED histórico, que cria carga maior).
- [[pendencias/sped-ecf-lucro-presumido]] — gerador ECF pendente (Sprint 16 PR2).
- [[pendencias/sped-validador-local]] — validador estrutural + amarrações ECD↔ECF pendente (Sprint 16 PR3).
- [[pendencias/sped-transmissao-pva-confirmacao]] — registro do `recibo_transmissao` é manual hoje (cliente cola o recibo ReceitaNet num endpoint futuro). Transição `status=transmitido→aceito→rejeitado` aguarda integração com webhook ReceitaNet quando a RFB publicar (não há previsão).

## Hub

[[README]] · [[sprints/sprint-16-sped|Sprint 16 (planejada)]] · [[modulos/contabil]] (consumido pelo gerador) · [[modulos/relatorios]] (DRE/Balanço via `calcula_dre`/`calcula_balanco`)
