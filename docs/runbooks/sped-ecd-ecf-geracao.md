---
tags: [runbook, sped, ecd, ecf, sprint-16]
fonte: "Sprint 16 PR1+PR2+PR3 — geração e validação SPED"
atualizado: 2026-05-25
---

# Runbook — Geração + validação + transmissão SPED ECD/ECF

> Fluxo end-to-end para o contador (ou worker Celery) gerar, validar
> localmente, baixar e transmitir um arquivo SPED. Cobre ECD (anual,
> entrega até último dia útil de maio) e ECF Lucro Presumido (anual,
> entrega até último dia útil de julho).

## Princípio inviolável (§8.12)

**O sistema NUNCA transmite ao Fisco automaticamente.** A geração é nossa
responsabilidade; a transmissão é ato consciente do cliente — exige
certificado A1 próprio dele no PVA da RFB. Não armazenamos o cert A1 do
cliente em hipótese alguma (ver [[adr/0014-transmissao-spedes-modelo]]).

## Visão geral do pipeline

```
┌────────────────────────────────────────────────────────────────────┐
│ 1. Gerar          POST /v1/empresas/{eid}/sped/{ecd|ecf}           │
│    └─► status='gerado', validacao_jsonb=null                       │
│                                                                    │
│ 2. Validar        POST /v1/empresas/{eid}/sped/{tipo}/{id}/validar │
│    └─► validacao_jsonb populado                                    │
│        se ok → status='validado'                                   │
│        se erros → status permanece 'gerado'                        │
│                                                                    │
│ 3. Corrigir       (loop até validacao.ok)                          │
│    └─► ajustar dados de origem (lançamentos, apurações)            │
│        gerar nova versão com forcar=true (supersede anterior)      │
│                                                                    │
│ 4. Baixar         GET /v1/empresas/{eid}/sped/{tipo}/{id}/download │
│    └─► .txt SPED + header X-Sped-Hash para integridade             │
│                                                                    │
│ 5. Transmitir     PVA/ReceitaNet — ato do cliente, cert A1 dele    │
│    └─► (futuro) PATCH .../recibo para registrar status='aceito'    │
└────────────────────────────────────────────────────────────────────┘
```

## 1. Gerar

### ECD (Escrituração Contábil Digital)

```bash
curl -X POST \
  https://api.fiscalai.com.br/v1/empresas/$EID/sped/ecd \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ano": 2025, "forcar": false}'
```

**Pré-requisitos:**

- Empresa NÃO MEI (LC 123 art. 18-A §13 — dispensa).
- Pelo menos 1 lançamento contábil confirmado/encerrado no ano.
- Plano de contas com vigência cobrindo 31/12 do ano.
- `empresa.codigo_municipio_ibge` populado (PATCH `.../municipio-ibge` se faltar).

**Resposta (201)**: `ArquivoSpedOut` com `id`, `tamanho_bytes`, `hash_arquivo` (SHA-256), `status='gerado'`.

**Erros comuns:**

| HTTP | Código | Causa |
|---|---|---|
| 409 | `SpedJaGerado` | Versão ativa existe; passar `forcar=true` para superseder |
| 422 | `EmpresaNaoElegivelEcd` | Empresa MEI |
| 422 | `SemDadosParaSped` | Sem lançamentos / plano vazio / sem IBGE |

### ECF (Escrituração Contábil Fiscal)

```bash
curl -X POST \
  https://api.fiscalai.com.br/v1/empresas/$EID/sped/ecf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ano": 2025, "forcar": false}'
```

**Pré-requisitos adicionais (LP):**

- Regime `lucro_presumido` (MVP — Lucro Real/Arbitrado em Fase 5).
- 4 apurações IRPJ + 4 CSLL trimestrais já registradas em `apuracao_fiscal` (Sprint 11 PR1).
- ECD do mesmo ano ideal (preenche bloco C040 com hash); ECF gera mesmo sem ECD, com C `IND_DAD='1'`.

## 2. Validar localmente

```bash
curl -X POST \
  https://api.fiscalai.com.br/v1/empresas/$EID/sped/ecd/$SPED_ID/validar \
  -H "Authorization: Bearer $TOKEN"
```

**Resposta SEMPRE 200** — erros são parte do payload, não exceção HTTP:

```json
{
  "arquivo": { "id": "...", "status": "validado", ... },
  "ok": true,
  "total_erros": 0,
  "total_warnings": 0,
  "validador_versao": "sped.validador.v1",
  "erros": [],
  "warnings": []
}
```

**Categorias de erro (ECD):**

| Código | Causa | Como corrigir |
|---|---|---|
| `estrutura.linha_quebrada` | Linha sem pipe inicial/final | Bug do gerador — abrir issue |
| `estrutura.9999_divergente` | Total declarado ≠ real | Bug do gerador — abrir issue |
| `estrutura.9900_divergente` | Contagem por tipo errada | Bug do gerador — abrir issue |
| `estrutura.bloco_*_ausente` | Bloco obrigatório faltando | Bug do gerador — abrir issue |
| `ecd.partidas_desbalanceadas` | Σ D ≠ Σ C num lançamento | Corrigir lançamento na contabilidade |
| `ecd.valor_total_divergente` | `valor_total` ≠ soma das partidas | Corrigir lançamento |
| `ecd.i155_conta_orfa` | Saldo periódico referencia conta inexistente | Cadastrar conta no plano |
| `ecd.i250_conta_orfa` | Partida referencia conta inexistente | Cadastrar conta |
| `ecd.i250_indicador_invalido` | IND_DC ≠ 'D'/'C' | Bug do gerador |

**Categorias de erro (ECF):**

| Código | Causa | Como corrigir |
|---|---|---|
| `ecf.p200_irpj_normal_divergente` | IRPJ normal ≠ base × 15% | Re-apurar IRPJ trimestral |
| `ecf.p200_total_divergente` | IRPJ total ≠ normal + adicional | Re-apurar IRPJ trimestral |
| `ecf.p300_csll_divergente` | CSLL ≠ base × 9% | Re-apurar CSLL trimestral |
| `ecf.y540_p100_divergente` | Receita anual ≠ Σ trimestres | Re-apurar (4 trimestres) |

Erros do gerador (estruturais) NÃO devem ocorrer em produção — se aparecerem, é bug do gerador, não do contador. Abrir issue com `hash_arquivo` + `algoritmo_versao`.

## 3. Corrigir e re-gerar

Quando há erro de negócio (lançamento desbalanceado, apuração trimestral
errada), corrigir no módulo de origem e re-gerar com `forcar=true`:

```bash
curl -X POST \
  https://api.fiscalai.com.br/v1/empresas/$EID/sped/ecd \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ano": 2025, "forcar": true}'
```

A versão anterior fica com `superseded_by=<novo_id>` (imutável, §8.2 —
nunca apagamos histórico). `GET /sped?somente_ativos=true` mostra só a
mais recente; `somente_ativos=false` mostra todas as versões.

## 4. Baixar o `.txt`

```bash
curl -X GET \
  https://api.fiscalai.com.br/v1/empresas/$EID/sped/ecd/$SPED_ID/download \
  -H "Authorization: Bearer $TOKEN" \
  -o sped_ecd_20250101-20251231.txt
```

Headers de resposta:

- `Content-Disposition: attachment; filename="sped_ecd_YYYYMMDD-YYYYMMDD.txt"`
- `X-Sped-Hash: <SHA-256>` — confirmar integridade após download:
  ```bash
  sha256sum sped_ecd_20250101-20251231.txt
  # deve bater com o header X-Sped-Hash
  ```
- `X-Sped-Algoritmo-Versao: sped.ecd.v1`

## 5. Transmitir (cliente, no PVA)

1. Cliente abre o **PVA ECD/ECF** baixado em [receita.economia.gov.br](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/download/pgd).
2. Importa o `.txt` recebido.
3. PVA executa sua própria validação (mais rigorosa que a nossa — inclui
   amarrações DCTFWeb, vínculo com ECD original, etc.).
4. Cliente **assina digitalmente** com certificado A1 ICP-Brasil próprio.
5. Cliente transmite. PVA gera **recibo de entrega** (`NUM_REC`).
6. **(Futuro — fora do MVP)** Cliente cola o `NUM_REC` em endpoint
   `PATCH /v1/empresas/{eid}/sped/{tipo}/{id}/recibo` que transita
   `status='validado' → 'transmitido' → 'aceito'`.

## Workers automáticos (Celery beat)

Beat schedule em `app/workers/celery_app.py`:

| Task | Cron | Comportamento |
|---|---|---|
| `sped.gerar_ecd_anual` | 03/abril 04:00 BR | Gera ECD do ano anterior para todas LP + SN ativas. Idempotente — empresas que já têm versão ativa caem em `SpedJaGerado` (não-erro). |
| `sped.gerar_ecf_anual` | 03/junho 04:00 BR | Gera ECF do ano anterior para empresas LP ativas. |

Workers rodam como superuser fiscal (bypass RLS — operação cross-tenant
de sistema). Resilientes — falha em uma empresa não aborta as demais.
Empresas sem dados / não-elegíveis viram categorias separadas no
contador final, não erros.

**Datas escolhidas**: ~30 dias antes do prazo legal — sobra tempo para o
cliente validar/corrigir/baixar/transmitir antes do vencimento.

**Ativação**: Celery ainda é opt-in (`poetry add celery[redis]` —
[[pendencias/celery-instalacao]]). Até então, geração é só on-demand
via endpoint REST.

## Troubleshooting

### "Plano de contas vazio"

Causa: empresa não escriturou o ano. Soluções:

1. Importar plano de contas via fluxo de migração (Sprint 18 — pendente).
2. Pular o ano (empresa em pré-operação).

### "Nenhuma apuração IRPJ/CSLL trimestral encontrada"

Causa: ECF requer 4 trimestres apurados em `apuracao_fiscal`. Soluções:

1. Apurar via `POST /v1/empresas/{eid}/lp/irpj` + `.../lp/csll` para cada
   trimestre (Sprint 11 PR1).
2. ECF pode rodar mesmo com 1-3 trimestres apurados (situação especial),
   mas o validador alertará sobre P100 incompleto.

### "Hash baixado ≠ X-Sped-Hash"

Causa: corrupção em transit ou cache intermediário. Soluções:

1. Baixar novamente (idempotente — mesmo `id`).
2. Conferir proxy/CDN entre cliente e API — desabilitar compressão para
   `/sped/*/download`.

### PVA recusa o arquivo

Causa: nosso validador local cobre o essencial mas o PVA tem regras
adicionais (versionamento de leiaute, amarrações DCTFWeb, etc.).
Soluções:

1. Verificar versão do PVA (sempre usar a mais recente).
2. Conferir `X-Sped-Algoritmo-Versao` — confirmar que o leiaute gerado
   bate com o ano-calendário declarado (ADE Cofis publicada).
3. Abrir issue colando a mensagem do PVA — adicionamos a regra ao
   validador local para detectar antes em casos futuros.

## Relacionados

- [[modulos/sped]] — descrição do bounded context
- [[principios/12-transmissao-consciente]] — §8.12
- [[adr/0014-transmissao-spedes-modelo]] — não armazenamos cert A1 do cliente
- [[pendencias/sped-storage-s3-gcs]] — conteúdo em BYTEA provisório
- [[pendencias/celery-instalacao]] — workers ativam quando instalar Celery
