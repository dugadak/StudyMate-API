from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from typing import Optional
from datetime import timedelta
import uuid


class User(AbstractUser):
    """Enhanced User model with additional security features"""

    email = models.EmailField(unique=True, help_text="사용자의 이메일 주소 (로그인 ID)")

    # Security fields
    is_email_verified = models.BooleanField(default=False, help_text="이메일 인증 완료 여부")
    failed_login_attempts = models.PositiveIntegerField(default=0, help_text="연속 로그인 실패 횟수")
    account_locked_until = models.DateTimeField(null=True, blank=True, help_text="계정 잠금 해제 시간")
    last_password_change = models.DateTimeField(auto_now_add=True, help_text="마지막 비밀번호 변경 시간")

    # Two-factor authentication
    is_2fa_enabled = models.BooleanField(default=False, help_text="2단계 인증 활성화 여부")
    backup_tokens = models.JSONField(default=list, blank=True, help_text="2FA 백업 토큰들")

    # Privacy and preferences
    privacy_level = models.CharField(
        max_length=20,
        choices=[
            ("public", "공개"),
            ("friends", "친구만"),
            ("private", "비공개"),
        ],
        default="public",
        help_text="프로필 공개 범위",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "auth_user"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "is_email_verified"]),
            models.Index(fields=["last_activity"]),
            models.Index(fields=["account_locked_until"]),
        ]
        verbose_name = "사용자"
        verbose_name_plural = "사용자들"

    def __str__(self) -> str:
        return f"{self.email} ({self.username})"

    def is_account_locked(self) -> bool:
        """계정이 잠겨있는지 확인"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False

    def lock_account(self, duration_minutes: int = 30) -> None:
        """계정을 지정된 시간동안 잠금"""
        self.account_locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=["account_locked_until"])

    def unlock_account(self) -> None:
        """계정 잠금 해제"""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=["account_locked_until", "failed_login_attempts"])

    def increment_failed_login(self) -> None:
        """로그인 실패 횟수 증가"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:  # 5회 실패시 30분 잠금
            self.lock_account(30)
        self.save(update_fields=["failed_login_attempts"])

    def reset_failed_login(self) -> None:
        """로그인 실패 횟수 초기화"""
        self.failed_login_attempts = 0
        self.save(update_fields=["failed_login_attempts"])

    def needs_password_change(self) -> bool:
        """비밀번호 변경이 필요한지 확인 (90일 경과)"""
        if not self.last_password_change:
            return True
        return timezone.now() - self.last_password_change > timedelta(days=90)

    def update_last_activity(self) -> None:
        """마지막 활동 시간 업데이트"""
        self.last_activity = timezone.now()
        self.save(update_fields=["last_activity"])


class UserProfile(models.Model):
    """Extended user profile with additional information"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=100, help_text="사용자 실명")
    bio = models.TextField(blank=True, null=True, max_length=500, help_text="자기소개 (최대 500자)")
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True, help_text="프로필 이미지")

    # Contact information
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(regex=r"^\+?1?\d{9,15}$", message="올바른 전화번호 형식이 아닙니다.")],
        help_text="연락처 전화번호",
    )

    # Location
    country = models.CharField(max_length=100, blank=True, help_text="거주 국가")
    timezone = models.CharField(max_length=50, default="Asia/Seoul", help_text="사용자 시간대")

    # Preferences
    language = models.CharField(
        max_length=10,
        choices=[
            ("ko", "한국어"),
            ("en", "English"),
            ("ja", "日本語"),
        ],
        default="ko",
        help_text="선호 언어",
    )
    theme = models.CharField(
        max_length=20,
        choices=[
            ("light", "라이트 모드"),
            ("dark", "다크 모드"),
            ("auto", "자동"),
        ],
        default="light",
        help_text="테마 설정",
    )

    # Statistics
    total_study_time = models.DurationField(default=timedelta(0), help_text="총 학습 시간")
    streak_days = models.PositiveIntegerField(default=0, help_text="연속 학습 일수")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_userprofile"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["name"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필들"

    def __str__(self) -> str:
        return f"{self.name} ({self.user.email})"

    def get_display_name(self) -> str:
        """표시할 이름 반환"""
        return self.name or self.user.username or self.user.email.split("@")[0]

    def update_study_streak(self) -> None:
        """학습 연속일수 업데이트"""
        # 구현은 study 앱에서 호출
        pass


class EmailVerificationToken(models.Model):
    """Email verification token model"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_email_verification_token"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "이메일 인증 토큰"
        verbose_name_plural = "이메일 인증 토큰들"

    def __str__(self) -> str:
        return f"Email verification for {self.user.email}"

    def is_expired(self) -> bool:
        """토큰이 만료되었는지 확인"""
        return timezone.now() > self.expires_at

    def is_valid(self) -> bool:
        """토큰이 유효한지 확인"""
        return not self.is_used and not self.is_expired()

    def mark_as_used(self) -> None:
        """토큰을 사용됨으로 표시"""
        self.is_used = True
        self.save(update_fields=["is_used"])


class PasswordResetToken(models.Model):
    """Password reset token model"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="요청한 IP 주소")

    class Meta:
        db_table = "accounts_password_reset_token"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["user", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]
        verbose_name = "비밀번호 재설정 토큰"
        verbose_name_plural = "비밀번호 재설정 토큰들"

    def __str__(self) -> str:
        return f"Password reset for {self.user.email}"

    def is_expired(self) -> bool:
        """토큰이 만료되었는지 확인"""
        return timezone.now() > self.expires_at

    def is_valid(self) -> bool:
        """토큰이 유효한지 확인"""
        return not self.is_used and not self.is_expired()

    def mark_as_used(self) -> None:
        """토큰을 사용됨으로 표시"""
        self.is_used = True
        self.save(update_fields=["is_used"])


class LoginHistory(models.Model):
    """User login history tracking"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_history")
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField()
    failure_reason = models.CharField(max_length=100, blank=True, help_text="로그인 실패 사유")
    location = models.CharField(max_length=100, blank=True, help_text="접속 위치 (대략적)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_login_history"
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address"]),
            models.Index(fields=["success"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "로그인 기록"
        verbose_name_plural = "로그인 기록들"

    def __str__(self) -> str:
        status = "성공" if self.success else "실패"
        return f"{self.user.email} - {status} ({self.created_at})"
