"""Endpoints REST contábil (Sprint 9 PR1 + PR2 + PR3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.contabil.encerramento_service import EncerramentoService
from app.modules.contabil.lancador_service import LancadorService
from app.modules.contabil.relatorios_service import RelatoriosService
from app.modules.contabil.repo import (
    ContaContabilRepo,
    LancamentoRepo,
    PartidaRepo,
)
from app.modules.contabil.schemas import (
    AberturaExercicioOut,
    BalanceteOut,
    ClonarPlanoOut,
    ContaContabilOut,
    CriarContaIn,
    CriarLancamentoIn,
    EncerramentoAnualOut,
    EncerramentoMensalOut,
    LancamentoOut,
    LinhaBalanceteOut,
    LinhaRazaoOut,
    LoteAutoOut,
    NaturezaConta,
    OrigemLancamento,
    PartidaOut,
    RazaoOut,
    StatusLancamento,
    TipoConta,
    TipoFatoAuto,
)
from app.modules.contabil.service import ContabilService
from app.shared.competencia import parse_competencia_mensal
from app.shared.db.deps import SessionDep, TenantDep

router = APIRouter(prefix="/v1/empresas", tags=["contabil"])


# ── Plano de contas ─────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/plano-contas",
    response_model=ContaContabilOut,
    status_code=201,
    summary="Cria uma conta contábil",
)
async def criar_conta(
    empresa_id: UUID,
    payload: CriarContaIn,
    ctx: TenantDep,
    session: SessionDep,
) -> ContaContabilOut:
    return await ContabilService().criar_conta(
        session, ctx.tenant_id, empresa_id, payload
    )


@router.post(
    "/{empresa_id}/plano-contas/clonar-padrao",
    response_model=ClonarPlanoOut,
    status_code=201,
    summary="Clona o plano de contas referencial RFB para a empresa",
    description=(
        "Cria todas as contas do plano referencial mínimo (36 contas) na "
        "empresa. Idempotente: contas que já existem são puladas."
    ),
)
async def clonar_plano(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    valid_from: date = Query(..., description="Data inicial de vigência do plano"),
) -> ClonarPlanoOut:
    return await ContabilService().clonar_plano_referencial(
        session, ctx.tenant_id, empresa_id, valid_from
    )


@router.get(
    "/{empresa_id}/plano-contas",
    response_model=list[ContaContabilOut],
    summary="Lista o plano de contas vigente",
)
async def listar_contas(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> list[ContaContabilOut]:
    contas = await ContaContabilRepo(session).listar(empresa_id)
    return [
        ContaContabilOut(
            id=c.id,
            codigo=c.codigo,
            descricao=c.descricao,
            parent_id=c.parent_id,
            natureza=NaturezaConta(c.natureza),
            tipo=TipoConta(c.tipo),
            nivel=c.nivel,
            aceita_lancamento=c.aceita_lancamento,
            codigo_ecd_referencial=c.codigo_ecd_referencial,
            valid_from=c.valid_from,
            valid_to=c.valid_to,
        )
        for c in contas
    ]


# ── Lançamentos ─────────────────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/lancamentos",
    response_model=LancamentoOut,
    status_code=201,
    summary="Cria lançamento contábil manual (rascunho)",
    description=(
        "Valida invariante Σ débitos = Σ créditos, contas analíticas e "
        "vigência. Lançamento criado em status='rascunho' — use o endpoint "
        "/confirmar para tornar definitivo."
    ),
)
async def criar_lancamento(
    empresa_id: UUID,
    payload: CriarLancamentoIn,
    ctx: TenantDep,
    session: SessionDep,
) -> LancamentoOut:
    return await ContabilService().criar_lancamento_manual(
        session, ctx.tenant_id, empresa_id, payload
    )


@router.post(
    "/{empresa_id}/lancamentos/{lancamento_id}/confirmar",
    response_model=LancamentoOut,
    summary="Confirma lançamento (rascunho → confirmado)",
)
async def confirmar_lancamento(
    empresa_id: UUID,
    lancamento_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
) -> LancamentoOut:
    return await ContabilService().confirmar_lancamento(
        session, empresa_id, lancamento_id
    )


@router.get(
    "/{empresa_id}/lancamentos",
    response_model=list[LancamentoOut],
    summary="Lista lançamentos da empresa",
)
async def listar_lancamentos(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    competencia: date | None = Query(default=None),
    status: StatusLancamento | None = Query(default=None),
) -> list[LancamentoOut]:
    status_str = status.value if status else None
    lancamentos = await LancamentoRepo(session).listar(
        empresa_id, competencia=competencia, status=status_str
    )
    partida_repo = PartidaRepo(session)
    out: list[LancamentoOut] = []
    for lanc in lancamentos:
        partidas = await partida_repo.por_lancamento(lanc.id)
        out.append(
            LancamentoOut(
                id=lanc.id,
                data_lancamento=lanc.data_lancamento,
                competencia=lanc.competencia,
                historico=lanc.historico,
                origem_tipo=OrigemLancamento(lanc.origem_tipo),
                origem_id=lanc.origem_id,
                total_debito=lanc.total_debito,
                total_credito=lanc.total_credito,
                status=StatusLancamento(lanc.status),
                criado_em=lanc.criado_em,
                partidas=[
                    PartidaOut(
                        id=p.id,
                        conta_contabil_id=p.conta_contabil_id,
                        tipo=NaturezaConta(p.tipo),
                        valor=p.valor,
                        ordem=p.ordem,
                    )
                    for p in partidas
                ],
            )
        )
    return out


# ── Motor automático (PR2) ──────────────────────────────────────────────────


@router.post(
    "/{empresa_id}/contabil/auto/{tipo}/{competencia}",
    response_model=LoteAutoOut,
    status_code=200,
    summary="Gera lançamentos automáticos para uma competência",
    description=(
        "Varre fatos do mês (NF / transação / depreciação / provisão) e gera "
        "lançamentos contábeis em status='confirmado' via algoritmo "
        "determinístico. Idempotente: UNIQUE (origem_tipo, origem_id) bloqueia "
        "duplicação. Requer plano de contas referencial clonado."
    ),
)
async def gerar_auto(
    empresa_id: UUID,
    tipo: TipoFatoAuto,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> LoteAutoOut:
    comp_date = parse_competencia_mensal(competencia)
    service = LancadorService()
    if tipo is TipoFatoAuto.NFE:
        resultado = await service.lote_nfe(
            session, ctx.tenant_id, empresa_id, comp_date
        )
    elif tipo is TipoFatoAuto.TRANSACAO:
        resultado = await service.lote_transacao(
            session, ctx.tenant_id, empresa_id, comp_date
        )
    elif tipo is TipoFatoAuto.DEPRECIACAO:
        resultado = await service.lote_depreciacao(
            session, ctx.tenant_id, empresa_id, comp_date
        )
    elif tipo is TipoFatoAuto.APURACAO:
        resultado = await service.lote_impostos(
            session, ctx.tenant_id, empresa_id, comp_date
        )
    else:  # PROVISAO
        resultado = await service.lote_provisao(
            session, ctx.tenant_id, empresa_id, comp_date
        )

    return LoteAutoOut(
        tipo=tipo,
        competencia=resultado.competencia,
        fatos_avaliados=resultado.fatos_avaliados,
        lancamentos_criados=resultado.lancamentos_criados,
        lancamentos_existentes=resultado.lancamentos_existentes,
        fatos_pulados=resultado.fatos_pulados,
        algoritmo_versao=resultado.algoritmo_versao,
    )


# ── Relatórios (PR3) ────────────────────────────────────────────────────────


@router.get(
    "/{empresa_id}/contabil/balancete/{competencia}",
    response_model=BalanceteOut,
    summary="Balancete de verificação por competência",
)
async def balancete(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> BalanceteOut:
    comp_date = parse_competencia_mensal(competencia)
    linhas_dom = await RelatoriosService().balancete(session, empresa_id, comp_date)
    linhas = [
        LinhaBalanceteOut(
            conta_id=l.conta_id,
            codigo=l.codigo,
            descricao=l.descricao,
            natureza=NaturezaConta(l.natureza),
            tipo=TipoConta(l.tipo),
            nivel=l.nivel,
            saldo_inicial=l.saldo_inicial,
            total_debitos=l.total_debitos,
            total_creditos=l.total_creditos,
            saldo_final=l.saldo_final,
        )
        for l in linhas_dom
    ]
    total_d = sum((l.total_debitos for l in linhas), start=Decimal("0"))
    total_c = sum((l.total_creditos for l in linhas), start=Decimal("0"))
    return BalanceteOut(
        competencia=comp_date,
        linhas=linhas,
        total_debitos=total_d,
        total_creditos=total_c,
    )


@router.get(
    "/{empresa_id}/contabil/diario",
    response_model=list[LancamentoOut],
    summary="Diário — lançamentos cronológicos",
)
async def diario(
    empresa_id: UUID,
    ctx: TenantDep,
    session: SessionDep,
    desde: date | None = Query(default=None),
    ate: date | None = Query(default=None),
) -> list[LancamentoOut]:
    lancamentos = await RelatoriosService().diario(
        session, empresa_id, desde=desde, ate=ate
    )
    partida_repo = PartidaRepo(session)
    out: list[LancamentoOut] = []
    for lanc in lancamentos:
        partidas = await partida_repo.por_lancamento(lanc.id)
        out.append(
            LancamentoOut(
                id=lanc.id,
                data_lancamento=lanc.data_lancamento,
                competencia=lanc.competencia,
                historico=lanc.historico,
                origem_tipo=OrigemLancamento(lanc.origem_tipo),
                origem_id=lanc.origem_id,
                total_debito=lanc.total_debito,
                total_credito=lanc.total_credito,
                status=StatusLancamento(lanc.status),
                criado_em=lanc.criado_em,
                partidas=[
                    PartidaOut(
                        id=p.id,
                        conta_contabil_id=p.conta_contabil_id,
                        tipo=NaturezaConta(p.tipo),
                        valor=p.valor,
                        ordem=p.ordem,
                    )
                    for p in partidas
                ],
            )
        )
    return out


@router.get(
    "/{empresa_id}/contabil/razao/{conta_id}/{competencia}",
    response_model=RazaoOut,
    summary="Razão de uma conta na competência",
)
async def razao(
    empresa_id: UUID,
    conta_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> RazaoOut:
    comp_date = parse_competencia_mensal(competencia)
    conta, saldo_inicial, linhas_dom = await RelatoriosService().razao(
        session, empresa_id, conta_id, comp_date
    )
    saldo_final = linhas_dom[-1].saldo_corrente if linhas_dom else saldo_inicial
    return RazaoOut(
        conta_id=conta.id,
        conta_codigo=conta.codigo,
        conta_descricao=conta.descricao,
        competencia=comp_date,
        saldo_inicial=saldo_inicial,
        saldo_final=saldo_final,
        linhas=[
            LinhaRazaoOut(
                lancamento_id=l.lancamento_id,
                data_lancamento=l.data_lancamento,
                historico=l.historico,
                debito=l.debito,
                credito=l.credito,
                saldo_corrente=l.saldo_corrente,
            )
            for l in linhas_dom
        ],
    )


@router.post(
    "/{empresa_id}/contabil/encerramento/{competencia}",
    response_model=EncerramentoMensalOut,
    status_code=200,
    summary="Encerra a competência (trava lançamentos + materializa saldos)",
)
async def encerrar_mes(
    empresa_id: UUID,
    competencia: str,
    ctx: TenantDep,
    session: SessionDep,
) -> EncerramentoMensalOut:
    comp_date = parse_competencia_mensal(competencia)
    resultado = await EncerramentoService().encerrar_mes(
        session, ctx.tenant_id, empresa_id, comp_date
    )
    return EncerramentoMensalOut(
        competencia=resultado.competencia,
        saldos_persistidos=resultado.saldos_persistidos,
        lancamentos_encerrados=resultado.lancamentos_encerrados,
    )


@router.post(
    "/{empresa_id}/contabil/encerramento-anual/{ano}",
    response_model=EncerramentoAnualOut,
    status_code=200,
    summary="Apuração do exercício — zera receitas e despesas",
)
async def encerrar_ano(
    empresa_id: UUID,
    ano: int,
    ctx: TenantDep,
    session: SessionDep,
) -> EncerramentoAnualOut:
    resultado = await EncerramentoService().encerrar_ano(
        session, ctx.tenant_id, empresa_id, ano
    )
    return EncerramentoAnualOut(
        ano=resultado.ano,
        receitas_zeradas=resultado.receitas_zeradas,
        despesas_zeradas=resultado.despesas_zeradas,
        resultado_exercicio=resultado.resultado_exercicio,
        lancamento_apuracao_id=resultado.lancamento_apuracao_id,
    )


@router.post(
    "/{empresa_id}/contabil/exercicio/{ano}/abrir",
    response_model=AberturaExercicioOut,
    status_code=200,
    summary="Abre exercício — transporta saldos patrimoniais e zera resultado (Sprint 18 PR1)",
    description=(
        "Materializa ``saldo_conta_mes`` de janeiro/ano com saldo_inicial "
        "herdado de dezembro/ano-1 para contas patrimoniais (Ativo/Passivo/PL/"
        "ContaResultado) e zero para receita/despesa. Idempotente — re-chamada "
        "não duplica linhas. Disparado automaticamente pelo encerramento anual; "
        "este endpoint serve para correção manual ou rebuild após edição "
        "retroativa de saldos."
    ),
)
async def abrir_exercicio(
    empresa_id: UUID,
    ano: int,
    ctx: TenantDep,
    session: SessionDep,
) -> AberturaExercicioOut:
    resultado = await EncerramentoService().abrir_exercicio(
        session, ctx.tenant_id, empresa_id, ano
    )
    return AberturaExercicioOut(
        ano=resultado.ano,
        contas_patrimoniais=resultado.contas_patrimoniais,
        contas_resultado=resultado.contas_resultado,
        saldo_total_transportado=resultado.saldo_total_transportado,
    )
