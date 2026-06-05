"""Testes do processador de redação de PII — _redact_pii (PR2 Segurança/LGPD).

§8.4: golden tests cobrindo:
  * Chaves sensíveis mascaradas (senha, token, authorization, email, cnpj, etc.)
  * CPF/CNPJ/e-mail/telefone no campo ``event`` mascarados
  * CPF/CNPJ/e-mail/telefone em valor de kwarg string mascarados
  * Não-str (int, None, Decimal) passam intactos
  * Corpo de erro SERPRO-style com CNPJ embutido é redacted
  * Processador não lança exceção em nenhum cenário
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.shared.logging import _redact_pii


# Helper: chama o processador com um event_dict e retorna o resultado
def _run(event_dict: dict[str, Any]) -> dict[str, Any]:
    logger = MagicMock()
    return _redact_pii(logger, "info", event_dict)


# ── 1. Chaves sensíveis — mascaramento completo (***) ────────────────────────


@pytest.mark.parametrize(
    "key",
    ["senha", "password", "token", "secret", "authorization", "bearer"],
)
def test_chave_sensivel_full_mascara(key: str) -> None:
    result = _run({"event": "login", key: "super-secret-value"})
    assert result[key] == "***"


def test_chave_authorization_case_insensitive() -> None:
    result = _run({"event": "req", "Authorization": "Bearer eyJhbGc..."})
    assert result["Authorization"] == "***"


def test_chave_token_substring_match() -> None:
    """Chave 'access_token' contém 'token' → deve ser mascarada."""
    result = _run({"event": "oauth", "access_token": "abc123"})
    assert result["access_token"] == "***"


# ── 2. Chaves sensíveis — mascaramento com prefixo (email, cpf, cnpj, etc.) ──


def test_chave_email_mascara_com_prefixo() -> None:
    result = _run({"event": "cadastro", "email": "joao.silva@empresa.com.br"})
    # Primeiros 4 chars + "***"
    assert result["email"].startswith("joao")
    assert "***" in result["email"]
    assert "silva" not in result["email"]


def test_chave_cpf_mascara_com_prefixo() -> None:
    result = _run({"event": "cadastro", "cpf": "123.456.789-09"})
    assert result["cpf"].startswith("123.")
    assert "***" in result["cpf"]


def test_chave_cnpj_mascara_com_prefixo() -> None:
    result = _run({"event": "cadastro", "cnpj": "12.345.678/0001-90"})
    assert result["cnpj"].startswith("12.3")
    assert "***" in result["cnpj"]


def test_chave_telefone_mascara_com_prefixo() -> None:
    result = _run({"event": "contato", "telefone": "+5511912345678"})
    assert "***" in result["telefone"]


# ── 3. Redação por padrão regex no campo ``event`` ───────────────────────────


def test_cpf_no_event_mascarado() -> None:
    result = _run({"event": "erro ao processar CPF 123.456.789-09 do usuário"})
    assert "123.456.789-09" not in result["event"]
    assert "[CPF***]" in result["event"]


def test_cnpj_no_event_mascarado() -> None:
    result = _run({"event": "empresa 12.345.678/0001-90 não encontrada"})
    assert "12.345.678/0001-90" not in result["event"]
    assert "[CNPJ***]" in result["event"]


def test_email_no_event_mascarado() -> None:
    result = _run({"event": "enviando para usuario@exemplo.com.br"})
    assert "usuario@exemplo.com.br" not in result["event"]
    assert "[EMAIL***]" in result["event"]


def test_phone_no_event_mascarado() -> None:
    result = _run({"event": "notificação para +5511987654321"})
    assert "+5511987654321" not in result["event"]
    assert "[PHONE***]" in result["event"]


# ── 4. Redação por padrão regex em valores de kwarg string ───────────────────


def test_cnpj_em_kwarg_string_mascarado() -> None:
    result = _run({
        "event": "upstream_error",
        "resp_body": "erro: CNPJ 12.345.678/0001-90 inativo",
    })
    assert "12.345.678/0001-90" not in result["resp_body"]
    assert "[CNPJ***]" in result["resp_body"]


def test_email_em_kwarg_string_mascarado() -> None:
    result = _run({
        "event": "validacao",
        "detalhe": "e-mail teste@empresa.com.br inválido",
    })
    assert "teste@empresa.com.br" not in result["detalhe"]
    assert "[EMAIL***]" in result["detalhe"]


# ── 5. Não-str passam intactos ───────────────────────────────────────────────


def test_int_passa_intacto() -> None:
    result = _run({"event": "metricas", "contagem": 42, "token_count": 7})
    # contagem = int → não mexe; token_count = int → não mexe (mesmo sendo chave sensível)
    assert result["contagem"] == 42
    assert result["token_count"] == 7


def test_none_passa_intacto() -> None:
    result = _run({"event": "nullable", "email": None})
    assert result["email"] is None


def test_decimal_passa_intacto() -> None:
    result = _run({"event": "valor", "valor_decimal": Decimal("1234.56")})
    assert result["valor_decimal"] == Decimal("1234.56")


def test_lista_passa_intacta() -> None:
    """Estruturas complexas (list, dict nested) não crasham o processor."""
    result = _run({"event": "bulk", "ids": [1, 2, 3], "meta": {"k": "v"}})
    assert result["ids"] == [1, 2, 3]
    assert result["meta"] == {"k": "v"}


# ── 6. Cenário SERPRO-realístico — corpo de erro com CNPJ embutido ───────────


def test_serpro_error_body_cnpj_redacted() -> None:
    """Simula o log de resp.text[:300] de integração SERPRO/Pluggy."""
    corpo_erro = (
        '{"codigo": "CNPJ_INVALIDO", "cnpj": "12.345.678/0001-90", '
        '"mensagem": "CNPJ 12.345.678/0001-90 não cadastrado", '
        '"cpf_socio": "987.654.321-00"}'
    )
    result = _run({
        "event": "serpro.error",
        "status": 422,
        "resp_text": corpo_erro,
    })
    assert "12.345.678/0001-90" not in result["resp_text"]
    assert "987.654.321-00" not in result["resp_text"]
    assert "[CNPJ***]" in result["resp_text"]
    assert "[CPF***]" in result["resp_text"]


def test_pluggy_error_body_email_redacted() -> None:
    corpo_erro = (
        "validation error: field 'email' value 'cliente@pluggy.com.br' rejected"
    )
    result = _run({
        "event": "pluggy.webhook_error",
        "erro": corpo_erro,
    })
    assert "cliente@pluggy.com.br" not in result["erro"]
    assert "[EMAIL***]" in result["erro"]


# ── 7. Resiliência — processador não pode crashar ────────────────────────────


def test_processor_nao_lanca_em_event_dict_vazio() -> None:
    result = _run({})
    # Não levantou — retornou o dict (mesmo que vazio)
    assert isinstance(result, dict)


def test_processor_nao_lanca_com_chave_nao_string() -> None:
    """Chaves numéricas (edge case) não devem causar AttributeError."""
    result = _run({"event": "ok", 42: "valor"})  # type: ignore[arg-type]
    assert result["event"] == "ok"


def test_processor_retorna_event_dict_sempre() -> None:
    """Contrato: processador SEMPRE retorna o event_dict."""
    event_dict: dict[str, Any] = {
        "event": "teste",
        "senha": "secreta",
        "cpf": "123.456.789-09",
    }
    result = _run(event_dict)
    assert isinstance(result, dict)
    assert "event" in result
