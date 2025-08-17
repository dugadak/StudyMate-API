from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from typing import Dict, Any, Optional
import logging
import uuid
from datetime import timedelta

from .models import (
    UserProfile, EmailVerificationToken, PasswordResetToken, 
    LoginHistory
)
from .serializers import (
    UserSerializer, UserProfileSerializer, UserRegistrationSerializer, 
    PasswordChangeSerializer, EmailVerificationSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    LoginHistorySerializer, UserDetailSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


class LoginThrottle(UserRateThrottle):
    """Custom throttle for login attempts"""
    scope = 'login'


class RegisterThrottle(AnonRateThrottle):
    """Custom throttle for registration attempts"""
    scope = 'register'


def get_client_ip(request) -> str:
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request) -> str:
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


class UserRegistrationView(generics.CreateAPIView):
    """Enhanced user registration with comprehensive validation and logging"""
    
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]
    
    @extend_schema(
        summary="사용자 회원가입",
        description="새 사용자 계정을 생성하고 이메일 인증 토큰을 발송합니다.",
        responses={
            201: UserSerializer,
            400: {"description": "입력 데이터 오류"},
            429: {"description": "요청 제한 초과"}
        }
    )
    def create(self, request, *args, **kwargs):
        """Create user with enhanced security and email verification"""
        
        # Get client information
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Check for suspicious patterns (basic)
        if self._is_suspicious_registration(ip_address, user_agent):
            logger.warning(f"Suspicious registration attempt from {ip_address}")
            return Response({
                'error': '보안상의 이유로 등록이 제한되었습니다. 나중에 다시 시도해주세요.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                user = serializer.save()
                
                # Create email verification token
                verification_token = EmailVerificationToken.objects.create(
                    user=user,
                    expires_at=timezone.now() + timedelta(hours=24)
                )
                
                # Send verification email
                self._send_verification_email(user, verification_token)
                
                # Log registration
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    success=True
                )
                
                logger.info(f"User registered successfully: {user.email} from {ip_address}")
                
                # Create token for immediate login (optional)
                token, created = Token.objects.get_or_create(user=user)
                
                return Response({
                    'user': UserSerializer(user).data,
                    'token': token.key,
                    'message': '회원가입이 완료되었습니다. 이메일을 확인하여 계정을 인증해주세요.',
                    'email_verification_required': True
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Registration failed: {str(e)}")
            return Response({
                'error': '회원가입 중 오류가 발생했습니다. 다시 시도해주세요.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _is_suspicious_registration(self, ip_address: str, user_agent: str) -> bool:
        """Check for suspicious registration patterns"""
        # Check registration rate from same IP
        cache_key = f'registration_attempts_{ip_address}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:  # Max 5 registrations per hour from same IP
            return True
        
        # Increment attempts counter
        cache.set(cache_key, attempts + 1, 3600)  # 1 hour
        
        # Basic user agent checks
        if not user_agent or len(user_agent) < 10:
            return True
        
        return False
    
    def _send_verification_email(self, user: User, token: EmailVerificationToken) -> None:
        """Send email verification"""
        try:
            verification_url = f"{settings.FRONTEND_URL}/verify-email/{token.token}"
            
            subject = "StudyMate 이메일 인증"
            message = f"""
안녕하세요 {user.profile.name}님,

StudyMate에 가입해주셔서 감사합니다.

아래 링크를 클릭하여 이메일 주소를 인증해주세요:
{verification_url}

이 링크는 24시간 후에 만료됩니다.

감사합니다.
StudyMate 팀
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False
            )
            
            logger.info(f"Verification email sent to {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")


@extend_schema(
    summary="사용자 로그인",
    description="이메일과 비밀번호로 로그인합니다.",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'email': {'type': 'string', 'format': 'email'},
                'password': {'type': 'string'}
            },
            'required': ['email', 'password']
        }
    },
    responses={
        200: UserSerializer,
        401: {"description": "인증 실패"},
        423: {"description": "계정 잠금"},
        429: {"description": "요청 제한 초과"}
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_view(request):
    """Enhanced login with security features"""
    
    email = request.data.get('email', '').lower().strip()
    password = request.data.get('password', '')
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    if not email or not password:
        return Response({
            'error': '이메일과 비밀번호를 입력해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check for suspicious login patterns
    if _is_suspicious_login(ip_address):
        logger.warning(f"Suspicious login attempt from {ip_address}")
        return Response({
            'error': '보안상의 이유로 로그인이 제한되었습니다.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    try:
        user = User.objects.get(email=email)
        
        # Check if account is locked
        if user.is_account_locked():
            _log_login_attempt(user, ip_address, user_agent, False, "계정 잠금")
            return Response({
                'error': '계정이 일시적으로 잠겨있습니다. 나중에 다시 시도해주세요.',
                'locked_until': user.account_locked_until.isoformat() if user.account_locked_until else None
            }, status=status.HTTP_423_LOCKED)
        
        # Check if account is active
        if not user.is_active:
            _log_login_attempt(user, ip_address, user_agent, False, "비활성 계정")
            return Response({
                'error': '비활성화된 계정입니다. 관리자에게 문의하세요.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Authenticate user
        authenticated_user = authenticate(username=email, password=password)
        
        if authenticated_user:
            # Reset failed login attempts
            user.reset_failed_login()
            user.update_last_activity()
            
            # Log successful login
            _log_login_attempt(user, ip_address, user_agent, True)
            
            # Create or get token
            token, created = Token.objects.get_or_create(user=user)
            
            logger.info(f"Successful login: {user.email} from {ip_address}")
            
            response_data = {
                'user': UserSerializer(user).data,
                'token': token.key,
                'message': '로그인되었습니다.'
            }
            
            # Check if email verification is required
            if not user.is_email_verified:
                response_data['email_verification_required'] = True
                response_data['message'] = '로그인되었습니다. 이메일 인증을 완료해주세요.'
            
            # Check if password change is required
            if user.needs_password_change():
                response_data['password_change_required'] = True
                response_data['message'] = '로그인되었습니다. 보안을 위해 비밀번호를 변경해주세요.'
            
            return Response(response_data)
        
        else:
            # Increment failed login attempts
            user.increment_failed_login()
            _log_login_attempt(user, ip_address, user_agent, False, "잘못된 비밀번호")
            
            # Generic error message for security
            return Response({
                'error': '이메일 또는 비밀번호가 잘못되었습니다.',
                'remaining_attempts': max(0, 5 - user.failed_login_attempts)
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    except User.DoesNotExist:
        # Log failed attempt without user
        LoginHistory.objects.create(
            user=None,
            ip_address=ip_address,
            user_agent=user_agent,
            success=False,
            failure_reason="존재하지 않는 사용자"
        )
        
        # Generic error message for security
        return Response({
            'error': '이메일 또는 비밀번호가 잘못되었습니다.'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return Response({
            'error': '로그인 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="사용자 로그아웃",
    description="현재 사용자를 로그아웃하고 토큰을 무효화합니다.",
    responses={
        200: {"description": "로그아웃 성공"},
        401: {"description": "인증 필요"}
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Enhanced logout with logging"""
    
    try:
        # Delete the token
        request.user.auth_token.delete()
        
        # Log logout
        logger.info(f"User logged out: {request.user.email}")
        
        return Response({'message': '로그아웃되었습니다.'})
    
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return Response({'message': '로그아웃되었습니다.'})


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Enhanced user profile management"""
    
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="사용자 프로필 조회",
        description="현재 사용자의 프로필 정보를 조회합니다.",
        responses={200: UserProfileSerializer}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        summary="사용자 프로필 수정",
        description="현재 사용자의 프로필 정보를 수정합니다.",
        responses={200: UserProfileSerializer}
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        summary="사용자 프로필 부분 수정",
        description="현재 사용자의 프로필 정보를 부분적으로 수정합니다.",
        responses={200: UserProfileSerializer}
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    def get_object(self):
        """Get or create user profile"""
        profile, created = UserProfile.objects.get_or_create(
            user=self.request.user,
            defaults={'name': self.request.user.username or 'User'}
        )
        return profile
    
    def perform_update(self, serializer):
        """Update profile with logging"""
        serializer.save()
        logger.info(f"Profile updated for user: {self.request.user.email}")


class PasswordChangeView(generics.GenericAPIView):
    """Enhanced password change with security features"""
    
    serializer_class = PasswordChangeSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="비밀번호 변경",
        description="현재 사용자의 비밀번호를 변경합니다.",
        responses={
            200: {"description": "비밀번호 변경 성공"},
            400: {"description": "입력 데이터 오류"}
        }
    )
    def post(self, request):
        """Change user password with enhanced security"""
        
        serializer = self.get_serializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                # Save new password
                serializer.save()
                
                # Invalidate all tokens (force re-login)
                Token.objects.filter(user=request.user).delete()
                
                # Log password change
                ip_address = get_client_ip(request)
                LoginHistory.objects.create(
                    user=request.user,
                    ip_address=ip_address,
                    user_agent=get_user_agent(request),
                    success=True
                )
                
                logger.info(f"Password changed for user: {request.user.email}")
                
                return Response({
                    'message': '비밀번호가 변경되었습니다. 다시 로그인해주세요.',
                    'requires_relogin': True
                })
        
        except Exception as e:
            logger.error(f"Password change failed: {str(e)}")
            return Response({
                'error': '비밀번호 변경 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmailVerificationView(APIView):
    """Email verification endpoint"""
    
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="이메일 인증",
        description="이메일 인증 토큰을 사용하여 계정을 인증합니다.",
        request=EmailVerificationSerializer,
        responses={
            200: {"description": "인증 성공"},
            400: {"description": "토큰 오류"}
        }
    )
    def post(self, request):
        """Verify email address"""
        
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                token = EmailVerificationToken.objects.get(
                    token=serializer.validated_data['token']
                )
                
                if not token.is_valid():
                    return Response({
                        'error': '유효하지 않거나 만료된 토큰입니다.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Mark user as verified
                user = token.user
                user.is_email_verified = True
                user.save(update_fields=['is_email_verified'])
                
                # Mark token as used
                token.mark_as_used()
                
                logger.info(f"Email verified for user: {user.email}")
                
                return Response({
                    'message': '이메일 인증이 완료되었습니다.',
                    'verified': True
                })
        
        except EmailVerificationToken.DoesNotExist:
            return Response({
                'error': '유효하지 않은 토큰입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Email verification failed: {str(e)}")
            return Response({
                'error': '이메일 인증 중 오류가 발생했습니다.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginHistoryView(generics.ListAPIView):
    """User login history"""
    
    serializer_class = LoginHistorySerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="로그인 기록 조회",
        description="현재 사용자의 로그인 기록을 조회합니다.",
        responses={200: LoginHistorySerializer(many=True)}
    )
    def get_queryset(self):
        """Get user's login history"""
        return LoginHistory.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:20]  # Last 20 logins


def _is_suspicious_login(ip_address: str) -> bool:
    """Check for suspicious login patterns"""
    # Check failed login attempts from IP
    cache_key = f'failed_login_attempts_{ip_address}'
    failed_attempts = cache.get(cache_key, 0)
    
    if failed_attempts >= 10:  # Max 10 failed attempts per hour
        return True
    
    return False


def _log_login_attempt(user: Optional[User], ip_address: str, user_agent: str, 
                      success: bool, failure_reason: str = '') -> None:
    """Log login attempt"""
    try:
        LoginHistory.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason if not success else ''
        )
        
        # Update cache for failed attempts
        if not success:
            cache_key = f'failed_login_attempts_{ip_address}'
            failed_attempts = cache.get(cache_key, 0)
            cache.set(cache_key, failed_attempts + 1, 3600)  # 1 hour
    
    except Exception as e:
        logger.error(f"Failed to log login attempt: {str(e)}")


# Additional views for password reset (simplified)
class PasswordResetRequestView(APIView):
    """Password reset request"""
    
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    
    @extend_schema(
        summary="비밀번호 재설정 요청",
        description="비밀번호 재설정 이메일을 발송합니다.",
        request=PasswordResetRequestSerializer,
        responses={
            200: {"description": "재설정 이메일 발송"},
            429: {"description": "요청 제한 초과"}
        }
    )
    def post(self, request):
        """Request password reset"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Create reset token
            reset_token = PasswordResetToken.objects.create(
                user=user,
                expires_at=timezone.now() + timedelta(hours=1),
                ip_address=get_client_ip(request)
            )
            
            # Send reset email (implementation needed)
            # _send_password_reset_email(user, reset_token)
            
            logger.info(f"Password reset requested for: {email}")
            
        except User.DoesNotExist:
            # Don't reveal if email exists
            pass
        
        # Always return success for security
        return Response({
            'message': '비밀번호 재설정 이메일이 발송되었습니다.'
        })


class AccountSecurityView(APIView):
    """Account security information"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="계정 보안 정보 조회",
        description="현재 사용자의 보안 관련 정보를 조회합니다.",
        responses={200: {"description": "보안 정보"}}
    )
    def get(self, request):
        """Get account security information"""
        user = request.user
        recent_logins = user.login_history.filter(success=True)[:5]
        
        return Response({
            'account_status': {
                'is_locked': user.is_account_locked(),
                'is_email_verified': user.is_email_verified,
                'is_2fa_enabled': user.is_2fa_enabled,
                'needs_password_change': user.needs_password_change(),
                'failed_login_attempts': user.failed_login_attempts,
            },
            'security_info': {
                'last_password_change': user.last_password_change.isoformat() if user.last_password_change else None,
                'last_activity': user.last_activity.isoformat() if user.last_activity else None,
                'account_created': user.date_joined.isoformat(),
            },
            'recent_logins': LoginHistorySerializer(recent_logins, many=True).data
        })