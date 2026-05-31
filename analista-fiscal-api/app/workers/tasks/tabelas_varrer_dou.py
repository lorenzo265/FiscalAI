"""Task Celery — varrer DOU + LLM extrai estrutura (Sprint 19.5 PR3).

Beat schedule: mensal dia 5 às 04:00 BRT (ver ``celery_app.py``).

Pipeline (resiliente — qualquer erro em uma matéria não aborta as demais):
  1. Expirar sugestões ``pendente`` > 60 dias (limpeza).
  2. Para cada (tipo_tabela, termo_busca):
     a) Buscar matérias DOU dos últimos 60 dias.
     b) Para cada matéria com PDF:
        - Baixar PDF + extrair texto via ``pdfplumber``.
        - Passar para LLM Gemini Flash com prompt versionado.
        - Re-check determinístico §8.6.
        - INSERT sugestao_vigencia_tabela (status='pendente', idempotente
          por URL DOU).
        - Disparar alerta Camada 2 tipo ``sugestao_vigencia_disponivel``.
  3. Resumo no log estruturado.

§8.8 cravado: o worker **nunca** cria vigência. Sugestões ficam pendentes
até admin aprovar via ``POST /v1/admin/sugestoes-vigencia/{id}/aprovar``.

Out-of-scope (declarado §8.12):
  * ICMS UF (27 SEFAZ heterogêneos) — adicionar quando 1º cliente migrar.
  * Resolução CGSN — extremamente rara (admin posta manual).
  * FGTS — fixo 8% desde 1990.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import redis.asyncio as redis_async
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import get_settings
from app.modules.tabelas_admin.pipeline_dou import processar_materia_dou
from app.modules.tabelas_admin.sugestoes_repo import SugestaoVigenciaRepo
from app.modules.tabelas_admin.sugestoes_service import (
    SugestaoVigenciaService,
)
from app.shared.db.perf import build_async_engine
from app.shared.integrations.dou.client import DouClient
from app.shared.integrations.dou.pdf import extrair_texto_pdf
from app.shared.llm.client import LLMClient
from app.shared.types import JsonObject
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TZ_BR = ZoneInfo("America/Sao_Paulo")


# Termos buscados no DOU. CGSN não está aqui — admin posta manual quando
# rara Resolução é publicada (out-of-scope da Camada 3 §8.12).
_TERMOS_BUSCA: dict[str, str] = {
    "inss": '"Portaria MPS/MF" AND "INSS"',
    "irrf": '"imposto de renda" AND "tabela progressiva"',
}


@celery_app.task(
    name="tabelas.varrer_dou_mensal",
    acks_late=True,
    max_retries=2,
    queue="default",
)
def varrer_dou_mensal() -> JsonObject:
    """Pipeline mensal — expira antigas + tenta extrair novas via LLM."""

    async def _run() -> tuple[int, int]:
        settings = get_settings()
        engine = build_async_engine(settings)
        agora = datetime.now(_TZ_BR)
        log.info("tabelas.dou.varredura_iniciada", inicio=agora.isoformat())

        expiradas = 0
        sugestoes_criadas = 0
        try:
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                await session.execute(
                    text("SET LOCAL ROLE tax_table_admin")
                )
                svc = SugestaoVigenciaService(
                    sugestao_repo=SugestaoVigenciaRepo(session),
                )
                # 1) Expirar pendentes > 60 dias.
                expiradas = await svc.expirar_pendentes_antigas(
                    session, max_dias=60
                )

            # 2) Buscar+extrair por tipo. Cada iteração em sessão própria
            # para não acumular estado e permitir falha isolada.
            desde = (agora - timedelta(days=60)).date()
            for tipo_tabela, termo in _TERMOS_BUSCA.items():
                try:
                    sugestoes_criadas += await _processar_tipo(
                        engine=engine,
                        tipo_tabela=tipo_tabela,
                        termo=termo,
                        desde=desde,
                    )
                except Exception:
                    log.exception(
                        "tabelas.dou.tipo_falhou", tipo_tabela=tipo_tabela
                    )
        finally:
            await engine.dispose()

        log.info(
            "tabelas.dou.varredura_concluida",
            expiradas=expiradas,
            sugestoes_criadas=sugestoes_criadas,
        )
        return expiradas, sugestoes_criadas

    try:
        expiradas, criadas = asyncio.run(_run())
    except Exception:
        log.exception("tabelas.dou.varredura_falhou")
        raise

    return {"expiradas": expiradas, "sugestoes_criadas": criadas}


async def _processar_tipo(
    *,
    engine: AsyncEngine,
    tipo_tabela: str,
    termo: str,
    desde: object,
) -> int:
    """Sprint 19.6 PR3 (#41) — pipeline real DOU → PDF → LLM → sugestão.

    Fluxo (cada matéria processada em sessão própria, fail-soft):

      1. ``DouClient.buscar_materias(termo, desde)`` → lista de MateriaDou.
      2. Para cada matéria: ``processar_materia_dou`` (pipeline_dou.py).
      3. Conta sugestões criadas; retorna total.

    Resilência: erro em uma matéria não aborta outras (try/except no
    ``processar_materia_dou`` interno). Erro no client DOU/LLM/pdfplumber
    cai no log e retorna 0.

    **Deps opcionais (grupos Poetry):**
      * `pdfplumber` — extração de texto. Sem ela, processar_materia_dou
        pula a matéria com log.
      * `boto3` — não obrigatório (não persiste PDF cru hoje).
      * `celery[redis]` — obrigatório pra rodar o worker em prod.
    """
    if not isinstance(desde, date):
        # Caller já passa date — defesa em profundidade.
        log.warning("tabelas.dou.desde_invalido", tipo_tabela=tipo_tabela)
        return 0

    settings = get_settings()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Inicializa colaboradores em request scope (DouClient não é context
    # manager — try/finally explícito garante cleanup mesmo em exceção).
    dou_client = DouClient()
    redis_client: redis_async.Redis[str] = redis_async.from_url(
        settings.REDIS_URL, decode_responses=True
    )
    llm_client = LLMClient(settings=settings, redis=redis_client)
    http_baixar_pdf = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    criadas = 0
    materias: list[object] = []
    try:
        try:
            materias_resp = await dou_client.buscar_materias(
                termo=termo, desde=desde
            )
        except Exception:
            log.exception(
                "tabelas.dou.busca_falhou",
                tipo_tabela=tipo_tabela,
                termo=termo,
            )
            return 0

        if not materias_resp:
            log.info(
                "tabelas.dou.sem_materias",
                tipo_tabela=tipo_tabela,
                termo=termo,
            )
            return 0

        materias = list(materias_resp)
        for materia in materias_resp:
            async with factory() as session:
                await session.execute(
                    text("SET LOCAL ROLE tax_table_admin")
                )
                svc = SugestaoVigenciaService(
                    sugestao_repo=SugestaoVigenciaRepo(session),
                )
                sugestao = await processar_materia_dou(
                    session,
                    materia,
                    tipo_tabela=tipo_tabela,
                    http_client=http_baixar_pdf,
                    llm_client=llm_client,
                    pdf_extractor=extrair_texto_pdf,
                    service=svc,
                )
                if sugestao is not None:
                    criadas += 1
    finally:
        await http_baixar_pdf.aclose()
        await llm_client.aclose()
        await dou_client.aclose()
        # `aclose` existe em redis-py 5.x; stubs de types-redis 4.6 podem
        # estar atrasados.
        await redis_client.aclose()  # type: ignore[attr-defined]

    log.info(
        "tabelas.dou.tipo_concluido",
        tipo_tabela=tipo_tabela,
        materias_encontradas=len(materias),
        sugestoes_criadas=criadas,
    )
    return criadas
