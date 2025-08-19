"""
ASGI config for studymate_api project.

WebSocket과 HTTP를 지원하는 ASGI 애플리케이션 설정
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Django 설정 초기화
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studymate_api.settings')
django.setup()

# Django HTTP 애플리케이션
django_asgi_app = get_asgi_application()

# WebSocket 라우팅 import (Django 설정 후에 import 해야 함)
from studymate_api.routing import websocket_urlpatterns

# ASGI 애플리케이션 설정
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
