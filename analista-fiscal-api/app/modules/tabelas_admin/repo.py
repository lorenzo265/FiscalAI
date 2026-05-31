"""Repositórios do painel admin de tabelas tributárias (Sprint 19.5 PR1).

Dois repos:

  * ``VigenciaTabelaLogRepo`` — CRUD do audit log ``vigencia_tabela_log``.
    Idempotência §8.9: ``by_idempotency_key`` permite o service detectar
    re-POST antes de tocar a tabela SCD.

  * ``SCDTabelasRepo`` — bridge thin para as 7 tabelas SCD tributárias.
    Cada método executa o INSERT — o trigger ``scd_close_previous_valid_to``
    da migration 0025 fecha o ``valid_to`` da vigência anterior automaticamente.
    O método retorna o número de linhas criadas (registros_criados do log).
    Não exporta um "update": SCD nunca atualiza, só insere nova versão.

Leitura de "max(valid_from existente)" para validação pré-INSERT no service
fica em métodos ``max_valid_from_<tipo>`` — usados antes de gravar para
devolver 422 claro em vez de deixar o trigger criar uma vigência sem efeito.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tabelas_admin.schemas import (
    VigenciaCbsIbsIn,
    VigenciaFgtsIn,
    VigenciaIcmsUfIn,
    VigenciaInssIn,
    VigenciaIrrfIn,
    VigenciaPresuncaoLpIn,
    VigenciaSimplesNacionalIn,
)
from app.shared.db.models import (
    AliquotaCbsIbs,
    AliquotaIcmsUf,
    PresuncaoLucroPresumido,
    TabelaFgtsAliquota,
    TabelaInssFaixa,
    TabelaIrrfFaixa,
    TabelaSimplesFaixa,
    VigenciaTabelaLog,
)


class VigenciaTabelaLogRepo:
    """CRUD do audit log."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def por_idempotency_key(
        self, key: UUID
    ) -> VigenciaTabelaLog | None:
        stmt = select(VigenciaTabelaLog).where(
            VigenciaTabelaLog.idempotency_key == key
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def criar(self, log: VigenciaTabelaLog) -> VigenciaTabelaLog:
        self._s.add(log)
        await self._s.flush()
        await self._s.refresh(log)
        return log

    async def listar_historico(
        self, tipo_tabela: str, *, limit: int = 50
    ) -> list[VigenciaTabelaLog]:
        stmt = (
            select(VigenciaTabelaLog)
            .where(VigenciaTabelaLog.tipo_tabela == tipo_tabela)
            .order_by(VigenciaTabelaLog.valid_from.desc())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())


class SCDTabelasRepo:
    """Bridge para as 7 tabelas SCD tributárias. Cada método persiste as
    linhas da nova vigência; o trigger ``scd_close_previous_valid_to`` da
    migration 0025 fecha o ``valid_to`` das vigências anteriores.

    O parâmetro ``fonte_norma`` é propagado para a coluna ``fonte`` (ou
    ``fonte_norma`` no caso CBS/IBS) de cada linha — citação obrigatória
    §8.5 também no fato persistido, não só no log de auditoria.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── max(valid_from) por tipo (validação pré-INSERT no service) ──────

    async def max_valid_from_inss(self) -> date | None:
        stmt = select(func.max(TabelaInssFaixa.valid_from))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_irrf(self) -> date | None:
        stmt = select(func.max(TabelaIrrfFaixa.valid_from))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_fgts(self) -> date | None:
        stmt = select(func.max(TabelaFgtsAliquota.valid_from))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_simples(self, anexo: str) -> date | None:
        stmt = select(func.max(TabelaSimplesFaixa.valid_from)).where(
            TabelaSimplesFaixa.anexo == anexo
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_presuncao(self) -> date | None:
        stmt = select(func.max(PresuncaoLucroPresumido.valid_from))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_icms(self, uf: str) -> date | None:
        stmt = select(func.max(AliquotaIcmsUf.valid_from)).where(
            AliquotaIcmsUf.uf == uf
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def max_valid_from_cbs_ibs(self) -> date | None:
        stmt = select(func.max(AliquotaCbsIbs.valid_from))
        return (await self._s.execute(stmt)).scalar_one_or_none()

    # ── INSERTs (trigger SCD fecha valid_to anterior) ──────────────────

    async def inserir_inss(
        self, payload: VigenciaInssIn, *, fonte_norma: str
    ) -> int:
        for f in payload.faixas:
            self._s.add(
                TabelaInssFaixa(
                    tipo=f.tipo,
                    faixa=f.faixa,
                    valor_ate=f.valor_ate,
                    aliquota=f.aliquota,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.faixas)

    async def inserir_irrf(
        self, payload: VigenciaIrrfIn, *, fonte_norma: str
    ) -> int:
        for f in payload.faixas:
            self._s.add(
                TabelaIrrfFaixa(
                    faixa=f.faixa,
                    base_ate=f.base_ate,
                    aliquota=f.aliquota,
                    parcela_deduzir=f.parcela_deduzir,
                    deducao_dependente=payload.deducao_dependente,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.faixas)

    async def inserir_fgts(
        self, payload: VigenciaFgtsIn, *, fonte_norma: str
    ) -> int:
        for a in payload.aliquotas:
            self._s.add(
                TabelaFgtsAliquota(
                    vinculo=a.vinculo,
                    aliquota=a.aliquota,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.aliquotas)

    async def inserir_simples_nacional(
        self, payload: VigenciaSimplesNacionalIn, *, fonte_norma: str
    ) -> int:
        for f in payload.faixas:
            self._s.add(
                TabelaSimplesFaixa(
                    anexo=payload.anexo,
                    faixa=f.faixa,
                    rbt12_ate=f.rbt12_ate,
                    aliquota_nominal=f.aliquota_nominal,
                    parcela_deduzir=f.parcela_deduzir,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.faixas)

    async def inserir_presuncao_lp(
        self, payload: VigenciaPresuncaoLpIn, *, fonte_norma: str
    ) -> int:
        for p in payload.presuncoes:
            self._s.add(
                PresuncaoLucroPresumido(
                    grupo_atividade=p.grupo_atividade,
                    cnae_pattern=p.cnae_pattern,
                    percentual_irpj=p.percentual_irpj,
                    percentual_csll=p.percentual_csll,
                    limite_receita_anual=p.limite_receita_anual,
                    prioridade=p.prioridade,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.presuncoes)

    async def inserir_icms_uf(
        self, payload: VigenciaIcmsUfIn, *, fonte_norma: str
    ) -> int:
        for a in payload.aliquotas:
            self._s.add(
                AliquotaIcmsUf(
                    uf=a.uf,
                    aliquota_interna=a.aliquota_interna,
                    aliquota_fecp=a.aliquota_fecp,
                    # Sprint 19.6 PR1 (#33) — dia vencimento por UF.
                    dia_vencimento_padrao=a.dia_vencimento_padrao,
                    valid_from=payload.valid_from,
                    fonte=fonte_norma,
                )
            )
        await self._s.flush()
        return len(payload.aliquotas)

    async def inserir_cbs_ibs(
        self, payload: VigenciaCbsIbsIn, *, fonte_norma: str
    ) -> int:
        for a in payload.aliquotas:
            self._s.add(
                AliquotaCbsIbs(
                    fase=a.fase,
                    regime=a.regime,
                    cnae_pattern=a.cnae_pattern,
                    classificacao_lc214=a.classificacao_lc214,
                    aliquota_cbs=a.aliquota_cbs,
                    aliquota_ibs=a.aliquota_ibs,
                    valid_from=payload.valid_from,
                    algoritmo_versao=payload.algoritmo_versao,
                    fonte_norma=fonte_norma,
                    observacao=a.observacao,
                )
            )
        await self._s.flush()
        return len(payload.aliquotas)

    # ── Snapshot: vigência ativa em uma data (GET /vigente?em=...) ─────

    async def snapshot_inss(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(TabelaInssFaixa)
            .where(TabelaInssFaixa.valid_from <= em)
            .where(
                (TabelaInssFaixa.valid_to.is_(None))
                | (TabelaInssFaixa.valid_to >= em)
            )
            .order_by(TabelaInssFaixa.tipo, TabelaInssFaixa.faixa)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "tipo": r.tipo,
                "faixa": r.faixa,
                "valor_ate": str(r.valor_ate),
                "aliquota": str(r.aliquota),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    async def snapshot_irrf(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(TabelaIrrfFaixa)
            .where(TabelaIrrfFaixa.valid_from <= em)
            .where(
                (TabelaIrrfFaixa.valid_to.is_(None))
                | (TabelaIrrfFaixa.valid_to >= em)
            )
            .order_by(TabelaIrrfFaixa.faixa)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "faixa": r.faixa,
                "base_ate": str(r.base_ate),
                "aliquota": str(r.aliquota),
                "parcela_deduzir": str(r.parcela_deduzir),
                "deducao_dependente": str(r.deducao_dependente),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    async def snapshot_fgts(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(TabelaFgtsAliquota)
            .where(TabelaFgtsAliquota.valid_from <= em)
            .where(
                (TabelaFgtsAliquota.valid_to.is_(None))
                | (TabelaFgtsAliquota.valid_to >= em)
            )
            .order_by(TabelaFgtsAliquota.vinculo)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "vinculo": r.vinculo,
                "aliquota": str(r.aliquota),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    async def snapshot_simples(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(TabelaSimplesFaixa)
            .where(TabelaSimplesFaixa.valid_from <= em)
            .where(
                (TabelaSimplesFaixa.valid_to.is_(None))
                | (TabelaSimplesFaixa.valid_to >= em)
            )
            .order_by(TabelaSimplesFaixa.anexo, TabelaSimplesFaixa.faixa)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "anexo": r.anexo,
                "faixa": r.faixa,
                "rbt12_ate": str(r.rbt12_ate),
                "aliquota_nominal": str(r.aliquota_nominal),
                "parcela_deduzir": str(r.parcela_deduzir),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    async def snapshot_presuncao(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(PresuncaoLucroPresumido)
            .where(PresuncaoLucroPresumido.valid_from <= em)
            .where(
                (PresuncaoLucroPresumido.valid_to.is_(None))
                | (PresuncaoLucroPresumido.valid_to >= em)
            )
            .order_by(
                PresuncaoLucroPresumido.prioridade,
                PresuncaoLucroPresumido.grupo_atividade,
            )
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "grupo_atividade": r.grupo_atividade,
                "cnae_pattern": r.cnae_pattern,
                "percentual_irpj": str(r.percentual_irpj),
                "percentual_csll": str(r.percentual_csll),
                "limite_receita_anual": (
                    str(r.limite_receita_anual)
                    if r.limite_receita_anual is not None
                    else None
                ),
                "prioridade": r.prioridade,
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    async def snapshot_icms(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(AliquotaIcmsUf)
            .where(AliquotaIcmsUf.valid_from <= em)
            .where(
                (AliquotaIcmsUf.valid_to.is_(None))
                | (AliquotaIcmsUf.valid_to >= em)
            )
            .order_by(AliquotaIcmsUf.uf)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "uf": r.uf,
                "aliquota_interna": str(r.aliquota_interna),
                "aliquota_fecp": str(r.aliquota_fecp),
                # Sprint 19.6 PR1 (#33) — exposto no snapshot pra UI.
                "dia_vencimento_padrao": r.dia_vencimento_padrao,
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]

    # ── Helpers usados pelo worker PR2 (lê só o valid_from ativo) ───────

    async def valid_from_ativa_inss(self, em: date) -> date | None:
        """Máximo ``valid_from`` ainda ativo em ``em`` (vigência corrente)."""
        stmt = (
            select(func.max(TabelaInssFaixa.valid_from))
            .where(TabelaInssFaixa.valid_from <= em)
            .where(
                (TabelaInssFaixa.valid_to.is_(None))
                | (TabelaInssFaixa.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def valid_from_ativa_irrf(self, em: date) -> date | None:
        stmt = (
            select(func.max(TabelaIrrfFaixa.valid_from))
            .where(TabelaIrrfFaixa.valid_from <= em)
            .where(
                (TabelaIrrfFaixa.valid_to.is_(None))
                | (TabelaIrrfFaixa.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def valid_from_ativa_fgts(self, em: date) -> date | None:
        stmt = (
            select(func.max(TabelaFgtsAliquota.valid_from))
            .where(TabelaFgtsAliquota.valid_from <= em)
            .where(
                (TabelaFgtsAliquota.valid_to.is_(None))
                | (TabelaFgtsAliquota.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def valid_from_ativa_simples(self, em: date) -> date | None:
        stmt = (
            select(func.max(TabelaSimplesFaixa.valid_from))
            .where(TabelaSimplesFaixa.valid_from <= em)
            .where(
                (TabelaSimplesFaixa.valid_to.is_(None))
                | (TabelaSimplesFaixa.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def valid_from_ativa_presuncao(self, em: date) -> date | None:
        stmt = (
            select(func.max(PresuncaoLucroPresumido.valid_from))
            .where(PresuncaoLucroPresumido.valid_from <= em)
            .where(
                (PresuncaoLucroPresumido.valid_to.is_(None))
                | (PresuncaoLucroPresumido.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def valid_from_ativa_icms_por_uf(
        self, em: date
    ) -> dict[str, date]:
        """Devolve ``{uf: valid_from_ativo}`` para cada UF com vigência ativa."""
        stmt = (
            select(AliquotaIcmsUf.uf, func.max(AliquotaIcmsUf.valid_from))
            .where(AliquotaIcmsUf.valid_from <= em)
            .where(
                (AliquotaIcmsUf.valid_to.is_(None))
                | (AliquotaIcmsUf.valid_to >= em)
            )
            .group_by(AliquotaIcmsUf.uf)
        )
        rows = (await self._s.execute(stmt)).all()
        return {uf: vf for uf, vf in rows}

    async def valid_from_ativa_cbs_ibs(self, em: date) -> date | None:
        stmt = (
            select(func.max(AliquotaCbsIbs.valid_from))
            .where(AliquotaCbsIbs.valid_from <= em)
            .where(
                (AliquotaCbsIbs.valid_to.is_(None))
                | (AliquotaCbsIbs.valid_to >= em)
            )
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def proxima_vigencia_futura_cbs_ibs(
        self, em: date
    ) -> date | None:
        """Próxima ``valid_from`` futura registrada (vigência agendada)."""
        stmt = (
            select(func.min(AliquotaCbsIbs.valid_from))
            .where(AliquotaCbsIbs.valid_from > em)
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()

    async def snapshot_cbs_ibs(self, em: date) -> list[dict[str, Any]]:
        stmt = (
            select(AliquotaCbsIbs)
            .where(AliquotaCbsIbs.valid_from <= em)
            .where(
                (AliquotaCbsIbs.valid_to.is_(None))
                | (AliquotaCbsIbs.valid_to >= em)
            )
            .order_by(AliquotaCbsIbs.fase, AliquotaCbsIbs.valid_from)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {
                "fase": r.fase,
                "regime": r.regime,
                "cnae_pattern": r.cnae_pattern,
                "classificacao_lc214": r.classificacao_lc214,
                "aliquota_cbs": str(r.aliquota_cbs),
                "aliquota_ibs": str(r.aliquota_ibs),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]


__all__ = ["VigenciaTabelaLogRepo", "SCDTabelasRepo"]
