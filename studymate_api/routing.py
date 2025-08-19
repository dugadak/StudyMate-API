"""
WebSocket 라우팅 설정

실시간 학습 분석 및 협업 학습을 위한 WebSocket 라우팅을 정의합니다.
"""

from django.urls import re_path, path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from .websocket_consumers import (
    LearningAnalyticsConsumer,
    StudyRoomConsumer,
    SystemMonitoringConsumer
)

# WebSocket URL 패턴
websocket_urlpatterns = [
    # 실시간 학습 분석
    re_path(r'ws/learning/analytics/$', LearningAnalyticsConsumer.as_asgi()),
    
    # 학습방 (그룹 학습)
    re_path(r'ws/study/room/(?P<room_id>\w+)/$', StudyRoomConsumer.as_asgi()),
    
    # 시스템 모니터링 (관리자용)
    re_path(r'ws/system/monitoring/$', SystemMonitoringConsumer.as_asgi()),
]

# ASGI 애플리케이션 설정
application = ProtocolTypeRouter({
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})