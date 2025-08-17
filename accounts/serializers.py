from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from django.utils import timezone
from typing import Dict, Any, Optional
import re
import logging

from .models import UserProfile, EmailVerificationToken, PasswordResetToken, LoginHistory
from studymate_api.serializers import (
    OptimizedModelSerializer, TimestampMixin, CachedMethodField,
    ListOnlySerializer, DetailOnlySerializer, PerformanceMonitoringMixin
)

User = get_user_model()
logger = logging.getLogger(__name__)


class PasswordValidationMixin:
    """Password validation mixin for consistent password validation"""
    
    def validate_password_strength(self, password: str) -> str:
        """Validate password strength with custom rules"""
        if len(password) < 8:
            raise serializers.ValidationError("비밀번호는 최소 8자 이상이어야 합니다.")
        
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError("비밀번호에는 최소 하나의 대문자가 포함되어야 합니다.")
        
        if not re.search(r'[a-z]', password):
            raise serializers.ValidationError("비밀번호에는 최소 하나의 소문자가 포함되어야 합니다.")
        
        if not re.search(r'\d', password):
            raise serializers.ValidationError("비밀번호에는 최소 하나의 숫자가 포함되어야 합니다.")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise serializers.ValidationError("비밀번호에는 최소 하나의 특수문자가 포함되어야 합니다.")
        
        # Django's built-in password validation
        try:
            validate_password(password)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        
        return password


class UserSerializer(OptimizedModelSerializer, TimestampMixin, PerformanceMonitoringMixin):
    """Enhanced user serializer with performance optimizations"""
    
    profile_name = CachedMethodField(cache_timeout=600)  # 10 minutes cache
    is_verified = serializers.BooleanField(source='is_email_verified', read_only=True)
    
    # Define fields for different contexts
    list_fields = ['id', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
    detail_fields = [
        'id', 'email', 'first_name', 'last_name', 'is_active', 'date_joined',
        'last_login', 'profile_name', 'is_verified', 'created_at_display'
    ]
    
    # Cached fields for expensive operations
    cached_fields = {'profile_name'}
    
    # Queryset optimization
    select_related_fields = ['profile']
    prefetch_related_fields = []
    needs_password_change = serializers.SerializerMethodField()
    last_login_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'is_active', 'is_verified', 'date_joined', 'last_login',
            'profile_name', 'needs_password_change', 'last_login_formatted',
            'privacy_level', 'is_2fa_enabled'
        ]
        read_only_fields = [
            'id', 'date_joined', 'last_login', 'is_verified',
            'needs_password_change', 'last_login_formatted', 'is_2fa_enabled'
        ]
        extra_kwargs = {
            'email': {'validators': [EmailValidator()]},
            'username': {'min_length': 3, 'max_length': 30},
        }
    
    def get_profile_name(self, obj: User) -> Optional[str]:
        """Get profile name with caching"""
        try:
            if hasattr(obj, 'profile') and obj.profile:
                return obj.profile.name
        except UserProfile.DoesNotExist:
            pass
        return None
    
    def get_needs_password_change(self, obj: User) -> bool:
        """Check if user needs to change password"""
        return obj.needs_password_change()
    
    def get_last_login_formatted(self, obj: User) -> Optional[str]:
        """Get formatted last login time"""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M:%S')
        return None
    
    def validate_email(self, value: str) -> str:
        """Validate email with additional checks"""
        # Normalize email
        value = value.lower().strip()
        
        # Check for disposable email domains (basic list)
        disposable_domains = [
            '10minutemail.com', 'mailinator.com', 'guerrillamail.com',
            'tempmail.org', 'throwaway.email'
        ]
        domain = value.split('@')[1] if '@' in value else ''
        if domain in disposable_domains:
            raise serializers.ValidationError("일회용 이메일 주소는 사용할 수 없습니다.")
        
        return value
    
    def validate_username(self, value: str) -> str:
        """Validate username with additional rules"""
        value = value.strip()
        
        # Check for inappropriate usernames
        inappropriate_usernames = [
            'admin', 'root', 'user', 'test', 'guest', 'anonymous',
            'null', 'undefined', 'system', 'administrator'
        ]
        if value.lower() in inappropriate_usernames:
            raise serializers.ValidationError("이 사용자명은 사용할 수 없습니다.")
        
        # Only allow alphanumeric and underscore
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            raise serializers.ValidationError("사용자명은 영문자, 숫자, 밑줄(_)만 사용할 수 있습니다.")
        
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Enhanced user profile serializer"""
    
    user = UserSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    study_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'user', 'name', 'bio', 'avatar', 'avatar_url', 'phone_number',
            'country', 'timezone', 'language', 'theme', 'display_name',
            'total_study_time', 'streak_days', 'study_stats',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'total_study_time', 'streak_days']
        extra_kwargs = {
            'name': {'min_length': 2, 'max_length': 100},
            'bio': {'max_length': 500},
        }
    
    def get_display_name(self, obj: UserProfile) -> str:
        """Get user's display name"""
        return obj.get_display_name()
    
    def get_avatar_url(self, obj: UserProfile) -> Optional[str]:
        """Get avatar URL if exists"""
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None
    
    def get_study_stats(self, obj: UserProfile) -> Dict[str, Any]:
        """Get user's study statistics"""
        return {
            'total_study_time_hours': obj.total_study_time.total_seconds() / 3600 if obj.total_study_time else 0,
            'streak_days': obj.streak_days,
            'profile_completion': self._calculate_profile_completion(obj),
        }
    
    def _calculate_profile_completion(self, obj: UserProfile) -> int:
        """Calculate profile completion percentage"""
        fields = ['name', 'bio', 'avatar', 'phone_number', 'country']
        completed = sum(1 for field in fields if getattr(obj, field))
        return int((completed / len(fields)) * 100)
    
    def validate_name(self, value: str) -> str:
        """Validate user name"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("이름을 입력해주세요.")
        
        # Check for inappropriate content (basic filter)
        inappropriate_words = ['admin', 'test', 'null', 'undefined']
        if any(word in value.lower() for word in inappropriate_words):
            raise serializers.ValidationError("적절하지 않은 이름입니다.")
        
        return value
    
    def validate_bio(self, value: str) -> str:
        """Validate bio content"""
        if value:
            value = value.strip()
            # Basic content filter
            if len(value) < 5:
                raise serializers.ValidationError("자기소개는 최소 5자 이상 입력해주세요.")
        return value


class UserRegistrationSerializer(serializers.ModelSerializer, PasswordValidationMixin):
    """Enhanced user registration serializer with comprehensive validation"""
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    name = serializers.CharField(max_length=100, min_length=2)
    terms_accepted = serializers.BooleanField(write_only=True)
    privacy_accepted = serializers.BooleanField(write_only=True)
    marketing_consent = serializers.BooleanField(default=False, required=False)
    
    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password_confirm', 'name',
            'terms_accepted', 'privacy_accepted', 'marketing_consent'
        ]
        extra_kwargs = {
            'email': {'validators': [EmailValidator()]},
            'username': {'min_length': 3, 'max_length': 30},
        }
    
    def validate_email(self, value: str) -> str:
        """Enhanced email validation"""
        value = value.lower().strip()
        
        # Check if email already exists
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일 주소입니다.")
        
        # Validate email format and domain
        validator = EmailValidator()
        try:
            validator(value)
        except DjangoValidationError:
            raise serializers.ValidationError("유효하지 않은 이메일 형식입니다.")
        
        # Check for disposable email domains
        disposable_domains = [
            '10minutemail.com', 'mailinator.com', 'guerrillamail.com',
            'tempmail.org', 'throwaway.email', 'temp-mail.org'
        ]
        domain = value.split('@')[1] if '@' in value else ''
        if domain in disposable_domains:
            raise serializers.ValidationError("일회용 이메일 주소는 사용할 수 없습니다.")
        
        return value
    
    def validate_username(self, value: str) -> str:
        """Enhanced username validation"""
        value = value.strip()
        
        # Check if username already exists
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 사용자명입니다.")
        
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_]+$', value):
            raise serializers.ValidationError("사용자명은 영문자, 숫자, 밑줄(_)만 사용할 수 있습니다.")
        
        # Check for reserved usernames
        reserved_usernames = [
            'admin', 'root', 'user', 'test', 'guest', 'anonymous',
            'null', 'undefined', 'system', 'administrator', 'support',
            'help', 'info', 'contact', 'api', 'www', 'mail', 'email'
        ]
        if value.lower() in reserved_usernames:
            raise serializers.ValidationError("이 사용자명은 사용할 수 없습니다.")
        
        return value
    
    def validate_password(self, value: str) -> str:
        """Validate password with enhanced rules"""
        return self.validate_password_strength(value)
    
    def validate_terms_accepted(self, value: bool) -> bool:
        """Validate terms acceptance"""
        if not value:
            raise serializers.ValidationError("이용약관에 동의해주세요.")
        return value
    
    def validate_privacy_accepted(self, value: bool) -> bool:
        """Validate privacy policy acceptance"""
        if not value:
            raise serializers.ValidationError("개인정보 처리방침에 동의해주세요.")
        return value
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "비밀번호가 일치하지 않습니다."})
        
        # Check if email and username are too similar
        email_local = attrs['email'].split('@')[0]
        if attrs['username'].lower() == email_local.lower():
            raise serializers.ValidationError({"username": "사용자명과 이메일 주소가 너무 유사합니다."})
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> User:
        """Create user with enhanced error handling and logging"""
        validated_data.pop('password_confirm')
        name = validated_data.pop('name')
        validated_data.pop('terms_accepted')
        validated_data.pop('privacy_accepted')
        marketing_consent = validated_data.pop('marketing_consent', False)
        
        try:
            # Create user
            user = User.objects.create_user(
                email=validated_data['email'],
                username=validated_data['username'],
                password=validated_data['password']
            )
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                name=name
            )
            
            # Log registration
            logger.info(f"New user registered: {user.email}")
            
            return user
            
        except Exception as e:
            logger.error(f"User registration failed: {str(e)}")
            raise serializers.ValidationError("회원가입 중 오류가 발생했습니다. 다시 시도해주세요.")


class PasswordChangeSerializer(serializers.Serializer, PasswordValidationMixin):
    """Enhanced password change serializer"""
    
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_current_password(self, value: str) -> str:
        """Validate current password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 올바르지 않습니다.")
        return value
    
    def validate_new_password(self, value: str) -> str:
        """Validate new password"""
        user = self.context['request'].user
        
        # Check if new password is same as current
        if user.check_password(value):
            raise serializers.ValidationError("새 비밀번호는 현재 비밀번호와 달라야 합니다.")
        
        return self.validate_password_strength(value)
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "새 비밀번호가 일치하지 않습니다."})
        return attrs
    
    def save(self) -> None:
        """Save password change and update timestamp"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.last_password_change = timezone.now()
        user.save(update_fields=['password', 'last_password_change'])
        
        logger.info(f"Password changed for user: {user.email}")


class EmailVerificationSerializer(serializers.Serializer):
    """Email verification serializer"""
    
    token = serializers.UUIDField(required=True)
    
    def validate_token(self, value) -> str:
        """Validate verification token"""
        try:
            token = EmailVerificationToken.objects.get(token=value)
            if not token.is_valid():
                if token.is_expired():
                    raise serializers.ValidationError("인증 토큰이 만료되었습니다.")
                else:
                    raise serializers.ValidationError("이미 사용된 토큰입니다.")
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 토큰입니다.")
        
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """Password reset request serializer"""
    
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value: str) -> str:
        """Validate email exists"""
        value = value.lower().strip()
        try:
            User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer, PasswordValidationMixin):
    """Password reset confirmation serializer"""
    
    token = serializers.UUIDField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_token(self, value) -> str:
        """Validate reset token"""
        try:
            token = PasswordResetToken.objects.get(token=value)
            if not token.is_valid():
                if token.is_expired():
                    raise serializers.ValidationError("재설정 토큰이 만료되었습니다.")
                else:
                    raise serializers.ValidationError("이미 사용된 토큰입니다.")
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 토큰입니다.")
        
        return value
    
    def validate_new_password(self, value: str) -> str:
        """Validate new password"""
        return self.validate_password_strength(value)
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-field validation"""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password_confirm": "비밀번호가 일치하지 않습니다."})
        return attrs


class LoginHistorySerializer(serializers.ModelSerializer):
    """Login history serializer"""
    
    status = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    
    class Meta:
        model = LoginHistory
        fields = [
            'id', 'ip_address', 'user_agent', 'success', 'status',
            'failure_reason', 'location', 'created_at', 'formatted_date'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_status(self, obj: LoginHistory) -> str:
        """Get login status in Korean"""
        return "성공" if obj.success else "실패"
    
    def get_formatted_date(self, obj: LoginHistory) -> str:
        """Get formatted date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S')


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user information serializer for admin"""
    
    profile = UserProfileSerializer(read_only=True)
    login_history = LoginHistorySerializer(many=True, read_only=True)
    account_status = serializers.SerializerMethodField()
    security_info = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'is_active', 'is_email_verified', 'date_joined', 'last_login',
            'last_activity', 'failed_login_attempts', 'account_locked_until',
            'is_2fa_enabled', 'privacy_level', 'profile', 'login_history',
            'account_status', 'security_info'
        ]
        read_only_fields = '__all__'
    
    def get_account_status(self, obj: User) -> Dict[str, Any]:
        """Get account status information"""
        return {
            'is_locked': obj.is_account_locked(),
            'needs_password_change': obj.needs_password_change(),
            'failed_attempts': obj.failed_login_attempts,
            'email_verified': obj.is_email_verified,
            'two_factor_enabled': obj.is_2fa_enabled,
        }
    
    def get_security_info(self, obj: User) -> Dict[str, Any]:
        """Get security information"""
        recent_logins = obj.login_history.filter(success=True)[:5]
        return {
            'last_password_change': obj.last_password_change.isoformat() if obj.last_password_change else None,
            'recent_successful_logins': recent_logins.count(),
            'last_failed_login': obj.login_history.filter(success=False).first().created_at.isoformat() if obj.login_history.filter(success=False).exists() else None,
        }