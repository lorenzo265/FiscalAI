"""Integração com a plataforma SERPRO Integra Contador (Sprint 6).

Cobre: PGDAS-D, DCTFWeb, DARF/DAS, e-CAC, DET, Procurações, Sicalc, MIT,
certidões CND. Custo médio ~R$0,96/empresa/mês (§7.1 do Plano).
"""

from app.shared.integrations.serpro.client import SerproClient
from app.shared.integrations.serpro.oauth import SerproOAuthClient

__all__ = ["SerproClient", "SerproOAuthClient"]
