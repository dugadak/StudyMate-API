"""
StudyMate API 헬스체크 및 모니터링 모듈

이 모듈은 다음 기능을 제공합니다:
- 애플리케이션 헬스체크
- 데이터베이스 연결 상태 확인
- Redis 캐시 상태 확인
- 외부 서비스 상태 확인
- 시스템 리소스 모니터링
- 성능 메트릭 수집
"""

import time
import psutil
import logging
from typing import Dict, Any, List, Optional, Tuple
from django.conf import settings
from django.db import connections, connection
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
import redis
import requests

logger = logging.getLogger(__name__)


class HealthChecker:
    """헬스체크 수행 클래스"""
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'redis': self._check_redis,
            'cache': self._check_cache,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
            'external_services': self._check_external_services,
        }
    
    def perform_health_check(self, include_detailed: bool = False) -> Dict[str, Any]:
        """전체 헬스체크 수행"""
        start_time = time.time()
        results = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {},
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development')
        }
        
        failed_checks = []
        
        for check_name, check_func in self.checks.items():
            try:
                check_result = check_func(include_detailed)
                results['checks'][check_name] = check_result
                
                if not check_result.get('healthy', False):
                    failed_checks.append(check_name)
            
            except Exception as e:
                logger.error(f"Health check {check_name} failed: {e}")
                results['checks'][check_name] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                failed_checks.append(check_name)
        
        # 전체 상태 결정
        if failed_checks:
            if len(failed_checks) >= len(self.checks) // 2:
                results['status'] = 'unhealthy'
            else:
                results['status'] = 'degraded'
            results['failed_checks'] = failed_checks
        
        results['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
        
        return results
    
    def _check_database(self, include_detailed: bool = False) -> Dict[str, Any]:
        """데이터베이스 연결 상태 확인"""
        result = {
            'healthy': False,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            start_time = time.time()
            
            # 메인 데이터베이스 연결 확인
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            result['healthy'] = True
            result['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
            
            if include_detailed:
                # 연결 풀 정보
                result['connections'] = {}
                for alias in connections:
                    try:
                        conn = connections[alias]
                        result['connections'][alias] = {
                            'vendor': conn.vendor,
                            'is_usable': conn.is_usable(),
                        }
                    except Exception as e:
                        result['connections'][alias] = {
                            'error': str(e),
                            'healthy': False
                        }
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Database health check failed: {e}")
        
        return result
    
    def _check_redis(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Redis 연결 상태 확인"""
        result = {
            'healthy': False,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            start_time = time.time()
            
            # Redis 연결 확인
            redis_config = getattr(settings, 'CACHES', {}).get('default', {})
            if redis_config.get('BACKEND') == 'django_redis.cache.RedisCache':
                location = redis_config.get('LOCATION', 'redis://localhost:6379/1')
                r = redis.from_url(location)
                
                # ping 테스트
                r.ping()
                
                result['healthy'] = True
                result['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
                
                if include_detailed:
                    info = r.info()
                    result['redis_info'] = {
                        'version': info.get('redis_version'),
                        'used_memory': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'total_commands_processed': info.get('total_commands_processed'),
                        'keyspace_hits': info.get('keyspace_hits'),
                        'keyspace_misses': info.get('keyspace_misses'),
                    }
            else:
                result['healthy'] = True
                result['note'] = 'Redis not configured'
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Redis health check failed: {e}")
        
        return result
    
    def _check_cache(self, include_detailed: bool = False) -> Dict[str, Any]:
        """캐시 시스템 상태 확인"""
        result = {
            'healthy': False,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            start_time = time.time()
            
            # 캐시 읽기/쓰기 테스트
            test_key = 'health_check_test'
            test_value = f'test_{int(time.time())}'
            
            cache.set(test_key, test_value, 60)
            cached_value = cache.get(test_key)
            
            if cached_value == test_value:
                result['healthy'] = True
                cache.delete(test_key)  # 정리
            else:
                result['error'] = 'Cache read/write test failed'
            
            result['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Cache health check failed: {e}")
        
        return result
    
    def _check_disk_space(self, include_detailed: bool = False) -> Dict[str, Any]:
        """디스크 공간 확인"""
        result = {
            'healthy': False,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            # 90% 이상 사용시 비정상
            result['healthy'] = free_percent > 10
            result['free_percent'] = round(free_percent, 2)
            
            if include_detailed:
                result['disk_info'] = {
                    'total_gb': round(disk_usage.total / (1024**3), 2),
                    'free_gb': round(disk_usage.free / (1024**3), 2),
                    'used_gb': round(disk_usage.used / (1024**3), 2),
                }
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Disk space health check failed: {e}")
        
        return result
    
    def _check_memory(self, include_detailed: bool = False) -> Dict[str, Any]:
        """메모리 사용량 확인"""
        result = {
            'healthy': False,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            memory = psutil.virtual_memory()
            
            # 90% 이상 사용시 비정상
            result['healthy'] = memory.percent < 90
            result['used_percent'] = memory.percent
            
            if include_detailed:
                result['memory_info'] = {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                }
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Memory health check failed: {e}")
        
        return result
    
    def _check_external_services(self, include_detailed: bool = False) -> Dict[str, Any]:
        """외부 서비스 상태 확인"""
        result = {
            'healthy': True,
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        external_services = getattr(settings, 'EXTERNAL_SERVICES', {
            'openai': 'https://api.openai.com/v1/models',
            # 'stripe': 'https://api.stripe.com/v1/account',
        })
        
        failed_services = []
        
        for service_name, service_url in external_services.items():
            try:
                start_time = time.time()
                response = requests.get(service_url, timeout=5)
                response_time = round((time.time() - start_time) * 1000, 2)
                
                service_result = {
                    'healthy': response.status_code < 400,
                    'status_code': response.status_code,
                    'response_time_ms': response_time
                }
                
                if not service_result['healthy']:
                    failed_services.append(service_name)
                
                result['services'][service_name] = service_result
            
            except Exception as e:
                result['services'][service_name] = {
                    'healthy': False,
                    'error': str(e)
                }
                failed_services.append(service_name)
        
        if failed_services:
            result['healthy'] = len(failed_services) < len(external_services)
            result['failed_services'] = failed_services
        
        return result


class SystemMonitor:
    """시스템 모니터링 클래스"""
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 프로세스 정보
            process = psutil.Process()
            
            return {
                'timestamp': timezone.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count(),
                },
                'memory': {
                    'percent': memory.percent,
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                },
                'disk': {
                    'percent': round((disk.used / disk.total) * 100, 2),
                    'total_gb': round(disk.total / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                },
                'process': {
                    'pid': process.pid,
                    'memory_percent': round(process.memory_percent(), 2),
                    'cpu_percent': round(process.cpu_percent(), 2),
                    'num_threads': process.num_threads(),
                    'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    @staticmethod
    def get_application_metrics() -> Dict[str, Any]:
        """애플리케이션 메트릭 수집"""
        try:
            # 데이터베이스 연결 풀 정보
            db_metrics = {}
            for alias in connections:
                try:
                    conn = connections[alias]
                    db_metrics[alias] = {
                        'vendor': conn.vendor,
                        'is_usable': conn.is_usable(),
                    }
                except Exception:
                    db_metrics[alias] = {'error': 'Connection failed'}
            
            # 캐시 메트릭 (Redis인 경우)
            cache_metrics = {}
            try:
                redis_config = getattr(settings, 'CACHES', {}).get('default', {})
                if redis_config.get('BACKEND') == 'django_redis.cache.RedisCache':
                    location = redis_config.get('LOCATION', 'redis://localhost:6379/1')
                    r = redis.from_url(location)
                    info = r.info()
                    
                    cache_metrics = {
                        'connected_clients': info.get('connected_clients', 0),
                        'used_memory': info.get('used_memory_human', 'N/A'),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0),
                        'total_commands_processed': info.get('total_commands_processed', 0),
                    }
            except Exception:
                cache_metrics = {'error': 'Redis metrics unavailable'}
            
            return {
                'timestamp': timezone.now().isoformat(),
                'database': db_metrics,
                'cache': cache_metrics,
                'settings': {
                    'debug': settings.DEBUG,
                    'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
                    'version': getattr(settings, 'VERSION', '1.0.0'),
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }


# API Views
class HealthCheckView(APIView):
    """헬스체크 엔드포인트"""
    
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="애플리케이션 헬스체크",
        description="""
        애플리케이션의 전반적인 상태를 확인합니다.
        
        상태 코드:
        - healthy: 모든 시스템이 정상
        - degraded: 일부 시스템에 문제 있음  
        - unhealthy: 주요 시스템에 문제 있음
        """,
        responses={
            200: {
                "description": "헬스체크 결과",
                "example": {
                    "status": "healthy",
                    "timestamp": "2024-01-01T12:00:00Z",
                    "checks": {
                        "database": {"healthy": True, "response_time_ms": 5.2},
                        "redis": {"healthy": True, "response_time_ms": 2.1},
                        "cache": {"healthy": True, "response_time_ms": 1.8}
                    },
                    "response_time_ms": 15.3
                }
            }
        }
    )
    def get(self, request):
        """헬스체크 수행"""
        include_detailed = request.query_params.get('detailed', 'false').lower() == 'true'
        
        health_checker = HealthChecker()
        result = health_checker.perform_health_check(include_detailed)
        
        # 상태에 따라 HTTP 상태 코드 결정
        http_status = status.HTTP_200_OK
        if result['status'] == 'degraded':
            http_status = status.HTTP_207_MULTI_STATUS
        elif result['status'] == 'unhealthy':
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(result, status=http_status)


class ReadinessCheckView(APIView):
    """준비 상태 체크 엔드포인트 (Kubernetes용)"""
    
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="애플리케이션 준비 상태 확인",
        description="애플리케이션이 요청을 처리할 준비가 되었는지 확인합니다.",
        responses={
            200: {"description": "준비 완료"},
            503: {"description": "준비 중"}
        }
    )
    def get(self, request):
        """준비 상태 확인"""
        try:
            # 필수 서비스만 확인 (빠른 체크)
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # 캐시 연결 확인
            cache.get('readiness_check')
            
            return Response({
                'status': 'ready',
                'timestamp': timezone.now().isoformat()
            })
        
        except Exception as e:
            return Response({
                'status': 'not_ready',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class LivenessCheckView(APIView):
    """생존 상태 체크 엔드포인트 (Kubernetes용)"""
    
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="애플리케이션 생존 상태 확인",
        description="애플리케이션이 살아있는지 확인합니다.",
        responses={
            200: {"description": "애플리케이션 정상"},
            503: {"description": "애플리케이션 비정상"}
        }
    )
    def get(self, request):
        """생존 상태 확인"""
        return Response({
            'status': 'alive',
            'timestamp': timezone.now().isoformat(),
            'uptime_seconds': time.time() - getattr(settings, 'START_TIME', time.time())
        })


class MetricsView(APIView):
    """시스템 메트릭 엔드포인트"""
    
    permission_classes = [AllowAny]  # 프로덕션에서는 제한 필요
    
    @extend_schema(
        summary="시스템 메트릭 조회",
        description="시스템 및 애플리케이션 메트릭을 조회합니다.",
        responses={
            200: {
                "description": "메트릭 정보",
                "example": {
                    "system": {
                        "cpu": {"percent": 45.2, "count": 4},
                        "memory": {"percent": 68.5, "total_gb": 16.0},
                        "disk": {"percent": 45.8, "total_gb": 500.0}
                    },
                    "application": {
                        "database": {"default": {"vendor": "postgresql"}},
                        "cache": {"connected_clients": 5}
                    }
                }
            }
        }
    )
    def get(self, request):
        """메트릭 수집 및 반환"""
        include_system = request.query_params.get('system', 'true').lower() == 'true'
        include_app = request.query_params.get('app', 'true').lower() == 'true'
        
        result = {}
        
        if include_system:
            result['system'] = SystemMonitor.get_system_metrics()
        
        if include_app:
            result['application'] = SystemMonitor.get_application_metrics()
        
        return Response(result)


# 전역 인스턴스
health_checker = HealthChecker()
system_monitor = SystemMonitor()

class RealTimeMetricsView(APIView):
    """실시간 메트릭 엔드포인트"""
    
    permission_classes = [AllowAny]  # 프로덕션에서는 제한 필요
    
    @extend_schema(
        summary="실시간 메트릭 조회",
        description="애플리케이션의 실시간 성능 메트릭을 조회합니다.",
        responses={
            200: {
                "description": "실시간 메트릭",
                "example": {
                    "request_counts": {
                        "GET:/api/study/": 1250,
                        "POST:/api/auth/login/": 45
                    },
                    "avg_response_times": {
                        "GET:/api/study/": 125.5
                    },
                    "recent_hour": {
                        "total_requests": 1543,
                        "error_rate": 2.1
                    }
                }
            }
        }
    )
    def get(self, request):
        """실시간 메트릭 반환"""
        try:
            from .monitoring_middleware import metrics_collector
            metrics = metrics_collector.get_metrics()
            return Response(metrics)
        except Exception as e:
            return Response({
                'error': f'Failed to collect real-time metrics: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertsView(APIView):
    """알림 상태 엔드포인트"""
    
    permission_classes = [AllowAny]  # 프로덕션에서는 제한 필요
    
    @extend_schema(
        summary="활성 알림 조회",
        description="현재 활성화된 알림들을 조회합니다.",
        responses={
            200: {
                "description": "활성 알림 목록",
                "example": {
                    "active_alerts": [
                        {
                            "type": "high_error_rate",
                            "message": "에러율이 15.2%로 임계값을 초과했습니다.",
                            "timestamp": "2024-01-01T12:00:00Z",
                            "severity": "warning"
                        }
                    ],
                    "alert_counts": {
                        "critical": 0,
                        "warning": 1,
                        "info": 0
                    }
                }
            }
        }
    )
    def get(self, request):
        """활성 알림 조회"""
        try:
            # 캐시에서 최근 알림 조회
            alert_keys = cache.keys('alert_*')
            active_alerts = []
            
            for key in alert_keys:
                alert_data = cache.get(key)
                if alert_data:
                    active_alerts.append(alert_data)
            
            # 심각도별 카운트
            alert_counts = {
                'critical': 0,
                'warning': 0,
                'info': 0
            }
            
            for alert in active_alerts:
                severity = alert.get('severity', 'info')
                alert_counts[severity] = alert_counts.get(severity, 0) + 1
            
            return Response({
                'active_alerts': active_alerts,
                'alert_counts': alert_counts,
                'timestamp': timezone.now().isoformat()
            })
        
        except Exception as e:
            return Response({
                'error': f'Failed to retrieve alerts: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Export
__all__ = [
    'HealthChecker',
    'SystemMonitor',
    'HealthCheckView',
    'ReadinessCheckView',
    'LivenessCheckView',
    'MetricsView',
    'RealTimeMetricsView',
    'AlertsView',
    'health_checker',
    'system_monitor',
]