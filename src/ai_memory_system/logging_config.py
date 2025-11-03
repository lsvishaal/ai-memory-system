"""
Structured Logging Configuration for AI Memory System

Provides JSON-formatted logging with context enrichment for production observability.
Follows best practices from .github/copilot-instructions-logging.md
"""

import logging
import sys
import os
from typing import Any, Dict, Optional, MutableMapping
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context and request ID tracking."""

    def add_fields(
        self,
        log_data: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to log record including request_id from context."""
        super().add_fields(log_data, record, message_dict)

        # Add timestamp
        log_data["timestamp"] = self.formatTime(record, self.datefmt)

        # Add log level
        log_data["level"] = record.levelname

        # Add logger name
        log_data["logger"] = record.name

        # Add request_id if available (from context var or extra)
        if hasattr(record, "request_id"):
            log_data["request_id"] = getattr(record, "request_id")
        elif "request_id" in message_dict:
            log_data["request_id"] = message_dict["request_id"]

        # Add file and line info for debugging errors
        if record.levelno >= logging.ERROR:
            log_data["file"] = record.pathname
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName


class RequestIDAdapter(logging.LoggerAdapter):
    """Logger adapter that automatically adds request_id from context var."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """Add request_id to extra if available in context."""
        # Import here to avoid circular dependency
        try:
            from ai_memory_system.main import request_id_var
            
            request_id = request_id_var.get("")
            if request_id:
                if "extra" not in kwargs:
                    kwargs["extra"] = {}
                kwargs["extra"]["request_id"] = request_id
        except (ImportError, LookupError):
            # request_id_var not available or not set
            pass
        
        return msg, kwargs


def setup_logging(log_level: Optional[str] = None, json_format: bool = True) -> logging.Logger:
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


# Global logger instance wrapped with RequestIDAdapter for automatic request_id injection
_base_logger = setup_logging()
logger = RequestIDAdapter(_base_logger, {})


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
