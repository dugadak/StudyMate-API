"""
Zero Trust 보안 미들웨어

모든 요청에 대해 "Never trust, always verify" 원칙을 적용합니다.
"""

import logging
import json
from typing import Optional, Dict, Any
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone

from studymate_api.zero_trust_security import (
    evaluate_request_security, SecurityAction, ThreatLevel
)

logger = logging.getLogger(__name__)


class ZeroTrustSecurityMiddleware(MiddlewareMixin):
    """Zero Trust 보안 미들웨어"""
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.zero_trust_enabled = getattr(settings, 'ZERO_TRUST_ENABLED', True)
        
        # Zero Trust를 적용하지 않을 경로들
        self.excluded_paths = {
            '/health/',
            '/metrics/',
            '/admin/login/',
            '/api/auth/register/',  # 신규 가입은 예외
            '/static/',
            '/media/',
            '/favicon.ico'
        }
        
        # 높은 보안이 필요한 경로들
        self.high_security_paths = {
            '/admin/',
            '/api/subscription/',
            '/api/study/generate-summary/',
            '/api/auth/profile/',
        }
        
        # 실시간 위협 탐지 설정
        self.threat_detection = {
            'max_requests_per_minute': 60,
            'max_failed_attempts': 5,
            'suspicious_patterns': [
                'sql', 'script', 'union', 'select', 'drop',
                '../', '<script>', 'javascript:', 'vbscript:'
            ]
        }
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """요청 전 Zero Trust 보안 검사"""
        if not self.zero_trust_enabled:
            return None
        
        # 제외 경로 확인
        if self._should_exclude_path(request.path):
            return None
        
        # 익명 사용자는 로그인 관련 경로만 허용
        if isinstance(request.user, AnonymousUser):
            if not self._is_allowed_for_anonymous(request.path):
                return self._create_auth_required_response()
            return None
        
        try:
            # Zero Trust 보안 평가
            action, context = evaluate_request_security(request, request.user)
            
            # 보안 컨텍스트를 request에 저장
            request.zero_trust_context = context
            
            # 보안 액션에 따른 처리
            response = self._handle_security_action(action, context, request)
            
            if response:
                return response
            
            # 추가 보안 검사
            self._perform_additional_security_checks(request)
            
        except Exception as e:
            logger.error(f"Zero Trust 미들웨어 오류: {e}")
            # 오류 시 보수적으로 차단
            return self._create_security_error_response()
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """응답 후 보안 로깅 및 추가 처리"""
        if not self.zero_trust_enabled:
            return response
        
        try:
            # Zero Trust 컨텍스트가 있으면 로깅
            if hasattr(request, 'zero_trust_context'):
                self._log_security_event(request, response)
            
            # 보안 헤더 추가
            self._add_security_headers(response)
            
            # 세션 보안 강화
            self._enhance_session_security(request, response)
            
        except Exception as e:
            logger.error(f"Zero Trust 응답 처리 오류: {e}")
        
        return response
    
    def _should_exclude_path(self, path: str) -> bool:
        """경로 제외 여부 확인"""
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True
        return False
    
    def _is_allowed_for_anonymous(self, path: str) -> bool:
        """익명 사용자에게 허용되는 경로인지 확인"""
        allowed_paths = {
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/auth/refresh/',
            '/api/docs/',
            '/api/redoc/',
            '/api/schema/'
        }
        
        for allowed_path in allowed_paths:
            if path.startswith(allowed_path):
                return True
        
        return False
    
    def _handle_security_action(self, action: SecurityAction, context: Dict[str, Any], 
                               request: HttpRequest) -> Optional[HttpResponse]:
        """보안 액션 처리"""
        if action == SecurityAction.ALLOW:
            # 신뢰할 수 있는 요청 - 디바이스/위치 학습
            self._learn_trusted_patterns(request, context)
            return None
        
        elif action == SecurityAction.CHALLENGE:
            # MFA 또는 추가 인증 필요
            return self._create_challenge_response(context)
        
        elif action == SecurityAction.BLOCK:
            # 요청 차단
            self._log_blocked_request(request, context)
            return self._create_blocked_response(context)
        
        elif action == SecurityAction.QUARANTINE:
            # 격리 조치
            self._quarantine_user(request.user, context)
            return self._create_quarantine_response()
        
        return None
    
    def _perform_additional_security_checks(self, request: HttpRequest):
        """추가 보안 검사"""
        # Rate limiting 검사
        self._check_rate_limits(request)
        
        # 악성 페이로드 검사
        self._check_malicious_payload(request)
        
        # 세션 하이재킹 검사
        self._check_session_hijacking(request)
    
    def _check_rate_limits(self, request: HttpRequest):
        """Rate limiting 검사"""
        user_id = request.user.id
        ip_address = self._get_client_ip(request)
        
        # 사용자별 요청 제한
        user_key = f"rate_limit:user:{user_id}"
        user_requests = cache.get(user_key, 0)
        
        if user_requests > self.threat_detection['max_requests_per_minute']:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            raise SecurityException("Too many requests")
        
        # IP별 요청 제한
        ip_key = f"rate_limit:ip:{ip_address}"
        ip_requests = cache.get(ip_key, 0)
        
        if ip_requests > self.threat_detection['max_requests_per_minute'] * 2:
            logger.warning(f"Rate limit exceeded for IP {ip_address}")
            raise SecurityException("Too many requests from IP")
        
        # 카운터 증가
        cache.set(user_key, user_requests + 1, timeout=60)
        cache.set(ip_key, ip_requests + 1, timeout=60)
    
    def _check_malicious_payload(self, request: HttpRequest):
        """악성 페이로드 검사"""
        # URL 파라미터 검사
        query_string = request.META.get('QUERY_STRING', '').lower()
        
        for pattern in self.threat_detection['suspicious_patterns']:
            if pattern in query_string:
                logger.warning(f"Suspicious pattern detected in URL: {pattern}")
                raise SecurityException("Malicious payload detected")
        
        # POST 데이터 검사 (JSON)
        if request.method == 'POST' and request.content_type == 'application/json':
            try:
                body = request.body.decode('utf-8').lower()
                for pattern in self.threat_detection['suspicious_patterns']:
                    if pattern in body:
                        logger.warning(f"Suspicious pattern detected in body: {pattern}")
                        raise SecurityException("Malicious payload detected")
            except UnicodeDecodeError:
                pass
    
    def _check_session_hijacking(self, request: HttpRequest):
        """세션 하이재킹 검사"""
        session = request.session
        
        # 세션에 저장된 IP와 현재 IP 비교
        stored_ip = session.get('secure_ip')
        current_ip = self._get_client_ip(request)
        
        if stored_ip and stored_ip != current_ip:
            logger.warning(f"Possible session hijacking: stored_ip={stored_ip}, current_ip={current_ip}")
            # 세션 무효화
            session.flush()
            raise SecurityException("Session security violation")
        
        # IP 정보 저장
        if not stored_ip:
            session['secure_ip'] = current_ip
        
        # User-Agent 변경 검사
        stored_ua = session.get('secure_user_agent')
        current_ua = request.META.get('HTTP_USER_AGENT', '')
        
        if stored_ua and stored_ua != current_ua:
            logger.warning(f"User-Agent changed mid-session")
            session.flush()
            raise SecurityException("Session security violation")
        
        if not stored_ua:
            session['secure_user_agent'] = current_ua
    
    def _learn_trusted_patterns(self, request: HttpRequest, context: Dict[str, Any]):
        """신뢰할 수 있는 패턴 학습"""
        user_id = request.user.id
        
        # 디바이스 패턴 학습
        device_context = context.get('context', {}).get('device_fingerprint', {})
        if device_context:
            cache_key = f"trusted_device:{user_id}:{device_context.get('browser_hash', '')}"
            cache.set(cache_key, True, timeout=86400 * 30)  # 30일
        
        # 위치 패턴 학습
        location_context = context.get('context', {}).get('location_context', {})
        if location_context and not location_context.get('is_vpn', False):
            cache_key = f"trusted_location:{user_id}"
            trusted_locations = cache.get(cache_key, [])
            
            new_location = {
                'country': location_context.get('country'),
                'city': location_context.get('city')
            }
            
            if new_location not in trusted_locations:
                trusted_locations.append(new_location)
                cache.set(cache_key, trusted_locations[-10:], timeout=86400 * 7)  # 7일, 최대 10개
    
    def _create_challenge_response(self, context: Dict[str, Any]) -> JsonResponse:
        """챌린지 응답 생성"""
        additional_measures = context.get('additional_measures', {})
        
        return JsonResponse({
            'error': 'additional_verification_required',
            'message': '추가 인증이 필요합니다.',
            'challenge_type': additional_measures.get('challenge_type', 'mfa'),
            'mfa_required': additional_measures.get('mfa_required', True),
            'trust_score': context.get('trust_score'),
            'timestamp': timezone.now().isoformat()
        }, status=403)
    
    def _create_blocked_response(self, context: Dict[str, Any]) -> JsonResponse:
        """차단 응답 생성"""
        return JsonResponse({
            'error': 'access_denied',
            'message': '보안상의 이유로 접근이 거부되었습니다.',
            'threat_level': context.get('threat_level'),
            'block_duration': context.get('additional_measures', {}).get('block_duration', 3600),
            'timestamp': timezone.now().isoformat()
        }, status=403)
    
    def _create_quarantine_response(self) -> JsonResponse:
        """격리 응답 생성"""
        return JsonResponse({
            'error': 'account_quarantined',
            'message': '계정이 일시적으로 격리되었습니다. 관리자에게 문의하세요.',
            'contact_support': True,
            'timestamp': timezone.now().isoformat()
        }, status=403)
    
    def _create_auth_required_response(self) -> JsonResponse:
        """인증 필요 응답 생성"""
        return JsonResponse({
            'error': 'authentication_required',
            'message': '인증이 필요합니다.',
            'login_url': '/api/auth/login/'
        }, status=401)
    
    def _create_security_error_response(self) -> JsonResponse:
        """보안 오류 응답 생성"""
        return JsonResponse({
            'error': 'security_error',
            'message': '보안 검사 중 오류가 발생했습니다.',
            'timestamp': timezone.now().isoformat()
        }, status=500)
    
    def _log_blocked_request(self, request: HttpRequest, context: Dict[str, Any]):
        """차단된 요청 로깅"""
        log_data = {
            'user_id': request.user.id,
            'ip_address': self._get_client_ip(request),
            'path': request.path,
            'method': request.method,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'threat_level': context.get('threat_level'),
            'trust_score': context.get('trust_score'),
            'timestamp': timezone.now().isoformat()
        }
        
        logger.warning(f"Zero Trust BLOCKED request: {log_data}")
    
    def _quarantine_user(self, user, context: Dict[str, Any]):
        """사용자 격리"""
        cache_key = f"quarantined_user:{user.id}"
        quarantine_data = {
            'quarantined_at': timezone.now().isoformat(),
            'reason': 'zero_trust_violation',
            'context': context,
            'duration': 86400  # 24시간
        }
        
        cache.set(cache_key, quarantine_data, timeout=86400)
        logger.critical(f"User {user.id} quarantined due to security violation")
    
    def _log_security_event(self, request: HttpRequest, response: HttpResponse):
        """보안 이벤트 로깅"""
        context = request.zero_trust_context
        
        log_data = {
            'user_id': request.user.id,
            'ip_address': self._get_client_ip(request),
            'path': request.path,
            'method': request.method,
            'status_code': response.status_code,
            'trust_score': context.get('trust_score'),
            'threat_level': context.get('threat_level'),
            'timestamp': timezone.now().isoformat()
        }
        
        # 보안 로그 레벨 결정
        threat_level = context.get('threat_level', 'low')
        if threat_level in ['high', 'critical']:
            logger.warning(f"Zero Trust HIGH RISK event: {log_data}")
        else:
            logger.info(f"Zero Trust event: {log_data}")
    
    def _add_security_headers(self, response: HttpResponse):
        """보안 헤더 추가"""
        # CSP 헤더
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self';"
        )
        
        # 기타 보안 헤더
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    def _enhance_session_security(self, request: HttpRequest, response: HttpResponse):
        """세션 보안 강화"""
        if hasattr(request, 'session'):
            session = request.session
            
            # 세션 로테이션 (높은 보안 경로)
            if request.path in self.high_security_paths:
                session.cycle_key()
            
            # 세션 만료 시간 단축 (의심스러운 활동)
            context = getattr(request, 'zero_trust_context', {})
            trust_score = context.get('trust_score', 1.0)
            
            if trust_score < 0.7:
                session.set_expiry(1800)  # 30분
            elif trust_score < 0.5:
                session.set_expiry(900)   # 15분
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """클라이언트 IP 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class SecurityException(Exception):
    """보안 예외"""
    pass


class ThreatDetectionMiddleware(MiddlewareMixin):
    """실시간 위협 탐지 미들웨어"""
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.threat_patterns = {
            'brute_force': {
                'window': 300,  # 5분
                'threshold': 10,
                'action': 'block'
            },
            'enumeration': {
                'window': 60,   # 1분
                'threshold': 20,
                'action': 'challenge'
            },
            'ddos': {
                'window': 60,   # 1분
                'threshold': 100,
                'action': 'block'
            }
        }
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """실시간 위협 탐지"""
        if isinstance(request.user, AnonymousUser):
            return None
        
        try:
            # 다양한 위협 패턴 탐지
            self._detect_brute_force(request)
            self._detect_enumeration(request)
            self._detect_ddos(request)
            
        except SecurityException as e:
            logger.warning(f"Threat detected: {e}")
            return JsonResponse({
                'error': 'threat_detected',
                'message': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=429)
        
        return None
    
    def _detect_brute_force(self, request: HttpRequest):
        """무차별 대입 공격 탐지"""
        if request.path.endswith('/login/') and request.method == 'POST':
            ip_address = self._get_client_ip(request)
            cache_key = f"brute_force:{ip_address}"
            
            attempts = cache.get(cache_key, 0)
            if attempts > self.threat_patterns['brute_force']['threshold']:
                raise SecurityException("Brute force attack detected")
            
            cache.set(cache_key, attempts + 1, 
                     timeout=self.threat_patterns['brute_force']['window'])
    
    def _detect_enumeration(self, request: HttpRequest):
        """사용자 열거 공격 탐지"""
        if '/api/' in request.path:
            user_id = request.user.id
            cache_key = f"enumeration:{user_id}"
            
            requests = cache.get(cache_key, 0)
            if requests > self.threat_patterns['enumeration']['threshold']:
                raise SecurityException("User enumeration detected")
            
            cache.set(cache_key, requests + 1,
                     timeout=self.threat_patterns['enumeration']['window'])
    
    def _detect_ddos(self, request: HttpRequest):
        """DDoS 공격 탐지"""
        ip_address = self._get_client_ip(request)
        cache_key = f"ddos:{ip_address}"
        
        requests = cache.get(cache_key, 0)
        if requests > self.threat_patterns['ddos']['threshold']:
            raise SecurityException("DDoS attack detected")
        
        cache.set(cache_key, requests + 1,
                 timeout=self.threat_patterns['ddos']['window'])
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """클라이언트 IP 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip