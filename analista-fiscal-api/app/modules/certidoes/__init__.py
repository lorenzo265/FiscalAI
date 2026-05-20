"""Módulo de certidões — CND federal (SERPRO), CRF (FGTS) e CNDT (Trabalhista).

Sprint 6 § PlanoBackend.md §7.1 + §9.2:
* Emissão sob demanda via SERPRO Integra Contador (CND) ou scraping (CRF/CNDT).
* Renovação automática quando ``valid_until`` faltar 30 dias (worker Celery —
  skeleton no PR3).
* Cada emissão é persistida em ``certidao`` (append-only), permitindo trilhar
  histórico de regularidade da empresa.
"""
