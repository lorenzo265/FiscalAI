---
tags: [runbook, migracao, onboarding, sped, csv, fase-3]
sprint_origem: 18
audiencia: "vendedor + contador + suporte"
---

# Runbook — Migração de escritório antigo

> Operação de onboarding de PME trazida de outro escritório contábil.
> Recebe 12 meses de SPED + opcional planilha CSV. Saída: dashboard cheio
> no dia 1 + comparativo "declarado pelo escritório antigo × recalculado por nós".

## Pré-requisitos

- [ ] Empresa criada no sistema (`POST /v1/empresas/`) com **CNPJ correto** —
      o importador valida CNPJ do SPED contra o cadastrado.
- [ ] Plano de contas clonado: `POST /v1/empresas/{eid}/plano-contas/clonar-padrao?valid_from=2024-01-01`.
      Contas ausentes do plano viram warning + lançamento pulado, não erro fatal.
- [ ] Cliente entregou os arquivos `.txt` SPED do escritório anterior:
  - **ECD** anual (1 arquivo por ano) — núcleo, alimenta lançamentos.
  - **ECF** anual (1 arquivo por ano) — só snapshot, mas útil para comparar.
  - **EFD-Contribuições** mensal (12 arquivos por ano) — popula NF + PIS/Cofins.
  - **EFD ICMS-IPI** mensal (12 arquivos por ano) — popula NF com ICMS.
- [ ] OU, se não tem SPED: planilha CSV de razão + balancete.

## Limites operacionais

- Limite por arquivo: **50 MB**.
- Período mínimo aceito: **2024-01-01** (corte do `PERIODO_INICIO_MINIMO`).
- Importação síncrona até ~30s. Acima disso → ver "Pendências conscientes".

## Pipeline recomendado (ordem importa)

```
1. ECD ano-corrente            ─┐
2. ECD ano anterior             ├─ Lança partidas (origem_tipo='importacao')
3. CSV razão complementar       ─┘

4. ECF ano-corrente            ─┐
5. ECF ano anterior             ├─ Snapshot apurações IRPJ/CSLL
                                ─┘

6. EFD-Contribuições ×12       ─┐
7. EFD ICMS-IPI ×12             ├─ Popula documento_fiscal + itens
                                ─┘

8. CSV balancete (opcional)    ─── Snapshot saldos para comparar
```

## Comandos

### 1. ECD anual

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "arquivo=@SPED_ECD_2024.txt" \
  https://api.fiscalai.com.br/v1/empresas/$EMPRESA_ID/migracao/sped/ecd/upload
```

Resposta:
```json
{
  "id": "<uuid lote>",
  "status": "concluido",
  "resumo": {
    "cnpj_arquivo": "12345678000190",
    "inicio_exercicio": "2024-01-01",
    "fim_exercicio": "2024-12-31",
    "contas_no_plano": 47,
    "lancamentos_no_arquivo": 1832,
    "lancamentos_criados": 1820,
    "lancamentos_existentes": 0,
    "lancamentos_pulados": 12,
    "saldos_periodicos": 12
  },
  "erros": { "warnings": [{"tipo": "conta_ausente", "codigo_conta": "5.1.99", ...}] }
}
```

### 2. ECF anual

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "arquivo=@SPED_ECF_2024.txt" \
  https://api.fiscalai.com.br/v1/empresas/$EMPRESA_ID/migracao/sped/ecf/upload
```

### 3. EFD-Contribuições mensal (loop)

```bash
for mes in 01 02 03 04 05 06 07 08 09 10 11 12; do
  curl -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -F "arquivo=@EFD_CONTRIB_2024-${mes}.txt" \
    https://api.fiscalai.com.br/v1/empresas/$EMPRESA_ID/migracao/sped/efd-contribuicoes/upload
done
```

### 4. CSV razão (fallback)

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "arquivo=@razao_2024.csv" \
  https://api.fiscalai.com.br/v1/empresas/$EMPRESA_ID/migracao/csv/razao/upload
```

CSV esperado:
```csv
data;conta_debito;conta_credito;historico;valor
15/03/2025;1.1.1.01;4.1.01;Recebimento NF 1001;1000,00
20/03/2025;5.1.01;1.1.1.01;Pagamento fornecedor;500,00
```

## Conferência pós-importação

### 1. Listar lotes da empresa
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.fiscalai.com.br/v1/empresas/$EMPRESA_ID/migracao/lotes
```

### 2. Comparar com o que esperamos
- DRE consolidada do ano: `GET /v1/empresas/{eid}/relatorios/dre?ano=2024`
- Balancete dezembro/2024: `GET /v1/empresas/{eid}/contabil/balancete/2024-12`
- Reabrir exercício 2025: `POST /v1/empresas/{eid}/contabil/exercicio/2025/abrir`
  (já chamado automaticamente pelo `encerrar_ano`, mas idempotente — útil
  para correção pós-edição retroativa)

### 3. Cross-check declarado × recalculado
- Lote ECF traz `resumo.apuracoes` com IRPJ/CSLL declarados pelo escritório anterior.
- Após nossas apurações (Sprint 11) rodarem em cima dos lançamentos importados,
  o front mostra delta — se >R$ 50 em algum trimestre, alerta o contador.

## Troubleshooting

### `422 EmpresaCnpjDivergente`
SPED entregue é de outra empresa. Confirme com o cliente qual o arquivo correto.
**Não force importação cross-CNPJ** — fatos imutáveis §8.2.

### `422 PeriodoForaCobertura`
SPED é anterior a 2024-01-01. Por enquanto, ignorar (PME jovem raramente
precisa importar tão atrás). Se cliente exige, considerar relaxar o
`PERIODO_INICIO_MINIMO` em PR dedicado — mas verifique cobertura SCD
(INSS, IRRF, ICMS UF) antes.

### `422 SpedInvalido: 9999 declarado=X ≠ total real=Y`
Arquivo SPED corrompido (linhas removidas/adicionadas). Peça novo download
ao cliente do PVA.

### `lote_status='concluido'` + muitos warnings `conta_ausente`
Plano de contas referencial não cobre as contas usadas pelo escritório
antigo. Solução manual: criar contas novas via `POST /plano-contas` +
`POST /lote/{id}/reprocessar` (endpoint futuro — por enquanto, novo
upload do SPED gera novo lote idempotente por hash).

### Re-upload do mesmo arquivo
**OK** — idempotência por hash devolve o lote anterior com
`reaproveitado=True`. Sem efeito colateral, sem custo extra.

### Upload >50MB
- ECD ano completo: ~5–15MB → OK.
- EFD-Contribuições ano completo (12 meses): ~30MB → quase no limite.
- Se exceder: split por trimestre ou aguardar workers Celery em background
  (pendência consciente #1).

## Pendências conscientes (a saber)

1. **CNPJ emitente** dos documentos importados via EFD vem placeholder
   `"00000000000000"`. Refinamento (lookup do 0150) entra em PR de seguimento.
2. **Tabela INSS 2024** não está seedada. Folha 2024 importada cai em
   `RegimeIncompativel` — registrar como TODO ao cliente.
3. **Bloco G (CIAP) e H (inventário)** do EFD ICMS-IPI não são importados.
4. **Workers Celery beat** não rodam — uploads grandes são síncronos.

## Métricas a observar

* Grafana: `migracao_lote_total{tipo, status}` deve incrementar.
* Langfuse: cada `migracao.lote.iniciado` deve fechar com
  `migracao.lote.concluido` em ~30s para arquivos ECD típicos.
* Loki: warnings `migracao.conta_ausente` em escala → revisar plano referencial.
