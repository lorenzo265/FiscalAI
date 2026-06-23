from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MensagemRecebidaIn(BaseModel):
    """Mensagem extraída do webhook Meta, já verificada via HMAC."""

    model_config = ConfigDict(extra="ignore")

    phone: str
    mensagem_id: str
    texto: str | None
    tipo: str


class WebhookVerificacaoOut(BaseModel):
    """Resposta ao challenge de verificação do webhook Meta."""

    challenge: str


class RespostaWhatsApp(BaseModel):
    """Resultado do processamento de uma mensagem para o remetente."""

    phone: str
    texto: str
    tipo: str = "resposta"  # "resposta" | "fallback" | "marketplace" | "dashboard"


class SessaoWhatsAppOut(BaseModel):
    """Estado atual da sessão de conversa."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone: str
    empresa_id: UUID
    mensagens_na_sessao: int
