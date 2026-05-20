from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from app.shared.types import JsonObject

import redis.asyncio as redis_async
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings
from app.modules.agenda.router import router as agenda_router
from app.modules.assistente.router import router as assistente_router
from app.modules.auth.router import router as auth_router
from app.modules.certidoes.router import router as certidoes_router
from app.modules.conciliacao.router import router as conciliacao_router
from app.modules.contabil.router import router as contabil_router
from app.modules.declaracao_anual.router import router as declaracao_anual_router
from app.modules.det.router import router as det_router
from app.modules.e_cac.router import router as e_cac_router
from app.modules.empresa.router import router as empresa_router
from app.modules.fiscal.router import router as fiscal_router
from app.modules.imobilizado.router import router as imobilizado_router
from app.modules.icms.router import router as icms_router
from app.modules.ingestao.router import router as ingestao_router
from app.modules.lucro_presumido.router import router as lucro_presumido_router
from app.modules.monitor_cadastral.router import router as monitor_cadastral_router
from app.modules.multa_juros.router import router as multa_juros_router
from app.modules.parcelamentos.router import router as parcelamentos_router
from app.modules.reinf.router import router as reinf_router
from app.modules.relatorios.router import router as relatorios_router
from app.modules.notas.router import router as notas_router
from app.modules.open_finance.router import (
    router as open_finance_router,
    webhook_router as open_finance_webhook_router,
)
from app.modules.pessoal.router import router as pessoal_router
from app.modules.pgdas.router import router as pgdas_router
from app.modules.provisoes.router import router as provisoes_router
from app.modules.whatsapp.router import router as whatsapp_router
from app.shared.exceptions import DomainError
from app.shared.integrations.brasil_api.client import BrasilApiClient
from app.shared.integrations.focus_nfe.client import FocusNfeClient
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender
from app.shared.integrations.pluggy.client import PluggyClient
from app.shared.integrations.serpro.client import SerproClient
from app.shared.llm.client import LLMClient
from app.shared.logging import configurar_logging

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configurar_logging(settings)

    engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    redis_client = redis_async.from_url(settings.REDIS_URL, decode_responses=True)

    llm_client = LLMClient(settings=settings, redis=redis_client)
    focus_client = FocusNfeClient(settings=settings)
    brasil_api_client = BrasilApiClient(settings=settings, redis=redis_client)
    whatsapp_sender = MetaWhatsAppSender(settings=settings)
    serpro_client = SerproClient(settings=settings, redis=redis_client)
    pluggy_client = PluggyClient(settings=settings, redis=redis_client)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.redis = redis_client
    app.state.llm_client = llm_client
    app.state.focus_client = focus_client
    app.state.brasil_api_client = brasil_api_client
    app.state.whatsapp_sender = whatsapp_sender
    app.state.serpro_client = serpro_client
    app.state.pluggy_client = pluggy_client

    log.info(
        "api.boot",
        environment=settings.ENVIRONMENT,
        database=_redact_dsn(settings.DATABASE_URL),
        redis=settings.REDIS_URL,
        ollama=settings.OLLAMA_URL,
        gemini_configurado=bool(settings.GEMINI_API_KEY),
        langfuse_configurado=bool(settings.LANGFUSE_HOST),
        focus_nfe_sandbox=settings.FOCUS_NFE_SANDBOX,
        focus_nfe_configurado=bool(settings.FOCUS_NFE_TOKEN),
        whatsapp_configurado=bool(settings.META_WHATSAPP_TOKEN),
        serpro_sandbox=settings.SERPRO_SANDBOX,
        serpro_configurado=bool(settings.SERPRO_CONSUMER_KEY),
        pluggy_configurado=bool(settings.PLUGGY_CLIENT_ID),
    )

    try:
        yield
    finally:
        await llm_client.aclose()
        await focus_client.aclose()
        await brasil_api_client.aclose()
        await whatsapp_sender.aclose()
        await serpro_client.aclose()
        await pluggy_client.aclose()
        await engine.dispose()
        # `aclose` existe em redis-py 5.x; stubs de types-redis 4.6 estão atrasados.
        await redis_client.aclose()  # type: ignore[attr-defined]
        log.info("api.shutdown")


app = FastAPI(
    title="Analista Fiscal API",
    description="Backend do Analista Fiscal — sistema fiscal-contábil multi-tenant para PMEs.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(empresa_router)
app.include_router(fiscal_router)
app.include_router(ingestao_router)
app.include_router(multa_juros_router)
app.include_router(agenda_router)
app.include_router(assistente_router)
app.include_router(notas_router)
app.include_router(whatsapp_router)
app.include_router(certidoes_router)
app.include_router(pgdas_router)
app.include_router(e_cac_router)
app.include_router(declaracao_anual_router)
app.include_router(open_finance_router)
app.include_router(open_finance_webhook_router)
app.include_router(conciliacao_router)
app.include_router(imobilizado_router)
app.include_router(provisoes_router)
app.include_router(contabil_router)
app.include_router(pessoal_router)
app.include_router(lucro_presumido_router)
app.include_router(icms_router)
app.include_router(reinf_router)
app.include_router(det_router)
app.include_router(monitor_cadastral_router)
app.include_router(parcelamentos_router)
app.include_router(relatorios_router)


@app.exception_handler(DomainError)
async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    log.warning(
        "domain.error",
        codigo=exc.codigo,
        mensagem=exc.mensagem,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={"codigo": exc.codigo, "mensagem": exc.mensagem},
    )


@app.get("/healthz", tags=["health"], summary="Liveness probe")
async def healthz() -> dict[str, str]:
    """Liveness — responde 200 enquanto o processo está vivo. Não toca dependências."""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"], summary="Readiness probe")
async def readyz(request: Request) -> JSONResponse:
    """Readiness — só responde 200 se Postgres e Redis estiverem acessíveis."""
    settings: Settings = request.app.state.settings
    engine: AsyncEngine = request.app.state.engine
    redis_client: redis_async.Redis[str] = request.app.state.redis

    checks: JsonObject = {"postgres": "unknown", "redis": "unknown"}
    todo_ok = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        checks["postgres"] = f"down: {exc.__class__.__name__}"
        todo_ok = False

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"down: {exc.__class__.__name__}"
        todo_ok = False

    return JSONResponse(
        status_code=200 if todo_ok else 503,
        content={
            "status": "ok" if todo_ok else "degraded",
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )


def _redact_dsn(dsn: str) -> str:
    """Remove senha do DSN para log."""
    if "@" not in dsn or "://" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    if "@" not in rest:
        return dsn
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{host}"
