from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.schemas import (
    LoginIn,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    TokenOut,
)
from app.modules.auth.service import AuthService
from app.shared.db.deps import AnonSessionDep, SystemSessionDep

router = APIRouter(prefix="/auth", tags=["auth"])
_service = AuthService()


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=201,
    summary="Cria tenant + usuário admin",
)
async def register(payload: RegisterIn, session: AnonSessionDep) -> RegisterOut:
    tenant, usuario, token, expires_in, refresh = await _service.registrar(
        session, payload
    )
    from app.modules.auth.schemas import TenantOut, UsuarioOut

    return RegisterOut(
        access_token=token,
        expires_in=expires_in,
        refresh_token=refresh,
        usuario=UsuarioOut.model_validate(usuario),
        tenant=TenantOut.model_validate(tenant),
    )


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Autentica e retorna JWT",
)
async def login(payload: LoginIn, session: AnonSessionDep) -> TokenOut:
    token, expires_in, refresh = await _service.login(session, payload)
    return TokenOut(access_token=token, expires_in=expires_in, refresh_token=refresh)


@router.post(
    "/refresh",
    response_model=TokenOut,
    summary="Rotaciona o refresh token e emite novo access token",
)
async def refresh(payload: RefreshIn, session: SystemSessionDep) -> TokenOut:
    token, expires_in, novo_refresh = await _service.renovar(
        session, raw_token=payload.refresh_token
    )
    return TokenOut(
        access_token=token, expires_in=expires_in, refresh_token=novo_refresh
    )
