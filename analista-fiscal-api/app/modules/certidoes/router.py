"""Endpoints REST de certidões (Sprint 6)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.modules.certidoes.repo import CertidoesRepo
from app.modules.certidoes.schemas import (
    CertidaoOut,
    CertidaoStatus,
    CertidaoTipo,
    EmitirCertidaoOut,
)
from app.modules.certidoes.scrapers import (
    CndtScraper,
    CrfScraper,
    NotImplementedScraper,
)
from app.modules.certidoes.service import CertidoesService
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["certidoes"])


@router.post(
    "/{empresa_id}/certidoes/{tipo}",
    response_model=EmitirCertidaoOut,
    status_code=202,
    summary="Emitir certidão fiscal (CND/CRF/CNDT)",
    description=(
        "Solicita a emissão da certidão indicada. CND é emitida via SERPRO "
        "Integra Contador. CRF e CNDT registram emissão como 'processando' "
        "(integração automática chega no PR3 da Sprint 6)."
    ),
)
async def emitir(
    empresa_id: UUID,
    tipo: CertidaoTipo,
    ctx: TenantDep,
    session: SessionDep,
    request: Request,
) -> EmitirCertidaoOut:
    serpro_client = getattr(request.app.state, "serpro_client", None)
    crf_scraper, cndt_scraper = _resolver_scrapers(request)
    service = CertidoesService()
    return await service.emitir(
        session,
        ctx.tenant_id,
        empresa_id,
        tipo,
        serpro_client=serpro_client,
        crf_scraper=crf_scraper,
        cndt_scraper=cndt_scraper,
    )


def _resolver_scrapers(
    request: Request,
) -> tuple[CrfScraper | None, CndtScraper | None]:
    """Sprint 19.6 PR1 (#3): factory dos scrapers baseado em settings.

    Default ``not_implemented`` retorna ``NotImplementedScraper`` —
    Service captura ``CertidaoEmissaoFalhou`` e cai no path legado
    (status='processando' + mensagem manual). Quando provider real
    estiver instalado, factory devolve instância real.
    """
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        return None, None
    crf_provider = getattr(settings, "CRF_SCRAPER_PROVIDER", "not_implemented")
    cndt_provider = getattr(settings, "CNDT_SCRAPER_PROVIDER", "not_implemented")
    crf: CrfScraper | None = (
        NotImplementedScraper(tipo="CRF")
        if crf_provider == "not_implemented"
        else None  # provider real entra aqui em PR futuro
    )
    cndt: CndtScraper | None = (
        NotImplementedScraper(tipo="CNDT")
        if cndt_provider == "not_implemented"
        else None
    )
    return crf, cndt


@router.get(
    "/{empresa_id}/certidoes",
    response_model=list[CertidaoOut],
    summary="Listar certidões emitidas",
)
async def listar(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[CertidaoOut]:
    certidoes = await CertidoesRepo(session).listar(empresa_id)
    return [
        CertidaoOut(
            id=c.id,
            empresa_id=c.empresa_id,
            tipo=CertidaoTipo(c.tipo),
            numero=c.numero,
            status=CertidaoStatus(c.status),
            emitida_em=c.emitida_em,
            valid_until=c.valid_until,
            pdf_storage_key=c.pdf_storage_key,
        )
        for c in certidoes
    ]
