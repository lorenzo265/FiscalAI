"""Alembic env — conexão síncrona (psycopg v3) para migrations.

O app usa asyncpg em produção; Alembic usa psycopg (v3) só aqui porque:
  - migrations são DDL puro, não precisam de async
  - asyncpg tem bug de socket no Windows com Docker Desktop
  - psycopg ``[binary]`` embute a própria libpq — sem dependência de libpq do
    sistema nem problema de path encoding no Windows
  - psycopg honra o ``autocommit_block()`` do Alembic, então
    ``CREATE INDEX CONCURRENTLY`` (migration 0041) roda fora de transação.
    O driver anterior (pg8000) NÃO escapava a transação no ``autocommit_block``
    e travava ``alembic upgrade head`` no 0041 com erro 25001.

Base.metadata é importado normalmente para o autogenerate detectar mudanças.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import get_settings
from app.shared.db import models as _models  # noqa: F401 — registra modelos com Base.metadata
from app.shared.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Converte postgresql+asyncpg:// → postgresql+psycopg:// para Alembic (ver docstring).
_db_url = get_settings().DATABASE_URL.replace("+asyncpg", "+psycopg", 1)
config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
