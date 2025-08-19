"""
테스트 전용 간소화된 URL 설정
"""

from django.urls import path
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
]