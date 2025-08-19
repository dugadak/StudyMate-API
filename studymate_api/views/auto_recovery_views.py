"""
자동 복구 시스템 관리 API

헬스 체크 상태 조회 및 복구 이력을 관리하는 API입니다.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes

from studymate_api.auto_recovery import (
    health_checker, auto_recovery_engine, get_system_health,
    start_monitoring, stop_monitoring, HealthStatus
)

logger = logging.getLogger(__name__)


class SystemHealthView(APIView):
    """시스템 헬스 상태 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        """전체 시스템 헬스 상태 조회"""
        try:
            health_data = get_system_health()
            
            # 상세 정보 추가
            health_data['monitoring_active'] = health_checker.running
            health_data['auto_recovery_active'] = auto_recovery_engine.running
            
            return Response(health_data)
            
        except Exception as e:
            logger.error(f"System health check error: {e}")
            return Response({
                'error': 'health_check_failed',
                'message': '시스템 헬스 체크 중 오류가 발생했습니다.',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceHealthView(APIView):
    """개별 서비스 헬스 상태 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request, service_name):
        """특정 서비스 헬스 상태 조회"""
        try:
            health = health_checker.get_health_status(service_name)
            
            if not health:
                return Response({
                    'error': 'service_not_found',
                    'message': f'서비스 "{service_name}"을 찾을 수 없습니다.'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # 최근 이력 추가
            recent_history = [
                record for record in auto_recovery_engine.get_recovery_history(50)
                if record['service_name'] == service_name
            ]
            
            return Response({
                'service_health': health.to_dict(),
                'recent_recovery_history': recent_history[-10:]  # 최근 10개
            })
            
        except Exception as e:
            logger.error(f"Service health check error: {e}")
            return Response({
                'error': 'health_check_failed',
                'message': '서비스 헬스 체크 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecoveryHistoryView(APIView):
    """복구 이력 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def get(self, request):
        """복구 이력 조회"""
        try:
            # 쿼리 파라미터
            limit = int(request.query_params.get('limit', 100))
            service_name = request.query_params.get('service')
            hours = request.query_params.get('hours')
            
            # 전체 이력 조회
            history = auto_recovery_engine.get_recovery_history(limit)
            
            # 서비스별 필터링
            if service_name:
                history = [record for record in history if record['service_name'] == service_name]
            
            # 시간 범위 필터링
            if hours:
                cutoff_time = timezone.now() - timedelta(hours=int(hours))
                history = [
                    record for record in history 
                    if record['timestamp'] >= cutoff_time
                ]
            
            # 통계 계산
            total_attempts = len(history)
            successful_attempts = len([r for r in history if r['success']])
            success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0
            
            # 서비스별 통계
            service_stats = {}
            for record in history:
                service = record['service_name']
                if service not in service_stats:
                    service_stats[service] = {'total': 0, 'successful': 0}
                service_stats[service]['total'] += 1
                if record['success']:
                    service_stats[service]['successful'] += 1
            
            # 액션별 통계
            action_stats = {}
            for record in history:
                action = record['action']
                if action not in action_stats:
                    action_stats[action] = {'total': 0, 'successful': 0}
                action_stats[action]['total'] += 1
                if record['success']:
                    action_stats[action]['successful'] += 1
            
            return Response({
                'recovery_history': history,
                'statistics': {
                    'total_attempts': total_attempts,
                    'successful_attempts': successful_attempts,
                    'success_rate': round(success_rate, 2),
                    'service_statistics': service_stats,
                    'action_statistics': action_stats
                },
                'query_parameters': {
                    'limit': limit,
                    'service_filter': service_name,
                    'time_range_hours': hours
                }
            })
            
        except Exception as e:
            logger.error(f"Recovery history error: {e}")
            return Response({
                'error': 'history_retrieval_failed',
                'message': '복구 이력 조회 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MonitoringControlView(APIView):
    """모니터링 제어 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        """모니터링 제어 (시작/중지)"""
        try:
            action = request.data.get('action')
            
            if action == 'start':
                start_monitoring()
                message = '자동 복구 모니터링이 시작되었습니다.'
            elif action == 'stop':
                stop_monitoring()
                message = '자동 복구 모니터링이 중지되었습니다.'
            else:
                return Response({
                    'error': 'invalid_action',
                    'message': '유효하지 않은 액션입니다. "start" 또는 "stop"을 사용하세요.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': message,
                'monitoring_active': health_checker.running,
                'auto_recovery_active': auto_recovery_engine.running,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Monitoring control error: {e}")
            return Response({
                'error': 'control_failed',
                'message': '모니터링 제어 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HealthCheckTriggerView(APIView):
    """수동 헬스 체크 트리거 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        """수동으로 헬스 체크 실행"""
        try:
            service_name = request.data.get('service_name')
            
            if service_name:
                # 특정 서비스만 체크
                if service_name not in health_checker.checks:
                    return Response({
                        'error': 'service_not_found',
                        'message': f'서비스 "{service_name}"을 찾을 수 없습니다.'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                health_check = health_checker.checks[service_name]
                result = health_checker._execute_check(health_check)
                health_checker.results[service_name] = result
                
                return Response({
                    'message': f'서비스 "{service_name}" 헬스 체크가 완료되었습니다.',
                    'result': result.to_dict()
                })
            else:
                # 모든 서비스 체크
                results = {}
                for check_name, health_check in health_checker.checks.items():
                    result = health_checker._execute_check(health_check)
                    health_checker.results[check_name] = result
                    results[check_name] = result.to_dict()
                
                return Response({
                    'message': '모든 서비스 헬스 체크가 완료되었습니다.',
                    'results': results,
                    'total_services': len(results)
                })
                
        except Exception as e:
            logger.error(f"Manual health check error: {e}")
            return Response({
                'error': 'health_check_failed',
                'message': '수동 헬스 체크 실행 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertTestView(APIView):
    """알림 테스트 API"""
    
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        """알림 시스템 테스트"""
        try:
            alert_type = request.data.get('type', 'email')
            test_config = request.data.get('config', {})
            
            # 테스트용 더미 헬스 데이터
            from studymate_api.auto_recovery import ServiceHealth
            test_health = ServiceHealth(
                service_name="test_service",
                status=HealthStatus.CRITICAL,
                response_time=5000.0,
                error_message="This is a test alert",
                last_check=timezone.now(),
                consecutive_failures=3
            )
            
            # 테스트 복구 규칙
            from studymate_api.auto_recovery import RecoveryRule, RecoveryAction
            test_rule = RecoveryRule(
                service_name="test_service",
                condition="critical",
                action=RecoveryAction.MANUAL_INTERVENTION,
                parameters={'alert_config': test_config}
            )
            
            # 알림 발송 테스트
            if alert_type == 'email':
                auto_recovery_engine._send_email_alert(test_health, test_config)
                message = '테스트 이메일이 발송되었습니다.'
            elif alert_type == 'slack':
                auto_recovery_engine._send_slack_alert(test_health, test_config)
                message = '테스트 Slack 메시지가 발송되었습니다.'
            else:
                return Response({
                    'error': 'invalid_alert_type',
                    'message': '유효하지 않은 알림 타입입니다.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': message,
                'test_config': test_config,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Alert test error: {e}")
            return Response({
                'error': 'alert_test_failed',
                'message': '알림 테스트 중 오류가 발생했습니다.',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def health_status_summary(request):
    """간단한 헬스 상태 요약 (일반 사용자용)"""
    try:
        health_data = get_system_health()
        
        # 민감한 정보 제거하고 요약만 제공
        summary = {
            'overall_status': health_data['overall_status'],
            'service_count': {
                'total': health_data['total_services'],
                'healthy': health_data['healthy_services'],
                'issues': health_data['total_services'] - health_data['healthy_services']
            },
            'last_updated': health_data['timestamp']
        }
        
        return Response(summary)
        
    except Exception as e:
        logger.error(f"Health summary error: {e}")
        return Response({
            'error': 'summary_failed',
            'message': '헬스 상태 요약 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)