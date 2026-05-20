from __future__ import annotations

import hashlib
import hmac as hmac_lib

from app.shared.types import JsonObject


def verificar_assinatura_meta(
    payload_bytes: bytes,
    signature_header: str,
    app_secret: str,
) -> bool:
    """Verifica X-Hub-Signature-256 do Meta WhatsApp Cloud API.

    Usa hmac.compare_digest para evitar timing attacks.
    DEVE ser chamada antes de qualquer processamento do payload.
    """
    expected = "sha256=" + hmac_lib.new(
        app_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(expected, signature_header)


def extrair_mensagens(payload: JsonObject) -> list[JsonObject]:
    """Extrai mensagens do envelope de webhook do Meta.

    Retorna lista de dicts com campos:
      - phone: número do remetente (formato E.164, ex: "5511999998888")
      - mensagem_id: ID único da mensagem no Meta
      - texto: corpo da mensagem (None se não for tipo "text")
      - tipo: "text" | "audio" | "image" | "interactive" | ...
    """
    mensagens: list[JsonObject] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                tipo = msg.get("type", "")
                texto: str | None = None
                if tipo == "text":
                    texto = msg.get("text", {}).get("body")
                mensagens.append(
                    {
                        "phone": msg.get("from", ""),
                        "mensagem_id": msg.get("id", ""),
                        "texto": texto,
                        "tipo": tipo,
                    }
                )
    return mensagens
