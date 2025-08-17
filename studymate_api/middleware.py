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
from .security import validate_and_sanitize, SecurityHeaders

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
        # Add comprehensive security headers
        security_headers = SecurityHeaders.get_security_headers()
        for header, value in security_headers.items():
            response[header] = value
        
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


class InputSanitizationMiddleware(MiddlewareMixin):
    """입력 데이터 보안 검증 및 삭제 미들웨어"""
    
    def process_request(self, request):
        """요청 데이터 검증 및 삭제"""
        # GET 파라미터 검증
        if request.GET:
            for key, value in request.GET.items():
                validation_result = validate_and_sanitize(value, strict=False)
                if not validation_result['is_safe']:
                    log_security_event(
                        event='malicious_get_parameter',
                        user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                        ip_address=self._get_client_ip(request),
                        details={
                            'parameter': key,
                            'value': value[:100],  # 처음 100자만 로그
                            'issues': validation_result['issues']
                        }
                    )
                    # 위험한 요청 차단
                    return JsonResponse({
                        'error': '요청에 보안 위험이 감지되었습니다.',
                        'code': 'SECURITY_RISK_DETECTED'
                    }, status=400)
        
        # POST 데이터 검증 (JSON)
        if request.content_type == 'application/json' and hasattr(request, 'body'):
            try:
                import json
                body_data = json.loads(request.body.decode('utf-8'))
                validation_result = validate_and_sanitize(body_data, strict=True)
                
                if not validation_result['is_safe']:
                    log_security_event(
                        event='malicious_post_data',
                        user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                        ip_address=self._get_client_ip(request),
                        details={
                            'content_type': request.content_type,
                            'issues': validation_result['issues']
                        }
                    )
                    return JsonResponse({
                        'error': '요청 데이터에 보안 위험이 감지되었습니다.',
                        'code': 'MALICIOUS_DATA_DETECTED'
                    }, status=400)
            
            except (json.JSONDecodeError, UnicodeDecodeError):
                # JSON 파싱 실패는 다른 미들웨어에서 처리
                pass
            except Exception as e:
                logger.error(f"Input sanitization error: {e}")
    
    def _get_client_ip(self, request) -> Optional[str]:
        """클라이언트 IP 주소 반환"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class CSRFProtectionMiddleware(MiddlewareMixin):
    """CSRF 보호 강화 미들웨어"""
    
    def process_request(self, request):
        """CSRF 검증"""
        # API 요청은 기본 CSRF 보호 외에 추가 검증
        if request.path.startswith('/api/') and request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # Referer 헤더 검증
            referer = request.META.get('HTTP_REFERER')
            host = request.META.get('HTTP_HOST')
            
            if referer and host:
                from urllib.parse import urlparse
                referer_host = urlparse(referer).netloc
                
                # 다른 도메인에서의 요청 차단
                if referer_host != host and not self._is_trusted_origin(referer_host):
                    log_security_event(
                        event='csrf_attack_attempt',
                        user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                        ip_address=self._get_client_ip(request),
                        details={
                            'referer': referer,
                            'host': host,
                            'path': request.path
                        }
                    )
                    return JsonResponse({
                        'error': 'Cross-site request blocked',
                        'code': 'CSRF_BLOCKED'
                    }, status=403)
    
    def _is_trusted_origin(self, origin: str) -> bool:
        """신뢰할 수 있는 origin인지 확인"""
        trusted_origins = getattr(settings, 'TRUSTED_ORIGINS', [])
        return origin in trusted_origins
    
    def _get_client_ip(self, request) -> Optional[str]:
        """클라이언트 IP 주소 반환"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class SQLInjectionProtectionMiddleware(MiddlewareMixin):
    """SQL 인젝션 보호 미들웨어"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.sql_patterns = [
            r"(\bunion\s+select\b)",
            r"(\bselect\s+.*\bfrom\b)",
            r"(\binsert\s+into\b)",
            r"(\bupdate\s+.*\bset\b)",
            r"(\bdelete\s+from\b)",
            r"(\bdrop\s+table\b)",
            r"(\bexec\s*\()",
            r"(--\s*$)",
            r"(/\*.*\*/)",
            r"(;\s*$)",
        ]
        self.sql_regex = re.compile("|".join(self.sql_patterns), re.IGNORECASE | re.MULTILINE)
    
    def process_request(self, request):
        """SQL 인젝션 패턴 검사"""
        # URL 파라미터 검사
        query_string = request.META.get('QUERY_STRING', '')
        if query_string and self.sql_regex.search(query_string):
            self._log_sql_injection_attempt(request, 'query_string', query_string)
            return JsonResponse({
                'error': 'Malicious request detected',
                'code': 'SQL_INJECTION_BLOCKED'
            }, status=400)
        
        # POST 데이터 검사
        if request.method == 'POST' and hasattr(request, 'body'):
            try:
                body_str = request.body.decode('utf-8')
                if self.sql_regex.search(body_str):
                    self._log_sql_injection_attempt(request, 'post_body', body_str[:200])
                    return JsonResponse({
                        'error': 'Malicious request detected',
                        'code': 'SQL_INJECTION_BLOCKED'
                    }, status=400)
            except UnicodeDecodeError:
                pass  # 바이너리 데이터는 검사하지 않음
    
    def _log_sql_injection_attempt(self, request, location: str, content: str):
        """SQL 인젝션 시도 로그"""
        log_security_event(
            event='sql_injection_attempt',
            user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
            ip_address=self._get_client_ip(request),
            details={
                'location': location,
                'content': content[:200],
                'path': request.path,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT')
            }
        )
    
    def _get_client_ip(self, request) -> Optional[str]:
        """클라이언트 IP 주소 반환"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class SessionSecurityMiddleware(MiddlewareMixin):
    """세션 보안 강화 미들웨어"""
    
    def process_request(self, request):
        """세션 보안 검증"""
        if hasattr(request, 'session') and request.session.session_key:
            # 세션 하이재킹 검증
            stored_ip = request.session.get('_ip_address')
            current_ip = self._get_client_ip(request)
            
            if stored_ip and stored_ip != current_ip:
                # IP 주소가 변경된 경우 세션 무효화
                log_security_event(
                    event='session_hijacking_attempt',
                    user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                    ip_address=current_ip,
                    details={
                        'stored_ip': stored_ip,
                        'current_ip': current_ip,
                        'session_key': request.session.session_key[:10] + '...'
                    }
                )
                request.session.flush()
                return JsonResponse({
                    'error': 'Session security violation detected',
                    'code': 'SESSION_HIJACKING_BLOCKED'
                }, status=401)
            
            # User-Agent 검증
            stored_ua = request.session.get('_user_agent')
            current_ua = request.META.get('HTTP_USER_AGENT', '')
            
            if stored_ua and stored_ua != current_ua:
                log_security_event(
                    event='session_user_agent_mismatch',
                    user_id=getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                    ip_address=current_ip,
                    details={
                        'stored_ua': stored_ua[:100],
                        'current_ua': current_ua[:100]
                    }
                )
                # User-Agent 변경은 경고만 로그하고 차단하지는 않음
        
        # 새 세션의 경우 보안 정보 저장
        if hasattr(request, 'session') and not request.session.get('_security_initialized'):
            request.session['_ip_address'] = self._get_client_ip(request)
            request.session['_user_agent'] = request.META.get('HTTP_USER_AGENT', '')
            request.session['_security_initialized'] = True
    
    def _get_client_ip(self, request) -> Optional[str]:
        """클라이언트 IP 주소 반환"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# Export middleware classes
__all__ = [
    'RequestLoggingMiddleware',
    'PerformanceMonitoringMiddleware',
    'SecurityMiddleware',
    'RateLimitMiddleware', 
    'ErrorTrackingMiddleware',
    'InputSanitizationMiddleware',
    'CSRFProtectionMiddleware',
    'SQLInjectionProtectionMiddleware',
    'SessionSecurityMiddleware'
]