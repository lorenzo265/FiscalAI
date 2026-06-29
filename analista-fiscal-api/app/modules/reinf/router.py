"""Endpoints REST — EFD-Reinf (Sprint 11 PR2 + Marco 4 PR2 #11)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.modules.reinf.repo import EfdReinfRepo
from app.modules.reinf.schemas import (
    EventoReinfOut,
    RegistrarRetencaoIn,
    TipoEventoReinfIn,
)
from app.modules.reinf.service import ReinfService
from app.modules.reinf.transmissao_reinf_service import TransmissaoReinfService
from app.shared.competencia import parse_competencia_mensal
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["efd_reinf"])


@router.post(
    "/{empresa_id}/reinf/retencoes-pj",
    response_model=EventoReinfOut,
    status_code=201,
    summary="Registra retenção PJ→PJ (R-4020) com cálculo IR + CSRF",
    description=(
        "Calcula IRRF 1,5% (Lei 7.713/1988) + CSRF 4,65% (Lei 10.833/2003) "
        "conforme regime do TOMADOR (empresa atual). Tomador em SN/MEI é "
        "dispensado de toda retenção (LC 123/2006 art. 13 §13). Dispensa "
        "automática de CSRF quando total < R$10 (IN RFB 459/2004). "
        "Idempotente por (empresa, R-4020, referencia_id)."
    ),
)
async def registrar_retencao_pj(
    empresa_id: UUID,
    payload: RegistrarRetencaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoReinfOut:
    evento = await ReinfService().registrar_retencao_r4020(
        session, ctx.tenant_id, empresa_id, payload
    )
    return EventoReinfOut.model_validate(evento)


@router.get(
    "/{empresa_id}/reinf/eventos",
    response_model=list[EventoReinfOut],
    summary="Lista eventos EFD-Reinf da empresa",
)
async def listar_eventos_reinf(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoEventoReinfIn | None = None,
    periodo: str | None = None,
    limite: int = 100,
) -> list[EventoReinfOut]:
    tipo_str = tipo.value if tipo else None
    periodo_date = parse_competencia_mensal(periodo) if periodo else None
    rows = await EfdReinfRepo(session).listar_empresa(
        empresa_id,
        tipo_evento=tipo_str,
        periodo=periodo_date,
        limite=limite,
    )
    return [EventoReinfOut.model_validate(r) for r in rows]


# ── EFD-Reinf transmissão real (Marco 4 PR2 #11) ────────────────────────────


def _construir_servico_transmissao() -> TransmissaoReinfService:
    """Factory — instancia o pipeline com defaults do ambiente.

    Cert A1 não é resolvido aqui ainda: por padrão a flag está OFF e o
    assinador cai em ``NotImplementedXmldsigSigner``. Pre-piloto pago, o
    cert virá do storage criptografado (mesma pendência do eSocial).
    """
    from app.config import get_settings
    from app.shared.crypto.xmldsig import construir_assinador
    from app.shared.integrations.reinf.client import ReinfClient

    s = get_settings()
    assinador = construir_assinador(
        cert_p12_bytes=None,  # Pre-piloto: cert ainda não vai do banco.
        senha=None,
        transmissao_ativa=s.REINF_TRANSMISSAO_ATIVA,
    )
    cliente = ReinfClient(s)
    return TransmissaoReinfService(
        settings=s, assinador=assinador, cliente=cliente
    )


@router.post(
    "/{empresa_id}/reinf/eventos/{evento_id}/assinar",
    response_model=EventoReinfOut,
    summary="Aplica XMLDSig (cert A1) ao evento — passa pra status='assinado'",
    description=(
        "§8.12 — fail-soft: sem grupo opt-in 'esocial' instalado ou sem "
        "cert A1 configurado, devolve 412 e mantém evento em 'preparado'. "
        "Quando assinado, evento fica pronto pra transmissão em lote."
    ),
)
async def assinar_evento_reinf(
    empresa_id: UUID,
    evento_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoReinfOut:
    servico = _construir_servico_transmissao()
    evento = await servico.assinar_evento(session, evento_id)
    return EventoReinfOut.model_validate(evento)


@router.post(
    "/{empresa_id}/reinf/transmissao/lotes",
    summary="Envia eventos EFD-Reinf assinados pendentes (até REINF_LOTE_MAX)",
    description=(
        "Agrupa eventos com status='assinado' em lote, envia à recepção "
        "EFD-Reinf e atualiza status='em_lote'. Idempotente via UUID5 sobre "
        "o conjunto de IDs do lote. 412 se REINF_TRANSMISSAO_ATIVA=false."
    ),
    status_code=202,
)
async def transmitir_lote_reinf(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    cnpj_contribuinte: str,
) -> dict[str, str | int | None]:
    servico = _construir_servico_transmissao()
    recibo = await servico.transmitir_lote(
        session, empresa_id, cnpj_contribuinte=cnpj_contribuinte
    )
    if recibo is None:
        return {"protocolo": None, "estado": None, "eventos": 0}
    return {
        "protocolo": recibo.protocolo,
        "estado": int(recibo.estado),
        "eventos": len(recibo.eventos),
    }


@router.post(
    "/{empresa_id}/reinf/transmissao/lotes/{protocolo}/consultar",
    summary="Consulta recibo EFD-Reinf e aplica status final aos eventos",
    description=(
        "Polling explícito do recibo. Quando finalizado, marca cada evento "
        "como 'aceito' (recibo emitido) ou 'rejeitado'."
    ),
)
async def consultar_recibo_reinf(
    empresa_id: UUID,
    protocolo: str,
    ctx: TenantDep,
    session: SessionDep,
) -> dict[str, str | int]:
    servico = _construir_servico_transmissao()
    recibo = await servico._cliente.consultar_recibo(protocolo)
    atualizados = await servico.aplicar_recibo(session, recibo)
    return {
        "protocolo": recibo.protocolo,
        "estado": int(recibo.estado),
        "atualizados": atualizados,
    }
