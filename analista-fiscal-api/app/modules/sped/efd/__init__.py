"""EFD — Escrituração Fiscal Digital mensal (Sprint 17).

Bounded context de geração de SPED mensal — duas obrigações distintas:

* **EFD-Contribuições** (Sprint 17 PR1) — apuração mensal de PIS/Cofins.
  Obrigatória para Lucro Presumido / Lucro Real. MEI e Simples Nacional
  são dispensados (a contrapartida do SN é a DEFIS anual — Sprint 6).
  Fundamento: IN RFB 1.252/2012 + Lei 9.715/1998 + Lei 9.718/1998.

* **EFD ICMS-IPI** (Sprint 17 PR2) — apuração mensal de ICMS e IPI.
  Obrigatória para empresas com inscrição estadual (comércio/indústria).
  Fundamento: Ajuste SINIEF 02/2009 + Convênio ICMS 143/2006.

Princípios cravados (idem ECD/ECF — ver ``app/modules/sped/__init__.py``):

* §8.2 — fato imutável; re-geração via ``supersedes``.
* §8.9 — idempotência por ``(empresa, tipo, periodo_inicio, periodo_fim)``.
* §8.12 — sistema NÃO transmite; cliente baixa e envia via PVA EFD-Contribuições
  / PVA EFD ICMS-IPI com certificado A1 dele.

Reusa em 100% o ``app/modules/sped/compartilhado.py`` (pipe-delimited,
bloco 9, hash SHA-256).
"""
