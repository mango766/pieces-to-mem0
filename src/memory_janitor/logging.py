"""
Structured Logging
==================

Configures structlog for consistent, structured logging.
Supports both JSON and console output formats.
"""

import logging
import sys
from pathlib import Path

import structlog
from structlog.typing import Processor

from memory_janitor.config import LOGS_DIR, get_settings


def setup_logging() -> None:
    """Configure structured logging based on settings."""
    settings = get_settings()
    log_config = settings.logging
    
    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine log level
    log_level = getattr(logging, log_config.level.upper(), logging.INFO)
    
    # Build processor chain
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if log_config.format == "json":
        # JSON format for production
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Add file handler if configured
    if log_config.file:
        log_path = Path(log_config.file)
        if not log_path.is_absolute():
            log_path = LOGS_DIR / log_path.name
        
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=log_config.max_size_mb * 1024 * 1024,
            backupCount=log_config.backup_count,
        )
        file_handler.setLevel(log_level)
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
