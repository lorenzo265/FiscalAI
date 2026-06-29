"""Integração de e-mail transacional (Marco 4 PR3 #14).

Provedor Resend (atrás de env) + fake para dev/teste, e templates puros
(onboarding, fatura, alerta fiscal). Camada 4 (integrações externas).
"""

from app.shared.integrations.email.provider import (
    EmailProvider,
    ResendProvider,
    build_email_provider,
)
from app.shared.integrations.email.templates import (
    renderizar_alerta_fiscal,
    renderizar_fatura,
    renderizar_onboarding,
)
from app.shared.integrations.email.types import (
    EmailEnviado,
    EmailMessage,
    TipoEmail,
)

__all__ = [
    "EmailEnviado",
    "EmailMessage",
    "EmailProvider",
    "ResendProvider",
    "TipoEmail",
    "build_email_provider",
    "renderizar_alerta_fiscal",
    "renderizar_fatura",
    "renderizar_onboarding",
]
