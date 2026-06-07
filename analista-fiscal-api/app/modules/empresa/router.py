from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Request

from app.modules.empresa.ibge import resolver_ibge
from app.modules.empresa.onboarding import (
    derivar_regime_por_porte,
    mapear_dados_brasil_api,
    sugerir_anexo_simples,
)
from app.modules.empresa.onboarding_bundle import OnboardingBundleService
from app.modules.empresa.schemas import (
    EmpresaIn,
    EmpresaOut,
    EmpresaUpdateIn,
    MunicipioIbgeIn,
    OnboardingBundleIn,
    OnboardingBundleOut,
    OnboardingCnpjIn,
    OnboardingResultadoOut,
)
from app.modules.empresa.service import EmpresaService
from app.shared.db.deps import SessionDep, TenantDep

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/empresas", tags=["empresas"])
_service = EmpresaService()
_onboarding_bundle = OnboardingBundleService()


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


@router.put(
    "/{empresa_id}",
    response_model=EmpresaOut,
    summary="Atualiza dados cadastrais da empresa (RLS ativo)",
    description=(
        "Atualização parcial dos campos de negócio (razão social, nome "
        "fantasia, regime, anexo, CNAE, município/IBGE/UF, IE/IM, faturamento "
        "12m). Campos omitidos ficam inalterados. O CNPJ é imutável e não é "
        "aceito. Mudança de regime re-deriva o perfil_ui automaticamente."
    ),
)
async def atualizar_empresa(
    empresa_id: UUID,
    payload: EmpresaUpdateIn,
    session: SessionDep,
) -> EmpresaOut:
    empresa = await _service.atualizar(session, empresa_id, payload)
    return EmpresaOut.model_validate(empresa)


@router.post(
    "/{empresa_id}/iss-validada",
    response_model=EmpresaOut,
    summary="Confirma que a alíquota ISS da empresa foi validada pelo contador",
    description=(
        "Após validação manual da alíquota ISS, o aviso `aviso_iss` deixa de "
        "aparecer nas emissões NFS-e subsequentes (m5 da auditoria Sprints 4-6)."
    ),
)
async def confirmar_iss_validada(
    empresa_id: UUID,
    session: SessionDep,
) -> EmpresaOut:
    empresa = await _service.marcar_iss_validada(session, empresa_id)
    return EmpresaOut.model_validate(empresa)


@router.patch(
    "/{empresa_id}/municipio-ibge",
    response_model=EmpresaOut,
    summary="Atualiza código IBGE 7-dígitos do município (PATCH manual)",
    description=(
        "Usado quando o resolver automático no onboarding não encontra match "
        "exato entre o nome retornado pela BrasilAPI e a tabela IBGE da UF. "
        "Sem código IBGE válido, emissão de NFS-e e transmissão de PGDAS-D "
        "falham com erro 422 (MunicipioIbgeAusente)."
    ),
)
async def atualizar_municipio_ibge_empresa(
    empresa_id: UUID,
    payload: MunicipioIbgeIn,
    session: SessionDep,
) -> EmpresaOut:
    empresa = await _service.atualizar_municipio_ibge(
        session, empresa_id, payload.codigo_municipio_ibge
    )
    return EmpresaOut.model_validate(empresa)


@router.post(
    "/onboarding",
    response_model=OnboardingResultadoOut,
    status_code=200,
    summary="Onboarding por CNPJ — consulta Receita Federal e sugere regime",
    description=(
        "Consulta a BrasilAPI (Receita Federal) para o CNPJ informado, deriva o regime "
        "tributário provável, resolve o código IBGE 7-dígitos do município "
        "(via ``/ibge/municipios/v1/{uf}``) e cria a empresa automaticamente no tenant. "
        "Cache de 30 dias na BrasilAPI. Idempotente: se empresa já existe retorna os dados."
    ),
)
async def onboarding_por_cnpj(
    payload: OnboardingCnpjIn,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> OnboardingResultadoOut:
    """Onboarding via CNPJ: BrasilAPI → regime sugerido → IBGE → cria empresa."""
    from app.shared.exceptions import CnpjJaCadastrado

    brasil_api = getattr(request.app.state, "brasil_api_client", None)
    if brasil_api is None:
        from app.shared.exceptions import BrasilApiIndisponivel

        raise BrasilApiIndisponivel("BrasilAPI não configurada neste ambiente")

    dados_raw = await brasil_api.consultar_cnpj(payload.cnpj)
    dados = mapear_dados_brasil_api(dados_raw)

    nome_municipio = str(dados.get("municipio", "")) or None
    uf = str(dados.get("uf", "")) or None
    codigo_ibge: str | None = None
    if nome_municipio and uf:
        try:
            municipios_uf = await brasil_api.listar_municipios_uf(uf)
            codigo_ibge = resolver_ibge(nome_municipio, municipios_uf)
        except Exception as exc:
            # Fail-open: onboarding continua sem IBGE; service de emissão/transmissão
            # levanta MunicipioIbgeAusente quando precisar. PATCH manual cobre o gap.
            log.warning(
                "empresa.ibge_lookup_falhou",
                cnpj_prefixo=payload.cnpj[:8],
                uf=uf,
                erro=str(exc),
            )

    if nome_municipio and uf and codigo_ibge is None:
        log.warning(
            "empresa.ibge_nao_resolvido",
            cnpj_prefixo=payload.cnpj[:8],
            nome_municipio=nome_municipio,
            uf=uf,
        )

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
        municipio=nome_municipio,
        codigo_municipio_ibge=codigo_ibge,
        uf=uf,
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
        municipio=nome_municipio,
        codigo_municipio_ibge=codigo_ibge,
        uf=uf,
        faturamento_12m=payload.faturamento_12m,
    )
    try:
        empresa = await _service.criar(session, ctx, empresa_in)
        resultado.empresa_criada = EmpresaOut.model_validate(empresa)
    except CnpjJaCadastrado:
        resultado.aviso = "CNPJ já cadastrado neste tenant — empresa existente mantida."

    return resultado


@router.post(
    "/{empresa_id}/onboarding/bundle",
    response_model=OnboardingBundleOut,
    status_code=201,
    summary="Bootstrap self-service: plano de contas + checklist por perfil_ui",
    description=(
        "Bundle do onboarding (Sprint 19 PR4) — chamar logo após criar a empresa. "
        "Clona o plano de contas referencial RFB (36 contas) e retorna checklist "
        "de próximos passos contextualizada por ``perfil_ui``. Idempotente — "
        "re-chamada não duplica nem regrede. Bloqueia com HTTP 409 se já houver "
        "lote de importação SPED concluído (plano da empresa vem do SPED, não "
        "do referencial)."
    ),
)
async def onboarding_bundle(
    empresa_id: UUID,
    payload: OnboardingBundleIn,
    ctx: TenantDep,
    session: SessionDep,
) -> OnboardingBundleOut:
    from datetime import date as _date

    valid_from = _date.fromisoformat(payload.valid_from) if payload.valid_from else _date.today()
    return await _onboarding_bundle.executar(
        session,
        ctx.tenant_id,
        empresa_id,
        valid_from=valid_from,
        welcome_digest_optin=payload.welcome_digest_optin,
    )
