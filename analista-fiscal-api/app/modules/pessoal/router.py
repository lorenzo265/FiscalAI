"""Endpoints REST do módulo pessoal (Sprint 10 PR1)."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.pessoal.eventos_service import EventosFolhaService
from app.modules.pessoal.repo import (
    DistribuicaoRepo,
    EventoESocialRepo,
    EventoFolhaRepo,
    FolhaRepo,
    FuncionarioRepo,
    HoleriteRepo,
    ProlaboreRepo,
    SocioRepo,
)
from app.modules.pessoal.schemas import (
    DecimoTerceiroIn,
    DistribuicaoIn,
    DistribuicaoOut,
    EsocialGerarIn,
    EventoESocialOut,
    EventoFolhaOut,
    FecharFolhaOut,
    FeriasIn,
    FolhaMensalOut,
    FuncionarioIn,
    FuncionarioOut,
    HoleriteOut,
    ProlaboreIn,
    ProlaboreOut,
    RescisaoIn,
    SocioIn,
    SocioOut,
    TipoEventoESocialIn,
    TipoEventoFolha,
)
from app.modules.pessoal.service import PessoalService
from app.modules.pessoal.socio_service import (
    DistribuicaoService,
    EsocialService,
    ProlaboreService,
    SocioService,
)
from app.shared.db.deps import SessionDep, TenantDep
from app.shared.exceptions import FolhaNaoEncontrada

router = APIRouter(prefix="/v1/empresas", tags=["pessoal"])

_COMPETENCIA_RE = re.compile(r"^\d{4}-\d{2}$")


def _parse_competencia(competencia: str) -> date:
    if not _COMPETENCIA_RE.match(competencia):
        raise HTTPException(
            status_code=422, detail="Competência deve estar no formato AAAA-MM"
        )
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


# ── Funcionários ────────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/funcionarios",
    response_model=FuncionarioOut,
    status_code=201,
    summary="Cadastra funcionário CLT",
)
async def cadastrar_funcionario(
    empresa_id: UUID,
    payload: FuncionarioIn,
    ctx: TenantDep,
    session: SessionDep,
) -> FuncionarioOut:
    funcionario = await PessoalService().cadastrar_funcionario(
        session, ctx.tenant_id, empresa_id, payload
    )
    return FuncionarioOut.model_validate(funcionario)


@router.get(
    "/{empresa_id}/funcionarios",
    response_model=list[FuncionarioOut],
    summary="Lista funcionários da empresa",
)
async def listar_funcionarios(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    somente_ativos: bool = True,
) -> list[FuncionarioOut]:
    rows = await FuncionarioRepo(session).listar(
        empresa_id, somente_ativos=somente_ativos
    )
    return [FuncionarioOut.model_validate(r) for r in rows]


# ── Folha mensal ────────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/folhas/{competencia}/fechar",
    response_model=FecharFolhaOut,
    status_code=200,
    summary="Calcula e fecha a folha mensal",
    description=(
        "Calcula INSS escalonado, IRRF (com dedução de INSS + dependentes) e "
        "FGTS para cada funcionário ativo na competência. Persiste folha + "
        "holerites em transação única. Idempotente via UNIQUE "
        "(empresa, competência) — segunda chamada retorna 409."
    ),
)
async def fechar_folha(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> FecharFolhaOut:
    comp_date = _parse_competencia(competencia)
    return await PessoalService().fechar_folha_mensal(
        session, ctx.tenant_id, empresa_id, comp_date
    )


@router.get(
    "/{empresa_id}/folhas",
    response_model=list[FolhaMensalOut],
    summary="Lista folhas mensais da empresa",
)
async def listar_folhas(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    limite: int = 24,
) -> list[FolhaMensalOut]:
    rows = await FolhaRepo(session).listar(empresa_id, limite=limite)
    return [FolhaMensalOut.model_validate(r) for r in rows]


@router.get(
    "/{empresa_id}/folhas/{competencia}/holerites",
    response_model=list[HoleriteOut],
    summary="Lista holerites de uma folha",
)
async def listar_holerites(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> list[HoleriteOut]:
    comp_date = _parse_competencia(competencia)
    folha = await FolhaRepo(session).por_competencia(empresa_id, comp_date)
    if folha is None:
        raise FolhaNaoEncontrada(
            f"Folha de {comp_date.isoformat()} não encontrada para a empresa"
        )
    rows = await HoleriteRepo(session).listar_da_folha(folha.id)
    return [HoleriteOut.model_validate(r) for r in rows]


# ── Eventos pontuais (Sprint 10 PR2) ────────────────────────────────────────


@router.post(
    "/{empresa_id}/funcionarios/{funcionario_id}/13o",
    response_model=EventoFolhaOut,
    status_code=201,
    summary="Registra pagamento de 13º (1ª ou 2ª parcela)",
    description=(
        "1ª parcela é paga sem desconto (até 30/nov). 2ª parcela tem INSS "
        "escalonado e IRRF exclusivo na fonte (até 20/dez). Idempotente por "
        "(funcionário, parcela, ano)."
    ),
)
async def registrar_13o(
    empresa_id: UUID,
    funcionario_id: UUID,
    payload: DecimoTerceiroIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoFolhaOut:
    evento = await EventosFolhaService().registrar_13o(
        session, ctx.tenant_id, empresa_id, funcionario_id, payload
    )
    return EventoFolhaOut.model_validate(evento)


@router.post(
    "/{empresa_id}/funcionarios/{funcionario_id}/ferias",
    response_model=EventoFolhaOut,
    status_code=201,
    summary="Registra pagamento de férias (com 1/3 + abono pecuniário opcional)",
    description=(
        "INSS + IRRF incidem sobre remuneração + 1/3 constitucional. Abono "
        "pecuniário (até 10 dias) é isento (Lei 7.713/1988). Idempotente por "
        "(funcionário, período_inicio)."
    ),
)
async def registrar_ferias(
    empresa_id: UUID,
    funcionario_id: UUID,
    payload: FeriasIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoFolhaOut:
    evento = await EventosFolhaService().registrar_ferias(
        session, ctx.tenant_id, empresa_id, funcionario_id, payload
    )
    return EventoFolhaOut.model_validate(evento)


@router.post(
    "/{empresa_id}/funcionarios/{funcionario_id}/rescisao",
    response_model=EventoFolhaOut,
    status_code=201,
    summary="Registra rescisão (5 modalidades CLT)",
    description=(
        "Calcula saldo + aviso (conforme tipo) + 13º proporcional + férias "
        "venc/prop + 1/3 + multa FGTS. Marca funcionário como demitido. "
        "Idempotente por funcionário (rescisão única)."
    ),
)
async def registrar_rescisao(
    empresa_id: UUID,
    funcionario_id: UUID,
    payload: RescisaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoFolhaOut:
    evento = await EventosFolhaService().registrar_rescisao(
        session, ctx.tenant_id, empresa_id, funcionario_id, payload
    )
    return EventoFolhaOut.model_validate(evento)


@router.get(
    "/{empresa_id}/funcionarios/{funcionario_id}/eventos",
    response_model=list[EventoFolhaOut],
    summary="Lista eventos pontuais do funcionário (13º, férias, rescisão)",
)
async def listar_eventos(
    empresa_id: UUID,
    funcionario_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoEventoFolha | None = None,
) -> list[EventoFolhaOut]:
    tipo_str = tipo.value if tipo else None
    rows = await EventoFolhaRepo(session).listar_do_funcionario(
        funcionario_id, tipo=tipo_str
    )
    return [EventoFolhaOut.model_validate(r) for r in rows]


# ── Sócios / Pró-labore / Distribuição (Sprint 10 PR3) ──────────────────────


@router.post(
    "/{empresa_id}/socios",
    response_model=SocioOut,
    status_code=201,
    summary="Cadastra sócio da empresa",
)
async def cadastrar_socio(
    empresa_id: UUID,
    payload: SocioIn,
    ctx: TenantDep,
    session: SessionDep,
) -> SocioOut:
    socio = await SocioService().cadastrar(
        session, ctx.tenant_id, empresa_id, payload
    )
    return SocioOut.model_validate(socio)


@router.get(
    "/{empresa_id}/socios",
    response_model=list[SocioOut],
    summary="Lista sócios da empresa",
)
async def listar_socios(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    somente_ativos: bool = True,
) -> list[SocioOut]:
    rows = await SocioRepo(session).listar(empresa_id, somente_ativos=somente_ativos)
    return [SocioOut.model_validate(r) for r in rows]


@router.post(
    "/{empresa_id}/socios/{socio_id}/prolabore",
    response_model=ProlaboreOut,
    status_code=201,
    summary="Registra pró-labore mensal do sócio",
    description=(
        "INSS 11% como contribuinte individual (plano simplificado — "
        "Lei 9.876/1999) limitado ao teto previdenciário. IRRF mensal "
        "regular. Idempotente por (sócio, competência)."
    ),
)
async def registrar_prolabore(
    empresa_id: UUID,
    socio_id: UUID,
    payload: ProlaboreIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ProlaboreOut:
    prolabore = await ProlaboreService().registrar_mensal(
        session, ctx.tenant_id, empresa_id, socio_id, payload
    )
    return ProlaboreOut.model_validate(prolabore)


@router.get(
    "/{empresa_id}/socios/{socio_id}/prolabore",
    response_model=list[ProlaboreOut],
    summary="Lista pró-labores do sócio",
)
async def listar_prolabore(
    empresa_id: UUID,
    socio_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    limite: int = 24,
) -> list[ProlaboreOut]:
    rows = await ProlaboreRepo(session).listar_do_socio(socio_id, limite=limite)
    return [ProlaboreOut.model_validate(r) for r in rows]


@router.post(
    "/{empresa_id}/socios/{socio_id}/distribuicoes",
    response_model=DistribuicaoOut,
    status_code=201,
    summary="Registra distribuição de lucros ao sócio",
    description=(
        "Lei 9.249/1995 art. 10 — isento até o limite contábil; excedente "
        "tributado como rendimento mensal IRRF. O ``limite_isento_apurado`` "
        "é input — calcule-o externamente conforme o regime (presunção "
        "menos impostos pagos, ou lucro líquido contábil)."
    ),
)
async def registrar_distribuicao(
    empresa_id: UUID,
    socio_id: UUID,
    payload: DistribuicaoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> DistribuicaoOut:
    distribuicao = await DistribuicaoService().registrar(
        session, ctx.tenant_id, empresa_id, socio_id, payload
    )
    return DistribuicaoOut.model_validate(distribuicao)


@router.get(
    "/{empresa_id}/socios/{socio_id}/distribuicoes",
    response_model=list[DistribuicaoOut],
    summary="Lista distribuições do sócio",
)
async def listar_distribuicoes(
    empresa_id: UUID,
    socio_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[DistribuicaoOut]:
    rows = await DistribuicaoRepo(session).listar_do_socio(socio_id)
    return [DistribuicaoOut.model_validate(r) for r in rows]


# ── eSocial skeleton (Sprint 10 PR3) ────────────────────────────────────────


@router.post(
    "/{empresa_id}/esocial/eventos",
    response_model=EventoESocialOut,
    status_code=201,
    summary="Gera evento eSocial (preparado, sem transmissão)",
    description=(
        "Cria o payload JSON do evento conforme leiaute S-1.3. Eventos "
        "suportados: S-1200 (remuneração), S-1210 (pagamento), S-2200 "
        "(admissão), S-2299 (desligamento), S-2400 (beneficiário/sócio). "
        "Transmissão real (com cert A1) será implementada em sprint futura."
    ),
)
async def gerar_evento_esocial(
    empresa_id: UUID,
    payload: EsocialGerarIn,
    ctx: TenantDep,
    session: SessionDep,
) -> EventoESocialOut:
    evento = await EsocialService().gerar(
        session, ctx.tenant_id, empresa_id, payload
    )
    return EventoESocialOut.model_validate(evento)


@router.get(
    "/{empresa_id}/esocial/eventos",
    response_model=list[EventoESocialOut],
    summary="Lista eventos eSocial gerados para a empresa",
)
async def listar_eventos_esocial(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    tipo: TipoEventoESocialIn | None = None,
    limite: int = 100,
) -> list[EventoESocialOut]:
    tipo_str = tipo.value if tipo else None
    rows = await EventoESocialRepo(session).listar_empresa(
        empresa_id, tipo_evento=tipo_str, limite=limite
    )
    return [EventoESocialOut.model_validate(r) for r in rows]
