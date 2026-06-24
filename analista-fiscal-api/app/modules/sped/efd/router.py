"""Endpoints REST — SPED EFD-Contribuições mensal (Sprint 17 PR1).

Download e listagem usam os endpoints genéricos cross-tipo
(``app/modules/sped/router.py``). Aqui ficam apenas os ``POST`` de
geração específicos por tipo de EFD.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.sped.efd.schemas import (
    ArquivoSpedOut,
    GerarEfdContribuicoesIn,
    GerarEfdIcmsIpiIn,
)
from app.modules.sped.efd.service import (
    EfdContribuicoesService,
    EfdIcmsIpiService,
)
from app.modules.sped.storage import mover_blob_sped_best_effort
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.storage.deps import StorageDep

router = APIRouter(prefix="/v1/empresas", tags=["sped"])


@router.post(
    "/{empresa_id}/sped/efd-contribuicoes",
    response_model=ArquivoSpedOut,
    status_code=201,
    summary="Gera EFD-Contribuições mensal (PIS/Cofins)",
    description=(
        "Gera o arquivo SPED EFD-Contribuições do mês informado e o persiste "
        "como snapshot imutável em ``arquivo_sped``. Obrigatória apenas para "
        "Lucro Presumido e Lucro Real (IN RFB 1.252/2012) — MEI e Simples "
        "Nacional ficam dispensados.\n\n"
        "Idempotente §8.9: chamadas repetidas com mesma ``(empresa, "
        "competencia)`` devolvem 409 ``SpedJaGerado`` a menos que "
        "``forcar=true`` — nesse caso a versão anterior é marcada como "
        "``superseded_by``. Use ``GET .../sped/{tipo}/{sped_id}/download`` "
        "(quando disponível) para baixar o ``.txt``.\n\n"
        "**Transmissão é ato consciente do cliente (§8.12)**: o sistema "
        "NUNCA transmite ao Fisco. Cliente baixa o ``.txt`` e envia via "
        "PVA EFD-Contribuições com o certificado A1 próprio."
    ),
)
async def gerar_efd_contribuicoes(
    empresa_id: UUID,
    payload: GerarEfdContribuicoesIn,
    ctx: TenantDep,
    session: SessionDep,
    storage: StorageDep,
) -> ArquivoSpedOut:
    gerada = await EfdContribuicoesService().gerar(
        session,
        ctx.tenant_id,
        empresa_id,
        competencia=payload.competencia,
        forcar=payload.forcar,
    )
    await mover_blob_sped_best_effort(session, gerada.arquivo, storage)
    return ArquivoSpedOut.model_validate(gerada.arquivo)


@router.post(
    "/{empresa_id}/sped/efd-icms-ipi",
    response_model=ArquivoSpedOut,
    status_code=201,
    summary="Gera EFD ICMS-IPI mensal",
    description=(
        "Gera o arquivo SPED EFD ICMS-IPI do mês informado e o persiste "
        "como snapshot imutável em ``arquivo_sped``. Obrigatória para "
        "empresas com inscrição estadual (Ajuste SINIEF 02/2009) — comércio "
        "e indústria. Sem IE, retorna 422 ``EmpresaNaoElegivelEfd``.\n\n"
        "Idempotente §8.9: chamadas repetidas com mesma ``(empresa, "
        "competencia)`` devolvem 409 ``SpedJaGerado`` a menos que "
        "``forcar=true`` — nesse caso a versão anterior é marcada como "
        "``superseded_by``.\n\n"
        "**Transmissão é ato consciente do cliente (§8.12)**: o sistema "
        "NUNCA transmite ao Fisco. Cliente baixa o ``.txt`` e envia via "
        "PVA EFD ICMS-IPI com o certificado A1 próprio."
    ),
)
async def gerar_efd_icms_ipi(
    empresa_id: UUID,
    payload: GerarEfdIcmsIpiIn,
    ctx: TenantDep,
    session: SessionDep,
    storage: StorageDep,
) -> ArquivoSpedOut:
    gerada = await EfdIcmsIpiService().gerar(
        session,
        ctx.tenant_id,
        empresa_id,
        competencia=payload.competencia,
        forcar=payload.forcar,
    )
    await mover_blob_sped_best_effort(session, gerada.arquivo, storage)
    return ArquivoSpedOut.model_validate(gerada.arquivo)
