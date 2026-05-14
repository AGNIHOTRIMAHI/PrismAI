"""
utils/logger.py — Structured, context-rich logging via structlog.

Every node receives a bound logger via `get_logger(node_name="…")`.
In production, output is JSON-formatted for log aggregators (Datadog, CloudWatch).
In development, it's colour-rendered for readability.
"""

import logging
import sys
from typing import Any

import structlog
from config import get_settings


def _configure_structlog() -> None:
    settings = get_settings()
    is_dev = not settings.is_production
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
       # structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_dev:
        # Pretty console output for local development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # JSON for production log aggregators
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


_configure_structlog()


def get_logger(node_name: str, **initial_ctx: Any) -> structlog.BoundLogger:
    """
    Return a bound logger pre-tagged with the calling node's name.

    Usage:
        log = get_logger("security_agent", pr_url="https://…")
        log.info("analysis_started", files=5)
    """
    return structlog.get_logger(node_name).bind(node=node_name, **initial_ctx)
