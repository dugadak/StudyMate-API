from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import views
from .zero_trust_views import (
    DeviceRegistrationView, MFAChallengeView, 
    LocationVerificationView, SecurityStatusView
)

app_name = 'accounts'

# Basic URL patterns
urlpatterns = [
    # Authentication endpoints
    path('register/', views.UserRegistrationView.as_view(), name='user-register'),
    path('login/', views.login_view, name='user-login'),
    path('logout/', views.logout_view, name='user-logout'),
    
    # JWT endpoints
    path('token/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token-verify'),
    
    # Profile management
    path('profile/', views.UserProfileView.as_view(), name='user-profile'),
    
    # Password management
    path('change-password/', views.PasswordChangeView.as_view(), name='password-change'),
    path('reset-password/request/', views.PasswordResetRequestView.as_view(), name='password-reset-request'),
    # path('reset-password/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    # Email verification
    path('verify-email/', views.EmailVerificationView.as_view(), name='email-verification'),
    # path('resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    
    # Security
    path('login-history/', views.LoginHistoryView.as_view(), name='login-history'),
    path('security/', views.AccountSecurityView.as_view(), name='account-security'),
    # path('2fa/enable/', views.Enable2FAView.as_view(), name='enable-2fa'),
    # path('2fa/disable/', views.Disable2FAView.as_view(), name='disable-2fa'),
    # path('2fa/verify/', views.Verify2FAView.as_view(), name='verify-2fa'),
    
    # Zero Trust Security
    path('zero-trust/devices/', DeviceRegistrationView.as_view(), name='zero-trust-devices'),
    path('zero-trust/mfa/', MFAChallengeView.as_view(), name='zero-trust-mfa'),
    path('zero-trust/location/', LocationVerificationView.as_view(), name='zero-trust-location'),
    path('zero-trust/status/', SecurityStatusView.as_view(), name='zero-trust-status'),
]