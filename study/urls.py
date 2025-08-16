from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'settings', views.StudySettingsViewSet, basename='studysettings')
router.register(r'summaries', views.StudySummaryViewSet, basename='studysummary')
router.register(r'progress', views.StudyProgressViewSet, basename='studyprogress')

urlpatterns = [
    path('', include(router.urls)),
    path('generate-summary/', views.GenerateSummaryView.as_view(), name='generate-summary'),
]