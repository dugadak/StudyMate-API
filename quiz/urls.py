from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'quizzes', views.QuizViewSet, basename='quiz')
router.register(r'attempts', views.QuizAttemptViewSet, basename='quizattempt')
router.register(r'sessions', views.QuizSessionViewSet, basename='quizsession')
router.register(r'progress', views.QuizProgressViewSet, basename='quizprogress')
router.register(r'categories', views.QuizCategoryViewSet, basename='quizcategory')

# URL patterns
urlpatterns = [
    # Router URLs
    path('', include(router.urls)),
    
    # Analytics and recommendations
    path('analytics/', views.QuizAnalyticsView.as_view(), name='quiz-analytics'),
    path('recommendations/', views.QuizRecommendationView.as_view(), name='quiz-recommendations'),
    
    # Quiz-specific endpoints
    path('quizzes/<int:pk>/attempt/', 
         views.QuizViewSet.as_view({'post': 'attempt'}), 
         name='quiz-attempt'),
    path('quizzes/<int:pk>/hints/', 
         views.QuizViewSet.as_view({'get': 'hints'}), 
         name='quiz-hints'),
    path('quizzes/<int:pk>/choices/', 
         views.QuizViewSet.as_view({'get': 'choices'}), 
         name='quiz-choices'),
    path('quizzes/<int:pk>/statistics/', 
         views.QuizViewSet.as_view({'get': 'statistics'}), 
         name='quiz-statistics'),
    path('quizzes/recommended/', 
         views.QuizViewSet.as_view({'get': 'recommended'}), 
         name='quiz-recommended'),
    path('quizzes/random/', 
         views.QuizViewSet.as_view({'get': 'random'}), 
         name='quiz-random'),
    
    # Attempt-specific endpoints
    path('attempts/statistics/', 
         views.QuizAttemptViewSet.as_view({'get': 'statistics'}), 
         name='attempt-statistics'),
    path('attempts/<int:pk>/rate-difficulty/', 
         views.QuizAttemptViewSet.as_view({'post': 'rate_difficulty'}), 
         name='attempt-rate-difficulty'),
    
    # Session-specific endpoints
    path('sessions/<int:pk>/start/', 
         views.QuizSessionViewSet.as_view({'post': 'start'}), 
         name='session-start'),
    path('sessions/<int:pk>/pause/', 
         views.QuizSessionViewSet.as_view({'post': 'pause'}), 
         name='session-pause'),
    path('sessions/<int:pk>/complete/', 
         views.QuizSessionViewSet.as_view({'post': 'complete'}), 
         name='session-complete'),
    path('sessions/<int:pk>/next-quiz/', 
         views.QuizSessionViewSet.as_view({'get': 'next_quiz'}), 
         name='session-next-quiz'),
    path('sessions/active/', 
         views.QuizSessionViewSet.as_view({'get': 'active'}), 
         name='session-active'),
    path('sessions/history/', 
         views.QuizSessionViewSet.as_view({'get': 'history'}), 
         name='session-history'),
    
    # Progress-specific endpoints
    path('progress/overview/', 
         views.QuizProgressViewSet.as_view({'get': 'overview'}), 
         name='progress-overview'),
    path('progress/<int:pk>/insights/', 
         views.QuizProgressViewSet.as_view({'get': 'insights'}), 
         name='progress-insights'),
    
    # Category-specific endpoints
    path('categories/tree/', 
         views.QuizCategoryViewSet.as_view({'get': 'tree'}), 
         name='category-tree'),
]