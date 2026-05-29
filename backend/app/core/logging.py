"""Structured logging configuration."""

import logging
import sys
from typing import Any

from app.core.config import get_settings


class StructuredFormatter(logging.Formatter):
    """Simple key=value structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras: list[str] = []
        for key in ("request_id", "component", "operation", "agent_id", "count"):
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    extras.append(f"{key}={value}")
        if extras:
            return f"{base} | {' '.join(extras)}"
        return base


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        StructuredFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.is_development else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# Keys that cannot be used in logging.Logger extra= (LogRecord reserved attrs)
_RESERVED_LOGRECORD_KEYS = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """Attach structured fields to a log record (avoids reserved LogRecord keys)."""
    safe = {}
    for key, value in kwargs.items():
        if key in _RESERVED_LOGRECORD_KEYS:
            safe[f"log_{key}"] = value
        else:
            safe[key] = value
    return {"extra": safe}
