"""Testes unitários — verificação HMAC do webhook Meta WhatsApp."""

from __future__ import annotations

import hashlib
import hmac as hmac_lib

from app.shared.integrations.meta_whatsapp.webhook import (
    extrair_mensagens,
    verificar_assinatura_meta,
)


def _gerar_assinatura(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac_lib.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestVerificarAssinaturaMeta:
    def test_assinatura_valida(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        secret = "meu_app_secret_123"
        sig = _gerar_assinatura(payload, secret)
        assert verificar_assinatura_meta(payload, sig, secret) is True

    def test_assinatura_invalida_payload_diferente(self) -> None:
        secret = "meu_app_secret_123"
        payload_original = b'{"object":"whatsapp_business_account"}'
        payload_adulterado = b'{"object":"hacker"}'
        sig = _gerar_assinatura(payload_original, secret)
        assert verificar_assinatura_meta(payload_adulterado, sig, secret) is False

    def test_assinatura_invalida_secret_diferente(self) -> None:
        payload = b'{"object":"whatsapp_business_account"}'
        sig = _gerar_assinatura(payload, "secret_correto")
        assert verificar_assinatura_meta(payload, sig, "secret_errado") is False

    def test_assinatura_sem_prefixo_sha256(self) -> None:
        payload = b'{"object":"test"}'
        secret = "abc"
        raw_hmac = hmac_lib.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verificar_assinatura_meta(payload, raw_hmac, secret) is False

    def test_timing_safe(self) -> None:
        """compare_digest deve ser usado (não ==)."""
        payload = b"x"
        secret = "s"
        sig = _gerar_assinatura(payload, secret)
        # Apenas garante que não lança exceção e retorna bool
        result = verificar_assinatura_meta(payload, sig, secret)
        assert isinstance(result, bool)

    # ── FIX #6 (PR6) — guards para app_secret e signature_header vazios ──────

    def test_app_secret_vazio_retorna_false(self) -> None:
        """Fail-closed: secret vazio → False imediato (sem computar HMAC)."""
        payload = b'{"object":"whatsapp_business_account"}'
        sig = _gerar_assinatura(payload, "qualquer_secret")
        assert verificar_assinatura_meta(payload, sig, app_secret="") is False

    def test_signature_header_vazio_retorna_false(self) -> None:
        """Fail-closed: header de assinatura vazio → False imediato."""
        payload = b'{"object":"whatsapp_business_account"}'
        assert verificar_assinatura_meta(payload, signature_header="", app_secret="meu_secret") is False

    def test_ambos_vazios_retorna_false(self) -> None:
        assert verificar_assinatura_meta(b"x", "", "") is False


class TestExtrairMensagens:
    def test_mensagem_texto(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "5511999998888",
                                        "id": "msg_abc123",
                                        "type": "text",
                                        "text": {"body": "quanto é meu DAS?"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        msgs = extrair_mensagens(payload)
        assert len(msgs) == 1
        assert msgs[0]["phone"] == "5511999998888"
        assert msgs[0]["texto"] == "quanto é meu DAS?"
        assert msgs[0]["tipo"] == "text"

    def test_payload_vazio(self) -> None:
        assert extrair_mensagens({}) == []
        assert extrair_mensagens({"entry": []}) == []

    def test_mensagem_nao_texto(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "5511999998888",
                                        "id": "msg_xyz",
                                        "type": "audio",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        msgs = extrair_mensagens(payload)
        assert len(msgs) == 1
        assert msgs[0]["tipo"] == "audio"
        assert msgs[0]["texto"] is None

    def test_multiplas_mensagens(self) -> None:
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {"from": "5511111", "id": "a", "type": "text", "text": {"body": "oi"}},
                                    {"from": "5522222", "id": "b", "type": "text", "text": {"body": "ola"}},
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        msgs = extrair_mensagens(payload)
        assert len(msgs) == 2
