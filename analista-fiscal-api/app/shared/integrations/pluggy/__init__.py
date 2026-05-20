"""Integração com Pluggy — Open Finance regulado pelo BCB (§7.3).

Cobre o fluxo MVP:
* Geração de connect_token para o widget JS do frontend.
* Sync de contas e transações via REST (PR2).
* Webhook callbacks de status do item (PR2).

CONSENT TYPE: o produto opera apenas em modo READ-ONLY no MVP — Pluggy é
Iniciadora de Pagamento autorizada, mas não usaremos esse recurso até o
módulo de Pagamentos (Sprint 14+).
"""

from app.shared.integrations.pluggy.auth import PluggyAuthClient
from app.shared.integrations.pluggy.client import PluggyClient
from app.shared.integrations.pluggy.webhook import (
    extrair_evento,
    verificar_assinatura_pluggy,
)

__all__ = [
    "PluggyAuthClient",
    "PluggyClient",
    "extrair_evento",
    "verificar_assinatura_pluggy",
]
