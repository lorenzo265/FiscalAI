"""Testes do verificador HMAC + extrator de eventos Pluggy (Sprint 7 PR2)."""

from __future__ import annotations

import hashlib
import hmac as hmac_module

import pytest

from app.shared.integrations.pluggy.webhook import (
    extrair_evento,
    verificar_assinatura_pluggy,
)

_SECRET = "secret-pluggy-test"


def _assinar(payload: bytes, secret: str = _SECRET) -> str:
    return hmac_module.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestVerificarAssinatura:
    def test_valida_sem_prefixo(self) -> None:
        body = b'{"event":"item/updated","id":"abc"}'
        sig = _assinar(body)
        assert verificar_assinatura_pluggy(body, sig, _SECRET) is True

    def test_valida_com_prefixo_sha256(self) -> None:
        body = b'{"event":"item/updated"}'
        sig = "sha256=" + _assinar(body)
        assert verificar_assinatura_pluggy(body, sig, _SECRET) is True

    def test_invalida_secret_diferente(self) -> None:
        body = b'{"x":1}'
        sig = _assinar(body, secret="outro")
        assert verificar_assinatura_pluggy(body, sig, _SECRET) is False

    def test_invalida_payload_modificado(self) -> None:
        body = b'{"x":1}'
        sig = _assinar(body)
        adulterado = b'{"x":2}'
        assert verificar_assinatura_pluggy(adulterado, sig, _SECRET) is False

    def test_secret_vazio_retorna_false(self) -> None:
        body = b'{"x":1}'
        sig = _assinar(body)
        assert verificar_assinatura_pluggy(body, sig, "") is False

    def test_signature_vazia_retorna_false(self) -> None:
        assert verificar_assinatura_pluggy(b"x", "", _SECRET) is False

    def test_aceita_signature_uppercase(self) -> None:
        body = b'{"x":1}'
        sig = _assinar(body).upper()
        assert verificar_assinatura_pluggy(body, sig, _SECRET) is True


class TestExtrairEvento:
    def test_campos_padrao(self) -> None:
        e_id, item_id, ev = extrair_evento(
            {"id": "evt-1", "itemId": "item-1", "event": "item/updated"}
        )
        assert (e_id, item_id, ev) == ("evt-1", "item-1", "item/updated")

    def test_fallback_event_id_eventid_camel(self) -> None:
        e_id, _, _ = extrair_evento({"eventId": "x", "itemId": "y", "event": "z"})
        assert e_id == "x"

    def test_item_snake_case(self) -> None:
        _, item_id, _ = extrair_evento(
            {"id": "e", "item_id": "snake", "event": "z"}
        )
        assert item_id == "snake"

    def test_campos_ausentes_retornam_none(self) -> None:
        e_id, item_id, ev = extrair_evento({})
        assert (e_id, item_id, ev) == (None, None, None)
