"""
URL configuration for studymate_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .views.personalization import PersonalizationViewSet
from .views.metrics import MetricsViewSet

# API Router for personalization and metrics
router = DefaultRouter()
router.register(r'personalization', PersonalizationViewSet, basename='personalization')
router.register(r'metrics', MetricsViewSet, basename='metrics')
urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Health Check & Monitoring  
    path('', include('studymate_api.health_urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # App URLs
    path('api/auth/', include('accounts.urls')),
    path('api/study/', include('study.urls')),
    path('api/quiz/', include('quiz.urls')),
    path('api/subscription/', include('subscription.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/home/', include('home.urls')),
    path('api/collab/', include('collaboration.urls')),
    path('api/stats/', include('stats.urls')),
    
    # Personalization API
    path('api/', include(router.urls)),
    
    # Django Allauth
    path('accounts/', include('allauth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
