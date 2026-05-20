from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.empresa.onboarding import (
    derivar_regime_por_porte,
    mapear_dados_brasil_api,
    sugerir_anexo_simples,
)
from app.modules.empresa.schemas import (
    EmpresaIn,
    EmpresaOut,
    OnboardingCnpjIn,
    OnboardingResultadoOut,
)
from app.modules.empresa.service import EmpresaService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["empresas"])
_service = EmpresaService()


@router.post(
    "",
    response_model=EmpresaOut,
    status_code=201,
    summary="Cadastra empresa no tenant",
)
async def criar_empresa(
    payload: EmpresaIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EmpresaOut:
    empresa = await _service.criar(session, ctx, payload)
    return EmpresaOut.model_validate(empresa)


@router.get(
    "",
    response_model=list[EmpresaOut],
    summary="Lista empresas do tenant (RLS ativo)",
)
async def listar_empresas(session: SessionDep) -> list[EmpresaOut]:
    empresas = await _service.listar(session)
    return [EmpresaOut.model_validate(e) for e in empresas]


@router.get(
    "/{empresa_id}",
    response_model=EmpresaOut,
    summary="Busca empresa por ID (RLS ativo)",
)
async def buscar_empresa(empresa_id: UUID, session: SessionDep) -> EmpresaOut:
    empresa = await _service.buscar(session, empresa_id)
    return EmpresaOut.model_validate(empresa)


@router.post(
    "/onboarding",
    response_model=OnboardingResultadoOut,
    status_code=200,
    summary="Onboarding por CNPJ — consulta Receita Federal e sugere regime",
    description=(
        "Consulta a BrasilAPI (Receita Federal) para o CNPJ informado, deriva o regime "
        "tributário provável e cria a empresa automaticamente no tenant. "
        "Cache de 30 dias na BrasilAPI. Idempotente: se empresa já existe retorna os dados."
    ),
)
async def onboarding_por_cnpj(
    payload: OnboardingCnpjIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> OnboardingResultadoOut:
    """Onboarding via CNPJ: BrasilAPI → regime sugerido → cria empresa."""
    from decimal import Decimal

    from app.shared.exceptions import CnpjJaCadastrado

    brasil_api = getattr(request.app.state, "brasil_api_client", None)
    if brasil_api is None:
        from app.shared.exceptions import BrasilApiIndisponivel

        raise BrasilApiIndisponivel("BrasilAPI não configurada neste ambiente")

    dados_raw = await brasil_api.consultar_cnpj(payload.cnpj)
    dados = mapear_dados_brasil_api(dados_raw)

    regime_sugerido = derivar_regime_por_porte(
        porte=str(dados.get("porte", "")),
        faturamento_anual=payload.faturamento_12m,
        cnae_principal=str(dados.get("cnae_principal", "")),
    )
    anexo_sugerido = sugerir_anexo_simples(str(dados.get("cnae_principal", "")) or None)

    resultado = OnboardingResultadoOut(
        cnpj=payload.cnpj,
        razao_social=str(dados.get("razao_social", "")),
        nome_fantasia=str(dados.get("nome_fantasia", "")) or None,
        porte=str(dados.get("porte", "")),
        situacao_cadastral=str(dados.get("situacao", "")),
        cnae_principal=str(dados.get("cnae_principal", "")) or None,
        cnae_descricao=str(dados.get("cnae_descricao", "")) or None,
        municipio=str(dados.get("municipio", "")) or None,
        uf=str(dados.get("uf", "")) or None,
        regime_sugerido=regime_sugerido,
        anexo_sugerido=anexo_sugerido,
    )

    # Cria a empresa automaticamente com os dados derivados
    empresa_in = EmpresaIn(
        cnpj=payload.cnpj,
        razao_social=str(dados.get("razao_social", "Empresa")),
        nome_fantasia=str(dados.get("nome_fantasia", "")) or None,
        regime_tributario=regime_sugerido,
        anexo_simples=anexo_sugerido,
        cnae_principal=str(dados.get("cnae_principal", "")) or None,
        municipio=str(dados.get("municipio", "")) or None,
        uf=str(dados.get("uf", "")) or None,
        faturamento_12m=payload.faturamento_12m,
    )
    try:
        empresa = await _service.criar(session, ctx, empresa_in)
        resultado.empresa_criada = EmpresaOut.model_validate(empresa)
    except CnpjJaCadastrado:
        resultado.aviso = "CNPJ já cadastrado neste tenant — empresa existente mantida."

    return resultado
