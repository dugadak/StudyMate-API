"""
분산 추적 미들웨어

HTTP 요청에 대한 자동 추적 및 컨텍스트 전파를 담당합니다.
"""

import logging
import time
from typing import Optional, Dict, Any
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from studymate_api.distributed_tracing import (
    studymate_tracer, get_current_trace_id, get_current_span_id
)

logger = logging.getLogger(__name__)


class DistributedTracingMiddleware(MiddlewareMixin):
    """분산 추적 미들웨어"""
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.tracing_enabled = getattr(settings, 'DISTRIBUTED_TRACING', {}).get('ENABLED', False)
        
        # 추적하지 않을 경로들
        self.excluded_paths = {
            '/health/',
            '/metrics/',
            '/admin/jsi18n/',
            '/static/',
            '/media/',
            '/favicon.ico'
        }
        
        # 추적할 중요한 엔드포인트들
        self.important_endpoints = {
            '/api/study/generate-summary/',
            '/api/quiz/attempt/',
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/subscription/subscribe/',
        }
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """요청 처리 시작"""
        if not self.tracing_enabled or self._should_exclude_path(request.path):
            return None
        
        # 분산 추적 시스템 초기화 확인
        if not studymate_tracer.is_initialized:
            try:
                studymate_tracer.initialize()
            except Exception as e:
                logger.warning(f"분산 추적 초기화 실패: {e}")
                return None
        
        # HTTP 요청 스팬 생성
        span_name = self._generate_span_name(request)
        span = studymate_tracer.create_span(span_name)
        
        # 요청 정보 추가
        self._add_request_attributes(span, request)
        
        # 스팬을 request에 저장
        request._tracing_span = span
        request._tracing_start_time = time.time()
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """응답 처리 완료"""
        if not self.tracing_enabled or not hasattr(request, '_tracing_span'):
            return response
        
        try:
            span = request._tracing_span
            start_time = getattr(request, '_tracing_start_time', time.time())
            
            # 응답 정보 추가
            self._add_response_attributes(span, request, response, start_time)
            
            # 스팬 종료
            span.end()
            
            # 트레이스 ID를 응답 헤더에 추가 (디버깅용)
            if settings.DEBUG:
                trace_id = get_current_trace_id()
                if trace_id:
                    response['X-Trace-ID'] = trace_id
        
        except Exception as e:
            logger.error(f"분산 추적 응답 처리 오류: {e}")
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """예외 처리"""
        if not self.tracing_enabled or not hasattr(request, '_tracing_span'):
            return None
        
        try:
            span = request._tracing_span
            
            # 예외 정보 기록
            span.record_exception(exception)
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(exception).__name__)
            span.set_attribute("error.message", str(exception))
            
            # HTTP 상태 코드 추정
            if hasattr(exception, 'status_code'):
                span.set_attribute("http.status_code", exception.status_code)
            else:
                span.set_attribute("http.status_code", 500)
        
        except Exception as e:
            logger.error(f"분산 추적 예외 처리 오류: {e}")
        
        return None
    
    def _should_exclude_path(self, path: str) -> bool:
        """경로 제외 여부 확인"""
        # 정확한 매칭
        if path in self.excluded_paths:
            return True
        
        # 접두사 매칭
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True
        
        return False
    
    def _generate_span_name(self, request: HttpRequest) -> str:
        """스팬 이름 생성"""
        method = request.method.upper()
        path = request.path
        
        # API 엔드포인트 정규화
        if path.startswith('/api/'):
            # 동적 ID 부분을 일반화
            normalized_path = self._normalize_api_path(path)
            return f"HTTP {method} {normalized_path}"
        
        # 일반 경로
        return f"HTTP {method} {path}"
    
    def _normalize_api_path(self, path: str) -> str:
        """API 경로 정규화 (ID 값들을 일반화)"""
        # 숫자 ID를 {id}로 치환
        import re
        
        # /api/study/subjects/123/ -> /api/study/subjects/{id}/
        path = re.sub(r'/\d+/', '/{id}/', path)
        
        # 끝에 있는 숫자 ID도 처리
        path = re.sub(r'/\d+$', '/{id}', path)
        
        return path
    
    def _add_request_attributes(self, span, request: HttpRequest):
        """요청 속성 추가"""
        # HTTP 기본 정보
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.build_absolute_uri())
        span.set_attribute("http.scheme", request.scheme)
        span.set_attribute("http.host", request.get_host())
        span.set_attribute("http.target", request.get_full_path())
        
        # User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if user_agent:
            span.set_attribute("http.user_agent", user_agent[:200])  # 길이 제한
        
        # 사용자 정보
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            span.set_attribute("user.id", request.user.id)
            span.set_attribute("user.email", request.user.email)
        
        # 요청 크기
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            span.set_attribute("http.request_content_length", int(content_length))
        
        # 중요한 엔드포인트 표시
        if request.path in self.important_endpoints:
            span.set_attribute("studymate.important_endpoint", True)
        
        # IP 주소 (프록시 고려)
        ip_address = self._get_client_ip(request)
        if ip_address:
            span.set_attribute("http.client_ip", ip_address)
    
    def _add_response_attributes(self, span, request: HttpRequest, response: HttpResponse, start_time: float):
        """응답 속성 추가"""
        # HTTP 상태 코드
        span.set_attribute("http.status_code", response.status_code)
        
        # 응답 크기
        if hasattr(response, 'content'):
            span.set_attribute("http.response_content_length", len(response.content))
        
        # 요청 처리 시간
        duration = time.time() - start_time
        span.set_attribute("http.duration", duration * 1000)  # 밀리초
        
        # 성능 분류
        if duration > 2.0:  # 2초 이상
            span.set_attribute("performance.slow", True)
        elif duration > 5.0:  # 5초 이상
            span.set_attribute("performance.very_slow", True)
        
        # 오류 상태 확인
        if response.status_code >= 400:
            span.set_attribute("error", True)
            
            if response.status_code >= 500:
                span.set_attribute("error.server", True)
            else:
                span.set_attribute("error.client", True)
        
        # Content-Type
        content_type = response.get('Content-Type', '')
        if content_type:
            span.set_attribute("http.response_content_type", content_type)
    
    def _get_client_ip(self, request: HttpRequest) -> Optional[str]:
        """클라이언트 IP 주소 추출"""
        # 프록시를 거친 경우 실제 IP 추출
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        return request.META.get('REMOTE_ADDR')


class UserContextMiddleware(MiddlewareMixin):
    """사용자 컨텍스트 추가 미들웨어"""
    
    def process_request(self, request: HttpRequest) -> None:
        """사용자 컨텍스트를 현재 스팬에 추가"""
        if not hasattr(request, '_tracing_span'):
            return
        
        span = request._tracing_span
        
        # 사용자 정보가 있으면 추가
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            studymate_tracer.add_user_context(span, request.user.id)
            
            # 사용자 관련 추가 정보
            if hasattr(request.user, 'subscription'):
                span.set_attribute("user.subscription_active", 
                                 request.user.subscription.is_active if request.user.subscription else False)
        
        return None


class BusinessContextMiddleware(MiddlewareMixin):
    """비즈니스 컨텍스트 추가 미들웨어"""
    
    def process_request(self, request: HttpRequest) -> None:
        """비즈니스 컨텍스트를 현재 스팬에 추가"""
        if not hasattr(request, '_tracing_span'):
            return
        
        span = request._tracing_span
        
        # URL 파라미터에서 비즈니스 엔티티 추출
        path_parts = request.path.split('/')
        
        # 과목 ID 추출
        if 'subjects' in path_parts:
            try:
                subject_index = path_parts.index('subjects')
                if subject_index + 1 < len(path_parts) and path_parts[subject_index + 1].isdigit():
                    subject_id = int(path_parts[subject_index + 1])
                    studymate_tracer.add_business_context(span, subject_id=subject_id)
            except (ValueError, IndexError):
                pass
        
        # 퀴즈 ID 추출
        if 'quizzes' in path_parts:
            try:
                quiz_index = path_parts.index('quizzes')
                if quiz_index + 1 < len(path_parts) and path_parts[quiz_index + 1].isdigit():
                    quiz_id = int(path_parts[quiz_index + 1])
                    studymate_tracer.add_business_context(span, quiz_id=quiz_id)
            except (ValueError, IndexError):
                pass
        
        # 요청 바디에서 추가 정보 추출 (POST/PUT 요청)
        if request.method in ['POST', 'PUT'] and request.content_type == 'application/json':
            try:
                import json
                data = json.loads(request.body)
                
                if 'subject_id' in data:
                    studymate_tracer.add_business_context(span, subject_id=data['subject_id'])
                
                if 'quiz_id' in data:
                    studymate_tracer.add_business_context(span, quiz_id=data['quiz_id'])
                
                # 작업 유형 추가
                if request.path.endswith('/generate-summary/'):
                    studymate_tracer.add_business_context(span, operation_type="ai_summary_generation")
                elif request.path.endswith('/attempt/'):
                    studymate_tracer.add_business_context(span, operation_type="quiz_attempt")
                
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        
        return None