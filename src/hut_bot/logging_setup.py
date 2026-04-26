from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(level: str = "INFO", logs_dir: Path | None = None) -> structlog.BoundLogger:
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if logs_dir is not None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(logs_dir / "hut_bot.log", encoding="utf-8"))

    logging.basicConfig(format="%(message)s", level=log_level, handlers=handlers)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()
