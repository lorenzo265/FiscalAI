from __future__ import annotations

import logging
import sys

import structlog

from app.config import Environment, Settings


def configurar_logging(settings: Settings) -> None:
    """Configura structlog para JSON em prod e console colorido em local/dev."""
    nivel = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=nivel,
    )

    processadores: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.ENVIRONMENT in (Environment.LOCAL, Environment.DEV):
        processadores.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processadores.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processadores,
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
