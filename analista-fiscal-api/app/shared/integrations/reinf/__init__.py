"""Integração EFD-Reinf (Marco 4 PR2 #11).

Cliente HTTP assíncrono pra envio de lote de eventos EFD-Reinf e consulta
de recibo. Camada 4 (integrações externas). Espelha o pacote eSocial.
"""

from app.shared.integrations.reinf.client import (
    ALGORITMO_VERSAO,
    ReinfClient,
    ReinfError,
)
from app.shared.integrations.reinf.types import (
    EstadoLote,
    EventoLote,
    LoteEnviado,
    ReciboEvento,
    ReciboLote,
)

__all__ = [
    "ALGORITMO_VERSAO",
    "EstadoLote",
    "EventoLote",
    "LoteEnviado",
    "ReciboEvento",
    "ReciboLote",
    "ReinfClient",
    "ReinfError",
]
