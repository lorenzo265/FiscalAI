from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis_async
import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.config import Environment, Settings, get_settings
from app.modules.advisor.router import router as advisor_router
from app.modules.agenda.router import router as agenda_router
from app.modules.assistente.router import router as assistente_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.billing.router import webhook_router as billing_webhook_router
from app.modules.certidoes.router import router as certidoes_router
from app.modules.certificado.router import router as certificado_router
from app.modules.conciliacao.router import router as conciliacao_router
from app.modules.contabil.router import router as contabil_router
from app.modules.declaracao_anual.router import router as declaracao_anual_router
from app.modules.det.router import router as det_router
from app.modules.e_cac.router import router as e_cac_router
from app.modules.empresa.router import router as empresa_router
from app.modules.fiscal.router import router as fiscal_router
from app.modules.icms.router import router as icms_router
from app.modules.imobilizado.router import router as imobilizado_router
from app.modules.ingestao.router import router as ingestao_router
from app.modules.lgpd.router import router as lgpd_router
from app.modules.lucro_presumido.router import router as lucro_presumido_router
from app.modules.manifestacao.router import router as manifestacao_router
from app.modules.marketplace.parceiros_router import router as marketplace_parceiros_router
from app.modules.marketplace.router import (
    router as marketplace_router,
)
from app.modules.marketplace.router import (
    webhook_router as marketplace_webhook_router,
)
from app.modules.migracao.router import router as migracao_router
from app.modules.monitor_cadastral.router import router as monitor_cadastral_router
from app.modules.multa_juros.router import router as multa_juros_router
from app.modules.notas.router import router as notas_router
from app.modules.open_finance.router import (
    router as open_finance_router,
)
from app.modules.open_finance.router import (
    webhook_router as open_finance_webhook_router,
)
from app.modules.parcelamentos.router import router as parcelamentos_router
from app.modules.pessoal.router import router as pessoal_router
from app.modules.pgdas.router import router as pgdas_router
from app.modules.provisoes.router import router as provisoes_router
from app.modules.reforma.router import router as reforma_router
from app.modules.reinf.router import router as reinf_router
from app.modules.relatorios.router import router as relatorios_router
from app.modules.sped.ecd.router import router as sped_ecd_router
from app.modules.sped.ecf.router import router as sped_ecf_router
from app.modules.sped.efd.router import router as sped_efd_router
from app.modules.sped.router import router as sped_router
from app.modules.tabelas_admin.router import (
    alertas_router as tabelas_admin_alertas_router,
)
from app.modules.tabelas_admin.router import (
    router as tabelas_admin_router,
)
from app.modules.tabelas_admin.router import (
    stats_router as tabelas_admin_stats_router,
)
from app.modules.tabelas_admin.router import (
    sugestoes_router as tabelas_admin_sugestoes_router,
)
from app.modules.whatsapp.router import router as whatsapp_router
from app.shared.cache import Cache
from app.shared.db.perf import build_async_engine, install_slow_query_listener
from app.shared.exceptions import DomainError
from app.shared.integrations.brasil_api.client import BrasilApiClient
from app.shared.integrations.focus_nfe.client import FocusNfeClient
from app.shared.integrations.meta_whatsapp.sender import MetaWhatsAppSender
from app.shared.integrations.pluggy.client import PluggyClient
from app.shared.integrations.serpro.client import SerproClient
from app.shared.llm.client import LLMClient
from app.shared.logging import configurar_logging
from app.shared.middleware.correlation_id import CorrelationIdMiddleware
from app.shared.middleware.rate_limit import RateLimitMiddleware
from app.shared.middleware.security_headers import SecurityHeadersMiddleware
from app.shared.storage import build_storage
from app.shared.types import JsonObject

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configurar_logging(settings)

    # Sprint 19 PR1 — pool config + slow query listener centralizados em
    # ``app/shared/db/perf.py``. Workers Celery passam pelo mesmo builder.
    engine: AsyncEngine = build_async_engine(settings)
    install_slow_query_listener(engine, settings.SLOW_QUERY_THRESHOLD_MS)
    session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    redis_client = redis_async.from_url(settings.REDIS_URL, decode_responses=True)

    # Sprint 19 PR2 — cache wrapper compartilhado para SCD lookups + outros
    # read-mostly. Repos aceitam ``Cache | None`` via DI; quando ausente,
    # fallback transparente ao DB (testes unitários, ambientes sem Redis).
    cache = Cache(redis_client)

    # Sprint 19.6 PR3 (#2) — storage de blobs. Default 'local' grava em
    # `.storage/`. Em prod usar 's3' + STORAGE_BUCKET via settings.
    storage = build_storage(
        backend=settings.STORAGE_BACKEND,
        base_path=settings.STORAGE_BASE_PATH,
        bucket=settings.STORAGE_BUCKET or None,
        endpoint_url=settings.STORAGE_S3_ENDPOINT_URL or None,
        region=settings.STORAGE_S3_REGION,
    )

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
    app.state.cache = cache
    app.state.storage = storage
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
        sentry_configurado=bool(settings.SENTRY_DSN),
        metrics_expostas=settings.ENABLE_METRICS,
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


_settings = get_settings()
# Sentry (error tracking) — init o mais cedo possível p/ capturar erros de boot.
# Só ativa com DSN configurado; send_default_pii=False é obrigatório (LGPD —
# nunca enviar CNPJ/CPF/dado fiscal ao Sentry).
if _settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=_settings.SENTRY_DSN,
        environment=_settings.ENVIRONMENT.value,
        traces_sample_rate=_settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )

app = FastAPI(
    title="Analista Fiscal API",
    description=(
        "Backend do **Analista Fiscal (FiscalAI)** — sistema fiscal-contábil multi-tenant "
        "para PMEs brasileiras (Simples Nacional + Lucro Presumido).\n\n"
        "## Autenticação\n\n"
        "Todos os endpoints (exceto `/v1/auth/login` e `/v1/auth/register`) exigem "
        "`Authorization: Bearer <token>` com JWT gerado em `/v1/auth/login`.\n\n"
        "## Rate Limiting\n\n"
        "Limites por tenant: **1000 req/hora** (endpoints comuns) e **100 req/hora** "
        "(endpoints sensíveis: auth, PGDAS, SPED, notas, certidões). "
        "Headers `X-RateLimit-Limit/Remaining/Reset` em todas as respostas.\n\n"
        "## Princípios\n\n"
        "- Multi-tenant via PostgreSQL RLS — isolamento total entre empresas.\n"
        "- Fatos fiscais imutáveis — cancelamento gera nova linha.\n"
        "- LLM nunca grava fatos — pipeline determinístico calcula/persiste.\n"
        "- Toda alíquota é SCD Type 2 (valid_from/valid_to)."
    ),
    version="1.0.0",
    contact={
        "name": "FiscalAI — Suporte Técnico",
        "email": "dev@fiscalai.com.br",
    },
    license_info={
        "name": "Proprietário — uso restrito",
    },
    openapi_tags=[
        {"name": "auth", "description": "Autenticação e registro de empresas."},
        {"name": "empresa", "description": "Perfil e configuração da empresa."},
        {"name": "fiscal", "description": "Apuração DAS — Simples Nacional."},
        {"name": "lucro_presumido", "description": "IRPJ/CSLL/PIS/Cofins LP, DARF, checklist trimestral."},
        {"name": "contabil", "description": "Plano de contas, lançamentos, balancetes, encerramento."},
        {"name": "pessoal", "description": "Folha CLT, eSocial, pró-labore."},
        {"name": "relatorios", "description": "DRE, Balanço Patrimonial, DFC, indicadores."},
        {"name": "sped", "description": "ECD, ECF, EFD-Contribuições, EFD ICMS-IPI."},
        {"name": "advisor", "description": "Sugestões determinísticas SN e LP (Camada 1)."},
        {"name": "ingestao", "description": "Upload de XML NF-e e PDFs."},
        {"name": "notas", "description": "Emissão NF-e e NFS-e via Focus NFe."},
        {"name": "certidoes", "description": "Certidões CND/CRF/CNDT via SERPRO."},
        {"name": "open_finance", "description": "Sincronização bancária via Pluggy."},
        {"name": "agenda", "description": "Calendário fiscal personalizado."},
        {"name": "marketplace", "description": "Marketplace de contadores parceiros."},
        {"name": "tabelas_admin", "description": "Administração de tabelas tributárias SCD (admin)."},
        {"name": "lgpd", "description": "Direito do titular (LGPD): exportação/portabilidade dos dados."},
        {"name": "health", "description": "Probes de saúde (liveness/readiness)."},
        {"name": "manifestacao_nfe", "description": "Manifestação do Destinatário NF-e (MD-e) — NT 2014.002."},
        {"name": "certificado_a1", "description": "Cofre de certificado A1 (.p12 ICP-Brasil) por empresa."},
    ],
    lifespan=lifespan,
)
app.add_middleware(RateLimitMiddleware)
# CORS adicionado por último → roda OUTERMOST (trata preflight OPTIONS e injeta
# os headers Access-Control-* antes do rate-limit). Origens vêm de settings;
# `allow_credentials=True` exige lista explícita (sem wildcard "*").
_cors_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)
# Security headers: adicionado depois do CORS, roda OUTER em relacao a CORS e
# rate-limit, entao os headers de seguranca caem tambem nas respostas 429 do
# rate-limit, nos erros e no preflight. HSTS so com TLS garantido no edge
# (staging/prod); em local/dev (http) ficaria perigoso e e desligado.
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_enabled=_settings.ENVIRONMENT in (Environment.STAGING, Environment.PROD),
)
# Correlation-ID por último → roda OUTERMOST: vincula request_id aos contextvars
# do structlog antes de tudo (inclusive do rate-limit) e ecoa X-Request-ID na
# resposta. Todo log do request passa a carregar o request_id.
app.add_middleware(CorrelationIdMiddleware)

# Prometheus /metrics — métricas agregadas (latência/contagem por rota/status),
# sem PII. Gated por ENABLE_METRICS; fora do schema OpenAPI.
if _settings.ENABLE_METRICS:
    Instrumentator().instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
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
app.include_router(marketplace_router)
app.include_router(marketplace_parceiros_router)
app.include_router(marketplace_webhook_router)
app.include_router(billing_router)
app.include_router(billing_webhook_router)
app.include_router(lgpd_router)
app.include_router(reforma_router)
app.include_router(advisor_router)
app.include_router(sped_ecd_router)
app.include_router(sped_ecf_router)
app.include_router(sped_efd_router)
app.include_router(sped_router)
app.include_router(migracao_router)
app.include_router(tabelas_admin_router)
app.include_router(tabelas_admin_alertas_router)
app.include_router(tabelas_admin_sugestoes_router)
app.include_router(tabelas_admin_stats_router)
app.include_router(manifestacao_router)
app.include_router(certificado_router)


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
