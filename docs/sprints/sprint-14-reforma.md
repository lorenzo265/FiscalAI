---
tags: [sprint, reforma-tributaria, cbs, ibs, fase-3, concluida]
fonte: "[[PlanoBackend]] §11 Sprint 14 + LC 214/2025"
status: concluida
fase: 3
marco: "Fase 3 aberta (S14 → S20: 200 pagantes + MRR R$40k+)"
testes_final: 1288
concluida_em: 2026-05-22
---

# Sprint 14 — Reforma Tributária (CBS/IBS informacional)

> Primeira sprint da Fase 3 (S14–S20). Abre o caminho para SPED ECD/ECF (S16), EFD-Contribuições/ICMS-IPI (S17) e Lucro Presumido pronto pra venda (S20).

## Objetivo

Cálculo CBS/IBS informacional 2026, suporte aos campos `vCBS`/`vIBS`/`cClassTrib` em NF-e 4.x, simulador de impacto da Reforma com 3 cenários (pessimista/realista/otimista) e backfill via worker Celery.

## Marco da sprint

- ✅ Suite **1288 testes passando**, 2 skipped, mypy 0 erros em 260 arquivos
- ✅ Princípios §8.3, §8.4, §8.8, §8.9, §8.10, §8.12 cravados
- ✅ Sprint 14 fechada — Fase 3 aberta. Próxima: [[sprints/sprint-15]] (AI Advisor proativo)

## Decisão de design

Detalhada em [[decisoes/adr-0016-reforma-tributaria-informacional-2026|ADR 0016]]: tabela SCD própria (`aliquota_cbs_ibs`) + simulador com cenários ±2pp em torno da alíquota da SCD. Alternativa "hardcoded 26,5%" foi rejeitada por violar §8.3 (decisões versionadas).

## PRs

### PR1 — SCD + algoritmo puro + golden tests (+40 testes)

- Migration `0034_sprint14_reforma_aliquotas.py`: tabela SCD `aliquota_cbs_ibs` + trigger reaproveitado da 0025 + REVOKE/GRANT + seed de 3 vigências (teste_2026 0,9%+0,1%; transicao_2027 8,8%+0,1%; pleno_2033 8,8%+17,7%).
- Model `AliquotaCbsIbs` em `app/shared/db/models.py`.
- Módulo `app/modules/reforma/`:
  - `periodo_transicao.py` — `fase(competencia)` puro com 3 fases.
  - `calcula_cbs_ibs.py` — `ALGORITMO_VERSAO="reforma.cbs-ibs.v1"`, quantize HALF_EVEN, observação obrigatória.
  - `repo.py::AliquotaCbsIbsRepo.vigente(competencia, regime, cnae, classificacao)` com scoring por especificidade (CNAE prefix longo vence curto).
- 3 exceções novas: `AliquotaCbsIbsAusente`, `BaseCalculoInvalida`, `PeriodoReformaNaoMapeado`.

### PR2 — Parser NF-e 4.x estendido + persistência + flag Focus (+20 testes)

- Migration `0035_sprint14_doc_fiscal_cclasstrib.py`: `documento_fiscal.cclasstrib VARCHAR(20)` + CHECK regex `^[0-9]{6}$` + índice parcial.
- Parser estendido: `NFeData` ganha `valor_cbs`/`valor_ibs`/`cclasstrib` opcionais; helper `_decimal_opt` distingue "tag ausente" de "tag com 0,00" (§8.2).
- `IngestaoService` propaga campos novos.
- Helper puro `integrar_documento.popular_cbs_ibs_informacional` (idempotente, não persiste; caller decide).
- Config `FOCUS_NFSE_ENVIA_CBS_IBS=False` adicionado — gate para emissão CBS/IBS em NFS-e (ativação real fica como pendência consciente).

### PR3 — Simulador 3 cenários + endpoints + worker + service (+29 testes)

- Algoritmo puro `simulador.py` (`ALGORITMO_VERSAO="reforma.simulador.v1"`): `projetar_impacto(...)` devolve 3 cenários (pessimista/realista/otimista, ±2pp) + `ImpactoFluxoCaixa` (split payment 2027 = ICMS_médio × prazo/30). Invariante `pessimista > realista > otimista` testada. Clamp alíquota em [0, 1].
- Schemas Pydantic v2 com `observacao_estimativa` obrigatório em toda saída.
- `ReformaService` orquestra simulador + `aliquota_vigente` + `recalcular_historico_documentos` (idempotente §8.9).
- `ReformaRepo` com queries auxiliares: `carga_apurada_12m` (soma PIS+Cofins+ICMS+ISS dos 12m + receita anualizada + ICMS médio mensal) + `documentos_do_ano_sem_cbs` + `atualizar_cbs_ibs_documento`.
- 4 endpoints sob `/v1/empresas/{eid}/reforma/*`: simulacao, aliquota-vigente, recalcular-historico, fase-atual.
- Worker Celery `reforma.refresh_cbs_ibs_historico` (diário 04:30) — itera empresas ativas e chama backfill; resiliente (falha em uma empresa não aborta as demais).
- 1 exceção nova: `SemApuracoesDoPeriodo(422)`.

## Pendências geradas

- [[pendencias/reforma-cbs-ibs-emissao-nfse]] — flag `FOCUS_NFSE_ENVIA_CBS_IBS` ativada quando Focus documentar.
- [[pendencias/reforma-aliquota-ibs-por-uf]] — expandir SCD com `uf VARCHAR(2)` quando Comitê Gestor IBS publicar.
- Imposto Seletivo (IS) — Fase 5 backlog.
- Split payment real 2027 — Sprint da Fase 5.
- Bloco K do SPED com CBS/IBS — Sprint 17.
- NFC-e/CT-e/MDF-e com CBS/IBS — pendência (parser cobre só NF-e 55).

## Princípios cravados

- §8.3 — SCD com trigger genérico + REVOKE.
- §8.4 — golden tests cobrindo `calcula_cbs_ibs` + `simulador`.
- §8.8 — LLM nunca chamado neste módulo.
- §8.9 — backfill idempotente.
- §8.10 — log estruturado em cada operação.
- §8.12 — `observacao_estimativa` propagada do algoritmo até o JSON.

## Relacionado

- ADR: [[decisoes/adr-0016-reforma-tributaria-informacional-2026]]
- Módulo: [[modulos/reforma]]
- Princípios: [[principios/03-scd-type-2]], [[principios/12-estimativa-labelada]]
- Próxima sprint: [[sprints/sprint-15]] (AI Advisor proativo)
