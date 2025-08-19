"""
자동 복구 시스템 URL 설정

헬스 체크 및 복구 관리를 위한 API 엔드포인트들을 정의합니다.
"""

from django.urls import path
from studymate_api.views.auto_recovery_views import (
    SystemHealthView,
    ServiceHealthView,
    RecoveryHistoryView,
    MonitoringControlView,
    HealthCheckTriggerView,
    AlertTestView,
    health_status_summary
)

app_name = 'auto_recovery'

urlpatterns = [
    # 시스템 헬스 상태 (관리자용)
    path('health/', SystemHealthView.as_view(), name='system_health'),
    path('health/<str:service_name>/', ServiceHealthView.as_view(), name='service_health'),
    
    # 복구 이력 및 통계
    path('recovery/history/', RecoveryHistoryView.as_view(), name='recovery_history'),
    
    # 모니터링 제어
    path('monitoring/control/', MonitoringControlView.as_view(), name='monitoring_control'),
    path('monitoring/trigger/', HealthCheckTriggerView.as_view(), name='health_check_trigger'),
    
    # 알림 테스트
    path('alerts/test/', AlertTestView.as_view(), name='alert_test'),
    
    # 간단한 헬스 상태 요약 (일반 사용자용)
    path('status/', health_status_summary, name='health_summary'),
]