from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CollaborationViewSet

router = DefaultRouter()
router.register(r'rooms', CollaborationViewSet, basename='rooms')

urlpatterns = [
    path('', include(router.urls)),
]