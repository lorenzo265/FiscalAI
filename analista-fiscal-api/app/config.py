from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: Environment = Environment.LOCAL
    LOG_LEVEL: str = "INFO"

    # CORS — origens do frontend autorizadas a chamar a API. Aceita lista
    # separada por vírgula via env (ex.: CORS_ORIGINS="http://localhost:3000,
    # https://app.arkan.com.br"). Default cobre o dev local do Next (:3000).
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Origens permitidas no CORS (lista; env aceita CSV).",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        """Permite CORS_ORIGINS como CSV no env (Pydantic não faz split de str→list)."""
        if isinstance(v, str):
            return [origem.strip() for origem in v.split(",") if origem.strip()]
        return v

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://fiscal:fiscal@localhost:5432/fiscal",
        description="DSN async do Postgres 16 (asyncpg driver).",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL do Redis 7 (cache + Celery broker a partir da Sprint 2).",
    )

    # Sprint 19 PR1 — pool de conexões + slow query log (perf/escala).
    # Default SQLAlchemy é 5+10 (estoura em 1k empresas concorrentes).
    DB_POOL_SIZE: int = Field(
        default=20,
        description="Tamanho do pool de conexões ao Postgres por engine.",
    )
    DB_MAX_OVERFLOW: int = Field(
        default=30,
        description="Conexões extras permitidas além de DB_POOL_SIZE em pico.",
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        description="Segundos a esperar por conexão livre antes de levantar.",
    )
    DB_POOL_RECYCLE: int = Field(
        default=1800,
        description="Segundos antes de reciclar conexão ociosa (30min default).",
    )
    SLOW_QUERY_THRESHOLD_MS: int = Field(
        default=500,
        description=(
            "Limite em ms para logar 'db.slow_query' estruturado. <=0 desliga."
        ),
    )
    OLLAMA_URL: str = Field(
        default="http://localhost:11434",
        description="URL do servidor Ollama (LLM local).",
    )
    OLLAMA_MODEL: str = Field(
        default="gemma3:4b",
        description="Modelo de chat do Ollama (LLM local). Ex.: gemma3:4b, gemma4:latest.",
    )

    # LLM — Sprint 3
    GEMINI_API_KEY: str = Field(
        default="",
        description="Chave da API do Google AI (Gemini). Obrigatória para providers Gemini.",
    )
    LANGFUSE_HOST: str = Field(
        default="",
        description="URL do servidor Langfuse self-hosted. Vazio = tracing desativado.",
    )
    LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Public key do Langfuse.")
    LANGFUSE_SECRET_KEY: str = Field(default="", description="Secret key do Langfuse.")

    # Observabilidade de produção — Marco 1 (2026-06-21)
    SENTRY_DSN: str = Field(
        default="",
        description="DSN do Sentry (error tracking). Vazio = Sentry desativado.",
    )
    SENTRY_TRACES_SAMPLE_RATE: float = Field(
        default=0.0,
        description="Fração de transações enviadas ao Sentry APM (0.0 a 1.0).",
    )
    ENABLE_METRICS: bool = Field(
        default=True,
        description="Expõe /metrics (Prometheus, métricas agregadas sem PII).",
    )

    # Billing — Stripe (Marco 2). Vazios = _FakeBillingProvider (dev/teste).
    STRIPE_SECRET_KEY: str = Field(
        default="", description="Stripe secret key (sk_...). Vazio = fake provider."
    )
    STRIPE_WEBHOOK_SECRET: str = Field(
        default="", description="Stripe webhook signing secret (whsec_...)."
    )
    STRIPE_PRICE_ESSENCIAL: str = Field(
        default="", description="Stripe Price ID do plano Essencial."
    )
    STRIPE_PRICE_PROFISSIONAL: str = Field(
        default="", description="Stripe Price ID do plano Profissional."
    )
    STRIPE_PRICE_AVANCADO: str = Field(
        default="", description="Stripe Price ID do plano Avancado."
    )
    BILLING_CHECKOUT_SUCCESS_URL: str = Field(
        default="https://app.arkan.com.br/assinatura/sucesso",
        description="URL de retorno do checkout Stripe (sucesso).",
    )
    BILLING_CHECKOUT_CANCEL_URL: str = Field(
        default="https://app.arkan.com.br/assinatura",
        description="URL de retorno do checkout Stripe (cancelado).",
    )

    # E-mail transacional (Marco 4 PR3). Vazio = _FakeEmailProvider (não envia).
    EMAIL_PROVIDER: str = Field(
        default="resend",
        description="Provedor de e-mail ('resend'). Outro valor + key = fake.",
    )
    EMAIL_API_KEY: str = Field(
        default="",
        description="API key do provedor (Resend re_...). Vazio = fake provider.",
    )
    EMAIL_FROM: str = Field(
        default="Arkan <nao-responda@arkan.com.br>",
        description="Remetente padrão (precisa de domínio verificado no provedor).",
    )

    # JWT — Sprint 1
    JWT_SECRET: str = Field(
        default="TROCAR_EM_PRODUCAO_gere_com_openssl_rand_hex_32",  # nosec B105
        description="Chave secreta para assinar tokens JWT. OBRIGATÓRIO trocar em prod.",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="Algoritmo JWT (RS256 na Sprint 13+).")
    JWT_EXPIRE_MINUTES: int = Field(default=60, description="TTL do access token em minutos.")
    JWT_REFRESH_EXPIRE_DAYS: int = Field(
        default=30,
        description="TTL do refresh token (dias). Rotacionado a cada uso (Marco 3).",
    )

    # Cifra de PII em repouso (Marco 3, LGPD §8.7). Chave AES-256 (32 bytes) em
    # base64. Default = placeholder DEV; em prod vem do KMS (fail-fast abaixo).
    PII_ENCRYPTION_KEY: str = Field(
        default="REVWX1BJSV9LRVlfVFJPQ0FSX0VNX1BST0RVQ0FPISE=",  # nosec B105
        description=(
            "Chave AES-256 (32 bytes em base64) para cifrar PII em repouso. "
            "OBRIGATÓRIO trocar em prod (vem do KMS). Gere com: openssl rand -base64 32."
        ),
    )

    # Sprint 5 — Focus NFe (NFS-e)
    FOCUS_NFE_TOKEN: str = Field(
        default="",
        description="Token de acesso à API Focus NFe (usuário no Basic Auth).",
    )
    FOCUS_NFE_SANDBOX: bool = Field(
        default=True,
        description="True = homologacao.focusnfe.com.br; False = api.focusnfe.com.br.",
    )
    FOCUS_NFSE_ENVIA_CBS_IBS: bool = Field(
        default=False,
        description=(
            "Sprint 14 PR2 — Reforma Tributária. Quando True, NotasService "
            "injeta campos CBS/IBS/cClassTrib no payload NFS-e enviado à "
            "Focus NFe. Default False — Focus ainda não documenta a API "
            "para todos os municípios (pendência: aguardar regulamentação "
            "do Comitê Gestor IBS e cobertura completa pela Focus)."
        ),
    )

    # Sprint 5 — Meta WhatsApp Cloud API
    META_WHATSAPP_TOKEN: str = Field(
        default="",
        description="Bearer token da API do Meta Graph para envio de mensagens.",
    )
    META_WHATSAPP_PHONE_ID: str = Field(
        default="",
        description="ID do número de telefone WhatsApp Business registrado no Meta.",
    )
    META_WHATSAPP_APP_SECRET: str = Field(
        default="",
        description="App secret do Meta para verificação HMAC-SHA256 do webhook.",
    )
    META_WHATSAPP_VERIFY_TOKEN: str = Field(
        default="fiscalai-webhook-verify",  # nosec B105
        description="Token de verificação do webhook Meta (string fixa definida no painel).",
    )

    # Sprint 15.5 — Envio do digest semanal via Meta WhatsApp utility template
    WHATSAPP_DIGEST_TEMPLATE_NAME: str = Field(
        default="weekly_digest_pt_br",
        description="Nome do template Meta UTILITY usado para o digest semanal.",
    )
    WHATSAPP_DIGEST_LANG_CODE: str = Field(
        default="pt_BR",
        description="Código de idioma do template Meta (BCP-47 com underscore).",
    )
    WHATSAPP_DIGEST_TEMPLATE_ATIVO: bool = Field(
        default=False,
        description=(
            "Flag opt-in para envio real. False = digest fica em "
            "status='preparado' sem enviar (ambiente sem template aprovado)."
        ),
    )

    # Sprint 5 — BrasilAPI (CNPJ lookup)
    BRASIL_API_URL: str = Field(
        default="https://brasilapi.com.br",
        description="URL base da BrasilAPI (CNPJ lookup — cache 30 dias).",
    )

    # Sprint 6 — SERPRO Integra Contador
    SERPRO_BASE_URL: str = Field(
        default="https://apigateway.serpro.gov.br",
        description="URL base do API Gateway SERPRO (Integra Contador).",
    )
    SERPRO_CONSUMER_KEY: str = Field(
        default="",
        description="Consumer key OAuth2 do plano contratado no Loja SERPRO.",
    )
    SERPRO_CONSUMER_SECRET: str = Field(
        default="",
        description="Consumer secret OAuth2 do plano contratado no Loja SERPRO.",
    )
    SERPRO_SANDBOX: bool = Field(
        default=True,
        description="True = ambiente Sandbox/Hom. SERPRO; False = produção.",
    )
    SERPRO_OAUTH_TTL_MARGIN_SEC: int = Field(
        default=60,
        description="Margem subtraída do TTL do token OAuth para evitar uso após expiração.",
    )
    SERPRO_CERT_ENCRYPTION_KEY: str = Field(
        default="",
        description=(
            "Chave simétrica (base64 32 bytes) usada para envelopar o e-CNPJ "
            "p12 do cliente em pgcrypto. Em prod vem do KMS."
        ),
    )

    # Sprint 7 — Pluggy (Open Finance, BCB regulado, §7.3 do Plano)
    PLUGGY_BASE_URL: str = Field(
        default="https://api.pluggy.ai",
        description="URL base da API Pluggy (Open Finance).",
    )
    PLUGGY_CLIENT_ID: str = Field(
        default="",
        description="Client ID Pluggy (gerado no painel pluggy.ai).",
    )
    PLUGGY_CLIENT_SECRET: str = Field(
        default="",
        description="Client secret Pluggy.",
    )
    PLUGGY_WEBHOOK_SECRET: str = Field(
        default="",
        description="Segredo HMAC-SHA256 para validar webhooks Pluggy.",
    )
    PLUGGY_CONNECT_TOKEN_TTL_MIN: int = Field(
        default=30,
        description="TTL em minutos do connect_token enviado ao widget.",
    )
    PLUGGY_API_KEY_TTL_MARGIN_SEC: int = Field(
        default=120,
        description="Margem subtraída do TTL da API key (2h) para renovação antecipada.",
    )

    # Sprint 13 — Marketplace (curadoria admin)
    MARKETPLACE_ADMIN_TOKEN: str = Field(
        default="",
        description=(
            "Token estático compartilhado para endpoints administrativos do "
            "marketplace (aprovar parceiro, listar todos). Vazio = endpoints "
            "admin retornam 503. Em prod vem do secret manager."
        ),
    )
    MARKETPLACE_PAGAMENTO_WEBHOOK_SECRET: str = Field(
        default="",
        description=(
            "Segredo HMAC-SHA256 para validar webhooks do provider de pagamento "
            "(header X-Provider-Signature). Vazio = webhook rejeitado com 401 "
            "(fail-closed). Em prod vem do secret manager (Stripe/Pagar.me webhook "
            "secret gerado no painel do provider)."
        ),
    )

    # Sprint 19.6 PR3 — Storage de blobs (PDFs/XMLs/recibos). Substitui
    # anti-pattern de BYTEA em Postgres. Default 'local' = .storage/
    # (dev/CI). Em prod usar 's3' com bucket + endpoint_url (opcional para
    # MinIO/R2) + region (default sa-east-1 = LGPD §8.7).
    STORAGE_BACKEND: str = Field(
        default="local",
        description="Backend de storage: 'local' | 'memory' | 's3'.",
    )
    STORAGE_BASE_PATH: str = Field(
        default=".storage",
        description="Diretório base do LocalDiskStorage (dev/CI).",
    )
    STORAGE_BUCKET: str = Field(
        default="",
        description="Bucket S3-compatível. Obrigatório se STORAGE_BACKEND=s3.",
    )
    STORAGE_S3_ENDPOINT_URL: str = Field(
        default="",
        description=(
            "Endpoint URL S3-compatível. Vazio = AWS S3 padrão; preenchido "
            "= MinIO/R2/etc. Ex.: 'https://minio.fiscalai.local:9000'."
        ),
    )
    STORAGE_S3_REGION: str = Field(
        default="sa-east-1",
        description="Região S3. Default sa-east-1 alinhado à LGPD §8.7.",
    )

    # Sprint 19.6 PR1 — Scrapers CRF (Caixa) + CNDT (TST). Refactor #3.
    # Default "not_implemented" = adapter sinaliza gate operacional não-código
    # (decisão de stack Playwright + provider captcha). Quando provider real
    # estiver pronto, trocar pra "playwright" ou similar.
    CRF_SCRAPER_PROVIDER: str = Field(
        default="not_implemented",
        description=(
            "Provider do scraper CRF: 'not_implemented' (fallback manual) ou "
            "'playwright' (quando Sprint 19.6 PR3 instalar Playwright + captcha)."
        ),
    )
    CNDT_SCRAPER_PROVIDER: str = Field(
        default="not_implemented",
        description=(
            "Provider do scraper CNDT: 'not_implemented' (fallback manual) ou "
            "'playwright' (idem CRF)."
        ),
    )

    # Sprint 19.7 PR2 (#13) — eSocial transmissão real.
    # Base URLs oficiais: produção restrita (sandbox) vs produção real.
    # Mantém o anti-pattern dos demais Sandbox flags: True em dev por
    # default, opt-in explícito pra produção.
    ESOCIAL_BASE_URL_SANDBOX: str = Field(
        default="https://webservices.producaorestrita.esocial.gov.br",
        description="Endpoint sandbox/produção restrita do eSocial.",
    )
    ESOCIAL_BASE_URL_PROD: str = Field(
        default="https://webservices.esocial.gov.br",
        description="Endpoint produção real do eSocial.",
    )
    ESOCIAL_SANDBOX: bool = Field(
        default=True,
        description=(
            "True = produção restrita (tpAmb=2); False = produção real "
            "(tpAmb=1). Default True em dev pra nunca emitir evento real."
        ),
    )
    ESOCIAL_TRANSMISSAO_ATIVA: bool = Field(
        default=False,
        description=(
            "§8.12 — Transmissão é ato consciente. Flag opt-in: False = "
            "evento fica em status='assinado' sem enviar (pronto pra "
            "admin baixar e transmitir manualmente). True = pipeline "
            "envia automaticamente após assinatura."
        ),
    )
    ESOCIAL_LOTE_MAX_EVENTOS: int = Field(
        default=50,
        description=(
            "Máximo de eventos por lote. Limite oficial = 50 (POST "
            "/lotes/eventos). Service quebra automaticamente lotes maiores."
        ),
    )
    ESOCIAL_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout HTTP por chamada à API eSocial.",
    )
    ESOCIAL_RECIBO_POLL_INTERVAL_SEC: int = Field(
        default=15,
        description=(
            "Intervalo entre polls de GET /lotes/eventos/{protocolo} "
            "enquanto processamento não finaliza (estado != 4)."
        ),
    )

    # Marco 4 PR2 (#11) — EFD-Reinf transmissão real (SERPRO/RFB).
    # Mesmo padrão do eSocial: Sandbox=True por default, opt-in explícito
    # pra produção. Endpoints oficiais confirmar no Manual EFD-Reinf antes
    # de ligar em prod (leiaute v2.1.2, recepção assíncrona de lote).
    REINF_BASE_URL_SANDBOX: str = Field(
        default="https://pre-reinf.receita.economia.gov.br",
        description="Endpoint sandbox/produção restrita do EFD-Reinf.",
    )
    REINF_BASE_URL_PROD: str = Field(
        default="https://reinf.receita.economia.gov.br",
        description="Endpoint produção real do EFD-Reinf.",
    )
    REINF_SANDBOX: bool = Field(
        default=True,
        description=(
            "True = produção restrita (tpAmb=2); False = produção real "
            "(tpAmb=1). Default True em dev pra nunca emitir evento real."
        ),
    )
    REINF_TRANSMISSAO_ATIVA: bool = Field(
        default=False,
        description=(
            "§8.12 — Transmissão é ato consciente. Flag opt-in: False = "
            "evento fica em status='assinado' sem enviar (pronto pra admin "
            "baixar e transmitir manualmente). True = pipeline envia "
            "automaticamente após assinatura."
        ),
    )
    REINF_LOTE_MAX_EVENTOS: int = Field(
        default=50,
        description=(
            "Máximo de eventos por lote EFD-Reinf. Service quebra "
            "automaticamente lotes maiores."
        ),
    )
    REINF_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout HTTP por chamada à API EFD-Reinf.",
    )
    REINF_RECIBO_POLL_INTERVAL_SEC: int = Field(
        default=15,
        description=(
            "Intervalo entre polls de consulta de recibo enquanto o "
            "processamento do lote não finaliza."
        ),
    )

    # Sprint 19.5 PR2 — Painel admin de tabelas tributárias
    ADMIN_WHATSAPP_PHONE: str | None = Field(
        default=None,
        description=(
            "Número WhatsApp do contador admin do sistema (não da PME). "
            "Quando configurado, o digest semanal Sprint 15.5 inclui bullets "
            "dos alertas críticos abertos em ``alerta_admin``. Vazio = hook "
            "noop (alertas só aparecem nos endpoints REST)."
        ),
    )

    # Prefixo do placeholder de JWT_SECRET — qualquer valor que inicie com
    # esta string é considerado não-seguro (commitado no repo, público).
    _JWT_PLACEHOLDER_PREFIX: str = "TROCAR_EM_PRODUCAO"

    # Chave PII de DEV (commitada no repo, pública). Em prod tem de vir do KMS.
    _PII_DEV_KEY_PLACEHOLDER: str = "REVWX1BJSV9LRVlfVFJPQ0FSX0VNX1BST0RVQ0FPISE="

    @model_validator(mode="after")
    def _fail_fast_em_prod(self) -> Self:
        if self.ENVIRONMENT is Environment.PROD:
            if "localhost" in self.DATABASE_URL or "127.0.0.1" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL aponta para localhost em ENVIRONMENT=prod")
            if "localhost" in self.REDIS_URL or "127.0.0.1" in self.REDIS_URL:
                raise ValueError("REDIS_URL aponta para localhost em ENVIRONMENT=prod")
            # JWT_SECRET com placeholder ou curto → forja de tid → takeover cross-tenant.
            if self.JWT_SECRET.startswith(self._JWT_PLACEHOLDER_PREFIX):
                raise ValueError(
                    "JWT_SECRET contém placeholder padrão em ENVIRONMENT=prod. "
                    "Gere um segredo com: openssl rand -hex 32"
                )
            if len(self.JWT_SECRET) < 32:
                raise ValueError(
                    f"JWT_SECRET tem {len(self.JWT_SECRET)} chars em ENVIRONMENT=prod "
                    "(mínimo 32). Gere com: openssl rand -hex 32)"
                )
            # META_WHATSAPP_VERIFY_TOKEN com valor padrão (hardcoded no repo)
            # em produção compromete a segurança do webhook Meta.
            if self.META_WHATSAPP_VERIFY_TOKEN == "fiscalai-webhook-verify":  # nosec B105
                raise ValueError(
                    "META_WHATSAPP_VERIFY_TOKEN usa o valor padrão em ENVIRONMENT=prod. "
                    "Configure um token aleatório no painel Meta e no env."
                )
            # PII_ENCRYPTION_KEY com placeholder DEV → PII cifrada com chave pública.
            if self.PII_ENCRYPTION_KEY == self._PII_DEV_KEY_PLACEHOLDER:
                raise ValueError(
                    "PII_ENCRYPTION_KEY usa o placeholder DEV em ENVIRONMENT=prod. "
                    "Configure a chave do KMS. Gere com: openssl rand -base64 32"
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
