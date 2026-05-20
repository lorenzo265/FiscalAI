from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import jwt

from app.config import get_settings
from app.shared.exceptions import TokenInvalido

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Contexto de tenant extraído do JWT — propagado para RLS via Depends."""

    tenant_id: UUID
    usuario_id: UUID


def criar_token(ctx: TenantContext) -> tuple[str, int]:
    """Cria access token JWT. Retorna (token, expires_in_seconds)."""
    settings = get_settings()
    agora = datetime.now(_TZ_BR)
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    exp = agora + timedelta(seconds=expires_in)

    payload: dict[str, str | int] = {
        "sub": str(ctx.usuario_id),
        "tid": str(ctx.tenant_id),
        "iat": int(agora.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def verificar_token(token: str) -> TenantContext:
    """Decodifica e valida JWT. Lança TokenInvalido se inválido ou expirado."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TenantContext(
            tenant_id=UUID(str(payload["tid"])),
            usuario_id=UUID(str(payload["sub"])),
        )
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise TokenInvalido("Token inválido ou expirado") from exc
