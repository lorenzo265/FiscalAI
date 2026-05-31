---
tags: [modulo, reforma-tributaria, cbs, ibs, scd]
fonte: "[[PlanoBackend]] §11 (Sprint 14) + LC 214/2025"
sprint_origem: "14"
path: "analista-fiscal-api/app/modules/reforma/"
status: concluido
---

# Módulo `reforma`

> Bounded context da Reforma Tributária (CBS/IBS). Fonte: [[PlanoBackend]] §11 Sprint 14 + LC 214/2025 + PLP 68/2024 (em tramitação).

## Responsabilidade

Cálculo CBS/IBS **informacional** sobre a base de uma operação ou apuração, lookup SCD de alíquotas vigentes por fase da Reforma, simulador de impacto em 3 cenários (pessimista/realista/otimista) e backfill de documentos fiscais via worker idempotente.

**Não escreve fato fiscal novo** — apenas popula `documento_fiscal.valor_cbs`/`valor_ibs` (campos informacionais, criados na migration 0002 e nunca antes preenchidos) e expõe endpoints de leitura. Nenhuma escrita em `apuracao_fiscal` neste módulo (princípio §8.8).

## Arquitetura

```
app/modules/reforma/
├── periodo_transicao.py       # fase(competencia) → enum
├── calcula_cbs_ibs.py         # ALGORITMO_VERSAO=reforma.cbs-ibs.v1
├── simulador.py               # ALGORITMO_VERSAO=reforma.simulador.v1
├── integrar_documento.py      # popular_cbs_ibs_informacional (puro)
├── schemas.py                 # Pydantic v2 com extra="forbid"
├── repo.py                    # AliquotaCbsIbsRepo + ReformaRepo
├── service.py                 # ReformaService — orquestração
└── router.py                  # 4 endpoints /v1/empresas/{eid}/reforma/*
```

## Cronograma (LC 214/2025)

| Fase | Janela | CBS | IBS | Status |
|---|---|---|---|---|
| `teste_2026` | 2026-01-01 a 2026-12-31 | 0,90% | 0,10% | informacional |
| `transicao_2027_2032` | 2027-01-01 a 2032-12-31 | 8,80% | 0,10% | preliminar |
| `regime_pleno_2033` | 2033-01-01+ | 8,80% | 17,70% | estimativa preliminar |

Repartição CBS/IBS no pleno (8,80% + 17,70% = 26,5%) é **preliminar** — alíquotas finais virão via Comitê Gestor IBS (PLP 68/2024).

## Endpoints

| Método | Path | Função |
|---|---|---|
| GET | `/v1/empresas/{eid}/reforma/simulacao?ano_alvo=2033` | 3 cenários + impacto fluxo de caixa |
| GET | `/v1/empresas/{eid}/reforma/aliquota-vigente?competencia=YYYY-MM-DD` | vigência SCD para a competência |
| POST | `/v1/empresas/{eid}/reforma/recalcular-historico` | backfill informacional do ano |
| GET | `/v1/empresas/{eid}/reforma/fase-atual?competencia=YYYY-MM-DD` | fase + fonte normativa |

## Worker Celery

- `reforma.refresh_cbs_ibs_historico` (diário 04:30) — itera empresas ativas e backfill ano corrente. Idempotente.

## Pendências do módulo

- [[pendencias/reforma-cbs-ibs-emissao-nfse|Emissão NFS-e com CBS/IBS via Focus]] — flag `FOCUS_NFSE_ENVIA_CBS_IBS=False` até Focus documentar.
- [[pendencias/reforma-aliquota-ibs-por-uf|IBS por UF]] — expandir SCD quando Comitê Gestor publicar.
- Imposto Seletivo (IS) — Fase 5 backlog.
- Split payment real 2027 — Sprint da Fase 5.
- NFC-e/CT-e/MDF-e com CBS/IBS — pendência (parser cobre só NF-e 55).

## Princípios aplicados

- [[principios/03-scd-type-2|03 — SCD Type 2]] (aliquota_cbs_ibs com trigger)
- [[principios/04-golden-tests|04 — Golden tests]] (calcula_cbs_ibs + simulador)
- [[principios/06-recheck-deterministico|06 — Re-check]] (validação base + alíquota)
- [[principios/08-llm-nao-escreve-fatos|08 — LLM não escreve fatos]]
- [[principios/09-idempotencia|09 — Idempotência]] (backfill)
- [[principios/10-observabilidade|10 — Observabilidade]] (log estruturado)
- [[principios/12-estimativa-labelada|12 — Estimativa labelada]] (observacao_estimativa em toda saída)

## Relacionado

- Sprint: [[sprints/sprint-14-reforma]]
- ADR: [[decisoes/adr-0016-reforma-tributaria-informacional-2026]]
