---
tags: [sprint, advisor, anomaly-detection, fator-r, digest, whatsapp, fase-3, concluida]
fonte: "[[PlanoBackend]] §11 Sprint 15 (linha 1520)"
status: concluida
fase: 3
marco: "Fase 3 em andamento (S14 → S20: 200 pagantes + MRR R$40k+)"
testes_final: 1386
concluida_em: 2026-05-24
---

# Sprint 15 — AI Advisor proativo

> Segunda sprint da Fase 3 (S14–S20). Constrói camada proativa do produto:
> anomaly detection diário + sugestões de otimização + weekly digest WhatsApp.

## Objetivo

Sair do modo **reativo** (assistente que responde quando perguntado — Sprint 4)
para **proativo** (sistema decide quando alertar e sugerir). Três entregáveis
ortogonais: detecção de saltos atípicos em apurações, sugestões financeiras
acionáveis (Fator R, parcelamento) e digest semanal pronto para envio via
WhatsApp utility template.

## Marco da sprint

- ✅ Suite **1386 testes** passando, 2 skipped, mypy 0 erros em 272 arquivos
- ✅ Princípios §8.1, §8.2, §8.4, §8.5, §8.6, §8.8, §8.9, §8.10, §8.12 cravados
- ✅ Sprint 15 fechada — Fase 3 segue. Próxima: [[sprints/sprint-16]] (SPED ECD + ECF)

## Decisão de design

LLM (Camada 3) **só** participa da redação final do texto do digest semanal.
Anomalia, Fator R, parcelamento, agregação do digest — tudo **determinístico**
(Camada 1, §8.8). Quando LLM é habilitado, `validar_resposta` rejeita qualquer
alucinação e o sistema cai automaticamente no template, preservando o custo
incorrido para observabilidade (§8.10). Endpoint REST sempre usa template;
LLM fica restrito ao worker beat (semanal, custo controlado).

## PRs

### PR1 — Anomaly detection (+33 testes)

- Migration `0036_sprint15_advisor_anomalias.py`: tabela `anomalia_fiscal`
  append-only com `supersedes`, UNIQUE parcial `(empresa, tipo, competencia)`
  WHERE `superseded_by IS NULL`. CHECKs cobrem tipo, severidade, método.
- Módulo `app/modules/advisor/`:
  - `calcula_anomalias.py` — `ALGORITMO_VERSAO="advisor.anomalia.v1"`. Z-score
    (N≥6) com thresholds 1,5/2,0/3,0; IQR Tukey (3≤N<6) com bandas Q±{1,5;3}×IQR.
    Edge cases tratados: série constante com salto > R$ 100 → alta sintética;
    série < 3 pontos → None silencioso; valor negativo → ValueError.
  - `AnomaliaFiscalRepo.registrar_ou_atualizar` é idempotente §8.9 — mesma
    chave + mesma detecção → no-op.
- 3 exceções: `AnomaliaNaoEncontrada` (404), `AnomaliaJaDispensada` (409),
  `HistoricoInsuficienteParaAnomalia` (422).
- Worker `advisor.detectar_anomalias_diario` (beat 07:30 BR).
- 2 endpoints: `GET /advisor/anomalias`, `POST .../anomalias/{id}/dispensar`.

### PR2 — Sugestões de otimização (+33 testes)

- Algoritmo puro `simula_fator_r.py` (`advisor.fator-r.v1`) — compara DAS mensal
  Anexo III × Anexo V para a mesma RBT12 (receita_12m). Reusa `calcular_das`
  da Sprint 2 (sem hardcoded — usa SCD `tabela_simples_faixa`). Calcula
  `fator_r`, `folha_necessaria_28pct`, `gap_folha_anual`, `economia_anual`.
  Boundary 28% segue `>=` da CGSN 140/2018.
- Orquestrador `sugestoes_otimizacao.py` (`advisor.sugestoes.v1`):
  - `sugerir_migracao_fator_r` — só emite se `deve_migrar` E |economia| ≥ R$ 100.
    Severidade alta se ≥ R$ 1.000/ano. Sugestão inversa (III→V) sempre
    informativa (avisa sobre impactos trabalhistas).
  - `sugerir_parcelamento_atrasado` — DAS não pago > 30 dias do vencimento
    (dia 20 do mês seguinte — LC 123 art. 21). Cita Lei 10.522/2002.
- `SugestoesRepo`: `folha_12m` (Holerite + ProlaboreMensal), `receita_12m`
  (DocumentoFiscal saída autorizada), `apuracoes_das_pendentes`.
- 2 exceções novas: `SemDadosParaSugestao` (422), `FatorRNaoAplicavel` (422).
- 1 endpoint: `GET /advisor/sugestoes`.

### PR3 — Weekly digest WhatsApp (+32 testes)

- Migration `0037_sprint15_advisor_digest.py`: `digest_semanal` (RLS,
  append-only). UNIQUE parcial `(empresa, semana_iso)` + UNIQUE `idempotency_key`.
- Algoritmo puro `gera_digest_semanal.py` (`advisor.digest.v1`) — função pura
  que agrega snapshots em `DigestEstruturado`: top-3 apurações, top-3 anomalias
  (severidade — alta > media > baixa), top-3 vencimentos (janela 14 dias),
  top-2 sugestões. `FonteCitavel.payload` contém valor monetário literal
  (`R$ 1,234.56`) — formato que `validar_resposta` reconhece.
- Redator `redigir_texto.py`:
  - `redigir_template(digest)` — caminho default 100% determinístico.
  - `redigir_via_llm(digest, llm_client, empresa_id)` — opt-in Gemini 2.5 Flash.
    System prompt cacheado 7d; user prompt cacheado 1h por (empresa, semana).
    `validar_resposta` rejeita alucinação → fallback ao template preservando
    custo já incorrido (§8.10).
- `AdvisorService.gerar_digest_semanal` orquestra. `forcar=False` → 409 se já
  gerado. `forcar=True` → supersede da versão anterior.
- 3 exceções novas: `DigestJaGeradoNaSemana` (409), `EmpresaSemWhatsapp` (422),
  `LlmIndisponivelDigest` (503).
- 3 endpoints: `POST /advisor/digest`, `GET /advisor/digests`, `GET .../{id}`.
- Worker `advisor.gerar_digest_semanal` (beat segunda 06:00 BR; itera apenas
  empresas com `whatsapp_phone IS NOT NULL`).

## Pendências geradas

- ~~**Envio real via Meta WhatsApp utility template**~~ → **resolvida na
  Sprint 15.5** (2026-05-24). Migration 0038 adiciona auditoria de envio;
  `MetaWhatsAppSender.enviar_template` com retry/backoff; service
  `enviar_digest_via_whatsapp` orquestra; worker beat segunda 06:30 BR;
  runbook `docs/runbooks/whatsapp-digest-template.md`. Resta apenas o passo
  operacional: cadastrar template `weekly_digest_pt_br` no Meta + setar
  `WHATSAPP_DIGEST_TEMPLATE_ATIVO=true`. Segue padrão §8.12 ("ativação é
  ato consciente do operador").
- **Distribuição isenta sub-utilizada** (sugestão) — depende de cálculo do
  limite isento a partir da DRE (Sprint 12).
- **Regime LP vs SN** (sugestão) — exige modelo de carga LP completo.

## Princípios cravados

- §8.1 — RLS multi-tenant nas 2 tabelas novas.
- §8.2 — `anomalia_fiscal` e `digest_semanal` append-only via supersedes.
- §8.4 — golden tests em `calcula_anomalias`, `simula_fator_r`,
  `sugestoes_otimizacao`, `gera_digest_semanal`.
- §8.5 — `FonteCitavel`/`citacoes` persistidas em JSONB para auditoria.
- §8.6 — `validar_resposta` rejeita alucinação; fallback determinístico.
- §8.8 — LLM nunca grava fatos; apenas redige texto a partir do snapshot.
- §8.9 — UNIQUE parcial em ambas as tabelas; `idempotency_key` no digest.
- §8.10 — `algoritmo_versao`, `custo_usd`, `tokens_*` persistidos.
- §8.12 — sugestões e digest carregam `observacao_estimativa`; transmissão
  fica como ato consciente.

## Relacionado

- Módulo: `app/modules/advisor/` (novo)
- Workers: `app/workers/tasks/advisor_anomalias.py`,
  `app/workers/tasks/advisor_digest_semanal.py`
- Migrations: `0036`, `0037`
- Próxima sprint: [[sprints/sprint-16]] (SPED ECD + ECF)
