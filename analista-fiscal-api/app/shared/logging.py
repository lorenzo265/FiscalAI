from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.config import Environment, Settings

# ── Padrões PII compilados em tempo de módulo (evitar recompilação por log) ──
# Ordem importa: CNPJ (14 dígitos) ANTES de CPF (11 dígitos) para evitar
# que o match de CPF capture os primeiros 11 dígitos de um CNPJ.
_RE_CNPJ = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
_RE_CPF = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_PHONE = re.compile(r"\+?\d{2}\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}")

# Chaves cujos VALORES são considerados sensíveis (comparação case-insensitive
# por substring). Divididas em dois grupos conforme nível de mascaramento:
#   - _KEYS_FULL: valor inteiramente substituído por "***"
#   - _KEYS_PREFIX: primeiros 4 chars + "***" (debuggabilidade)
_KEYS_FULL = frozenset(
    {"senha", "password", "token", "secret", "authorization", "bearer"}
)
_KEYS_PREFIX = frozenset({"email", "cpf", "cnpj", "telefone", "phone"})


def _mask_full(value: str) -> str:
    """Substitui completamente — sem prefixo identificável."""
    return "***"


def _mask_prefix(value: str) -> str:
    """Mantém prefixo de 4 chars para debuggabilidade (ex.: 'jo.s***')."""
    return value[:4] + "***" if len(value) > 4 else "***"


def _mask_patterns_in_string(text: str) -> str:
    """Varre a string e mascara qualquer CNPJ/CPF/e-mail/telefone encontrado.

    Ordem de aplicação (evitar matches parciais entre padrões sobrepostos):
    1. CNPJ  — 14+ dígitos (mais longo; antes do CPF de 11 dígitos)
    2. Phone — pode conter sequência numérica longa (antes do CPF)
    3. CPF   — 11 dígitos (após CNPJ e phone já mascarados)
    4. Email — separado por '@', sem sobreposição com os anteriores
    """
    text = _RE_CNPJ.sub("[CNPJ***]", text)
    text = _RE_PHONE.sub("[PHONE***]", text)
    text = _RE_CPF.sub("[CPF***]", text)
    text = _RE_EMAIL.sub("[EMAIL***]", text)
    return text


def _redact_pii(
    logger: WrappedLogger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: EventDict,
) -> EventDict:
    """Processador structlog que redige PII antes de qualquer renderer.

    Dois mecanismos de redação:

    1. **Por chave**: se a chave do evento (case-insensitive) contém uma
       palavra sensível, substitui o valor string — preservando não-str
       intactos (int, Decimal, None, etc.).

    2. **Por padrão regex**: varre o campo ``event`` (mensagem) e cada valor
       string do event_dict em busca de CPF/CNPJ/e-mail/telefone e mascara
       os matches. Resolve o vazamento de corpo de erro de APIs upstream
       (ex.: ``resp.text[:300]`` com CNPJ embutido).

    Não levanta — qualquer exceção interna retorna o event_dict sem crash.
    """
    try:
        _redact_pii_inplace(event_dict)
    except Exception:
        # Redação não pode derrubar o log — silencia qualquer falha interna.
        pass
    return event_dict


def _redact_pii_inplace(event_dict: EventDict) -> None:
    """Aplica redação in-place no event_dict."""
    # 1. Redação por chave
    for key in list(event_dict.keys()):
        if not isinstance(key, str):
            continue
        key_lower = key.lower()
        value = event_dict[key]
        if not isinstance(value, str):
            continue  # ints, Decimal, None, nested dicts — passam intactos

        if any(sensitive in key_lower for sensitive in _KEYS_FULL):
            event_dict[key] = _mask_full(value)
        elif any(sensitive in key_lower for sensitive in _KEYS_PREFIX):
            event_dict[key] = _mask_prefix(value)

    # 2. Redação por padrão regex na mensagem de evento
    event = event_dict.get("event")
    if isinstance(event, str):
        event_dict["event"] = _mask_patterns_in_string(event)

    # 3. Redação por padrão regex em todos os valores string restantes
    for key, value in event_dict.items():
        if not isinstance(value, str) or key == "event":
            continue
        # Só roda regex se o valor não foi já substituído por chave (***-only)
        if "***" not in value:
            event_dict[key] = _mask_patterns_in_string(value)


def configurar_logging(settings: Settings) -> None:
    """Configura structlog para JSON em prod e console colorido em local/dev.

    O processador ``_redact_pii`` é inserido antes de qualquer renderer,
    garantindo que CPF/CNPJ/e-mail/telefone e chaves sensíveis (senha,
    token, secret, authorization) nunca cheguem ao Loki/stdout em claro.
    Isso cobre tanto disciplina de call-site quanto corpo de erro de APIs
    upstream (serpro/pluggy resp.text com CNPJ embutido).
    """
    nivel = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=nivel,
    )

    processadores: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_pii,  # LGPD §8.7 — antes de qualquer renderer
    ]

    if settings.ENVIRONMENT in (Environment.LOCAL, Environment.DEV):
        processadores.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processadores.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processadores,
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


__all__ = ["configurar_logging", "_redact_pii"]
