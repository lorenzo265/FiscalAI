"""Integração eSocial (Sprint 19.7 PR2 #13).

Cliente HTTP assíncrono pra envio de lotes de eventos eSocial e
consulta de recibo. Camada 4 (integrações externas).
"""

from app.shared.integrations.esocial.client import (
    ALGORITMO_VERSAO,
    EsocialClient,
    EsocialError,
)
from app.shared.integrations.esocial.types import (
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)

__all__ = [
    "ALGORITMO_VERSAO",
    "EsocialClient",
    "EsocialError",
    "EventoLote",
    "LoteEnviado",
    "ReciboEvento",
    "ReciboLote",
]
