"""Service contábil — plano de contas + lançamentos manuais (Sprint 9 PR1)."""

from __future__ import annotations

import uuid
from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contabil.partidas import (
    ContaView,
    PartidaIn as PartidaInDomain,
    validar_partidas,
)
from app.modules.contabil.plano_referencial import PLANO_REFERENCIAL
from app.modules.contabil.repo import (
    ContaContabilRepo,
    LancamentoRepo,
    PartidaRepo,
    SaldoContaMesRepo,
)
from app.modules.contabil.schemas import (
    ClonarPlanoOut,
    ContaContabilOut,
    CriarContaIn,
    CriarLancamentoIn,
    LancamentoOut,
    NaturezaConta,
    OrigemLancamento,
    PartidaOut,
    StatusLancamento,
    TipoConta,
)
from app.modules.empresa.repo import EmpresaRepo
from app.shared.db.models import ContaContabil, LancamentoContabil, PartidaLancamento
from app.shared.exceptions import (
    ContaJaExiste,
    EmpresaNaoEncontrada,
    LancamentoEmMesEncerrado,
    LancamentoInvalido,
    LancamentoJaConfirmado,
    LancamentoNaoEncontrado,
)

log = structlog.get_logger(__name__)


class ContabilService:
    # ── Plano de contas ──────────────────────────────────────────────────────

    async def criar_conta(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: CriarContaIn,
    ) -> ContaContabilOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = ContaContabilRepo(session)
        existente = await repo.por_codigo(empresa_id, payload.codigo)
        if existente is not None and existente.valid_to is None:
            raise ContaJaExiste(
                f"Conta {payload.codigo} já existe e está vigente"
            )

        if payload.parent_id is not None:
            parent = await repo.por_id(payload.parent_id)
            if parent is None or parent.empresa_id != empresa_id:
                raise ContaJaExiste(
                    f"Parent {payload.parent_id} não encontrado nesta empresa"
                )

        conta = await repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            codigo=payload.codigo,
            descricao=payload.descricao,
            parent_id=payload.parent_id,
            natureza=payload.natureza.value,
            tipo=payload.tipo.value,
            nivel=payload.nivel,
            aceita_lancamento=payload.aceita_lancamento,
            codigo_ecd_referencial=payload.codigo_ecd_referencial,
            valid_from=payload.valid_from,
        )
        await session.commit()
        log.info(
            "contabil.conta.criada",
            empresa_id=str(empresa_id),
            codigo=conta.codigo,
            aceita_lancamento=conta.aceita_lancamento,
        )
        return _conta_para_out(conta)

    async def clonar_plano_referencial(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        valid_from: date,
    ) -> ClonarPlanoOut:
        """Cria todas as contas do plano referencial RFB para a empresa.

        Idempotente: contas que já existem no mesmo código são puladas.
        Resolve parent_id por código (lookup após cada criação).
        """
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        repo = ContaContabilRepo(session)
        codigo_para_id: dict[str, uuid.UUID] = {}
        criadas = 0
        existentes = 0

        for item in PLANO_REFERENCIAL:
            ja_existe = await repo.por_codigo(empresa_id, item.codigo)
            if ja_existe is not None:
                codigo_para_id[item.codigo] = ja_existe.id
                existentes += 1
                continue

            parent_id: uuid.UUID | None = None
            if item.parent_codigo is not None:
                parent_id = codigo_para_id.get(item.parent_codigo)

            conta = await repo.criar(
                tenant_id=tenant_id,
                empresa_id=empresa_id,
                codigo=item.codigo,
                descricao=item.descricao,
                parent_id=parent_id,
                natureza=item.natureza,
                tipo=item.tipo,
                nivel=item.nivel,
                aceita_lancamento=item.aceita_lancamento,
                codigo_ecd_referencial=item.codigo_ecd_referencial,
                valid_from=valid_from,
            )
            codigo_para_id[item.codigo] = conta.id
            criadas += 1

        await session.commit()
        log.info(
            "contabil.plano.clonado",
            empresa_id=str(empresa_id),
            criadas=criadas,
            existentes=existentes,
            valid_from=valid_from.isoformat(),
        )
        return ClonarPlanoOut(
            contas_criadas=criadas,
            contas_existentes=existentes,
            primeira_competencia=valid_from,
        )

    # ── Lançamentos manuais ──────────────────────────────────────────────────

    async def criar_lancamento_manual(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        empresa_id: uuid.UUID,
        payload: CriarLancamentoIn,
    ) -> LancamentoOut:
        empresa = await EmpresaRepo(session).por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")

        # §8.2 — fatos contábeis imutáveis após encerramento. Defesa em
        # profundidade: o CHECK em ``status`` bloqueia mutação de lançamentos
        # já encerrados, mas não impede criação retroativa em mês fechado.
        comp_mes1 = date(payload.competencia.year, payload.competencia.month, 1)
        if await SaldoContaMesRepo(session).competencia_encerrada(
            empresa_id, comp_mes1
        ):
            raise LancamentoEmMesEncerrado(
                f"Competência {comp_mes1:%Y-%m} encerrada — use lançamento "
                f"de ajuste retroativo em competência aberta."
            )

        # Valida partidas via algoritmo puro.
        conta_repo = ContaContabilRepo(session)
        ids = [p.conta_id for p in payload.partidas]
        contas_db = await conta_repo.carregar_para_validacao(ids)
        contas_view = {
            cid: ContaView(
                id=c.id,
                empresa_id=c.empresa_id,
                aceita_lancamento=c.aceita_lancamento,
                valid_from=c.valid_from,
                valid_to=c.valid_to,
            )
            for cid, c in contas_db.items()
        }
        partidas_domain = [
            PartidaInDomain(conta_id=p.conta_id, tipo=p.tipo.value, valor=p.valor)
            for p in payload.partidas
        ]
        resultado = validar_partidas(
            partidas_domain, contas_view,
            empresa_id=empresa_id,
            competencia=payload.competencia,
        )
        if not resultado.valido:
            raise LancamentoInvalido(
                f"Partidas inválidas: {', '.join(resultado.erros)}"
            )

        lanc_repo = LancamentoRepo(session)
        partida_repo = PartidaRepo(session)

        lancamento = await lanc_repo.criar(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            data_lancamento=payload.data_lancamento,
            competencia=payload.competencia,
            historico=payload.historico,
            origem_tipo=OrigemLancamento.MANUAL.value,
            origem_id=None,
            total_debito=resultado.total_debito,
            total_credito=resultado.total_credito,
            status=StatusLancamento.RASCUNHO.value,
        )

        partidas_persistidas = await partida_repo.criar_lote(
            tenant_id=tenant_id,
            lancamento_id=lancamento.id,
            partidas=[
                (p.conta_id, p.tipo.value, p.valor) for p in payload.partidas
            ],
        )
        await session.commit()

        log.info(
            "contabil.lancamento.criado",
            empresa_id=str(empresa_id),
            lancamento_id=str(lancamento.id),
            total=str(resultado.total_debito),
            partidas=len(partidas_persistidas),
        )

        return _lancamento_para_out(lancamento, partidas_persistidas)

    async def confirmar_lancamento(
        self,
        session: AsyncSession,
        empresa_id: uuid.UUID,
        lancamento_id: uuid.UUID,
    ) -> LancamentoOut:
        repo = LancamentoRepo(session)
        lanc = await repo.por_id(lancamento_id)
        if lanc is None or lanc.empresa_id != empresa_id:
            raise LancamentoNaoEncontrado(f"Lançamento {lancamento_id} não encontrado")
        if lanc.status == StatusLancamento.ENCERRADO.value:
            raise LancamentoJaConfirmado(
                f"Lançamento {lancamento_id} já está encerrado"
            )
        # §8.2 — rascunho criado antes do encerramento não pode ser promovido
        # a confirmado depois (burlaria o gate de competência fechada).
        if await SaldoContaMesRepo(session).competencia_encerrada(
            empresa_id, lanc.competencia
        ):
            raise LancamentoEmMesEncerrado(
                f"Competência {lanc.competencia:%Y-%m} encerrada — rascunho não "
                f"pode ser confirmado em mês fechado."
            )
        if lanc.status == StatusLancamento.CONFIRMADO.value:
            # Idempotente
            partidas = await PartidaRepo(session).por_lancamento(lancamento_id)
            return _lancamento_para_out(lanc, partidas)

        await repo.confirmar(lanc)
        await session.commit()
        partidas = await PartidaRepo(session).por_lancamento(lancamento_id)

        log.info(
            "contabil.lancamento.confirmado",
            lancamento_id=str(lancamento_id),
        )
        return _lancamento_para_out(lanc, partidas)


# ── helpers puros ────────────────────────────────────────────────────────────


def _conta_para_out(c: ContaContabil) -> ContaContabilOut:
    return ContaContabilOut(
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


def _lancamento_para_out(
    lanc: LancamentoContabil, partidas: list[PartidaLancamento]
) -> LancamentoOut:
    return LancamentoOut(
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
