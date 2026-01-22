"""
Structured logging setup for Shiny App Generator.

This module configures logging with:
- Multiple log levels
- File and console output
- Request ID tracking
- Formatted output
"""

import logging
import logging.handlers
import sys
import uuid
from pathlib import Path
from typing import Optional
from contextvars import ContextVar

from config import config

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class RequestIdFilter(logging.Filter):
    """Add request ID to log records."""

    def filter(self, record):
        """Add request_id attribute to record."""
        record.request_id = request_id_var.get() or "N/A"
        return True


class ColoredFormatter(logging.Formatter):
    """Colored console output formatter."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.RESET}"
            )

        return super().format(record)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    enable_request_id: Optional[bool] = None,
) -> logging.Logger:
    """
    Set up application logging.

    Args:
        level: Log level (default from config)
        log_file: Log file path (default from config)
        enable_request_id: Enable request ID tracking (default from config)

    Returns:
        Configured root logger
    """
    # Get configuration
    if level is None:
        level = config.log_level
    if log_file is None:
        log_file = config.log_file
    if enable_request_id is None:
        enable_request_id = config.enable_request_id

    # Convert level string to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatters
    if enable_request_id:
        console_format = (
            "%(asctime)s [%(levelname)s] [%(request_id)s] "
            "%(name)s:%(lineno)d - %(message)s"
        )
        file_format = (
            "%(asctime)s [%(levelname)s] [%(request_id)s] "
            "%(name)s:%(lineno)d - %(message)s"
        )
    else:
        console_format = (
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        )
        file_format = console_format

    # Console handler (with colors)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_formatter = ColoredFormatter(
        console_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    if enable_request_id:
        console_handler.addFilter(RequestIdFilter())
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if log_file:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler (max 10MB, keep 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(
            file_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        if enable_request_id:
            file_handler.addFilter(RequestIdFilter())
        root_logger.addHandler(file_handler)

        logging.info(f"Logging to file: {log_file}")

    # Log startup message
    logging.info(f"Logging initialized at level: {level}")
    if enable_request_id:
        logging.info("Request ID tracking enabled")

    return root_logger


def generate_request_id() -> str:
    """
    Generate a unique request ID.

    Returns:
        Unique request ID (8-character hex string)
    """
    return uuid.uuid4().hex[:8]


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Set request ID for current context.

    Args:
        request_id: Request ID to set (generates new if None)

    Returns:
        The request ID that was set
    """
    if request_id is None:
        request_id = generate_request_id()

    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """
    Get current request ID.

    Returns:
        Current request ID or None
    """
    return request_id_var.get()


def clear_request_id():
    """Clear current request ID."""
    request_id_var.set(None)


class LogContext:
    """Context manager for request ID tracking."""

    def __init__(self, request_id: Optional[str] = None):
        """
        Initialize log context.

        Args:
            request_id: Request ID (generates new if None)
        """
        self.request_id = request_id or generate_request_id()
        self.previous_id = None

    def __enter__(self):
        """Enter context and set request ID."""
        self.previous_id = get_request_id()
        set_request_id(self.request_id)
        return self.request_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore previous request ID."""
        if self.previous_id:
            set_request_id(self.previous_id)
        else:
            clear_request_id()


# Convenience function for logging with context
def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log a message with additional context.

    Args:
        logger: Logger instance
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        **kwargs: Additional context to include in message
    """
    if kwargs:
        context_str = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        message = f"{message} | {context_str}"

    log_method = getattr(logger, level.lower())
    log_method(message)


# Example usage logger
if __name__ == "__main__":
    # Setup logging
    setup_logging(level="DEBUG")

    # Create a logger
    logger = logging.getLogger(__name__)

    # Log without request ID
    logger.info("Application starting")

    # Log with request ID
    with LogContext() as req_id:
        logger.info(f"Processing request: {req_id}")
        logger.debug("Debug information")
        logger.warning("Warning message")

    # Log without request ID again
    logger.info("Request processing complete")
