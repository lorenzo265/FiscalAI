"""Service do Lucro Presumido (Sprint 11 PR1).

Apura IRPJ/CSLL trimestrais e PIS/Cofins mensais, resolve presunção por
CNAE da empresa e persiste em ``apuracao_fiscal`` (tabela central — §8.2,
§8.9 garante idempotência via UNIQUE composto).

§8.1 RLS via ``get_session``.
§8.2 Apuração persistida é fato imutável.
§8.3 Snapshot da presunção vigente vai pro ``output_jsonb`` (SCD-friendly).
§8.10 Log estruturado por apuração.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.types import JsonObject

from app.modules.empresa.repo import EmpresaRepo
from app.modules.lucro_presumido.calcula_csll import (
    ResultadoCsllLp,
    calcular_csll_trimestral,
)
from app.modules.lucro_presumido.calcula_irpj import (
    ResultadoIrpjLp,
    calcular_irpj_trimestral,
)
from app.modules.lucro_presumido.calcula_pis_cofins import (
    ResultadoTributoCumulativo,
    calcular_cofins_cumulativo_mensal,
    calcular_pis_cumulativo_mensal,
)
from app.modules.lucro_presumido.repo import (
    ApuracaoLpRepo,
    PresuncaoLpRepo,
    PresuncaoResolvida,
)
from app.modules.lucro_presumido.schemas import (
    ApurarIrpjCsllTrimestralIn,
    ApurarPisCofinsMensalIn,
)
from app.shared.db.models import ApuracaoFiscal, Empresa
from app.shared.exceptions import (
    ApuracaoLPJaExiste,
    EmpresaForaDoRegimeLP,
    EmpresaNaoEncontrada,
    PresuncaoNaoEncontrada,
)

log = structlog.get_logger(__name__)

_REGIME_LP = "lucro_presumido"


class LucroPresumidoService:
    # ── IRPJ / CSLL trimestrais ─────────────────────────────────────────

    async def apurar_irpj_trimestral(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarIrpjCsllTrimestralIn,
    ) -> ApuracaoFiscal:
        empresa = await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(payload.ano, payload.trimestre)
        presuncao = await _resolver_presuncao(session, competencia, empresa)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, "irpj"):
            raise ApuracaoLPJaExiste(
                f"IRPJ {payload.ano}-T{payload.trimestre} já apurado"
            )

        resultado = calcular_irpj_trimestral(
            receita_bruta_trimestre=payload.receita_bruta_trimestre,
            percentual_presuncao=presuncao.percentual_irpj,
            ganhos_capital=payload.ganhos_capital,
            receitas_aplicacoes=payload.receitas_aplicacoes,
            outras_adicoes=payload.outras_adicoes,
            meses_periodo=payload.meses_periodo,
            irrf_a_compensar=payload.irrf_a_compensar,
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo="irpj",
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas=_stringify(_presuncao_snapshot(presuncao)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, "irpj", competencia, resultado)
        return apuracao

    async def apurar_csll_trimestral(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarIrpjCsllTrimestralIn,
    ) -> ApuracaoFiscal:
        empresa = await _empresa_lp(session, empresa_id)
        competencia = _data_trimestre(payload.ano, payload.trimestre)
        presuncao = await _resolver_presuncao(session, competencia, empresa)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, "csll"):
            raise ApuracaoLPJaExiste(
                f"CSLL {payload.ano}-T{payload.trimestre} já apurada"
            )

        resultado = calcular_csll_trimestral(
            receita_bruta_trimestre=payload.receita_bruta_trimestre,
            percentual_presuncao=presuncao.percentual_csll,
            ganhos_capital=payload.ganhos_capital,
            receitas_aplicacoes=payload.receitas_aplicacoes,
            outras_adicoes=payload.outras_adicoes,
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo="csll",
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas=_stringify(_presuncao_snapshot(presuncao)),
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, "csll", competencia, resultado)
        return apuracao

    # ── PIS / Cofins mensais ────────────────────────────────────────────

    async def apurar_pis_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
    ) -> ApuracaoFiscal:
        return await self._apurar_cumulativo(
            session, tenant_id, empresa_id, payload, tipo="pis",
        )

    async def apurar_cofins_mensal(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
    ) -> ApuracaoFiscal:
        return await self._apurar_cumulativo(
            session, tenant_id, empresa_id, payload, tipo="cofins",
        )

    async def _apurar_cumulativo(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        empresa_id: UUID,
        payload: ApurarPisCofinsMensalIn,
        *,
        tipo: str,
    ) -> ApuracaoFiscal:
        await _empresa_lp(session, empresa_id)
        competencia = date(payload.competencia.year, payload.competencia.month, 1)

        if await ApuracaoLpRepo(session).buscar(empresa_id, competencia, tipo):
            raise ApuracaoLPJaExiste(
                f"{tipo.upper()} de {competencia.isoformat()} já apurado"
            )

        fn = (
            calcular_pis_cumulativo_mensal
            if tipo == "pis"
            else calcular_cofins_cumulativo_mensal
        )
        resultado = fn(
            payload.receita_bruta_mes, exclusoes=payload.exclusoes
        )
        apuracao = ApuracaoFiscal(
            tenant_id=tenant_id,
            empresa_id=empresa_id,
            competencia=competencia,
            tipo=tipo,
            regime=_REGIME_LP,
            input_jsonb=_stringify(payload.model_dump()),
            output_jsonb=_stringify(asdict(resultado)),
            faixas_usadas={"observacao": "regime cumulativo (Lei 9.718/1998)"},
            algoritmo_versao=resultado.algoritmo_versao,
        )
        await _commit_apuracao(session, apuracao)
        _log_apuracao(empresa_id, tipo, competencia, resultado)
        return apuracao

    # ── Helper de diagnóstico (debug do match de CNAE) ──────────────────

    async def resolver_presuncao(
        self, session: AsyncSession, empresa_id: UUID, em: date
    ) -> PresuncaoResolvida:
        empresa = await _empresa_lp(session, empresa_id)
        return await _resolver_presuncao(session, em, empresa)


# ── Helpers privados ─────────────────────────────────────────────────────


def _data_trimestre(ano: int, trimestre: int) -> date:
    """Primeiro dia do trimestre (1/1, 1/4, 1/7, 1/10) — competência canônica."""
    mes_inicial = {1: 1, 2: 4, 3: 7, 4: 10}[trimestre]
    return date(ano, mes_inicial, 1)


async def _empresa_lp(session: AsyncSession, empresa_id: UUID) -> Empresa:
    empresa = await EmpresaRepo(session).por_id(empresa_id)
    if empresa is None:
        raise EmpresaNaoEncontrada(f"Empresa {empresa_id} não encontrada")
    if empresa.regime_tributario != _REGIME_LP:
        raise EmpresaForaDoRegimeLP(
            f"Empresa está em regime {empresa.regime_tributario!r}, não em "
            f"lucro_presumido — apuração indevida"
        )
    return empresa


async def _resolver_presuncao(
    session: AsyncSession, em: date, empresa: Empresa
) -> PresuncaoResolvida:
    # Fase 2 PR3: RBT12 vem de rbt12_mensal (view materializada) com fallback
    # para empresa.faturamento_12m declarado.
    rbt12_da_view = await EmpresaRepo(session).rbt12_da_view(empresa.id, em)
    faturamento = (
        rbt12_da_view if rbt12_da_view is not None else empresa.faturamento_12m
    )
    resolvida = await PresuncaoLpRepo(session).resolver_por_cnae(
        em, empresa.cnae_principal, faturamento_12m=faturamento,
    )
    if resolvida is None:
        raise PresuncaoNaoEncontrada(
            f"Sem grupo de presunção LP para CNAE {empresa.cnae_principal!r} "
            f"em {em.isoformat()}"
        )
    return resolvida


def _presuncao_snapshot(p: PresuncaoResolvida) -> JsonObject:
    return {
        "grupo_atividade": p.grupo_atividade,
        "percentual_irpj": str(p.percentual_irpj),
        "percentual_csll": str(p.percentual_csll),
        "cnae_pattern": p.cnae_pattern,
        "prioridade": p.prioridade,
        "fonte": p.fonte,
    }


async def _commit_apuracao(
    session: AsyncSession, apuracao: ApuracaoFiscal
) -> None:
    try:
        await ApuracaoLpRepo(session).criar(apuracao)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApuracaoLPJaExiste(
            f"Apuração ({apuracao.tipo}, {apuracao.competencia}) já existe"
        ) from exc


def _log_apuracao(
    empresa_id: UUID, tipo: str, competencia: date, resultado: object
) -> None:
    log.info(
        f"lp.{tipo}.apurado",
        empresa_id=str(empresa_id),
        competencia=competencia.isoformat(),
        algoritmo_versao=getattr(resultado, "algoritmo_versao", None),
    )


def _stringify(o: Any) -> Any:  # noqa: ANN401 — helper recursivo dinâmico
    """Converte Decimals e datas em strings JSON-safe."""
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_stringify(x) for x in o]
    return o
