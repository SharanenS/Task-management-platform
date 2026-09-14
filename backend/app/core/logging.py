import re
"""Structured logging configuration using structlog."""

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

def sanitize_error(message: str | None) -> str:
    """
    Sanitize error messages to eliminate sensitive credentials, connection strings,
    embedded passwords, query-parameter secrets, and authorization tokens.
    """
    if not message:
        return ""
    # 1. Redact URL credentials: scheme://[user]:[password]@host or scheme://token@host
    s = re.sub(r"://([^:/@]*):([^@]+)@", "://***:***@", str(message))
    s = re.sub(r"://([^:/@]+)@([a-zA-Z0-9.-]+)", r"://***@\g<2>", s)
    # 2. Redact query-string secrets: ?token=xyz, &password=xyz, etc.
    s = re.sub(
        r"([?&](?:token|password|passwd|secret|api_key|apikey|api-key|key|client_secret|client-secret|access_token|refresh_token|auth)=)([^&\s]+)",
        r"\g<1>***",
        s,
        flags=re.IGNORECASE,
    )
    # 3. Redact Authorization Bearer tokens
    s = re.sub(r"(Bearer\s+)[A-Za-z0-9\-_.]+", r"\g<1>***", s, flags=re.IGNORECASE)
    # 4. Redact standalone JWT-like tokens
    s = re.sub(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+", "eyJ***.***.***", s)
    return s
