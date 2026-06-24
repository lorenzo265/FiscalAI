"""Tarefas Celery — geração anual proativa de ECD e ECF (Sprint 16 PR3).

Beat schedule (ver ``celery_app.py``):

  * ``sped.gerar_ecd_anual`` — 03/abril 04:00 BR (prazo legal ECD = último
    dia útil de maio, ~30 dias de folga).
  * ``sped.gerar_ecf_anual`` — 03/junho 04:00 BR (prazo legal ECF = último
    dia útil de julho, ~30 dias de folga).

Geram a versão do **ano anterior** (ano-calendário fechado). Idempotente —
``EcdService.gerar``/``EcfService.gerar`` levantam ``SpedJaGerado`` quando
a versão ativa já existe; o worker absorve essa exceção como "já feito"
e continua.

Resiliente — falha em uma empresa não aborta as demais. Roda como
superuser fiscal (bypass RLS — operação cross-tenant de sistema). MEI é
pulado em ECD/ECF (``EmpresaNaoElegivelEcd``). Para ECF, apenas empresas
LP elegíveis.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from app.config import get_settings
from app.modules.sped.ecd.service import EcdService
from app.modules.sped.ecf.service import EcfService
from app.modules.sped.storage import mover_blob_sped_best_effort
from app.shared.db.models import Empresa
from app.shared.db.perf import build_async_engine
from app.shared.exceptions import (
    EmpresaNaoElegivelEcd,
    SemDadosParaSped,
    SpedJaGerado,
)
from app.shared.storage import ObjectStorage, build_storage_from_settings
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

_GerarFn = Callable[[AsyncSession, Empresa, int], Awaitable[None]]

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


@lru_cache(maxsize=1)
def _worker_storage() -> ObjectStorage:
    """Object storage do worker (singleton por processo).

    Lazy: só constrói no primeiro blob a mover, nunca no import. Reusa o
    mesmo adapter/cliente boto3 por toda a batelada noturna.
    """
    return build_storage_from_settings(get_settings())


@celery_app.task(
    name="sped.gerar_ecd_anual",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_ecd_anual() -> JsonObject:
    """Gera ECD do ano anterior para todas empresas ativas (LP + SN).

    MEI é pulado (dispensa LC 123 art. 18-A §13). Empresas sem
    lançamentos contábeis no ano caem em ``SemDadosParaSped`` e são
    contadas como ``empresas_sem_dados`` (não é erro do sistema).
    """
    ano_alvo = datetime.now(_TZ_BR).year - 1
    return _executar_geracao(
        ano_alvo=ano_alvo,
        gerar_fn=_gerar_ecd_para_empresa,
        nome_log="sped.ecd",
        regimes_aceitos=("lucro_presumido", "simples_nacional"),
    )


@celery_app.task(
    name="sped.gerar_ecf_anual",
    acks_late=True,
    max_retries=3,
    queue="default",
)
def gerar_ecf_anual() -> JsonObject:
    """Gera ECF do ano anterior para empresas Lucro Presumido ativas."""
    ano_alvo = datetime.now(_TZ_BR).year - 1
    return _executar_geracao(
        ano_alvo=ano_alvo,
        gerar_fn=_gerar_ecf_para_empresa,
        nome_log="sped.ecf",
        regimes_aceitos=("lucro_presumido",),
    )


# ── Implementação compartilhada ─────────────────────────────────────────────


async def _gerar_ecd_para_empresa(
    session: AsyncSession, empresa: Empresa, ano: int
) -> None:
    gerada = await EcdService().gerar(
        session, empresa.tenant_id, empresa.id, ano=ano
    )
    await mover_blob_sped_best_effort(session, gerada.arquivo, _worker_storage())


async def _gerar_ecf_para_empresa(
    session: AsyncSession, empresa: Empresa, ano: int
) -> None:
    gerada = await EcfService().gerar(
        session, empresa.tenant_id, empresa.id, ano=ano
    )
    await mover_blob_sped_best_effort(session, gerada.arquivo, _worker_storage())


async def _executar_geracao_async(
    *,
    ano_alvo: int,
    gerar_fn: _GerarFn,
    nome_log: str,
    regimes_aceitos: tuple[str, ...],
) -> JsonObject:
    """Núcleo async de :func:`_executar_geracao` — exposto para testes.

    Contadores agregados:

    * ``empresas_ok`` — gerou nova versão.
    * ``empresas_ja_gerada`` — ``SpedJaGerado`` (idempotente — não-erro).
    * ``empresas_sem_dados`` — ``SemDadosParaSped`` (geralmente empresa
      em pré-operação ou sem contabilidade no ano).
    * ``empresas_nao_elegivel`` — MEI / regime não suportado.
    * ``empresas_erro`` — exceção inesperada (loga e segue).
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
            stmt = (
                select(Empresa)
                .where(Empresa.ativa.is_(True))
                .where(Empresa.regime_tributario.in_(regimes_aceitos))
            )
            empresas = list(
                (await session.execute(stmt)).scalars().all()
            )

        for empresa in empresas:
            async with sess_factory() as session:
                try:
                    await gerar_fn(session, empresa, ano_alvo)
                    empresas_ok += 1
                except SpedJaGerado:
                    empresas_ja_gerada += 1
                except SemDadosParaSped:
                    empresas_sem_dados += 1
                except EmpresaNaoElegivelEcd:
                    empresas_nao_elegivel += 1
                except Exception:
                    await session.rollback()
                    log.exception(
                        f"{nome_log}.empresa_falhou",
                        empresa_id=str(empresa.id),
                        ano=ano_alvo,
                    )
                    empresas_erro += 1
    finally:
        await engine.dispose()

    resultado: JsonObject = {
        "status": "ok",
        "ano_alvo": ano_alvo,
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
    ano_alvo: int,
    gerar_fn: _GerarFn,
    nome_log: str,
    regimes_aceitos: tuple[str, ...],
) -> JsonObject:
    """Wrapper sync — entry point usado pelas tasks Celery."""
    try:
        return asyncio.run(
            _executar_geracao_async(
                ano_alvo=ano_alvo,
                gerar_fn=gerar_fn,
                nome_log=nome_log,
                regimes_aceitos=regimes_aceitos,
            )
        )
    except Exception:
        log.exception(f"{nome_log}.batch_falhou")
        raise
