"""
StudyMate API 모니터링 미들웨어

실시간 메트릭 수집 및 성능 모니터링을 위한 미들웨어입니다.
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Any, Optional
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self):
        self.request_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.status_codes = defaultdict(int)
        self.recent_requests = deque(maxlen=1000)  # 최근 1000개 요청
        self.lock = threading.Lock()
        
        # 시간대별 통계
        self.hourly_stats = defaultdict(lambda: {
            'requests': 0,
            'errors': 0,
            'avg_response_time': 0,
            'total_response_time': 0
        })
    
    def record_request(self, request_data: Dict[str, Any]):
        """요청 데이터 기록"""
        with self.lock:
            path = request_data.get('path', 'unknown')
            method = request_data.get('method', 'unknown')
            status_code = request_data.get('status_code', 0)
            response_time = request_data.get('response_time_ms', 0)
            timestamp = request_data.get('timestamp', timezone.now())
            
            # 경로별 카운트
            key = f"{method}:{path}"
            self.request_counts[key] += 1
            
            # 응답 시간 기록 (최근 100개만 유지)
            if len(self.response_times[key]) >= 100:
                self.response_times[key].pop(0)
            self.response_times[key].append(response_time)
            
            # 에러 카운트
            if status_code >= 400:
                self.error_counts[key] += 1
            
            # 상태 코드 통계
            status_group = f"{status_code // 100}xx"
            self.status_codes[status_group] += 1
            
            # 최근 요청 기록
            self.recent_requests.append(request_data)
            
            # 시간대별 통계
            hour_key = timestamp.strftime('%Y-%m-%d:%H')
            self.hourly_stats[hour_key]['requests'] += 1
            self.hourly_stats[hour_key]['total_response_time'] += response_time
            
            if status_code >= 400:
                self.hourly_stats[hour_key]['errors'] += 1
            
            # 평균 응답 시간 계산
            if self.hourly_stats[hour_key]['requests'] > 0:
                self.hourly_stats[hour_key]['avg_response_time'] = (
                    self.hourly_stats[hour_key]['total_response_time'] / 
                    self.hourly_stats[hour_key]['requests']
                )
    
    def get_metrics(self) -> Dict[str, Any]:
        """수집된 메트릭 반환"""
        with self.lock:
            # 최근 1시간 통계
            now = timezone.now()
            hour_ago = now - timedelta(hours=1)
            recent_requests = [
                req for req in self.recent_requests 
                if req.get('timestamp', now) >= hour_ago
            ]
            
            # 평균 응답 시간 계산
            avg_response_times = {}
            for key, times in self.response_times.items():
                if times:
                    avg_response_times[key] = sum(times) / len(times)
            
            return {
                'timestamp': timezone.now().isoformat(),
                'request_counts': dict(self.request_counts),
                'error_counts': dict(self.error_counts),
                'status_codes': dict(self.status_codes),
                'avg_response_times': avg_response_times,
                'recent_hour': {
                    'total_requests': len(recent_requests),
                    'unique_ips': len(set(req.get('ip_address') for req in recent_requests if req.get('ip_address'))),
                    'error_rate': len([req for req in recent_requests if req.get('status_code', 0) >= 400]) / max(len(recent_requests), 1) * 100
                },
                'hourly_stats': dict(self.hourly_stats)
            }
    
    def reset_metrics(self):
        """메트릭 초기화"""
        with self.lock:
            self.request_counts.clear()
            self.response_times.clear()
            self.error_counts.clear()
            self.status_codes.clear()
            self.recent_requests.clear()
            self.hourly_stats.clear()


# 전역 메트릭 수집기
metrics_collector = MetricsCollector()


class RealTimeMonitoringMiddleware(MiddlewareMixin):
    """실시간 모니터링 미들웨어"""
    
    def process_request(self, request):
        """요청 처리 시작"""
        request._monitoring_start_time = time.time()
        request._monitoring_data = {
            'method': request.method,
            'path': request.path,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
            'timestamp': timezone.now()
        }
    
    def process_response(self, request, response):
        """요청 처리 완료"""
        if hasattr(request, '_monitoring_start_time'):
            response_time_ms = (time.time() - request._monitoring_start_time) * 1000
            
            # 모니터링 데이터 완성
            monitoring_data = getattr(request, '_monitoring_data', {})
            monitoring_data.update({
                'status_code': response.status_code,
                'response_time_ms': response_time_ms,
                'content_length': len(response.content) if hasattr(response, 'content') else 0
            })
            
            # 메트릭 수집기에 기록
            metrics_collector.record_request(monitoring_data)
            
            # 캐시에 실시간 데이터 저장 (최근 통계용)
            self._cache_real_time_data(monitoring_data)
            
            # 성능 경고
            if response_time_ms > 5000:  # 5초 이상
                logger.warning(
                    f"Very slow request: {request.method} {request.path} took {response_time_ms:.2f}ms",
                    extra=monitoring_data
                )
            
            # 에러 로깅
            if response.status_code >= 500:
                logger.error(
                    f"Server error: {request.method} {request.path} returned {response.status_code}",
                    extra=monitoring_data
                )
        
        return response
    
    def _get_client_ip(self, request) -> Optional[str]:
        """클라이언트 IP 주소 반환"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def _cache_real_time_data(self, data: Dict[str, Any]):
        """실시간 데이터를 캐시에 저장"""
        try:
            # 최근 요청 통계를 캐시에 저장
            cache_key = f"rt_metrics_{timezone.now().strftime('%Y%m%d%H%M')}"
            cached_data = cache.get(cache_key, [])
            cached_data.append(data)
            
            # 최근 100개 요청만 유지
            if len(cached_data) > 100:
                cached_data = cached_data[-100:]
            
            cache.set(cache_key, cached_data, 300)  # 5분간 보관
            
        except Exception as e:
            logger.error(f"Failed to cache real-time data: {e}")


class AlertingMiddleware(MiddlewareMixin):
    """알림 미들웨어"""
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.error_threshold = getattr(settings, 'ERROR_RATE_THRESHOLD', 10)  # 10%
        self.response_time_threshold = getattr(settings, 'RESPONSE_TIME_THRESHOLD', 2000)  # 2초
        self.check_interval = 60  # 1분마다 체크
        self.last_check = time.time()
    
    def process_response(self, request, response):
        """응답 처리 및 알림 체크"""
        now = time.time()
        
        # 주기적으로 알림 조건 체크
        if now - self.last_check > self.check_interval:
            self._check_alert_conditions()
            self.last_check = now
        
        return response
    
    def _check_alert_conditions(self):
        """알림 조건 확인"""
        try:
            metrics = metrics_collector.get_metrics()
            
            # 에러율 체크
            recent_hour = metrics.get('recent_hour', {})
            error_rate = recent_hour.get('error_rate', 0)
            
            if error_rate > self.error_threshold:
                self._send_alert(
                    'high_error_rate',
                    f"에러율이 {error_rate:.1f}%로 임계값 {self.error_threshold}%를 초과했습니다.",
                    {'error_rate': error_rate, 'threshold': self.error_threshold}
                )
            
            # 평균 응답 시간 체크
            avg_response_times = metrics.get('avg_response_times', {})
            for endpoint, avg_time in avg_response_times.items():
                if avg_time > self.response_time_threshold:
                    self._send_alert(
                        'slow_response',
                        f"엔드포인트 {endpoint}의 평균 응답시간이 {avg_time:.1f}ms로 임계값을 초과했습니다.",
                        {'endpoint': endpoint, 'avg_time': avg_time, 'threshold': self.response_time_threshold}
                    )
        
        except Exception as e:
            logger.error(f"Alert condition check failed: {e}")
    
    def _send_alert(self, alert_type: str, message: str, data: Dict[str, Any]):
        """알림 발송"""
        # 알림 중복 방지
        cache_key = f"alert_{alert_type}_{hash(message)}"
        if cache.get(cache_key):
            return
        
        cache.set(cache_key, True, 3600)  # 1시간 동안 중복 방지
        
        # 로그 기록
        logger.warning(f"ALERT [{alert_type}]: {message}", extra=data)
        
        # 외부 알림 서비스 연동 (예: Slack, 이메일 등)
        # self._send_external_alert(alert_type, message, data)
    
    def _send_external_alert(self, alert_type: str, message: str, data: Dict[str, Any]):
        """외부 알림 서비스로 알림 발송"""
        # 구현 예시: Slack webhook
        try:
            import requests
            webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
            if webhook_url:
                payload = {
                    'text': f"🚨 StudyMate API Alert",
                    'attachments': [{
                        'color': 'danger' if alert_type in ['high_error_rate', 'slow_response'] else 'warning',
                        'fields': [
                            {'title': 'Alert Type', 'value': alert_type, 'short': True},
                            {'title': 'Message', 'value': message, 'short': False},
                            {'title': 'Data', 'value': str(data), 'short': False}
                        ]
                    }]
                }
                requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send external alert: {e}")


# Export
__all__ = [
    'MetricsCollector',
    'RealTimeMonitoringMiddleware',
    'AlertingMiddleware',
    'metrics_collector',
]