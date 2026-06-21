"""Repositórios do módulo pessoal (Sprint 10 PR1).

Inclui:
  * ``FuncionarioRepo`` — CRUD de funcionários CLT.
  * ``FolhaRepo``       — cabeçalho da folha + idempotência por competência.
  * ``HoleriteRepo``    — holerites individuais com UNIQUE (folha, funcionario).
  * ``TabelasTributariasRepo`` — leitura SCD das tabelas INSS/IRRF/FGTS.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pessoal.calcula_fgts import ResultadoFgts
from app.modules.pessoal.calcula_inss import FaixaInss, ResultadoInssEmpregado
from app.modules.pessoal.calcula_irrf import FaixaIrrf, ResultadoIrrf
from app.shared.db.models import (
    DistribuicaoLucros,
    EventoESocial,
    EventoFolha,
    FolhaMensal,
    Funcionario,
    Holerite,
    ProlaboreMensal,
    Socio,
    TabelaFgtsAliquota,
    TabelaInssFaixa,
    TabelaIrrfFaixa,
)


class FuncionarioRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, funcionario_id: UUID) -> Funcionario | None:
        stmt = select(Funcionario).where(Funcionario.id == funcionario_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def cpf_existe(self, empresa_id: UUID, cpf: str) -> bool:
        stmt = select(Funcionario.id).where(
            Funcionario.empresa_id == empresa_id, Funcionario.cpf == cpf
        )
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def listar(
        self, empresa_id: UUID, *, somente_ativos: bool = True
    ) -> list[Funcionario]:
        stmt = select(Funcionario).where(Funcionario.empresa_id == empresa_id)
        if somente_ativos:
            stmt = stmt.where(Funcionario.ativo.is_(True))
        stmt = stmt.order_by(Funcionario.nome)
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_ativos_para_folha(
        self, empresa_id: UUID, competencia: date
    ) -> list[Funcionario]:
        """Ativos na competência: admitidos antes do fim do mês e não demitidos
        antes do dia 1."""
        stmt = (
            select(Funcionario)
            .where(Funcionario.empresa_id == empresa_id)
            .where(Funcionario.ativo.is_(True))
            .where(Funcionario.data_admissao <= competencia)
            .order_by(Funcionario.nome)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, f: Funcionario) -> Funcionario:
        self._s.add(f)
        await self._s.flush()
        await self._s.refresh(f)
        return f


class FolhaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, folha_id: UUID) -> FolhaMensal | None:
        stmt = select(FolhaMensal).where(FolhaMensal.id == folha_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def por_competencia(
        self, empresa_id: UUID, competencia: date
    ) -> FolhaMensal | None:
        stmt = select(FolhaMensal).where(
            FolhaMensal.empresa_id == empresa_id,
            FolhaMensal.competencia == competencia,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar(
        self, empresa_id: UUID, *, limite: int = 24
    ) -> list[FolhaMensal]:
        stmt = (
            select(FolhaMensal)
            .where(FolhaMensal.empresa_id == empresa_id)
            .order_by(FolhaMensal.competencia.desc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, folha: FolhaMensal) -> FolhaMensal:
        self._s.add(folha)
        await self._s.flush()
        await self._s.refresh(folha)
        return folha


class HoleriteRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def listar_da_folha(self, folha_id: UUID) -> list[Holerite]:
        stmt = (
            select(Holerite)
            .where(Holerite.folha_mensal_id == folha_id)
            .order_by(Holerite.criado_em)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar_em_massa(self, holerites: list[Holerite]) -> None:
        self._s.add_all(holerites)
        await self._s.flush()


class EventoFolhaRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, evento_id: UUID) -> EventoFolha | None:
        stmt = select(EventoFolha).where(EventoFolha.id == evento_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_do_funcionario(
        self, funcionario_id: UUID, *, tipo: str | None = None
    ) -> list[EventoFolha]:
        stmt = (
            select(EventoFolha)
            .where(EventoFolha.funcionario_id == funcionario_id)
            .order_by(EventoFolha.data_evento.desc())
        )
        if tipo is not None:
            stmt = stmt.where(EventoFolha.tipo == tipo)
        return list((await self._s.execute(stmt)).scalars().all())

    async def buscar_13o(
        self, funcionario_id: UUID, ano: int, parcela: int
    ) -> EventoFolha | None:
        tipo = "13_primeira" if parcela == 1 else "13_segunda"
        stmt = (
            select(EventoFolha)
            .where(EventoFolha.funcionario_id == funcionario_id)
            .where(EventoFolha.tipo == tipo)
            .where(EventoFolha.ano_referencia == ano)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def buscar_rescisao(
        self, funcionario_id: UUID
    ) -> EventoFolha | None:
        stmt = (
            select(EventoFolha)
            .where(EventoFolha.funcionario_id == funcionario_id)
            .where(EventoFolha.tipo == "rescisao")
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(self, evento: EventoFolha) -> EventoFolha:
        self._s.add(evento)
        await self._s.flush()
        await self._s.refresh(evento)
        return evento


class SocioRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_id(self, socio_id: UUID) -> Socio | None:
        stmt = select(Socio).where(Socio.id == socio_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def cpf_existe(self, empresa_id: UUID, cpf: str) -> bool:
        stmt = select(Socio.id).where(
            Socio.empresa_id == empresa_id, Socio.cpf == cpf
        )
        return (await self._s.execute(stmt)).scalar_one_or_none() is not None

    async def listar(
        self, empresa_id: UUID, *, somente_ativos: bool = True
    ) -> list[Socio]:
        stmt = select(Socio).where(Socio.empresa_id == empresa_id)
        if somente_ativos:
            stmt = stmt.where(Socio.ativo.is_(True))
        stmt = stmt.order_by(Socio.nome)
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, s: Socio) -> Socio:
        self._s.add(s)
        await self._s.flush()
        await self._s.refresh(s)
        return s


class ProlaboreRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_competencia(
        self, socio_id: UUID, competencia: date
    ) -> ProlaboreMensal | None:
        stmt = select(ProlaboreMensal).where(
            ProlaboreMensal.socio_id == socio_id,
            ProlaboreMensal.competencia == competencia,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_do_socio(
        self, socio_id: UUID, *, limite: int = 24
    ) -> list[ProlaboreMensal]:
        stmt = (
            select(ProlaboreMensal)
            .where(ProlaboreMensal.socio_id == socio_id)
            .order_by(ProlaboreMensal.competencia.desc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, p: ProlaboreMensal) -> ProlaboreMensal:
        self._s.add(p)
        await self._s.flush()
        await self._s.refresh(p)
        return p


class DistribuicaoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def listar_do_socio(
        self, socio_id: UUID, *, limite: int = 50
    ) -> list[DistribuicaoLucros]:
        stmt = (
            select(DistribuicaoLucros)
            .where(DistribuicaoLucros.socio_id == socio_id)
            .order_by(DistribuicaoLucros.data_distribuicao.desc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, d: DistribuicaoLucros) -> DistribuicaoLucros:
        self._s.add(d)
        await self._s.flush()
        await self._s.refresh(d)
        return d

    async def soma_bruta_no_mes(
        self,
        empresa_id: UUID,
        socio_id: UUID,
        ano: int,
        mes: int,
    ) -> Decimal:
        """Retorna a soma dos valores brutos distribuídos no mês para a PJ×PF.

        Usado pela Lei 15.270/2025 para calcular o acumulado do mês e
        determinar a retenção antecipada de 10% sobre dividendos.

        Args:
            empresa_id: identificador da PJ pagadora.
            socio_id: identificador da PF beneficiária.
            ano: ano calendário (ex.: 2026).
            mes: mês calendário (1–12).

        Returns:
            Soma dos valores brutos pagos no mês. Zero se não houver registros.
        """
        stmt = select(
            func.coalesce(func.sum(DistribuicaoLucros.valor), Decimal("0"))
        ).where(
            DistribuicaoLucros.empresa_id == empresa_id,
            DistribuicaoLucros.socio_id == socio_id,
            extract("year", DistribuicaoLucros.data_distribuicao) == ano,
            extract("month", DistribuicaoLucros.data_distribuicao) == mes,
        )
        result = (await self._s.execute(stmt)).scalar_one()
        return Decimal(str(result))

    async def soma_retencao_no_mes(
        self,
        empresa_id: UUID,
        socio_id: UUID,
        ano: int,
        mes: int,
    ) -> Decimal:
        """Soma da retenção de 10% (Lei 15.270/2025) já retida no mês p/ a PJ×PF.

        Usado para o recálculo incremental de múltiplos pagamentos no mês: a
        retenção devida no pagamento atual é ``10% × total_do_mês`` menos o que
        já foi retido (este valor). Sem isso, o 2º+ pagamento reteria a mais.

        Returns:
            Soma de ``retencao_dividendos_10pct`` no mês. Zero se não houver.
        """
        stmt = select(
            func.coalesce(
                func.sum(DistribuicaoLucros.retencao_dividendos_10pct),
                Decimal("0"),
            )
        ).where(
            DistribuicaoLucros.empresa_id == empresa_id,
            DistribuicaoLucros.socio_id == socio_id,
            extract("year", DistribuicaoLucros.data_distribuicao) == ano,
            extract("month", DistribuicaoLucros.data_distribuicao) == mes,
        )
        result = (await self._s.execute(stmt)).scalar_one()
        return Decimal(str(result))


class EventoESocialRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def buscar(
        self, empresa_id: UUID, tipo_evento: str, referencia_id: UUID
    ) -> EventoESocial | None:
        stmt = select(EventoESocial).where(
            EventoESocial.empresa_id == empresa_id,
            EventoESocial.tipo_evento == tipo_evento,
            EventoESocial.referencia_id == referencia_id,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_empresa(
        self,
        empresa_id: UUID,
        *,
        tipo_evento: str | None = None,
        limite: int = 100,
    ) -> list[EventoESocial]:
        stmt = (
            select(EventoESocial)
            .where(EventoESocial.empresa_id == empresa_id)
            .order_by(EventoESocial.criado_em.desc())
            .limit(limite)
        )
        if tipo_evento:
            stmt = stmt.where(EventoESocial.tipo_evento == tipo_evento)
        return list((await self._s.execute(stmt)).scalars().all())

    async def criar(self, e: EventoESocial) -> EventoESocial:
        self._s.add(e)
        await self._s.flush()
        await self._s.refresh(e)
        return e

    # Sprint 19.7 PR2 (#13) — helpers do pipeline de transmissão.

    async def por_id(self, evento_id: UUID) -> EventoESocial | None:
        stmt = select(EventoESocial).where(EventoESocial.id == evento_id)
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def listar_por_status(
        self,
        empresa_id: UUID,
        *,
        status: str,
        limite: int = 200,
    ) -> list[EventoESocial]:
        stmt = (
            select(EventoESocial)
            .where(EventoESocial.empresa_id == empresa_id)
            .where(EventoESocial.status == status)
            .order_by(EventoESocial.criado_em.asc())
            .limit(limite)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def listar_por_lote(
        self, lote_protocolo: str
    ) -> list[EventoESocial]:
        stmt = (
            select(EventoESocial)
            .where(EventoESocial.lote_protocolo == lote_protocolo)
            .order_by(EventoESocial.criado_em.asc())
        )
        return list((await self._s.execute(stmt)).scalars().all())


class TabelasTributariasRepo:
    """Leitura SCD Type 2 das tabelas tributárias (§8.3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def inss_faixas_vigentes(
        self, em: date, *, tipo: str = "empregado"
    ) -> list[FaixaInss]:
        stmt = (
            select(TabelaInssFaixa)
            .where(TabelaInssFaixa.tipo == tipo)
            .where(TabelaInssFaixa.valid_from <= em)
            .where(
                (TabelaInssFaixa.valid_to == None)  # noqa: E711
                | (TabelaInssFaixa.valid_to >= em)
            )
            .order_by(TabelaInssFaixa.faixa)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            FaixaInss(faixa=r.faixa, valor_ate=r.valor_ate, aliquota=r.aliquota)
            for r in rows
        ]

    async def irrf_faixas_vigentes(self, em: date) -> list[FaixaIrrf]:
        stmt = (
            select(TabelaIrrfFaixa)
            .where(TabelaIrrfFaixa.valid_from <= em)
            .where(
                (TabelaIrrfFaixa.valid_to == None)  # noqa: E711
                | (TabelaIrrfFaixa.valid_to >= em)
            )
            .order_by(TabelaIrrfFaixa.faixa)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            FaixaIrrf(
                faixa=r.faixa,
                base_ate=r.base_ate,
                aliquota=r.aliquota,
                parcela_deduzir=r.parcela_deduzir,
                deducao_dependente=r.deducao_dependente,
            )
            for r in rows
        ]

    async def fgts_aliquota_vigente(
        self, em: date, *, vinculo: str = "clt"
    ) -> Decimal | None:
        stmt = (
            select(TabelaFgtsAliquota.aliquota)
            .where(TabelaFgtsAliquota.vinculo == vinculo)
            .where(TabelaFgtsAliquota.valid_from <= em)
            .where(
                (TabelaFgtsAliquota.valid_to == None)  # noqa: E711
                | (TabelaFgtsAliquota.valid_to >= em)
            )
            .order_by(TabelaFgtsAliquota.valid_from.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def teto_inss_contribuinte_individual_vigente(
        self, em: date
    ) -> Decimal | None:
        """Teto do INSS para contribuinte individual — única faixa (11% plana)."""
        stmt = (
            select(TabelaInssFaixa.valor_ate)
            .where(TabelaInssFaixa.tipo == "contribuinte_individual")
            .where(TabelaInssFaixa.valid_from <= em)
            .where(
                (TabelaInssFaixa.valid_to == None)  # noqa: E711
                | (TabelaInssFaixa.valid_to >= em)
            )
            .order_by(TabelaInssFaixa.valid_from.desc())
            .limit(1)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


# Reexporta dataclasses úteis para o service (evita imports cruzados nos callers).
__all__ = [
    "FuncionarioRepo",
    "FolhaRepo",
    "HoleriteRepo",
    "EventoFolhaRepo",
    "SocioRepo",
    "ProlaboreRepo",
    "DistribuicaoRepo",
    "EventoESocialRepo",
    "TabelasTributariasRepo",
    "ResultadoFgts",
    "ResultadoInssEmpregado",
    "ResultadoIrrf",
]
