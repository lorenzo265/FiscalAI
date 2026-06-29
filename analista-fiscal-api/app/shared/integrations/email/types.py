"""Tipos do contrato de e-mail transacional (Marco 4 PR3 #14)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TipoEmail(StrEnum):
    """Templates transacionais suportados."""

    ONBOARDING = "onboarding"
    FATURA = "fatura"
    ALERTA_FISCAL = "alerta_fiscal"


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """Mensagem pronta pra envio — corpo já renderizado (HTML + texto).

    ``to`` é o destinatário (e-mail único). ``texto`` é o fallback
    plain-text obrigatório (acessibilidade + clientes sem HTML).
    ``remetente`` None usa o default do provider (``EMAIL_FROM``).
    """

    to: str
    assunto: str
    html: str
    texto: str
    remetente: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EmailEnviado:
    """Resultado de um envio — id do provedor + nome do provider."""

    provider: str
    message_id: str
