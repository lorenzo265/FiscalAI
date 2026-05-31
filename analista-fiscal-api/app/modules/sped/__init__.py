"""SPED — Sistema Público de Escrituração Digital (Sprint 16+).

Bounded context para geração e validação de arquivos SPED:

* **ECD** (Escrituração Contábil Digital) — anual, Sprint 16 PR1.
* **ECF** (Escrituração Contábil Fiscal) — anual, Sprint 16 PR2.
* **EFD-Contribuições** — mensal, Sprint 17.
* **EFD ICMS-IPI** — mensal, Sprint 17.

Princípios cravados:

* §8.2 — ``arquivo_sped`` é fato imutável; re-geração via supersedes.
* §8.4 — golden tests por bloco contra o layout oficial publicado pela
  RFB (ato COTEPE/ICMS) garantem que o formato pipe-delimited está
  correto antes do PVA aceitar.
* §8.8 — LLM nunca participa da geração; pipeline é 100% determinístico
  consumindo plano de contas + lançamentos + balancetes + apurações.
* §8.9 — idempotência por ``(empresa, tipo, periodo_inicio, periodo_fim)``.
* §8.10 — log estruturado em cada geração + hash SHA-256 persistido
  para integridade pós-download.
* §8.12 — **NUNCA transmitimos SPED automaticamente** — geração + validação
  local + cliente baixa e transmite via PVA/ReceitaNet com cert A1 dele.
  Não armazenamos certificado A1 do cliente (ADR 0014).
"""
