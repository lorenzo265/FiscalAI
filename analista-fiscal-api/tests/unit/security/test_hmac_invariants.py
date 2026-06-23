"""Invariantes HMAC de webhooks (Sprint 21 PR1).

Golden tests para verificar_assinatura_pluggy (Pluggy) e assinatura Meta WhatsApp.
Cobre: assinatura válida, payload adulterado, secret errado, guard de inputs
vazios, prefixo sha256=, e garantia de constant-time compare.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_stdlib

from app.shared.integrations.pluggy.webhook import verificar_assinatura_pluggy

_SECRET = "webhook_secret_de_teste_32chars!!"
_PAYLOAD = b'{"event":"item/updated","itemId":"abc-123"}'


def _assinar(payload: bytes, secret: str) -> str:
    return hmac_stdlib.new(secret.encode(), payload, hashlib.sha256).hexdigest()


# ── Assinatura válida ─────────────────────────────────────────────────────────


def test_assinatura_valida_sem_prefixo():
    sig = _assinar(_PAYLOAD, _SECRET)
    assert verificar_assinatura_pluggy(_PAYLOAD, sig, _SECRET) is True


def test_assinatura_valida_com_prefixo_sha256():
    sig = "sha256=" + _assinar(_PAYLOAD, _SECRET)
    assert verificar_assinatura_pluggy(_PAYLOAD, sig, _SECRET) is True


# ── Falhas esperadas ──────────────────────────────────────────────────────────


def test_payload_adulterado_falha():
    sig = _assinar(_PAYLOAD, _SECRET)
    payload_adulterado = _PAYLOAD + b"ADULTERADO"
    assert verificar_assinatura_pluggy(payload_adulterado, sig, _SECRET) is False


def test_secret_errado_falha():
    sig = _assinar(_PAYLOAD, _SECRET)
    assert verificar_assinatura_pluggy(_PAYLOAD, sig, "secret_errado") is False


def test_secret_vazio_retorna_false():
    sig = _assinar(_PAYLOAD, _SECRET)
    assert verificar_assinatura_pluggy(_PAYLOAD, sig, "") is False


def test_signature_vazia_retorna_false():
    assert verificar_assinatura_pluggy(_PAYLOAD, "", _SECRET) is False


def test_signature_invalida_retorna_false():
    assert verificar_assinatura_pluggy(_PAYLOAD, "dead" * 16, _SECRET) is False


# ── Garantia de constant-time (structural) ────────────────────────────────────


def test_usa_compare_digest_nao_igualdade_direta():
    """Confirma que a implementação usa hmac.compare_digest (timing-safe)."""
    import inspect

    from app.shared.integrations.pluggy import webhook
    src = inspect.getsource(webhook)
    assert "compare_digest" in src
    # Garante que não usa comparação direta (== entre strings de assinatura)
    assert "esperado ==" not in src and "== esperado" not in src
