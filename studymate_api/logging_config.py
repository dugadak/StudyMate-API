"""
Advanced logging configuration for StudyMate API

This module provides:
- Structured logging with JSON formatting
- Performance monitoring logging
- Security event logging
- Business metrics logging
- Log filtering and formatting
- Integration with external monitoring systems
"""

import logging
import logging.config
import json
import time
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
import os


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage']:
                log_entry[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class PerformanceLogFormatter(logging.Formatter):
    """Formatter for performance logging"""
    
    def format(self, record):
        """Format performance log record"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'type': 'performance',
            'operation': getattr(record, 'operation', 'unknown'),
            'duration_ms': getattr(record, 'duration_ms', 0),
            'user_id': getattr(record, 'user_id', None),
            'request_path': getattr(record, 'request_path', None),
            'status_code': getattr(record, 'status_code', None),
            'query_count': getattr(record, 'query_count', None),
            'cache_hits': getattr(record, 'cache_hits', None),
            'cache_misses': getattr(record, 'cache_misses', None),
        }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class SecurityLogFormatter(logging.Formatter):
    """Formatter for security event logging"""
    
    def format(self, record):
        """Format security log record"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'type': 'security',
            'event': getattr(record, 'event', 'unknown'),
            'user_id': getattr(record, 'user_id', None),
            'ip_address': getattr(record, 'ip_address', None),
            'user_agent': getattr(record, 'user_agent', None),
            'request_path': getattr(record, 'request_path', None),
            'severity': record.levelname,
            'details': getattr(record, 'details', {}),
        }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class BusinessMetricsFormatter(logging.Formatter):
    """Formatter for business metrics logging"""
    
    def format(self, record):
        """Format business metrics log record"""
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'type': 'business_metrics',
            'metric': getattr(record, 'metric', 'unknown'),
            'value': getattr(record, 'value', 0),
            'unit': getattr(record, 'unit', 'count'),
            'user_id': getattr(record, 'user_id', None),
            'tags': getattr(record, 'tags', {}),
            'context': getattr(record, 'context', {}),
        }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from logs"""
    
    SENSITIVE_FIELDS = {
        'password', 'token', 'secret', 'key', 'authorization',
        'stripe_key', 'openai_key', 'api_key', 'access_token',
        'refresh_token', 'session_key', 'credit_card', 'cvv'
    }
    
    def filter(self, record):
        """Filter sensitive data from log record"""
        # Filter message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._mask_sensitive_data(record.msg)
        
        # Filter extra fields
        for key in list(record.__dict__.keys()):
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                record.__dict__[key] = '[REDACTED]'
            elif isinstance(record.__dict__[key], (dict, list)):
                record.__dict__[key] = self._mask_sensitive_data_recursive(record.__dict__[key])
        
        return True
    
    def _mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive data in text"""
        # Simple regex patterns for common sensitive data
        import re
        
        # Mask potential tokens/keys
        text = re.sub(r'["\']?[a-zA-Z0-9_-]{32,}["\']?', '[REDACTED]', text)
        
        # Mask email passwords in URLs
        text = re.sub(r'://[^:]+:[^@]+@', '://[REDACTED]:[REDACTED]@', text)
        
        return text
    
    def _mask_sensitive_data_recursive(self, data):
        """Recursively mask sensitive data in data structures"""
        if isinstance(data, dict):
            return {
                key: '[REDACTED]' if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS)
                else self._mask_sensitive_data_recursive(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._mask_sensitive_data_recursive(item) for item in data]
        elif isinstance(data, str):
            return self._mask_sensitive_data(data)
        else:
            return data


def get_logging_config() -> Dict[str, Any]:
    """Get comprehensive logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[{levelname}] {asctime} {name} {module}:{lineno} {funcName}() - {message}',
                'style': '{',
            },
            'simple': {
                'format': '[{levelname}] {asctime} - {message}',
                'style': '{',
            },
            'json': {
                '()': 'studymate_api.logging_config.JSONFormatter',
            },
            'performance': {
                '()': 'studymate_api.logging_config.PerformanceLogFormatter',
            },
            'security': {
                '()': 'studymate_api.logging_config.SecurityLogFormatter',
            },
            'business_metrics': {
                '()': 'studymate_api.logging_config.BusinessMetricsFormatter',
            },
        },
        'filters': {
            'sensitive_data': {
                '()': 'studymate_api.logging_config.SensitiveDataFilter',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
                'filters': ['sensitive_data'],
                'level': 'INFO',
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'studymate.log'),
                'maxBytes': 1024 * 1024 * 100,  # 100MB
                'backupCount': 10,
                'formatter': 'json',
                'filters': ['sensitive_data'],
                'level': 'INFO',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'errors.log'),
                'maxBytes': 1024 * 1024 * 50,  # 50MB
                'backupCount': 5,
                'formatter': 'json',
                'filters': ['sensitive_data'],
                'level': 'ERROR',
            },
            'performance_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'performance.log'),
                'maxBytes': 1024 * 1024 * 50,  # 50MB
                'backupCount': 5,
                'formatter': 'performance',
                'level': 'INFO',
            },
            'security_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'security.log'),
                'maxBytes': 1024 * 1024 * 50,  # 50MB
                'backupCount': 10,
                'formatter': 'security',
                'level': 'INFO',
            },
            'business_metrics_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(log_dir, 'business_metrics.log'),
                'maxBytes': 1024 * 1024 * 100,  # 100MB
                'backupCount': 10,
                'formatter': 'business_metrics',
                'level': 'INFO',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['error_file'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['security_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False,
            },
            'studymate_api': {
                'handlers': ['console', 'file', 'error_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'accounts': {
                'handlers': ['console', 'file', 'security_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'study': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'quiz': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'subscription': {
                'handlers': ['console', 'file', 'security_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'notifications': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'performance': {
                'handlers': ['performance_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'security': {
                'handlers': ['security_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'business_metrics': {
                'handlers': ['business_metrics_file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
    }
    
    # Add debug logging in development
    if settings.DEBUG:
        config['handlers']['console']['level'] = 'DEBUG'
        config['loggers']['studymate_api']['level'] = 'DEBUG'
    
    return config


def setup_logging():
    """Setup logging configuration"""
    config = get_logging_config()
    logging.config.dictConfig(config)


# Utility functions for structured logging
def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log performance metrics"""
    logger = logging.getLogger('performance')
    logger.info(
        f"Performance: {operation} took {duration_ms:.2f}ms",
        extra={
            'operation': operation,
            'duration_ms': duration_ms,
            **kwargs
        }
    )


def log_security_event(event: str, user_id: Optional[int] = None, 
                      ip_address: Optional[str] = None, **kwargs):
    """Log security events"""
    logger = logging.getLogger('security')
    logger.warning(
        f"Security event: {event}",
        extra={
            'event': event,
            'user_id': user_id,
            'ip_address': ip_address,
            **kwargs
        }
    )


def log_business_metric(metric: str, value: float, unit: str = 'count', **kwargs):
    """Log business metrics"""
    logger = logging.getLogger('business_metrics')
    logger.info(
        f"Business metric: {metric} = {value} {unit}",
        extra={
            'metric': metric,
            'value': value,
            'unit': unit,
            **kwargs
        }
    )


def log_api_request(request, response, duration_ms: float):
    """Log API request with performance data"""
    logger = logging.getLogger('studymate_api.requests')
    
    # Extract request info
    user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
    
    logger.info(
        f"API {request.method} {request.path} - {response.status_code} ({duration_ms:.2f}ms)",
        extra={
            'operation': 'api_request',
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'user_id': user_id,
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'content_length': len(response.content) if hasattr(response, 'content') else 0,
        }
    )


def log_ai_request(model: str, prompt_tokens: int, completion_tokens: int, 
                   cost: Optional[float] = None, **kwargs):
    """Log AI service requests"""
    logger = logging.getLogger('studymate_api.ai')
    
    logger.info(
        f"AI request: {model} - {prompt_tokens + completion_tokens} tokens",
        extra={
            'model': model,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'cost': cost,
            **kwargs
        }
    )


def log_database_query(query_count: int, duration_ms: float, **kwargs):
    """Log database query performance"""
    logger = logging.getLogger('studymate_api.database')
    
    if query_count > 10 or duration_ms > 100:
        logger.warning(
            f"High database usage: {query_count} queries in {duration_ms:.2f}ms",
            extra={
                'query_count': query_count,
                'duration_ms': duration_ms,
                **kwargs
            }
        )


# Export main functions
__all__ = [
    'setup_logging',
    'log_performance',
    'log_security_event', 
    'log_business_metric',
    'log_api_request',
    'log_ai_request',
    'log_database_query',
    'JSONFormatter',
    'PerformanceLogFormatter',
    'SecurityLogFormatter',
    'BusinessMetricsFormatter',
    'SensitiveDataFilter'
]