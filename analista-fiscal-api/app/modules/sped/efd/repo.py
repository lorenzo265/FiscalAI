"""Repositórios — SPED EFD-Contribuições mensal (Sprint 17 PR1).

Coleta:

* Documentos fiscais (NF-e/NFC-e/NFS-e) emitidos no mês — alimentam
  blocos A e C do gerador.
* Apurações PIS + Cofins já calculadas (Sprint 11 PR1) — alimentam o
  bloco M consolidado.

Todas as queries respeitam RLS (sessão tem ``SET LOCAL app.tenant_id``).
``ArquivoSpedRepo`` é re-exportado de ``ecd.repo`` — é genérico por tipo
e serve ECD/ECF/EFD igual.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sped.ecd.repo import ArquivoSpedRepo  # re-export genérico
from app.shared.db.models import ApuracaoFiscal, DocumentoFiscal

_TZ_BR = ZoneInfo("America/Sao_Paulo")

__all__ = [
    "ApuracaoIcmsLida",
    "ApuracaoPisCofinsAgregada",
    "ApuracoesIcmsRepo",
    "ApuracoesPisCofinsRepo",
    "ArquivoSpedRepo",
    "DocumentosParaEfdRepo",
]


@dataclass(frozen=True, slots=True)
class ApuracaoIcmsLida:
    """Snapshot extraído da ``ApuracaoFiscal`` (tipo='icms') da Sprint 11 PR2.

    Os campos espelham ``ResultadoIcmsMensal`` de
    ``app/modules/icms/calcula_icms.py`` (algoritmo ``icms.mensal.v1``).
    """

    uf: str
    debito: Decimal
    credito: Decimal
    saldo_credor_anterior: Decimal
    ajustes_devedores: Decimal
    ajustes_credores: Decimal
    icms_a_recolher: Decimal
    saldo_credor_a_transportar: Decimal


@dataclass(frozen=True, slots=True)
class ApuracaoPisCofinsAgregada:
    """Snapshot dos dois ``ApuracaoFiscal`` (pis + cofins) do mês.

    Os valores são extraídos do ``output_jsonb`` persistido na Sprint 11
    PR1 (``lp.pis.cumulativo.v1`` / ``lp.cofins.cumulativo.v1``).
    """

    base_calculo_pis: Decimal
    aliquota_pis: Decimal  # 0.0065 (fração) — converter para % no service
    valor_pis: Decimal
    base_calculo_cofins: Decimal
    aliquota_cofins: Decimal  # 0.03
    valor_cofins: Decimal


class DocumentosParaEfdRepo:
    """Lê documentos fiscais do mês (RLS pela sessão)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_periodo(
        self,
        empresa_id: UUID,
        periodo_inicio: date,
        periodo_fim: date,
        *,
        tipos: tuple[str, ...] = ("nfe", "nfce", "nfse"),
        somente_vigentes: bool = True,
    ) -> list[DocumentoFiscal]:
        """Documentos no intervalo, filtrando tipos relevantes para EFD.

        ``somente_vigentes=True`` exclui versões superseded (§8.2) — usa
        apenas a linha ativa de cada chave. Cancelados ficam (mas
        recebem ``COD_SIT='02'`` no gerador).
        """
        condicoes = [
            DocumentoFiscal.empresa_id == empresa_id,
            DocumentoFiscal.emitida_em >= _datetime_inicio_dia(periodo_inicio),
            DocumentoFiscal.emitida_em < _datetime_inicio_dia(_dia_seguinte(periodo_fim)),
            DocumentoFiscal.tipo.in_(tipos),
        ]
        if somente_vigentes:
            condicoes.append(DocumentoFiscal.superseded_by.is_(None))

        stmt = (
            select(DocumentoFiscal)
            .where(and_(*condicoes))
            .order_by(
                asc(DocumentoFiscal.emitida_em),
                asc(DocumentoFiscal.numero),
            )
        )
        return list((await self._s.execute(stmt)).scalars().all())


class ApuracoesPisCofinsRepo:
    """Lê apurações PIS + Cofins persistidas (Sprint 11 PR1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_competencia(
        self, empresa_id: UUID, competencia: date
    ) -> ApuracaoPisCofinsAgregada | None:
        """Carrega PIS + Cofins do mês e agrega em um único DTO.

        Retorna ``None`` se *qualquer* dos dois faltar — service decide
        se isso vira ``SemDadosParaSped`` ou se a EFD vai com bases zero
        (mês sem movimento).
        """
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia == competencia)
            .where(ApuracaoFiscal.tipo.in_(("pis", "cofins")))
        )
        registros = list((await self._s.execute(stmt)).scalars().all())
        if len(registros) < 2:
            return None
        por_tipo = {r.tipo: r for r in registros}
        if "pis" not in por_tipo or "cofins" not in por_tipo:
            return None

        pis = por_tipo["pis"].output_jsonb
        cofins = por_tipo["cofins"].output_jsonb
        return ApuracaoPisCofinsAgregada(
            base_calculo_pis=_dec(pis.get("base_calculo")),
            aliquota_pis=_dec(pis.get("aliquota")),
            valor_pis=_dec(pis.get("tributo")),
            base_calculo_cofins=_dec(cofins.get("base_calculo")),
            aliquota_cofins=_dec(cofins.get("aliquota")),
            valor_cofins=_dec(cofins.get("tributo")),
        )


class ApuracoesIcmsRepo:
    """Lê apuração ICMS mensal persistida (Sprint 11 PR2, ``icms.mensal.v1``)."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_competencia(
        self, empresa_id: UUID, competencia: date
    ) -> ApuracaoIcmsLida | None:
        """Carrega a apuração ICMS do mês.

        Retorna ``None`` se não houver — service decide se levanta
        ``SemDadosParaSped`` ou se a EFD vai com bases zero.
        """
        stmt = (
            select(ApuracaoFiscal)
            .where(ApuracaoFiscal.empresa_id == empresa_id)
            .where(ApuracaoFiscal.competencia == competencia)
            .where(ApuracaoFiscal.tipo == "icms")
        )
        registro = (await self._s.execute(stmt)).scalar_one_or_none()
        if registro is None:
            return None
        output = registro.output_jsonb
        return ApuracaoIcmsLida(
            uf=str(output.get("uf", "")),
            debito=_dec(output.get("debito")),
            credito=_dec(output.get("credito")),
            saldo_credor_anterior=_dec(output.get("saldo_credor_anterior")),
            ajustes_devedores=_dec(output.get("ajustes_devedores")),
            ajustes_credores=_dec(output.get("ajustes_credores")),
            icms_a_recolher=_dec(output.get("icms_a_recolher")),
            saldo_credor_a_transportar=_dec(
                output.get("saldo_credor_a_transportar")
            ),
        )


# ── Helpers internos ────────────────────────────────────────────────────────


def _dec(valor: object) -> Decimal:
    """Converte qualquer numérico vindo do JSONB em Decimal (zero em ``None``)."""
    if valor is None:
        return Decimal("0")
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(cast(int | float | str, valor)))


def _datetime_inicio_dia(d: date) -> datetime:
    """``date`` → ``datetime`` à 00:00 (tz-aware America/Sao_Paulo).

    A coluna ``emitida_em`` é ``TIMESTAMPTZ``; o filtro precisa de
    ``datetime`` consciente do fuso para não excluir notas emitidas
    perto de 00:00 UTC.
    """
    return datetime(d.year, d.month, d.day, tzinfo=_TZ_BR)


def _dia_seguinte(d: date) -> date:
    return d + timedelta(days=1)
