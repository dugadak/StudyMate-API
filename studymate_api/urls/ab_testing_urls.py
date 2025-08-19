"""
A/B 테스트 시스템 URL 설정

A/B 테스트 관리 및 분석을 위한 API 엔드포인트들을 정의합니다.
"""

from django.urls import path
from studymate_api.views.ab_testing_views import (
    ABTestManagementView,
    ABTestDetailView,
    ABTestResultsView,
    UserABTestView,
    ABTestFeedbackView,
    ABTestAnalyticsView
)

app_name = 'ab_testing'

urlpatterns = [
    # A/B 테스트 관리 (관리자용)
    path('tests/', ABTestManagementView.as_view(), name='test_management'),
    path('tests/<str:test_id>/', ABTestDetailView.as_view(), name='test_detail'),
    path('tests/<str:test_id>/results/', ABTestResultsView.as_view(), name='test_results'),
    
    # 사용자 A/B 테스트 정보
    path('user/tests/', UserABTestView.as_view(), name='user_tests'),
    path('user/feedback/', ABTestFeedbackView.as_view(), name='user_feedback'),
    
    # A/B 테스트 분석 (관리자용)
    path('analytics/', ABTestAnalyticsView.as_view(), name='analytics'),
]