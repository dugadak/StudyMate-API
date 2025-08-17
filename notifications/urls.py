from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationTemplateViewSet, NotificationScheduleViewSet,
    NotificationViewSet, DeviceTokenViewSet, NotificationPreferenceViewSet,
    NotificationBatchViewSet, NotificationAnalyticsViewSet
)

app_name = 'notifications'

# Create router for API endpoints
router = DefaultRouter()
router.register(r'templates', NotificationTemplateViewSet, basename='template')
router.register(r'schedules', NotificationScheduleViewSet, basename='schedule')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'devices', DeviceTokenViewSet, basename='device')
router.register(r'preferences', NotificationPreferenceViewSet, basename='preference')
router.register(r'batches', NotificationBatchViewSet, basename='batch')
router.register(r'analytics', NotificationAnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('api/', include(router.urls)),
]