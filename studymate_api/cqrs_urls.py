"""
CQRS 패턴을 위한 URL 설정

CQRS 기반 API 엔드포인트를 정의합니다.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# CQRS ViewSet들 import
from study.cqrs_views import (
    CQRSSubjectViewSet, CQRSStudySummaryViewSet, 
    CQRSStudyProgressViewSet, CQRSStudyAnalyticsViewSet
)

# CQRS 전용 라우터 생성
cqrs_router = DefaultRouter()

# Study 관련 CQRS ViewSet 등록
cqrs_router.register(r'subjects', CQRSSubjectViewSet, basename='cqrs-subjects')
cqrs_router.register(r'study-summaries', CQRSStudySummaryViewSet, basename='cqrs-study-summaries')
cqrs_router.register(r'study-progress', CQRSStudyProgressViewSet, basename='cqrs-study-progress')
cqrs_router.register(r'study-analytics', CQRSStudyAnalyticsViewSet, basename='cqrs-study-analytics')

# CQRS URL 패턴
urlpatterns = [
    # CQRS 기반 API
    path('', include(cqrs_router.urls)),
    
    # CQRS 시스템 정보 (개발/테스트용)
    path('system/info/', include([
        # CQRS 시스템 상태는 별도 view로 구현 가능
    ]))
]