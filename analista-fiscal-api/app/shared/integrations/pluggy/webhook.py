"""Validação HMAC e parsing de webhooks Pluggy (Sprint 7 PR2).

Pluggy assina cada webhook com HMAC-SHA256 sobre o corpo bruto da requisição
e envia o digest no header ``X-Pluggy-Signature`` (hex). Validação obrigatória
antes de qualquer processamento — não retornar 200 sem verificar.

Eventos relevantes (§7.3):
* ``item/updated``        — item teve novo sync com sucesso → puxar contas/transações
* ``item/login_succeeded`` — primeira conexão deu certo
* ``item/login_error``    — credenciais expiraram, cliente precisa reconectar
* ``item/waiting_user_input`` — MFA pendente
* ``transactions/created`` — novas transações disponíveis
* ``transactions/updated`` — transação reclassificada (PENDING → CONFIRMED ou ajuste de valor)
"""

from __future__ import annotations

import hashlib
import hmac as hmac_module

from app.shared.types import JsonObject

_SIGNATURE_PREFIX = "sha256="


def verificar_assinatura_pluggy(
    payload_bytes: bytes,
    signature: str,
    webhook_secret: str,
) -> bool:
    """Valida ``X-Pluggy-Signature`` contra HMAC-SHA256(payload, secret).

    Aceita o header com ou sem prefixo ``sha256=`` (Pluggy varia em alguns
    eventos). Comparação via ``hmac.compare_digest`` para resistir a timing
    attacks.

    Args:
        payload_bytes: Body cru da requisição (não decodificado).
        signature: Valor de ``X-Pluggy-Signature``.
        webhook_secret: Segredo configurado no painel Pluggy
            (``PLUGGY_WEBHOOK_SECRET`` em :class:`Settings`).

    Returns:
        True se a assinatura é válida.
    """
    if not webhook_secret or not signature:
        return False

    esperado = hmac_module.new(
        webhook_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()

    # Normaliza: aceita "sha256=<hex>" ou apenas "<hex>".
    recebido = (
        signature[len(_SIGNATURE_PREFIX):]
        if signature.startswith(_SIGNATURE_PREFIX)
        else signature
    )
    return hmac_module.compare_digest(esperado, recebido.strip().lower())


def extrair_evento(payload: JsonObject) -> tuple[str | None, str | None, str | None]:
    """Decompõe payload Pluggy em ``(event_id, item_id, event_type)``.

    Formato Pluggy (Webhooks v2):
        ``{
            "event": "item/updated",
            "id": "evt-uuid",
            "itemId": "item-uuid",
            "createdAt": "...",
            ...
        }``

    Campos ausentes retornam ``None`` na posição correspondente — o caller
    decide se ignora o evento.
    """
    event_id = payload.get("id") or payload.get("eventId")
    item_id = payload.get("itemId") or payload.get("item_id")
    event_type = payload.get("event") or payload.get("eventType")
    return (
        str(event_id) if event_id else None,
        str(item_id) if item_id else None,
        str(event_type) if event_type else None,
    )
