"""
고급 메트릭 수집 및 분석 시스템

비즈니스 메트릭, 사용자 참여도, 시스템 성능 등을 종합적으로 수집하고 분석합니다.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from django.core.cache import cache
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

logger = logging.getLogger(__name__)
User = get_user_model()


class MetricType(Enum):
    """메트릭 타입 분류"""
    BUSINESS = "business"  # 비즈니스 메트릭
    USER_ENGAGEMENT = "user_engagement"  # 사용자 참여도
    SYSTEM_PERFORMANCE = "system_performance"  # 시스템 성능
    AI_USAGE = "ai_usage"  # AI 모델 사용량
    LEARNING_ANALYTICS = "learning_analytics"  # 학습 분석


class EventType(Enum):
    """이벤트 타입 정의"""
    # 사용자 관련
    USER_REGISTER = "user_register"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # 학습 관련
    STUDY_SESSION_START = "study_session_start"
    STUDY_SESSION_END = "study_session_end"
    SUMMARY_GENERATED = "summary_generated"
    QUIZ_ATTEMPTED = "quiz_attempted"
    QUIZ_COMPLETED = "quiz_completed"
    
    # AI 관련
    AI_REQUEST = "ai_request"
    AI_RESPONSE = "ai_response"
    AI_ERROR = "ai_error"
    
    # 구독 관련
    SUBSCRIPTION_STARTED = "subscription_started"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    
    # 시스템 관련
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"


@dataclass
class MetricEvent:
    """메트릭 이벤트 데이터 클래스"""
    event_type: EventType
    metric_type: MetricType
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    value: Union[int, float, str] = 1
    metadata: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()
        if self.metadata is None:
            self.metadata = {}


class MetricsCollector:
    """중앙화된 메트릭 수집기"""
    
    def __init__(self):
        self.cache_prefix = "metrics:"
        self.batch_size = 100
        self.flush_interval = 60  # 초
        
    def track_event(self, event: MetricEvent):
        """이벤트 추적"""
        try:
            # 실시간 카운터 업데이트
            self._update_realtime_counters(event)
            
            # 배치 처리를 위한 이벤트 저장
            self._store_event_for_batch(event)
            
            # 특별한 이벤트에 대한 즉시 처리
            self._handle_special_events(event)
            
            logger.debug(f"메트릭 이벤트 추적: {event.event_type.value}")
            
        except Exception as e:
            logger.error(f"메트릭 이벤트 추적 실패: {e}")
    
    def _update_realtime_counters(self, event: MetricEvent):
        """실시간 카운터 업데이트"""
        current_time = timezone.now()
        
        # 시간대별 카운터 (시간, 일, 주, 월)
        time_buckets = [
            current_time.strftime('%Y-%m-%d-%H'),  # 시간별
            current_time.strftime('%Y-%m-%d'),     # 일별
            f"{current_time.year}-W{current_time.isocalendar()[1]}",  # 주별
            current_time.strftime('%Y-%m'),        # 월별
        ]
        
        for bucket in time_buckets:
            cache_key = f"{self.cache_prefix}counter:{event.event_type.value}:{bucket}"
            cache.set(cache_key, (cache.get(cache_key, 0) + 1), timeout=86400 * 7)  # 7일 유지
    
    def _store_event_for_batch(self, event: MetricEvent):
        """배치 처리를 위한 이벤트 저장"""
        cache_key = f"{self.cache_prefix}batch_events"
        events = cache.get(cache_key, [])
        
        events.append(asdict(event))
        
        # 배치 크기 초과 시 플러시
        if len(events) >= self.batch_size:
            self._flush_batch_events(events)
            cache.delete(cache_key)
        else:
            cache.set(cache_key, events, timeout=self.flush_interval * 2)
    
    def _flush_batch_events(self, events: List[Dict]):
        """배치 이벤트 플러시"""
        try:
            # 데이터베이스에 저장하거나 외부 분석 시스템으로 전송
            # 여기서는 로그로 기록
            logger.info(f"배치 이벤트 플러시: {len(events)}개 이벤트")
            
            # 실제 구현에서는 데이터베이스나 분석 시스템에 저장
            # self._save_to_database(events)
            # self._send_to_analytics(events)
            
        except Exception as e:
            logger.error(f"배치 이벤트 플러시 실패: {e}")
    
    def _handle_special_events(self, event: MetricEvent):
        """특별한 이벤트 즉시 처리"""
        if event.event_type == EventType.PAYMENT_SUCCESS:
            self._track_revenue_event(event)
        elif event.event_type == EventType.AI_ERROR:
            self._track_error_rate(event)
        elif event.event_type in [EventType.USER_LOGIN, EventType.STUDY_SESSION_START]:
            self._track_user_activity(event)
    
    def _track_revenue_event(self, event: MetricEvent):
        """수익 이벤트 추적"""
        amount = event.metadata.get('amount', 0)
        current_date = timezone.now().strftime('%Y-%m-%d')
        
        cache_key = f"{self.cache_prefix}revenue:{current_date}"
        current_revenue = cache.get(cache_key, 0)
        cache.set(cache_key, current_revenue + amount, timeout=86400 * 30)
    
    def _track_error_rate(self, event: MetricEvent):
        """에러율 추적"""
        current_hour = timezone.now().strftime('%Y-%m-%d-%H')
        error_key = f"{self.cache_prefix}errors:{current_hour}"
        
        cache.set(error_key, cache.get(error_key, 0) + 1, timeout=86400)
    
    def _track_user_activity(self, event: MetricEvent):
        """사용자 활동 추적"""
        if event.user_id:
            # 활성 사용자 추적
            today = timezone.now().strftime('%Y-%m-%d')
            active_users_key = f"{self.cache_prefix}active_users:{today}"
            
            active_users = cache.get(active_users_key, set())
            active_users.add(event.user_id)
            cache.set(active_users_key, active_users, timeout=86400)


class BusinessMetricsAnalyzer:
    """비즈니스 메트릭 분석기"""
    
    def __init__(self):
        self.cache_prefix = "metrics:business:"
    
    def get_user_acquisition_metrics(self, days: int = 30) -> Dict[str, Any]:
        """사용자 획득 메트릭"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        metrics = {
            'total_registrations': 0,
            'daily_registrations': [],
            'conversion_rate': 0,
            'acquisition_sources': {},
        }
        
        try:
            # 일별 등록자 수 계산
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                cache_key = f"metrics:counter:user_register:{date_str}"
                daily_count = cache.get(cache_key, 0)
                
                metrics['daily_registrations'].append({
                    'date': date_str,
                    'count': daily_count
                })
                metrics['total_registrations'] += daily_count
                
                current_date += timedelta(days=1)
            
            # 평균 일일 등록자 수
            metrics['average_daily_registrations'] = metrics['total_registrations'] / days
            
        except Exception as e:
            logger.error(f"사용자 획득 메트릭 계산 실패: {e}")
        
        return metrics
    
    def get_engagement_metrics(self, days: int = 30) -> Dict[str, Any]:
        """사용자 참여도 메트릭"""
        metrics = {
            'daily_active_users': [],
            'session_duration': {'average': 0, 'median': 0},
            'feature_usage': {},
            'retention_rates': {},
        }
        
        try:
            # 일별 활성 사용자
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                cache_key = f"metrics:active_users:{date_str}"
                active_users = cache.get(cache_key, set())
                
                metrics['daily_active_users'].append({
                    'date': date_str,
                    'count': len(active_users) if active_users else 0
                })
                
                current_date += timedelta(days=1)
            
            # 기능 사용률
            feature_events = [
                EventType.SUMMARY_GENERATED,
                EventType.QUIZ_ATTEMPTED,
                EventType.AI_REQUEST,
            ]
            
            for event_type in feature_events:
                cache_key = f"metrics:counter:{event_type.value}:{timezone.now().strftime('%Y-%m-%d')}"
                usage_count = cache.get(cache_key, 0)
                metrics['feature_usage'][event_type.value] = usage_count
                
        except Exception as e:
            logger.error(f"참여도 메트릭 계산 실패: {e}")
        
        return metrics
    
    def get_revenue_metrics(self, days: int = 30) -> Dict[str, Any]:
        """수익 메트릭"""
        metrics = {
            'total_revenue': 0,
            'daily_revenue': [],
            'average_revenue_per_user': 0,
            'subscription_metrics': {
                'new_subscriptions': 0,
                'cancelled_subscriptions': 0,
                'churn_rate': 0
            }
        }
        
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                cache_key = f"metrics:revenue:{date_str}"
                daily_revenue = cache.get(cache_key, 0)
                
                metrics['daily_revenue'].append({
                    'date': date_str,
                    'amount': daily_revenue
                })
                metrics['total_revenue'] += daily_revenue
                
                current_date += timedelta(days=1)
            
            # 구독 관련 메트릭
            new_subs_key = f"metrics:counter:subscription_started:{timezone.now().strftime('%Y-%m')}"
            cancelled_subs_key = f"metrics:counter:subscription_cancelled:{timezone.now().strftime('%Y-%m')}"
            
            metrics['subscription_metrics']['new_subscriptions'] = cache.get(new_subs_key, 0)
            metrics['subscription_metrics']['cancelled_subscriptions'] = cache.get(cancelled_subs_key, 0)
            
            # 이탈률 계산
            if metrics['subscription_metrics']['new_subscriptions'] > 0:
                metrics['subscription_metrics']['churn_rate'] = (
                    metrics['subscription_metrics']['cancelled_subscriptions'] / 
                    metrics['subscription_metrics']['new_subscriptions']
                ) * 100
                
        except Exception as e:
            logger.error(f"수익 메트릭 계산 실패: {e}")
        
        return metrics


class SystemPerformanceAnalyzer:
    """시스템 성능 분석기"""
    
    def __init__(self):
        self.cache_prefix = "metrics:performance:"
    
    def get_api_performance_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """API 성능 메트릭"""
        metrics = {
            'request_count': 0,
            'error_rate': 0,
            'average_response_time': 0,
            'cache_hit_rate': 0,
            'hourly_stats': []
        }
        
        try:
            current_time = timezone.now()
            
            for i in range(hours):
                hour_time = current_time - timedelta(hours=i)
                hour_str = hour_time.strftime('%Y-%m-%d-%H')
                
                # API 요청 수
                request_key = f"metrics:counter:api_request:{hour_str}"
                requests = cache.get(request_key, 0)
                
                # 에러 수
                error_key = f"metrics:counter:api_error:{hour_str}"
                errors = cache.get(error_key, 0)
                
                # 캐시 히트/미스
                cache_hit_key = f"metrics:counter:cache_hit:{hour_str}"
                cache_miss_key = f"metrics:counter:cache_miss:{hour_str}"
                hits = cache.get(cache_hit_key, 0)
                misses = cache.get(cache_miss_key, 0)
                
                hourly_error_rate = (errors / requests * 100) if requests > 0 else 0
                hourly_cache_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0
                
                metrics['hourly_stats'].append({
                    'hour': hour_str,
                    'requests': requests,
                    'errors': errors,
                    'error_rate': hourly_error_rate,
                    'cache_hit_rate': hourly_cache_rate
                })
                
                metrics['request_count'] += requests
            
            # 전체 통계 계산
            total_errors = sum(stat['errors'] for stat in metrics['hourly_stats'])
            total_hits = sum(cache.get(f"metrics:counter:cache_hit:{stat['hour']}", 0) for stat in metrics['hourly_stats'])
            total_cache_ops = total_hits + sum(cache.get(f"metrics:counter:cache_miss:{stat['hour']}", 0) for stat in metrics['hourly_stats'])
            
            metrics['error_rate'] = (total_errors / metrics['request_count'] * 100) if metrics['request_count'] > 0 else 0
            metrics['cache_hit_rate'] = (total_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0
            
        except Exception as e:
            logger.error(f"API 성능 메트릭 계산 실패: {e}")
        
        return metrics
    
    def get_ai_usage_metrics(self, days: int = 7) -> Dict[str, Any]:
        """AI 사용량 메트릭"""
        metrics = {
            'total_ai_requests': 0,
            'requests_by_provider': {},
            'average_response_time': 0,
            'error_rate': 0,
            'cost_analysis': {}
        }
        
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                
                # AI 요청 총 수
                ai_request_key = f"metrics:counter:ai_request:{date_str}"
                daily_requests = cache.get(ai_request_key, 0)
                metrics['total_ai_requests'] += daily_requests
                
                # AI 에러 수
                ai_error_key = f"metrics:counter:ai_error:{date_str}"
                daily_errors = cache.get(ai_error_key, 0)
                
                current_date += timedelta(days=1)
            
            # AI 에러율 계산
            total_ai_errors = sum(
                cache.get(f"metrics:counter:ai_error:{(end_date - timedelta(days=i)).strftime('%Y-%m-%d')}", 0)
                for i in range(days)
            )
            
            metrics['error_rate'] = (total_ai_errors / metrics['total_ai_requests'] * 100) if metrics['total_ai_requests'] > 0 else 0
            
        except Exception as e:
            logger.error(f"AI 사용량 메트릭 계산 실패: {e}")
        
        return metrics


# 전역 메트릭 수집기 인스턴스
metrics_collector = MetricsCollector()


# 편의 함수들
def track_user_event(event_type: EventType, user_id: int, metadata: Dict = None):
    """사용자 이벤트 추적"""
    event = MetricEvent(
        event_type=event_type,
        metric_type=MetricType.USER_ENGAGEMENT,
        user_id=user_id,
        metadata=metadata or {}
    )
    metrics_collector.track_event(event)


def track_business_event(event_type: EventType, value: Union[int, float] = 1, metadata: Dict = None):
    """비즈니스 이벤트 추적"""
    event = MetricEvent(
        event_type=event_type,
        metric_type=MetricType.BUSINESS,
        value=value,
        metadata=metadata or {}
    )
    metrics_collector.track_event(event)


def track_system_event(event_type: EventType, metadata: Dict = None):
    """시스템 이벤트 추적"""
    event = MetricEvent(
        event_type=event_type,
        metric_type=MetricType.SYSTEM_PERFORMANCE,
        metadata=metadata or {}
    )
    metrics_collector.track_event(event)


def track_ai_event(event_type: EventType, provider: str, metadata: Dict = None):
    """AI 이벤트 추적"""
    metadata = metadata or {}
    metadata['provider'] = provider
    
    event = MetricEvent(
        event_type=event_type,
        metric_type=MetricType.AI_USAGE,
        metadata=metadata
    )
    metrics_collector.track_event(event)


class MetricsMiddleware:
    """메트릭 수집 미들웨어"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        # 요청 추적
        track_system_event(EventType.API_REQUEST, {
            'method': request.method,
            'path': request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip': self._get_client_ip(request)
        })
        
        response = self.get_response(request)
        
        # 응답 시간 추적
        response_time = time.time() - start_time
        
        # 에러 추적
        if response.status_code >= 400:
            track_system_event(EventType.API_ERROR, {
                'status_code': response.status_code,
                'path': request.path,
                'response_time': response_time
            })
        
        return response
    
    def _get_client_ip(self, request):
        """클라이언트 IP 주소 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Django 명령어를 위한 매니저 클래스
class MetricsManager:
    """메트릭 관리 매니저"""
    
    def __init__(self):
        self.business_analyzer = BusinessMetricsAnalyzer()
        self.performance_analyzer = SystemPerformanceAnalyzer()
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """대시보드용 종합 메트릭"""
        return {
            'user_acquisition': self.business_analyzer.get_user_acquisition_metrics(30),
            'engagement': self.business_analyzer.get_engagement_metrics(30),
            'revenue': self.business_analyzer.get_revenue_metrics(30),
            'api_performance': self.performance_analyzer.get_api_performance_metrics(24),
            'ai_usage': self.performance_analyzer.get_ai_usage_metrics(7),
            'generated_at': timezone.now().isoformat()
        }
    
    def export_metrics_report(self, format_type: str = 'json') -> str:
        """메트릭 리포트 내보내기"""
        metrics = self.get_dashboard_metrics()
        
        if format_type == 'json':
            return json.dumps(metrics, indent=2, default=str)
        else:
            return str(metrics)
    
    def clear_old_metrics(self, days: int = 30):
        """오래된 메트릭 데이터 정리"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Redis 캐시에서 오래된 메트릭 키 삭제
        # 실제 구현에서는 패턴 매칭을 통한 일괄 삭제 필요
        logger.info(f"{days}일 이전 메트릭 데이터 정리 완료")