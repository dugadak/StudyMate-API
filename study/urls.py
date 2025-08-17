from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet, basename='subject')
router.register(r'settings', views.StudySettingsViewSet, basename='studysettings')
router.register(r'summaries', views.StudySummaryViewSet, basename='studysummary')
router.register(r'progress', views.StudyProgressViewSet, basename='studyprogress')
router.register(r'goals', views.StudyGoalViewSet, basename='studygoal')

# URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('generate-summary/', views.GenerateSummaryView.as_view(), name='generate-summary'),
    path('analytics/', views.StudyAnalyticsView.as_view(), name='study-analytics'),
    
    # Subject-specific endpoints
    path('subjects/<int:pk>/statistics/', 
         views.SubjectViewSet.as_view({'get': 'statistics'}), 
         name='subject-statistics'),
    path('subjects/categories/', 
         views.SubjectViewSet.as_view({'get': 'categories'}), 
         name='subject-categories'),
    path('subjects/popular/', 
         views.SubjectViewSet.as_view({'get': 'popular'}), 
         name='subject-popular'),
    
    # Settings-specific endpoints
    path('settings/<int:pk>/test-notification-time/', 
         views.StudySettingsViewSet.as_view({'post': 'test_notification_time'}), 
         name='settings-test-notification'),
    path('settings/<int:pk>/ai-config/', 
         views.StudySettingsViewSet.as_view({'get': 'ai_config'}), 
         name='settings-ai-config'),
    path('settings/bulk-update-notifications/', 
         views.StudySettingsViewSet.as_view({'get': 'bulk_update_notification_times'}), 
         name='settings-bulk-update-notifications'),
    
    # Summary-specific endpoints
    path('summaries/<int:pk>/mark-as-read/', 
         views.StudySummaryViewSet.as_view({'post': 'mark_as_read'}), 
         name='summary-mark-read'),
    path('summaries/<int:pk>/toggle-bookmark/', 
         views.StudySummaryViewSet.as_view({'post': 'toggle_bookmark'}), 
         name='summary-toggle-bookmark'),
    path('summaries/<int:pk>/rate/', 
         views.StudySummaryViewSet.as_view({'post': 'rate'}), 
         name='summary-rate'),
    path('summaries/statistics/', 
         views.StudySummaryViewSet.as_view({'get': 'statistics'}), 
         name='summary-statistics'),
    path('summaries/bookmarks/', 
         views.StudySummaryViewSet.as_view({'get': 'bookmarks'}), 
         name='summary-bookmarks'),
    path('summaries/recent/', 
         views.StudySummaryViewSet.as_view({'get': 'recent'}), 
         name='summary-recent'),
    
    # Progress-specific endpoints
    path('progress/overview/', 
         views.StudyProgressViewSet.as_view({'get': 'overview'}), 
         name='progress-overview'),
    path('progress/<int:pk>/weekly-report/', 
         views.StudyProgressViewSet.as_view({'get': 'weekly_report'}), 
         name='progress-weekly-report'),
    path('progress/<int:pk>/learning-insights/', 
         views.StudyProgressViewSet.as_view({'get': 'learning_insights'}), 
         name='progress-insights'),
    path('progress/leaderboard/', 
         views.StudyProgressViewSet.as_view({'get': 'leaderboard'}), 
         name='progress-leaderboard'),
    path('progress/<int:pk>/update-goals/', 
         views.StudyProgressViewSet.as_view({'post': 'update_goals'}), 
         name='progress-update-goals'),
    
    # Goal-specific endpoints
    path('goals/<int:pk>/complete/', 
         views.StudyGoalViewSet.as_view({'post': 'complete'}), 
         name='goal-complete'),
    path('goals/active/', 
         views.StudyGoalViewSet.as_view({'get': 'active'}), 
         name='goal-active'),
    path('goals/completed/', 
         views.StudyGoalViewSet.as_view({'get': 'completed'}), 
         name='goal-completed'),
]