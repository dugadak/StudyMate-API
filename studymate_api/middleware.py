"""
Custom middleware for StudyMate API

This module provides:
- Request/Response logging middleware
- Performance monitoring middleware
- Security enhancement middleware
- Error tracking middleware
- Business metrics collection middleware
"""

import time
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser
from typing import Optional, Dict, Any
import uuid

from .logging_config import log_api_request, log_performance, log_security_event
from .exceptions import RateLimitException

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware for comprehensive request/response logging"""
    
    def process_request(self, request):
        """Process incoming request"""
        # Store request start time
        request._start_time = time.time()
        request._request_id = str(uuid.uuid4())
        
        # Log incoming request
        logger.info(
            f"Incoming request: {request.method} {request.path}",
            extra={
                'request_id': request._request_id,
                'method': request.method,
                'path': request.path,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'content_type': request.content_type,
                'content_length': request.META.get('CONTENT_LENGTH', 0),
            }
        )
    
    def process_response(self, request, response):
        """Process outgoing response"""
        if hasattr(request, '_start_time'):
            duration_ms = (time.time() - request._start_time) * 1000
            
            # Log API request with performance data
            log_api_request(request, response, duration_ms)
            
            # Add performance headers in debug mode
            if settings.DEBUG:
                response['X-Request-ID'] = getattr(request, '_request_id', 'unknown')
                response['X-Response-Time'] = f"{duration_ms:.2f}ms"
        
        return response
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """Middleware for performance monitoring and alerts"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.slow_request_threshold = getattr(settings, 'SLOW_REQUEST_THRESHOLD_MS', 1000)
        self.critical_request_threshold = getattr(settings, 'CRITICAL_REQUEST_THRESHOLD_MS', 5000)
    
    def process_request(self, request):
        """Start performance monitoring"""
        request._perf_start = time.time()
        request._initial_query_count = self._get_query_count()
    
    def process_response(self, request, response):
        """Monitor response performance"""
        if hasattr(request, '_perf_start'):
            duration_ms = (time.time() - request._perf_start) * 1000
            query_count = self._get_query_count() - getattr(request, '_initial_query_count', 0)
            
            # Log performance metrics
            log_performance(
                operation='http_request',
                duration_ms=duration_ms,
                user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                request_path=request.path,
                status_code=response.status_code,
                query_count=query_count
            )
            
            # Alert on slow requests
            if duration_ms > self.critical_request_threshold:
                logger.critical(
                    f"CRITICAL: Very slow request {request.method} {request.path} took {duration_ms:.2f}ms",
                    extra={
                        'duration_ms': duration_ms,
                        'query_count': query_count,
                        'request_path': request.path,
                        'method': request.method,
                        'status_code': response.status_code
                    }
                )
            elif duration_ms > self.slow_request_threshold:
                logger.warning(
                    f"Slow request {request.method} {request.path} took {duration_ms:.2f}ms",
                    extra={
                        'duration_ms': duration_ms,
                        'query_count': query_count,
                        'request_path': request.path,
                        'method': request.method,
                        'status_code': response.status_code
                    }
                )
        
        return response
    
    def _get_query_count(self) -> int:
        """Get current database query count"""
        try:
            from django.db import connection
            return len(connection.queries)
        except:
            return 0


class SecurityMiddleware(MiddlewareMixin):
    """Enhanced security middleware"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.suspicious_patterns = [
            'script', 'javascript:', 'vbscript:', 'onload', 'onerror',
            'eval(', 'document.cookie', 'window.location', 'union select',
            'drop table', 'insert into', 'delete from', '../', '..\\',
            '<script', '</script>', 'cmd.exe', '/bin/bash', 'passwd'
        ]
    
    def process_request(self, request):
        """Process request for security threats"""
        client_ip = self._get_client_ip(request)
        
        # Check for suspicious patterns in request
        if self._has_suspicious_content(request):
            log_security_event(
                event='suspicious_request_content',
                user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                ip_address=client_ip,
                details={
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                }
            )
        
        # Check for multiple failed requests from same IP
        if self._is_potential_attack(client_ip):
            log_security_event(
                event='potential_attack_detected',
                ip_address=client_ip,
                details={
                    'path': request.path,
                    'method': request.method
                }
            )
    
    def process_response(self, request, response):
        """Process response for security headers"""
        # Add security headers
        if not settings.DEBUG:
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Log authentication failures
        if response.status_code == 401:
            log_security_event(
                event='authentication_failure',
                user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                ip_address=self._get_client_ip(request),
                details={
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT')
                }
            )
        
        return response
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _has_suspicious_content(self, request) -> bool:
        """Check if request contains suspicious content"""
        # Check query parameters
        for key, value in request.GET.items():
            if any(pattern in str(value).lower() for pattern in self.suspicious_patterns):
                return True
        
        # Check POST data if available
        if hasattr(request, 'body') and request.body:
            try:
                body_str = request.body.decode('utf-8').lower()
                if any(pattern in body_str for pattern in self.suspicious_patterns):
                    return True
            except:
                pass
        
        # Check headers
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if any(pattern in user_agent for pattern in ['sqlmap', 'nikto', 'nmap', 'masscan']):
            return True
        
        return False
    
    def _is_potential_attack(self, ip_address: str) -> bool:
        """Check if IP shows signs of potential attack"""
        if not ip_address:
            return False
        
        cache_key = f"security_check_{ip_address}"
        request_count = cache.get(cache_key, 0)
        
        # More than 100 requests per minute from same IP
        if request_count > 100:
            return True
        
        cache.set(cache_key, request_count + 1, 60)  # 1 minute
        return False


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.rate_limits = getattr(settings, 'RATE_LIMITS', {
            'default': {'requests': 1000, 'window': 3600},  # 1000 requests per hour
            'api': {'requests': 500, 'window': 3600},        # 500 API requests per hour
            'auth': {'requests': 10, 'window': 300},         # 10 auth requests per 5 minutes
        })
    
    def process_request(self, request):
        """Check rate limits"""
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser) else None
        
        # Determine rate limit type
        rate_limit_type = self._get_rate_limit_type(request)
        
        # Check rate limit
        if self._is_rate_limited(client_ip, user_id, rate_limit_type):
            raise RateLimitException(
                message=f"Rate limit exceeded for {rate_limit_type}",
                retry_after=self.rate_limits[rate_limit_type]['window']
            )
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _get_rate_limit_type(self, request) -> str:
        """Determine rate limit type based on request"""
        if request.path.startswith('/api/auth/'):
            return 'auth'
        elif request.path.startswith('/api/'):
            return 'api'
        else:
            return 'default'
    
    def _is_rate_limited(self, ip_address: str, user_id: Optional[int], rate_limit_type: str) -> bool:
        """Check if request should be rate limited"""
        rate_config = self.rate_limits.get(rate_limit_type, self.rate_limits['default'])
        
        # Create cache keys for IP and user
        ip_key = f"rate_limit_{rate_limit_type}_ip_{ip_address}"
        user_key = f"rate_limit_{rate_limit_type}_user_{user_id}" if user_id else None
        
        # Check IP rate limit
        ip_count = cache.get(ip_key, 0)
        if ip_count >= rate_config['requests']:
            return True
        
        # Check user rate limit if authenticated
        if user_key:
            user_count = cache.get(user_key, 0)
            if user_count >= rate_config['requests']:
                return True
        
        # Increment counters
        cache.set(ip_key, ip_count + 1, rate_config['window'])
        if user_key:
            user_count = cache.get(user_key, 0)
            cache.set(user_key, user_count + 1, rate_config['window'])
        
        return False


class ErrorTrackingMiddleware(MiddlewareMixin):
    """Middleware for error tracking and monitoring"""
    
    def process_exception(self, request, exception):
        """Track exceptions"""
        error_id = str(uuid.uuid4())
        
        # Log exception with context
        logger.error(
            f"Unhandled exception {error_id}: {str(exception)}",
            extra={
                'error_id': error_id,
                'exception_type': exception.__class__.__name__,
                'request_path': request.path,
                'request_method': request.method,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'request_data': self._get_safe_request_data(request)
            },
            exc_info=True
        )
        
        # In production, you might want to send this to an external error tracking service
        # like Sentry, Rollbar, or a custom analytics platform
    
    def _get_client_ip(self, request) -> Optional[str]:
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _get_safe_request_data(self, request) -> Dict[str, Any]:
        """Get safe request data for logging (excluding sensitive info)"""
        safe_data = {
            'query_params': dict(request.GET),
            'content_type': request.content_type,
        }
        
        # Only include POST data if it's safe
        if request.method == 'POST' and request.content_type == 'application/json':
            try:
                if hasattr(request, 'body') and request.body:
                    body_data = json.loads(request.body.decode('utf-8'))
                    # Remove sensitive fields
                    safe_body = {
                        key: '[REDACTED]' if any(sensitive in key.lower() 
                                               for sensitive in ['password', 'token', 'secret', 'key'])
                        else value
                        for key, value in body_data.items()
                    }
                    safe_data['body'] = safe_body
            except:
                pass
        
        return safe_data


# Export middleware classes
__all__ = [
    'RequestLoggingMiddleware',
    'PerformanceMonitoringMiddleware',
    'SecurityMiddleware',
    'RateLimitMiddleware', 
    'ErrorTrackingMiddleware'
]