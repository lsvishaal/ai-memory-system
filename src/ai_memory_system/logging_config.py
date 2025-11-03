"""
Structured Logging Configuration for AI Memory System

Provides JSON-formatted logging with context enrichment for production observability.
Follows best practices from .github/copilot-instructions-logging.md
"""

import logging
import sys
import os
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Add log level
        log_record["level"] = record.levelname

        # Add logger name
        log_record["logger"] = record.name

        # Add file and line info for debugging
        if record.levelno >= logging.ERROR:
            log_record["file"] = record.pathname
            log_record["line"] = record.lineno
            log_record["function"] = record.funcName


def setup_logging(log_level: str = None, json_format: bool = True) -> logging.Logger:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting (True) or plain text (False)

    Returns:
        Configured logger instance
    """
    # Get log level from environment or parameter
    level_name = log_level or os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Create logger
    logger = logging.getLogger("ai_memory_system")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Set formatter
    if json_format:
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Global logger instance
logger = setup_logging()


def log_with_context(level: str, message: str, **context: Any) -> None:
    """
    Log message with structured context.

    Args:
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        **context: Additional context as key-value pairs

    Example:
        log_with_context('info', 'Vector upserted', vector_id=123, collection='ai_memory')
    """
    log_func = getattr(logger, level.lower())
    log_func(message, extra=context)
