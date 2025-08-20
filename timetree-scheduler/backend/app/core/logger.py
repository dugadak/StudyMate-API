"""
Structured logging configuration using structlog.

Provides JSON-formatted logs with trace IDs for observability.
"""

import logging
import logging.config
import sys
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory

from .config import settings


def setup_logging() -> None:
    """Configure structured logging with appropriate formatters."""
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )
    
    # Disable some noisy loggers in development
    if settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add timestamp
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Add correlation ID processor
            add_correlation_id,
            # Choose formatter based on environment
            get_formatter(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_formatter() -> Any:
    """Get appropriate log formatter based on configuration."""
    if settings.LOG_FORMAT == "json":
        return structlog.processors.JSONRenderer(
            sort_keys=True,
            ensure_ascii=False,
        )
    else:
        return structlog.dev.ConsoleRenderer(
            colors=settings.DEBUG,
            exception_formatter=structlog.dev.plain_traceback,
        )


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    import contextvars
    
    # Try to get correlation ID from context
    try:
        from app.middleware.logging import correlation_id_var
        correlation_id = correlation_id_var.get(None)
        if correlation_id:
            event_dict["correlation_id"] = correlation_id
    except (ImportError, LookupError):
        pass
    
    return event_dict


class LoggerMixin:
    """Mixin to add structured logging to any class."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger bound to the current class."""
        return structlog.get_logger(self.__class__.__name__)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (defaults to caller's module)
    
    Returns:
        structlog.BoundLogger: Configured logger
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get("__name__", "unknown")
    
    return structlog.get_logger(name)


def log_api_request(
    method: str,
    url: str,
    status_code: int = None,
    duration_ms: float = None,
    user_id: str = None,
    **kwargs
) -> None:
    """
    Log API request with structured data.
    
    Args:
        method: HTTP method
        url: Request URL
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        user_id: User ID if authenticated
        **kwargs: Additional log data
    """
    logger = get_logger("api")
    
    log_data = {
        "event": "api_request",
        "method": method,
        "url": url,
        **kwargs
    }
    
    if status_code is not None:
        log_data["status_code"] = status_code
    
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    
    if user_id:
        log_data["user_id"] = user_id
    
    # Choose log level based on status code
    if status_code is None:
        logger.info("API request started", **log_data)
    elif status_code >= 500:
        logger.error("API request failed", **log_data)
    elif status_code >= 400:
        logger.warning("API request error", **log_data)
    else:
        logger.info("API request completed", **log_data)


def log_ai_request(
    provider: str,
    model: str,
    prompt_tokens: int = None,
    completion_tokens: int = None,
    duration_ms: float = None,
    success: bool = True,
    error: str = None,
    **kwargs
) -> None:
    """
    Log AI API request with structured data.
    
    Args:
        provider: AI provider (e.g., "openai", "anthropic")
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        duration_ms: Request duration in milliseconds
        success: Whether the request was successful
        error: Error message if failed
        **kwargs: Additional log data
    """
    logger = get_logger("ai")
    
    log_data = {
        "event": "ai_request",
        "provider": provider,
        "model": model,
        "success": success,
        **kwargs
    }
    
    if prompt_tokens is not None:
        log_data["prompt_tokens"] = prompt_tokens
    
    if completion_tokens is not None:
        log_data["completion_tokens"] = completion_tokens
    
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    
    if error:
        log_data["error"] = error
    
    if success:
        logger.info("AI request completed", **log_data)
    else:
        logger.error("AI request failed", **log_data)


def log_timetree_request(
    endpoint: str,
    method: str,
    status_code: int = None,
    duration_ms: float = None,
    rate_limit_remaining: int = None,
    success: bool = True,
    error: str = None,
    **kwargs
) -> None:
    """
    Log TimeTree API request with structured data.
    
    Args:
        endpoint: API endpoint
        method: HTTP method
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        rate_limit_remaining: Remaining rate limit
        success: Whether the request was successful
        error: Error message if failed
        **kwargs: Additional log data
    """
    logger = get_logger("timetree")
    
    log_data = {
        "event": "timetree_request",
        "endpoint": endpoint,
        "method": method,
        "success": success,
        **kwargs
    }
    
    if status_code is not None:
        log_data["status_code"] = status_code
    
    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)
    
    if rate_limit_remaining is not None:
        log_data["rate_limit_remaining"] = rate_limit_remaining
    
    if error:
        log_data["error"] = error
    
    if success:
        logger.info("TimeTree request completed", **log_data)
    else:
        logger.error("TimeTree request failed", **log_data)


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in log entries.
    
    Args:
        data: Data dictionary to mask
    
    Returns:
        Dict[str, Any]: Masked data dictionary
    """
    sensitive_keys = {
        "password", "token", "secret", "key", "authorization",
        "cookie", "session", "credential", "api_key"
    }
    
    masked_data = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                masked_data[key] = f"{value[:4]}***{value[-4:]}"
            else:
                masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value)
        else:
            masked_data[key] = value
    
    return masked_data