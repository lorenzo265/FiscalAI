from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
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

    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://fiscal:fiscal@localhost:5432/fiscal",
        description="DSN async do Postgres 16 (asyncpg driver).",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="URL do Redis 7 (cache + Celery broker a partir da Sprint 2).",
    )
    OLLAMA_URL: str = Field(
        default="http://localhost:11434",
        description="URL do servidor Ollama (LLM local).",
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

    # JWT — Sprint 1
    JWT_SECRET: str = Field(
        default="TROCAR_EM_PRODUCAO_gere_com_openssl_rand_hex_32",
        description="Chave secreta para assinar tokens JWT. OBRIGATÓRIO trocar em prod.",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="Algoritmo JWT (RS256 na Sprint 13+).")
    JWT_EXPIRE_MINUTES: int = Field(default=60, description="TTL do access token em minutos.")

    # Sprint 5 — Focus NFe (NFS-e)
    FOCUS_NFE_TOKEN: str = Field(
        default="",
        description="Token de acesso à API Focus NFe (usuário no Basic Auth).",
    )
    FOCUS_NFE_SANDBOX: bool = Field(
        default=True,
        description="True = homologacao.focusnfe.com.br; False = api.focusnfe.com.br.",
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
        default="fiscalai-webhook-verify",
        description="Token de verificação do webhook Meta (string fixa definida no painel).",
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

    @model_validator(mode="after")
    def _fail_fast_em_prod(self) -> Self:
        if self.ENVIRONMENT is Environment.PROD:
            if "localhost" in self.DATABASE_URL or "127.0.0.1" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL aponta para localhost em ENVIRONMENT=prod")
            if "localhost" in self.REDIS_URL or "127.0.0.1" in self.REDIS_URL:
                raise ValueError("REDIS_URL aponta para localhost em ENVIRONMENT=prod")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
