from __future__ import annotations

from fastapi import APIRouter

from app.modules.auth.schemas import LoginIn, RegisterIn, RegisterOut, TokenOut
from app.modules.auth.service import AuthService
from app.shared.db.deps import AnonSessionDep

router = APIRouter(prefix="/auth", tags=["auth"])
_service = AuthService()


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=201,
    summary="Cria tenant + usuário admin",
)
async def register(payload: RegisterIn, session: AnonSessionDep) -> RegisterOut:
    tenant, usuario, token, expires_in = await _service.registrar(session, payload)
    from app.modules.auth.schemas import TenantOut, UsuarioOut

    return RegisterOut(
        access_token=token,
        expires_in=expires_in,
        usuario=UsuarioOut.model_validate(usuario),
        tenant=TenantOut.model_validate(tenant),
    )


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Autentica e retorna JWT",
)
async def login(payload: LoginIn, session: AnonSessionDep) -> TokenOut:
    token, expires_in = await _service.login(session, payload)
    return TokenOut(access_token=token, expires_in=expires_in)
