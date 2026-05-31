"""Endpoints REST — painel admin de tabelas tributárias (Sprint 19.5 PR1).

9 endpoints sob ``/v1/admin/tabelas/``:

  * 7 POSTs (1 por tipo) que criam vigência via Camada 1 ``TabelaAdminService``.
  * ``GET /{tipo}/historico`` — lista logs de auditoria por tipo.
  * ``GET /{tipo}/vigente?em=YYYY-MM-DD`` — snapshot da vigência ativa.

Auth: todos os endpoints usam ``TaxTableAdminSessionDep`` (``X-Admin-Token``
+ role Postgres ``tax_table_admin``). Sem JWT — operação cross-tenant de
sistema, não autenticada por usuário PME nem por parceiro marketplace.

URL convention: usa kebab-case nas paths (``simples-nacional``,
``presuncao-lp``, ``icms-uf``, ``cbs-ibs``) seguindo o padrão do projeto;
internamente converte para snake_case (``simples_nacional`` etc.) — espelho
do CHECK constraint em ``vigencia_tabela_log.tipo_tabela``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final

from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query

from app.modules.tabelas_admin.alertas_repo import AlertaAdminRepo
from app.modules.tabelas_admin.alertas_schemas import (
    AlertaAdminOut,
    Severidade,
    SnoozeIn,
)
from app.modules.tabelas_admin.alertas_service import AlertaAdminService
from app.modules.tabelas_admin.repo import (
    SCDTabelasRepo,
    VigenciaTabelaLogRepo,
)
from app.modules.tabelas_admin.sugestoes_repo import SugestaoVigenciaRepo
from app.modules.tabelas_admin.sugestoes_schemas import (
    RejeitarSugestaoIn,
    StatusSugestao,
    SugestaoVigenciaOut,
)
from app.modules.tabelas_admin.sugestoes_service import (
    SugestaoVigenciaService,
)
from app.modules.tabelas_admin.schemas import (
    TIPOS_TABELA_SUPORTADOS,
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
    VigenciaSnapshotOut,
    VigenciaTabelaLogOut,
)
from app.modules.tabelas_admin.service import TabelaAdminService
from app.shared.db.deps import TaxTableAdminSessionDep
from app.shared.exceptions import TipoTabelaDesconhecido

router = APIRouter(prefix="/v1/admin/tabelas", tags=["admin-tabelas-tributarias"])


# Mapa kebab-case (URL) → snake_case (interno).
_URL_PARA_TIPO: Final[dict[str, str]] = {
    "inss": "inss",
    "irrf": "irrf",
    "fgts": "fgts",
    "simples-nacional": "simples_nacional",
    "presuncao-lp": "presuncao_lp",
    "icms-uf": "icms_uf",
    "cbs-ibs": "cbs_ibs",
}


def _resolver_tipo(tipo_url: str) -> str:
    interno = _URL_PARA_TIPO.get(tipo_url)
    if interno is None:
        raise TipoTabelaDesconhecido(
            f"tipo_tabela {tipo_url!r} desconhecido; suportados: "
            f"{list(_URL_PARA_TIPO.keys())}",
        )
    return interno


def _service(session: TaxTableAdminSessionDep) -> TabelaAdminService:
    return TabelaAdminService(
        log_repo=VigenciaTabelaLogRepo(session),
        scd_repo=SCDTabelasRepo(session),
        # Camada 2 (Sprint 19.5 PR2): auto-resolução de alertas relacionados
        # no mesmo commit que cria a vigência.
        alerta_repo=AlertaAdminRepo(session),
    )


def _alerta_service(session: TaxTableAdminSessionDep) -> AlertaAdminService:
    return AlertaAdminService(
        alerta_repo=AlertaAdminRepo(session),
        scd_repo=SCDTabelasRepo(session),
    )


def _sugestao_service(
    session: TaxTableAdminSessionDep,
) -> SugestaoVigenciaService:
    """Camada 3: aprovar reusa o TabelaAdminService (PR1 + PR2 wiring)."""
    return SugestaoVigenciaService(
        sugestao_repo=SugestaoVigenciaRepo(session),
        tabela_admin_service=_service(session),
    )


# ── POSTs (1 por tipo) ──────────────────────────────────────────────────────


@router.post(
    "/inss/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência da tabela INSS (Portaria MPS/MF)",
    description=(
        "Aceita JSON da Portaria publicada (faixas progressivas + alíquotas + "
        "fonte_norma com citação completa). Idempotente §8.9: re-POST com "
        "mesma idempotency_key + mesmo payload devolve o log anterior. "
        "Resolve estruturalmente as pendências #9 (INSS 2026) e #37 (INSS 2024)."
    ),
)
async def criar_vigencia_inss(
    payload: VigenciaInssIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_inss(session, payload)
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/irrf/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência da tabela IRRF mensal (Lei + Portaria RFB)",
)
async def criar_vigencia_irrf(
    payload: VigenciaIrrfIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_irrf(session, payload)
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/fgts/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência da tabela FGTS (Lei 8.036/1990 + alterações)",
)
async def criar_vigencia_fgts(
    payload: VigenciaFgtsIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_fgts(session, payload)
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/simples-nacional/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência de um anexo do Simples Nacional (Resolução CGSN)",
)
async def criar_vigencia_simples_nacional(
    payload: VigenciaSimplesNacionalIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_simples_nacional(
        session, payload
    )
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/presuncao-lp/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência da presunção LP (Lei 9.249/1995)",
)
async def criar_vigencia_presuncao_lp(
    payload: VigenciaPresuncaoLpIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_presuncao_lp(
        session, payload
    )
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/icms-uf/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência ICMS por UF (lei estadual + convênio CONFAZ)",
)
async def criar_vigencia_icms_uf(
    payload: VigenciaIcmsUfIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_icms_uf(session, payload)
    return VigenciaTabelaLogOut.model_validate(log)


@router.post(
    "/cbs-ibs/vigencia",
    response_model=VigenciaTabelaLogOut,
    summary="Cria nova vigência CBS/IBS (LC 214/2025 + PLP 68/2024)",
)
async def criar_vigencia_cbs_ibs(
    payload: VigenciaCbsIbsIn,
    session: TaxTableAdminSessionDep,
) -> VigenciaTabelaLogOut:
    log = await _service(session).criar_vigencia_cbs_ibs(session, payload)
    return VigenciaTabelaLogOut.model_validate(log)


# ── GETs ────────────────────────────────────────────────────────────────────


@router.get(
    "/{tipo}/historico",
    response_model=list[VigenciaTabelaLogOut],
    summary="Lista logs de auditoria do tipo de tabela (admin)",
)
async def listar_historico(
    session: TaxTableAdminSessionDep,
    tipo: Annotated[str, Path(description="Tipo de tabela em kebab-case")],
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[VigenciaTabelaLogOut]:
    tipo_interno = _resolver_tipo(tipo)
    logs = await _service(session).historico(tipo_interno, limit=limite)
    return [VigenciaTabelaLogOut.model_validate(li) for li in logs]


@router.get(
    "/{tipo}/vigente",
    response_model=VigenciaSnapshotOut,
    summary="Snapshot da vigência ativa em uma data (admin)",
    description=(
        "Devolve as linhas SCD ativas em ``em`` (default: hoje). UI consome "
        "para pré-visualizar antes de postar nova versão."
    ),
)
async def vigente_em(
    session: TaxTableAdminSessionDep,
    tipo: Annotated[str, Path(description="Tipo de tabela em kebab-case")],
    em: Annotated[date | None, Query()] = None,
) -> VigenciaSnapshotOut:
    tipo_interno = _resolver_tipo(tipo)
    data_alvo = em or date.today()
    registros = await _service(session).snapshot_vigente(tipo_interno, data_alvo)
    return VigenciaSnapshotOut(
        tipo_tabela=tipo_interno,
        em=data_alvo,
        registros=registros,
    )


# ── Alertas (Sprint 19.5 PR2) ───────────────────────────────────────────────
#
# Endpoints de alerta vivem em /v1/admin/alertas (sem /tabelas no prefixo).
# Router separado para evitar conflito com o prefix /v1/admin/tabelas do
# painel principal. Ambos são plugados em app/main.py com o mesmo guard
# tax_table_admin via ``TaxTableAdminSessionDep``.

alertas_router = APIRouter(prefix="/v1/admin/alertas", tags=["admin-alertas"])


@alertas_router.get(
    "",
    response_model=list[AlertaAdminOut],
    summary="Lista alertas do painel admin",
    description=(
        "Filtros opcionais: ``severidade`` (info|aviso|critico) e ``resolvido`` "
        "(false = abertos hoje; true = passado/resolvido)."
    ),
)
async def listar_alertas(
    session: TaxTableAdminSessionDep,
    severidade: Severidade | None = None,
    resolvido: bool | None = False,
    limite: int = Query(default=100, ge=1, le=500),
) -> list[AlertaAdminOut]:
    rows = await _alerta_service(session).listar(
        severidade=severidade, resolvido=resolvido, limite=limite
    )
    return [AlertaAdminOut.model_validate(r) for r in rows]


@alertas_router.post(
    "/{alerta_id}/resolver",
    response_model=AlertaAdminOut,
    summary="Marca alerta como resolvido",
)
async def resolver_alerta(
    alerta_id: UUID,
    session: TaxTableAdminSessionDep,
) -> AlertaAdminOut:
    alerta = await _alerta_service(session).resolver(session, alerta_id)
    if alerta is None:
        raise HTTPException(
            status_code=404, detail=f"Alerta {alerta_id} não encontrado"
        )
    return AlertaAdminOut.model_validate(alerta)


@alertas_router.post(
    "/{alerta_id}/snooze",
    response_model=AlertaAdminOut,
    summary="Adia alerta (default 30 dias, max 90)",
)
async def snooze_alerta(
    alerta_id: UUID,
    payload: SnoozeIn,
    session: TaxTableAdminSessionDep,
) -> AlertaAdminOut:
    alerta = await _alerta_service(session).snooze(
        session, alerta_id, dias=payload.dias
    )
    if alerta is None:
        raise HTTPException(
            status_code=404, detail=f"Alerta {alerta_id} não encontrado"
        )
    return AlertaAdminOut.model_validate(alerta)


@alertas_router.get(
    "/digest",
    summary="Digest admin completo (Sprint 19.6 PR3 #42)",
    description=(
        "Retorna texto markdown pronto pra envio via Meta WhatsApp / e-mail / "
        "Slack. Hook do digest admin do sistema — consumido por cron externo "
        "ou worker dedicado (Sprint futura) quando ADMIN_WHATSAPP_PHONE "
        "estiver configurado. Sem alertas críticos = mensagem curta "
        "'tudo em dia'."
    ),
)
async def digest_admin(
    session: TaxTableAdminSessionDep,
) -> dict[str, object]:
    return await _alerta_service(session).montar_digest_admin_completo()


# ── Stats operacionais (Sprint 19.6 PR4) ────────────────────────────────────


stats_router = APIRouter(prefix="/v1/admin/stats", tags=["admin-stats"])


@stats_router.get(
    "/whatsapp-dedup",
    summary="Stats de dedup WhatsApp (Sprint 19.6 PR4 #18)",
    description=(
        "Reporta saúde da task `whatsapp.expurgar_processadas` (cron daily "
        "04:00) sem depender de Grafana. Devolve total atual + quantos "
        "registros têm > 7 dias (deveriam ter sido expurgados — se o worker "
        "está rodando, esse contador deve ficar próximo de 0)."
    ),
)
async def stats_whatsapp_dedup(
    session: TaxTableAdminSessionDep,
) -> dict[str, object]:
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from sqlalchemy import func, select

    from app.shared.db.models import WhatsappMensagemProcessada

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    limite_7d = agora - timedelta(days=7)

    total = (
        await session.execute(
            select(func.count()).select_from(WhatsappMensagemProcessada)
        )
    ).scalar_one()
    pendentes_expurgo = (
        await session.execute(
            select(func.count())
            .select_from(WhatsappMensagemProcessada)
            .where(WhatsappMensagemProcessada.processed_at < limite_7d)
        )
    ).scalar_one()
    ultimo_processado = (
        await session.execute(
            select(func.max(WhatsappMensagemProcessada.processed_at))
        )
    ).scalar_one_or_none()

    return {
        "total_atual": int(total),
        "pendentes_expurgo_7d": int(pendentes_expurgo),
        "ultimo_processado_em": (
            ultimo_processado.isoformat() if ultimo_processado else None
        ),
        # Se pendentes_expurgo_7d > 0, task não está rodando (ou está mas
        # com erro). Operador checa logs de `whatsapp.expurgar_processadas`.
        "health": "ok" if pendentes_expurgo == 0 else "task_atrasada",
        "verificado_em": agora.isoformat(),
    }


# ── Sugestões de vigência (Sprint 19.5 PR3) ─────────────────────────────────
#
# Camada 3 do painel admin. Sugestões geradas pelo worker DOU+LLM ficam
# pendentes até admin aprovar via 1 clique aqui — princípio §8.8 inviolável.

sugestoes_router = APIRouter(
    prefix="/v1/admin/sugestoes-vigencia", tags=["admin-sugestoes-vigencia"]
)


@sugestoes_router.get(
    "",
    response_model=list[SugestaoVigenciaOut],
    summary="Lista sugestões de vigência (default: pendentes)",
)
async def listar_sugestoes(
    session: TaxTableAdminSessionDep,
    status: StatusSugestao | None = "pendente",
    tipo_tabela: str | None = None,
    limite: int = Query(default=100, ge=1, le=500),
) -> list[SugestaoVigenciaOut]:
    rows = await _sugestao_service(session).listar(
        status=status, tipo_tabela=tipo_tabela, limite=limite
    )
    return [SugestaoVigenciaOut.model_validate(r) for r in rows]


@sugestoes_router.get(
    "/{sugestao_id}",
    response_model=SugestaoVigenciaOut,
    summary="Detalha sugestão (incluindo recheck_observacoes)",
)
async def detalhar_sugestao(
    sugestao_id: UUID,
    session: TaxTableAdminSessionDep,
) -> SugestaoVigenciaOut:
    repo = SugestaoVigenciaRepo(session)
    row = await repo.por_id(sugestao_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Sugestão {sugestao_id} não encontrada"
        )
    return SugestaoVigenciaOut.model_validate(row)


@sugestoes_router.post(
    "/{sugestao_id}/aprovar",
    response_model=SugestaoVigenciaOut,
    summary="Aprova sugestão — chama Camada 1 e linka vigência criada",
    description=(
        "Idempotente §8.9: aprovar 2× a mesma sugestão devolve 409 "
        "(SugestaoVigenciaForaDeFluxo). A vigência criada na Camada 1 "
        "pode ser consultada via ``vigencia_tabela_log_id``."
    ),
)
async def aprovar_sugestao(
    sugestao_id: UUID,
    session: TaxTableAdminSessionDep,
) -> SugestaoVigenciaOut:
    sugestao = await _sugestao_service(session).aprovar(session, sugestao_id)
    return SugestaoVigenciaOut.model_validate(sugestao)


@sugestoes_router.post(
    "/{sugestao_id}/rejeitar",
    response_model=SugestaoVigenciaOut,
    summary="Rejeita sugestão com motivo",
)
async def rejeitar_sugestao(
    sugestao_id: UUID,
    payload: RejeitarSugestaoIn,
    session: TaxTableAdminSessionDep,
) -> SugestaoVigenciaOut:
    sugestao = await _sugestao_service(session).rejeitar(
        session, sugestao_id, motivo=payload.motivo
    )
    return SugestaoVigenciaOut.model_validate(sugestao)


__all__ = [
    "router",
    "alertas_router",
    "sugestoes_router",
    "stats_router",
    "TIPOS_TABELA_SUPORTADOS",
]
