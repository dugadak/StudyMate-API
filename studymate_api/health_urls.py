"""
StudyMate API 헬스체크 및 모니터링 URL 설정
"""

from django.urls import path
from .health import (
    HealthCheckView, ReadinessCheckView, LivenessCheckView, 
    MetricsView, RealTimeMetricsView, AlertsView
)

urlpatterns = [
    # 기본 헬스체크
    path('health/', HealthCheckView.as_view(), name='health_check'),
    
    # Kubernetes용 엔드포인트
    path('health/ready/', ReadinessCheckView.as_view(), name='readiness_check'),
    path('health/alive/', LivenessCheckView.as_view(), name='liveness_check'),
    
    # 메트릭 엔드포인트  
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('metrics/realtime/', RealTimeMetricsView.as_view(), name='realtime_metrics'),
    path('alerts/', AlertsView.as_view(), name='alerts'),
    
    # 호환성을 위한 추가 경로
    path('ping/', LivenessCheckView.as_view(), name='ping'),
    path('status/', HealthCheckView.as_view(), name='status'),
]