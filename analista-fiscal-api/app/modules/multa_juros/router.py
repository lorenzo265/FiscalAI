from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter

from app.modules.multa_juros.schemas import SimularMoraIn, SimularMoraOut
from app.modules.multa_juros.service import simular_denuncia_espontanea, simular_mora
from app.shared.db.deps import SessionDep, TenantDep

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/empresas/{empresa_id}/multa-juros", tags=["multa-juros"])


@router.post(
    "/simular",
    response_model=SimularMoraOut,
    summary="Simula multa e juros de mora (pagamento em atraso)",
    status_code=200,
)
async def simular_multa_juros(
    empresa_id: UUID,
    payload: SimularMoraIn,
    _tenant: TenantDep,
    session: SessionDep,
) -> SimularMoraOut:
    """Calcula mora ordinária por pagamento em atraso (Lei 9.430/1996, art. 61, §2º).

    Componentes retornados:
    - **multa_mora**: 0,33%/dia sobre o principal, teto 20% (~61º dia).
    - **juros_selic**: SELIC acumulada (meses cheios após vencimento, sem o mês do pagamento).
    - **acrescimo_mes_pagamento**: 1% fixo referente ao mês em que ocorre o pagamento.

    Use este endpoint para simular o valor total de um DARF ou DAS em atraso.
    Para denúncia espontânea (sem multa), use `/denuncia-espontanea`.
    Nenhum dado é persistido.
    """
    log.info(
        "multa_juros.simular",
        empresa_id=str(empresa_id),
        dias=str(payload.data_pagamento - payload.data_vencimento),
    )
    return await simular_mora(payload, session)


@router.post(
    "/denuncia-espontanea",
    response_model=SimularMoraOut,
    summary="Simula acréscimos para denúncia espontânea (CTN art. 138)",
    status_code=200,
)
async def simular_denuncia_espontanea_endpoint(
    empresa_id: UUID,
    payload: SimularMoraIn,
    _tenant: TenantDep,
    session: SessionDep,
) -> SimularMoraOut:
    """Calcula acréscimos para pagamento em denúncia espontânea (CTN art. 138).

    Na denúncia espontânea o contribuinte confessa o débito e paga integralmente
    antes de qualquer ato de ofício da Receita Federal. Por força do CTN art. 138,
    a **multa é excluída**. Apenas SELIC e o acréscimo de 1% do mês são devidos.

    Campos retornados:
    - **multa_mora**: sempre R$ 0,00 (afastada pelo CTN art. 138).
    - **juros_selic**: SELIC acumulada (meses cheios após vencimento).
    - **acrescimo_mes_pagamento**: 1% fixo referente ao mês do pagamento.

    Para mora ordinária (com multa), use `/simular`.
    Nenhum dado é persistido.
    """
    log.info(
        "multa_juros.denuncia_espontanea",
        empresa_id=str(empresa_id),
        dias=str(payload.data_pagamento - payload.data_vencimento),
    )
    return await simular_denuncia_espontanea(payload, session)
