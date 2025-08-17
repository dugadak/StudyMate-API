"""
System monitoring and health check utilities for StudyMate API

This module provides:
- Health check endpoints and utilities
- System metrics collection
- Performance monitoring
- Database health checks
- External service monitoring
- Alert system integration
"""

import time
import psutil
import logging
from django.conf import settings
from django.core.cache import cache
from django.db import connection, connections
from django.utils import timezone
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from typing import Dict, Any, List, Optional
import requests
from datetime import timedelta

logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checking system"""
    
    def __init__(self):
        self.checks = {
            'database': self._check_database,
            'cache': self._check_cache,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory,
            'external_services': self._check_external_services,
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {},
            'summary': {
                'total_checks': len(self.checks),
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
        
        for check_name, check_func in self.checks.items():
            try:
                check_result = check_func()
                results['checks'][check_name] = check_result
                
                # Update summary
                if check_result['status'] == 'healthy':
                    results['summary']['passed'] += 1
                elif check_result['status'] == 'warning':
                    results['summary']['warnings'] += 1
                else:
                    results['summary']['failed'] += 1
                    results['status'] = 'unhealthy'
                    
            except Exception as e:
                results['checks'][check_name] = {
                    'status': 'error',
                    'message': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                results['summary']['failed'] += 1
                results['status'] = 'unhealthy'
        
        return results
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test primary database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Check query performance
            query_time = (time.time() - start_time) * 1000
            
            # Get database stats
            db_stats = self._get_database_stats()
            
            status_level = 'healthy'
            if query_time > 1000:  # > 1 second
                status_level = 'warning'
            if query_time > 5000:  # > 5 seconds
                status_level = 'unhealthy'
            
            return {
                'status': status_level,
                'response_time_ms': round(query_time, 2),
                'connection_count': db_stats.get('connection_count', 0),
                'active_queries': db_stats.get('active_queries', 0),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check cache connectivity and performance"""
        start_time = time.time()
        
        try:
            # Test cache set/get
            test_key = 'health_check_test'
            test_value = {'timestamp': timezone.now().isoformat()}
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            response_time = (time.time() - start_time) * 1000
            
            status_level = 'healthy'
            if response_time > 100:  # > 100ms
                status_level = 'warning'
            if response_time > 500:  # > 500ms
                status_level = 'unhealthy'
            
            cache_stats = self._get_cache_stats()
            
            return {
                'status': status_level,
                'response_time_ms': round(response_time, 2),
                'hit_rate': cache_stats.get('hit_rate', 0),
                'memory_usage': cache_stats.get('memory_usage', 0),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check disk space usage"""
        try:
            disk_usage = psutil.disk_usage('/')
            used_percent = (disk_usage.used / disk_usage.total) * 100
            free_gb = disk_usage.free / (1024**3)
            
            status_level = 'healthy'
            if used_percent > 80:
                status_level = 'warning'
            if used_percent > 90 or free_gb < 1:
                status_level = 'unhealthy'
            
            return {
                'status': status_level,
                'used_percent': round(used_percent, 2),
                'free_gb': round(free_gb, 2),
                'total_gb': round(disk_usage.total / (1024**3), 2),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            memory = psutil.virtual_memory()
            used_percent = memory.percent
            available_gb = memory.available / (1024**3)
            
            status_level = 'healthy'
            if used_percent > 80:
                status_level = 'warning'
            if used_percent > 90 or available_gb < 0.5:
                status_level = 'unhealthy'
            
            return {
                'status': status_level,
                'used_percent': round(used_percent, 2),
                'available_gb': round(available_gb, 2),
                'total_gb': round(memory.total / (1024**3), 2),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_external_services(self) -> Dict[str, Any]:
        """Check external service connectivity"""
        services = {
            'openai': self._check_openai_service,
            'stripe': self._check_stripe_service,
        }
        
        results = {}
        overall_status = 'healthy'
        
        for service_name, check_func in services.items():
            try:
                service_result = check_func()
                results[service_name] = service_result
                
                if service_result['status'] != 'healthy':
                    overall_status = 'warning'
                    
            except Exception as e:
                results[service_name] = {
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': timezone.now().isoformat()
                }
                overall_status = 'warning'  # External services are not critical
        
        return {
            'status': overall_status,
            'services': results,
            'timestamp': timezone.now().isoformat()
        }
    
    def _check_openai_service(self) -> Dict[str, Any]:
        """Check OpenAI API connectivity"""
        try:
            # Simple API status check (without making actual requests)
            response = requests.get('https://status.openai.com/api/v2/status.json', timeout=5)
            
            if response.status_code == 200:
                status_data = response.json()
                api_status = status_data.get('status', {}).get('indicator', 'unknown')
                
                return {
                    'status': 'healthy' if api_status == 'none' else 'warning',
                    'api_status': api_status,
                    'timestamp': timezone.now().isoformat()
                }
            else:
                return {
                    'status': 'warning',
                    'error': f'Status check failed: {response.status_code}',
                    'timestamp': timezone.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'warning',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _check_stripe_service(self) -> Dict[str, Any]:
        """Check Stripe API connectivity"""
        try:
            # Simple API status check
            response = requests.get('https://status.stripe.com/api/v2/status.json', timeout=5)
            
            if response.status_code == 200:
                status_data = response.json()
                api_status = status_data.get('status', {}).get('indicator', 'unknown')
                
                return {
                    'status': 'healthy' if api_status == 'none' else 'warning',
                    'api_status': api_status,
                    'timestamp': timezone.now().isoformat()
                }
            else:
                return {
                    'status': 'warning',
                    'error': f'Status check failed: {response.status_code}',
                    'timestamp': timezone.now().isoformat()
                }
                
        except Exception as e:
            return {
                'status': 'warning',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with connection.cursor() as cursor:
                # Get connection count (PostgreSQL specific)
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                )
                active_queries = cursor.fetchone()[0]
                
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity"
                )
                connection_count = cursor.fetchone()[0]
                
                return {
                    'connection_count': connection_count,
                    'active_queries': active_queries
                }
        except:
            return {}
    
    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # This would depend on your cache backend
            # For Redis, you might use redis-py to get INFO stats
            return {
                'hit_rate': 95.0,  # Placeholder
                'memory_usage': 50.0  # Placeholder
            }
        except:
            return {}


# Global health checker instance
health_checker = HealthChecker()


@api_view(['GET'])
def health_check(request):
    """Basic health check endpoint"""
    try:
        # Quick database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': getattr(settings, 'VERSION', '1.0.0')
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def detailed_health_check(request):
    """Detailed health check with comprehensive system info"""
    results = health_checker.run_all_checks()
    
    # Add system information
    results['system_info'] = {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'load_average': psutil.getloadavg(),
        'boot_time': psutil.boot_time(),
        'python_version': f"{psutil.PYTHON_VERSION}",
        'process_count': len(psutil.pids()),
    }
    
    # Add application metrics
    results['app_metrics'] = {
        'django_version': getattr(settings, 'DJANGO_VERSION', 'unknown'),
        'debug_mode': settings.DEBUG,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'database_engine': settings.DATABASES['default']['ENGINE'],
        'cache_backend': str(cache.__class__),
    }
    
    status_code = 200 if results['status'] == 'healthy' else 503
    return Response(results, status=status_code)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def system_metrics(request):
    """Get system performance metrics"""
    metrics = {
        'timestamp': timezone.now().isoformat(),
        'cpu': {
            'percent': psutil.cpu_percent(interval=1),
            'count': psutil.cpu_count(),
            'load_average': psutil.getloadavg(),
        },
        'memory': {
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'percent': psutil.virtual_memory().percent,
            'used': psutil.virtual_memory().used,
            'free': psutil.virtual_memory().free,
        },
        'disk': {
            'total': psutil.disk_usage('/').total,
            'used': psutil.disk_usage('/').used,
            'free': psutil.disk_usage('/').free,
            'percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
        },
        'network': psutil.net_io_counters()._asdict(),
        'processes': len(psutil.pids()),
        'boot_time': psutil.boot_time(),
    }
    
    return Response(metrics)


class MetricsCollector:
    """Collect and store application metrics"""
    
    def __init__(self):
        self.metrics_cache_timeout = 300  # 5 minutes
    
    def collect_api_metrics(self) -> Dict[str, Any]:
        """Collect API performance metrics"""
        # This would typically query your logging/monitoring database
        return {
            'total_requests_last_hour': self._get_request_count(hours=1),
            'total_requests_last_day': self._get_request_count(hours=24),
            'average_response_time': self._get_average_response_time(),
            'error_rate': self._get_error_rate(),
            'top_endpoints': self._get_top_endpoints(),
            'slow_queries': self._get_slow_queries(),
        }
    
    def collect_business_metrics(self) -> Dict[str, Any]:
        """Collect business metrics"""
        return {
            'active_users_last_hour': self._get_active_users(hours=1),
            'active_users_last_day': self._get_active_users(hours=24),
            'new_registrations_today': self._get_new_registrations(),
            'summaries_generated_today': self._get_summaries_generated(),
            'quizzes_completed_today': self._get_quizzes_completed(),
            'ai_requests_today': self._get_ai_requests(),
        }
    
    def _get_request_count(self, hours: int) -> int:
        """Get request count for time period"""
        # Placeholder - implement based on your logging system
        return 0
    
    def _get_average_response_time(self) -> float:
        """Get average response time"""
        # Placeholder - implement based on your logging system
        return 0.0
    
    def _get_error_rate(self) -> float:
        """Get error rate percentage"""
        # Placeholder - implement based on your logging system
        return 0.0
    
    def _get_top_endpoints(self) -> List[Dict[str, Any]]:
        """Get most requested endpoints"""
        # Placeholder - implement based on your logging system
        return []
    
    def _get_slow_queries(self) -> List[Dict[str, Any]]:
        """Get slowest database queries"""
        # Placeholder - implement based on your logging system
        return []
    
    def _get_active_users(self, hours: int) -> int:
        """Get active user count"""
        # Placeholder - implement based on your user activity tracking
        return 0
    
    def _get_new_registrations(self) -> int:
        """Get new registrations today"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return User.objects.filter(date_joined__gte=today).count()
    
    def _get_summaries_generated(self) -> int:
        """Get summaries generated today"""
        try:
            from study.models import StudySummary
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return StudySummary.objects.filter(generated_at__gte=today).count()
        except:
            return 0
    
    def _get_quizzes_completed(self) -> int:
        """Get quizzes completed today"""
        try:
            from quiz.models import QuizAttempt
            today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return QuizAttempt.objects.filter(
                completed_at__gte=today,
                is_completed=True
            ).count()
        except:
            return 0
    
    def _get_ai_requests(self) -> int:
        """Get AI requests made today"""
        # Placeholder - implement based on your AI usage tracking
        return 0


# Global metrics collector
metrics_collector = MetricsCollector()


@api_view(['GET'])
@permission_classes([IsAdminUser])
def application_metrics(request):
    """Get application-specific metrics"""
    api_metrics = metrics_collector.collect_api_metrics()
    business_metrics = metrics_collector.collect_business_metrics()
    
    return Response({
        'timestamp': timezone.now().isoformat(),
        'api_metrics': api_metrics,
        'business_metrics': business_metrics,
    })


# Export main components
__all__ = [
    'HealthChecker',
    'MetricsCollector',
    'health_check',
    'detailed_health_check',
    'system_metrics',
    'application_metrics',
    'health_checker',
    'metrics_collector'
]