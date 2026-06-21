from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.modules.fiscal.schemas import ApuracaoDASIn, ApuracaoDASOut
from app.modules.fiscal.service import FiscalService
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.db.models import ApuracaoFiscal
from app.shared.exceptions import (
    ApuracaoJaExiste,
    ApuracaoNaoEncontrada,
    EmpresaForaSimplesNacional,
    EmpresaNaoEncontrada,
    FatorRObrigatorio,
    RegimeIncompativel,
    TabelaTributariaAusente,
)

router = APIRouter(prefix="/v1/empresas", tags=["fiscal"])


def _apuracao_to_out(ap: ApuracaoFiscal) -> ApuracaoDASOut:
    out = ap.output_jsonb
    from decimal import Decimal

    sublimite_str = out.get("sublimite_aplicado")
    rbt12_prop_str = out.get("rbt12_proporcionalizado")
    return ApuracaoDASOut(
        id=ap.id,
        empresa_id=ap.empresa_id,
        competencia=ap.competencia,
        tipo=ap.tipo,
        regime=ap.regime,
        anexo=out.get("anexo", ""),
        anexo_efetivo=out.get("anexo_efetivo", ""),
        faixa=int(out.get("faixa", 0)),
        rbt12_usado=Decimal(out.get("rbt12_usado", "0")),
        aliquota_nominal=Decimal(out.get("aliquota_nominal", "0")),
        aliquota_efetiva=Decimal(out.get("aliquota_efetiva", "0")),
        receita_mes=Decimal(out.get("receita_mes", "0")),
        valor_das=Decimal(out.get("valor_das", "0")),
        fator_r=Decimal(out["fator_r"]) if out.get("fator_r") else None,
        algoritmo_versao=out.get("algoritmo_versao", ""),
        status=ap.status,
        uf=out.get("uf"),
        sublimite_aplicado=Decimal(sublimite_str) if sublimite_str else None,
        sublimite_excedido=bool(out.get("sublimite_excedido", False)),
        rbt12_proporcionalizado=Decimal(rbt12_prop_str) if rbt12_prop_str else None,
    )


@router.post(
    "/{empresa_id}/apuracoes/das",
    response_model=ApuracaoDASOut,
    status_code=201,
    summary="Calcular DAS — Simples Nacional",
)
async def calcular_das(
    empresa_id: UUID,
    payload: ApuracaoDASIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoDASOut:
    service = FiscalService(session)
    try:
        apuracao = await service.calcular_e_salvar_das(ctx.tenant_id, empresa_id, payload)
    except EmpresaNaoEncontrada as e:
        raise e
    except RegimeIncompativel as e:
        raise e
    except FatorRObrigatorio as e:
        raise e
    except EmpresaForaSimplesNacional as e:
        raise e
    except ApuracaoJaExiste as e:
        raise e
    except TabelaTributariaAusente as e:
        raise e
    return _apuracao_to_out(apuracao)


@router.get(
    "/{empresa_id}/apuracoes/{competencia}/das",
    response_model=ApuracaoDASOut,
    summary="Consultar DAS calculado",
)
async def consultar_das(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> ApuracaoDASOut:
    service = FiscalService(session)
    try:
        apuracao = await service.buscar_das(empresa_id, competencia)
    except ApuracaoNaoEncontrada as e:
        raise e
    return _apuracao_to_out(apuracao)
