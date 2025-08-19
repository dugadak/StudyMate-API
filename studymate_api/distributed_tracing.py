"""
분산 추적 시스템 (OpenTelemetry)

마이크로서비스 환경에서 요청의 전체 생명주기를 추적하고 모니터링합니다.
"""

import os
import logging
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from contextlib import contextmanager
from datetime import datetime, timedelta

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.status import Status, StatusCode

from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.utils import timezone

logger = logging.getLogger(__name__)


class StudyMateTracer:
    """StudyMate 전용 분산 추적 관리자"""
    
    def __init__(self):
        self.tracer = None
        self.is_initialized = False
        self.service_name = "studymate-api"
        self.service_version = getattr(settings, 'VERSION', '1.0.0')
        
        # 추적 메트릭
        self.trace_metrics = {
            'total_spans': 0,
            'error_spans': 0,
            'slow_spans': 0,
            'last_reset': timezone.now()
        }
    
    def initialize(self):
        """OpenTelemetry 초기화"""
        if self.is_initialized:
            return
        
        try:
            # 리소스 정의
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": self.service_version,
                "service.namespace": "studymate",
                "deployment.environment": settings.DEBUG and "development" or "production"
            })
            
            # TracerProvider 설정
            trace.set_tracer_provider(TracerProvider(resource=resource))
            
            # Exporter 설정
            self._setup_exporters()
            
            # 자동 계측 설정
            self._setup_auto_instrumentation()
            
            # Tracer 인스턴스 생성
            self.tracer = trace.get_tracer(__name__, self.service_version)
            
            self.is_initialized = True
            logger.info("OpenTelemetry 분산 추적 시스템 초기화 완료")
            
        except Exception as e:
            logger.error(f"OpenTelemetry 초기화 실패: {e}")
            raise
    
    def _setup_exporters(self):
        """Exporter 설정"""
        tracer_provider = trace.get_tracer_provider()
        
        # Console Exporter (개발용)
        if settings.DEBUG:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(
                BatchSpanProcessor(console_exporter)
            )
        
        # Jaeger Exporter
        jaeger_endpoint = getattr(settings, 'JAEGER_ENDPOINT', None)
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(':')[0],
                agent_port=int(jaeger_endpoint.split(':')[1]) if ':' in jaeger_endpoint else 14268,
                collector_endpoint=f"http://{jaeger_endpoint}/api/traces"
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(jaeger_exporter)
            )
        
        # OTLP Exporter (Observability 플랫폼용)
        otlp_endpoint = getattr(settings, 'OTEL_EXPORTER_OTLP_ENDPOINT', None)
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers=getattr(settings, 'OTEL_EXPORTER_OTLP_HEADERS', {})
            )
            tracer_provider.add_span_processor(
                BatchSpanProcessor(otlp_exporter)
            )
    
    def _setup_auto_instrumentation(self):
        """자동 계측 설정"""
        try:
            # Django 자동 계측
            DjangoInstrumentor().instrument()
            
            # Database 자동 계측
            Psycopg2Instrumentor().instrument()
            
            # Redis 자동 계측
            RedisInstrumentor().instrument()
            
            # HTTP 요청 자동 계측
            RequestsInstrumentor().instrument()
            
            # 로깅 자동 계측
            LoggingInstrumentor().instrument(set_logging_format=True)
            
            logger.info("자동 계측 설정 완료")
            
        except Exception as e:
            logger.warning(f"자동 계측 설정 중 오류: {e}")
    
    def create_span(self, name: str, kind: trace.SpanKind = trace.SpanKind.INTERNAL,
                   attributes: Optional[Dict[str, Any]] = None) -> trace.Span:
        """새로운 스팬 생성"""
        if not self.is_initialized:
            self.initialize()
        
        span = self.tracer.start_span(name, kind=kind, attributes=attributes or {})
        self.trace_metrics['total_spans'] += 1
        
        return span
    
    def trace_function(self, operation_name: Optional[str] = None,
                      span_kind: trace.SpanKind = trace.SpanKind.INTERNAL,
                      record_exception: bool = True):
        """함수 추적 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                span_name = operation_name or f"{func.__module__}.{func.__name__}"
                
                with self.create_span(span_name, span_kind) as span:
                    try:
                        # 함수 메타데이터 추가
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("function.module", func.__module__)
                        
                        # 실행 시작 시간 기록
                        start_time = timezone.now()
                        
                        # 함수 실행
                        result = func(*args, **kwargs)
                        
                        # 실행 시간 계산
                        execution_time = (timezone.now() - start_time).total_seconds()
                        span.set_attribute("function.execution_time", execution_time)
                        
                        # 느린 함수 감지
                        if execution_time > 1.0:  # 1초 이상
                            span.set_attribute("performance.slow", True)
                            self.trace_metrics['slow_spans'] += 1
                            logger.warning(f"느린 함수 감지: {span_name} ({execution_time:.2f}s)")
                        
                        return result
                        
                    except Exception as e:
                        if record_exception:
                            span.record_exception(e)
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            self.trace_metrics['error_spans'] += 1
                        raise
            
            return wrapper
        return decorator
    
    def trace_database_query(self, query_type: str, table_name: str = None):
        """데이터베이스 쿼리 추적"""
        @contextmanager
        def db_span():
            span_name = f"db.{query_type}"
            if table_name:
                span_name += f".{table_name}"
            
            with self.create_span(span_name, trace.SpanKind.CLIENT) as span:
                span.set_attribute("db.operation", query_type)
                span.set_attribute("db.system", "postgresql")
                
                if table_name:
                    span.set_attribute("db.table", table_name)
                
                try:
                    yield span
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return db_span()
    
    def trace_ai_request(self, provider: str, model: str, operation: str):
        """AI 요청 추적"""
        @contextmanager
        def ai_span():
            span_name = f"ai.{provider}.{operation}"
            
            with self.create_span(span_name, trace.SpanKind.CLIENT) as span:
                span.set_attribute("ai.provider", provider)
                span.set_attribute("ai.model", model)
                span.set_attribute("ai.operation", operation)
                
                start_time = timezone.now()
                
                try:
                    yield span
                    
                    # 응답 시간 기록
                    response_time = (timezone.now() - start_time).total_seconds()
                    span.set_attribute("ai.response_time", response_time)
                    
                    # AI 요청이 느린 경우 (5초 이상)
                    if response_time > 5.0:
                        span.set_attribute("performance.slow_ai", True)
                        logger.warning(f"느린 AI 요청: {provider}/{model} ({response_time:.2f}s)")
                
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return ai_span()
    
    def trace_cache_operation(self, operation: str, key: str):
        """캐시 작업 추적"""
        @contextmanager  
        def cache_span():
            span_name = f"cache.{operation}"
            
            with self.create_span(span_name, trace.SpanKind.CLIENT) as span:
                span.set_attribute("cache.operation", operation)
                span.set_attribute("cache.key", key)
                span.set_attribute("cache.system", "redis")
                
                try:
                    yield span
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        return cache_span()
    
    def add_user_context(self, span: trace.Span, user_id: int, session_id: str = None):
        """사용자 컨텍스트 추가"""
        span.set_attribute("user.id", user_id)
        if session_id:
            span.set_attribute("session.id", session_id)
    
    def add_business_context(self, span: trace.Span, subject_id: int = None, 
                           quiz_id: int = None, operation_type: str = None):
        """비즈니스 컨텍스트 추가"""
        if subject_id:
            span.set_attribute("business.subject_id", subject_id)
        if quiz_id:
            span.set_attribute("business.quiz_id", quiz_id)
        if operation_type:
            span.set_attribute("business.operation", operation_type)
    
    def get_trace_metrics(self) -> Dict[str, Any]:
        """추적 메트릭 조회"""
        current_time = timezone.now()
        time_since_reset = (current_time - self.trace_metrics['last_reset']).total_seconds()
        
        return {
            'total_spans': self.trace_metrics['total_spans'],
            'error_spans': self.trace_metrics['error_spans'],
            'slow_spans': self.trace_metrics['slow_spans'],
            'error_rate': (self.trace_metrics['error_spans'] / max(1, self.trace_metrics['total_spans'])) * 100,
            'slow_rate': (self.trace_metrics['slow_spans'] / max(1, self.trace_metrics['total_spans'])) * 100,
            'spans_per_second': self.trace_metrics['total_spans'] / max(1, time_since_reset),
            'last_reset': self.trace_metrics['last_reset'],
            'is_initialized': self.is_initialized
        }
    
    def reset_metrics(self):
        """메트릭 초기화"""
        self.trace_metrics = {
            'total_spans': 0,
            'error_spans': 0,
            'slow_spans': 0,
            'last_reset': timezone.now()
        }


class StudyMateSpanProcessor:
    """StudyMate 전용 스팬 처리기"""
    
    def __init__(self):
        self.business_events = []
        self.performance_alerts = []
    
    def on_start(self, span: trace.Span, parent_context):
        """스팬 시작 시 처리"""
        pass
    
    def on_end(self, span: trace.Span):
        """스팬 종료 시 처리"""
        try:
            # 비즈니스 이벤트 감지
            self._detect_business_events(span)
            
            # 성능 이슈 감지
            self._detect_performance_issues(span)
            
            # 메트릭 수집
            self._collect_span_metrics(span)
            
        except Exception as e:
            logger.error(f"스팬 처리 중 오류: {e}")
    
    def _detect_business_events(self, span: trace.Span):
        """비즈니스 이벤트 감지"""
        span_name = span.name
        attributes = span.attributes or {}
        
        # 학습 완료 이벤트
        if 'study.complete' in span_name:
            self.business_events.append({
                'type': 'study_completed',
                'user_id': attributes.get('user.id'),
                'subject_id': attributes.get('business.subject_id'),
                'timestamp': span.end_time
            })
        
        # 퀴즈 완료 이벤트
        elif 'quiz.submit' in span_name:
            self.business_events.append({
                'type': 'quiz_completed',
                'user_id': attributes.get('user.id'),
                'quiz_id': attributes.get('business.quiz_id'),
                'timestamp': span.end_time
            })
    
    def _detect_performance_issues(self, span: trace.Span):
        """성능 이슈 감지"""
        duration = span.end_time - span.start_time if span.end_time else None
        if not duration:
            return
        
        duration_ms = duration / 1000000  # 나노초를 밀리초로 변환
        
        # 느린 요청 감지
        if duration_ms > 2000:  # 2초 이상
            self.performance_alerts.append({
                'type': 'slow_request',
                'span_name': span.name,
                'duration_ms': duration_ms,
                'attributes': dict(span.attributes or {}),
                'timestamp': span.end_time
            })
        
        # 데이터베이스 쿼리 이슈
        if span.name.startswith('db.') and duration_ms > 1000:  # 1초 이상
            self.performance_alerts.append({
                'type': 'slow_database_query',
                'span_name': span.name,
                'duration_ms': duration_ms,
                'table': span.attributes.get('db.table') if span.attributes else None,
                'timestamp': span.end_time
            })
    
    def _collect_span_metrics(self, span: trace.Span):
        """스팬 메트릭 수집"""
        cache_key = f"span_metrics:{span.name}"
        current_metrics = cache.get(cache_key, {'count': 0, 'total_duration': 0})
        
        duration = span.end_time - span.start_time if span.end_time else 0
        duration_ms = duration / 1000000
        
        current_metrics['count'] += 1
        current_metrics['total_duration'] += duration_ms
        current_metrics['avg_duration'] = current_metrics['total_duration'] / current_metrics['count']
        
        cache.set(cache_key, current_metrics, timeout=3600)


# 전역 tracer 인스턴스
studymate_tracer = StudyMateTracer()

# 편의 함수들
def trace_function(operation_name: Optional[str] = None, 
                  span_kind: trace.SpanKind = trace.SpanKind.INTERNAL):
    """함수 추적 데코레이터"""
    return studymate_tracer.trace_function(operation_name, span_kind)


def trace_database_query(query_type: str, table_name: str = None):
    """데이터베이스 쿼리 추적"""
    return studymate_tracer.trace_database_query(query_type, table_name)


def trace_ai_request(provider: str, model: str, operation: str):
    """AI 요청 추적"""
    return studymate_tracer.trace_ai_request(provider, model, operation)


def trace_cache_operation(operation: str, key: str):
    """캐시 작업 추적"""
    return studymate_tracer.trace_cache_operation(operation, key)


def get_current_trace_id() -> Optional[str]:
    """현재 트레이스 ID 조회"""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """현재 스팬 ID 조회"""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, '016x')
    return None


def initialize_tracing():
    """분산 추적 시스템 초기화"""
    studymate_tracer.initialize()