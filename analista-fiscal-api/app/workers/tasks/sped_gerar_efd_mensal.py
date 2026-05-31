"""Tarefas Celery — geração mensal proativa de EFD-Contribuições + EFD ICMS-IPI.

Sprint 19.6 PR4 (#34). Beat schedule (ver ``celery_app.py``):

  * ``sped.gerar_efd_contribuicoes_mensal`` — dia 5 às 04:00 BR (prazo
    legal: 10º dia útil do 2º mês subsequente, ~6 semanas de folga).
  * ``sped.gerar_efd_icms_ipi_mensal`` — dia 5 às 04:00 BR (prazo varia
    por UF — Convênio ICMS 92/2006 padrão dia 20 do mês seguinte, mas
    SP/RS/MG têm prazos próprios cobertos pela coluna
    `aliquota_icms_uf.dia_vencimento_padrao` da Sprint 19.6 PR1).

Geram a competência do **mês anterior** (mês fechado). Idempotente —
service levanta ``SpedJaGerado`` quando versão ativa existe.

Resiliente — falha em uma empresa não aborta as demais. EFD-Contribuições
hoje cobre só Lucro Presumido (regime cumulativo); LR é out-of-scope
MVP (PlanoBackend §1.1). EFD ICMS-IPI itera empresas com IE cadastrada
(qualquer regime).

Pattern espelha ``sped_gerar_anual.py`` mas a unidade é mês civil.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.config import get_settings
from app.modules.sped.efd.service import EfdContribuicoesService, EfdIcmsIpiService
from app.shared.db.models import Empresa
from app.shared.db.perf import build_async_engine
from app.shared.exceptions import (
    EmpresaNaoElegivelEfd,
    SemDadosParaSped,
    SpedJaGerado,
)
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

_GerarMensalFn = Callable[
    [AsyncSession, Empresa, date], Awaitable[None]
]

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@celery_app.task(
    name="sped.gerar_efd_contribuicoes_mensal",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_efd_contribuicoes_mensal() -> JsonObject:
    """Gera EFD-Contribuições do mês anterior pra todas empresas LP ativas.

    MVP: cobre apenas regime cumulativo (LP). Lucro Real out-of-scope
    (PlanoBackend §1.1 — sempre foi SN+LP).
    """
    competencia_alvo = _competencia_mes_anterior()
    return _executar_geracao(
        competencia_alvo=competencia_alvo,
        gerar_fn=_gerar_efd_contribuicoes_para_empresa,
        nome_log="sped.efd_contribuicoes",
        regimes_aceitos=("lucro_presumido",),
        exige_inscricao_estadual=False,
    )


@celery_app.task(
    name="sped.gerar_efd_icms_ipi_mensal",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_efd_icms_ipi_mensal() -> JsonObject:
    """Gera EFD ICMS-IPI do mês anterior pra empresas com IE ativa.

    Independente de regime (LP/SN/LR) — depende apenas de ter inscrição
    estadual. Empresas sem IE são puladas (``EmpresaNaoElegivelEfd``).
    """
    competencia_alvo = _competencia_mes_anterior()
    return _executar_geracao(
        competencia_alvo=competencia_alvo,
        gerar_fn=_gerar_efd_icms_ipi_para_empresa,
        nome_log="sped.efd_icms_ipi",
        regimes_aceitos=None,  # qualquer regime — filtro é por IE
        exige_inscricao_estadual=True,
    )


# ── Implementação compartilhada ─────────────────────────────────────────────


def _competencia_mes_anterior() -> date:
    """Primeiro dia do mês anterior ao corrente (BR timezone)."""
    hoje = datetime.now(_TZ_BR).date()
    if hoje.month == 1:
        return date(hoje.year - 1, 12, 1)
    return date(hoje.year, hoje.month - 1, 1)


async def _gerar_efd_contribuicoes_para_empresa(
    session: AsyncSession, empresa: Empresa, competencia: date
) -> None:
    await EfdContribuicoesService().gerar(
        session, empresa.tenant_id, empresa.id, competencia=competencia
    )


async def _gerar_efd_icms_ipi_para_empresa(
    session: AsyncSession, empresa: Empresa, competencia: date
) -> None:
    await EfdIcmsIpiService().gerar(
        session, empresa.tenant_id, empresa.id, competencia=competencia
    )


async def _executar_geracao_async(
    *,
    competencia_alvo: date,
    gerar_fn: _GerarMensalFn,
    nome_log: str,
    regimes_aceitos: tuple[str, ...] | None,
    exige_inscricao_estadual: bool,
) -> JsonObject:
    """Pipeline async — exposto para testes mockarem.

    Contadores:
      * ``empresas_ok`` — gerou nova versão.
      * ``empresas_ja_gerada`` — ``SpedJaGerado`` (idempotente, não-erro).
      * ``empresas_sem_dados`` — ``SemDadosParaSped`` (apuração pendente).
      * ``empresas_nao_elegivel`` — MEI / SN (EFD-Contrib) ou sem IE
        (EFD ICMS-IPI).
      * ``empresas_erro`` — exceção inesperada (loga + segue).
    """
    settings = get_settings()
    engine = build_async_engine(settings)
    empresas_ok = 0
    empresas_ja_gerada = 0
    empresas_sem_dados = 0
    empresas_nao_elegivel = 0
    empresas_erro = 0

    try:
        sess_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with sess_factory() as session:
            stmt = select(Empresa).where(Empresa.ativa.is_(True))
            if regimes_aceitos is not None:
                stmt = stmt.where(
                    Empresa.regime_tributario.in_(regimes_aceitos)
                )
            if exige_inscricao_estadual:
                stmt = stmt.where(Empresa.ie.is_not(None))
            empresas = list(
                (await session.execute(stmt)).scalars().all()
            )

        for empresa in empresas:
            async with sess_factory() as session:
                try:
                    await gerar_fn(session, empresa, competencia_alvo)
                    empresas_ok += 1
                except SpedJaGerado:
                    empresas_ja_gerada += 1
                except SemDadosParaSped:
                    empresas_sem_dados += 1
                except EmpresaNaoElegivelEfd:
                    empresas_nao_elegivel += 1
                except Exception:
                    await session.rollback()
                    log.exception(
                        f"{nome_log}.empresa_falhou",
                        empresa_id=str(empresa.id),
                        competencia=competencia_alvo.isoformat(),
                    )
                    empresas_erro += 1
    finally:
        await engine.dispose()

    resultado: JsonObject = {
        "status": "ok",
        "competencia": competencia_alvo.isoformat(),
        "empresas_ok": empresas_ok,
        "empresas_ja_gerada": empresas_ja_gerada,
        "empresas_sem_dados": empresas_sem_dados,
        "empresas_nao_elegivel": empresas_nao_elegivel,
        "empresas_erro": empresas_erro,
    }
    log.info(f"{nome_log}.batch_concluido", **resultado)
    return resultado


def _executar_geracao(
    *,
    competencia_alvo: date,
    gerar_fn: _GerarMensalFn,
    nome_log: str,
    regimes_aceitos: tuple[str, ...] | None,
    exige_inscricao_estadual: bool,
) -> JsonObject:
    """Wrapper sync — entry point usado pelas tasks Celery."""
    try:
        return asyncio.run(
            _executar_geracao_async(
                competencia_alvo=competencia_alvo,
                gerar_fn=gerar_fn,
                nome_log=nome_log,
                regimes_aceitos=regimes_aceitos,
                exige_inscricao_estadual=exige_inscricao_estadual,
            )
        )
    except Exception:
        log.exception(f"{nome_log}.batch_falhou")
        raise


__all__ = [
    "gerar_efd_contribuicoes_mensal",
    "gerar_efd_icms_ipi_mensal",
]
