from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db import models
from django.forms import Textarea
from typing import Any, Optional
import logging

from .models import (
    User, UserProfile, EmailVerificationToken, 
    PasswordResetToken, LoginHistory
)

logger = logging.getLogger(__name__)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = '프로필 정보'
    extra = 0
    
    fields = (
        'name', 'bio', 'avatar', 'phone_number', 'country', 
        'timezone', 'language', 'theme', 'total_study_time', 'streak_days'
    )
    readonly_fields = ('total_study_time', 'streak_days')


class LoginHistoryInline(admin.TabularInline):
    """Inline admin for LoginHistory"""
    model = LoginHistory
    extra = 0
    max_num = 10
    can_delete = False
    readonly_fields = (
        'ip_address', 'user_agent', 'success', 'failure_reason', 
        'location', 'created_at'
    )
    fields = readonly_fields
    ordering = ('-created_at',)
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with additional fields and security features"""
    
    list_display = [
        'email', 'username', 'name_link', 'is_verified_status', 
        'account_status', 'last_activity', 'date_joined'
    ]
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 'is_email_verified',
        'is_2fa_enabled', 'privacy_level', 'date_joined', 'last_login'
    ]
    search_fields = ['email', 'username', 'first_name', 'last_name', 'profile__name']
    ordering = ['-date_joined']
    readonly_fields = [
        'date_joined', 'last_login', 'last_activity', 'created_at', 
        'updated_at', 'account_lock_status', 'security_summary'
    ]
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('개인정보', {
            'fields': ('username', 'first_name', 'last_name')
        }),
        ('권한', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 
                'groups', 'user_permissions'
            )
        }),
        ('보안 설정', {
            'fields': (
                'is_email_verified', 'is_2fa_enabled', 'privacy_level',
                'failed_login_attempts', 'account_locked_until',
                'last_password_change', 'account_lock_status'
            )
        }),
        ('활동 기록', {
            'fields': (
                'last_login', 'last_activity', 'date_joined', 
                'created_at', 'updated_at'
            )
        }),
        ('보안 요약', {
            'fields': ('security_summary',),
            'classes': ('collapse',),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
        ('추가 정보', {
            'fields': ('first_name', 'last_name', 'is_email_verified'),
        }),
    )
    
    inlines = [UserProfileInline, LoginHistoryInline]
    
    actions = [
        'unlock_accounts', 'lock_accounts', 'verify_emails', 
        'force_password_change', 'export_user_data'
    ]
    
    def name_link(self, obj: User) -> str:
        """Display profile name with link"""
        try:
            name = obj.profile.name
            url = reverse('admin:accounts_userprofile_change', args=[obj.profile.pk])
            return format_html('<a href="{}">{}</a>', url, name)
        except:
            return '-'
    name_link.short_description = '이름'
    name_link.admin_order_field = 'profile__name'
    
    def is_verified_status(self, obj: User) -> str:
        """Display email verification status"""
        if obj.is_email_verified:
            return format_html(
                '<span style="color: green;">✓ 인증됨</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ 미인증</span>'
            )
    is_verified_status.short_description = '이메일 인증'
    is_verified_status.admin_order_field = 'is_email_verified'
    
    def account_status(self, obj: User) -> str:
        """Display account status"""
        if not obj.is_active:
            return format_html('<span style="color: red;">비활성</span>')
        elif obj.is_account_locked():
            return format_html('<span style="color: orange;">잠김</span>')
        elif obj.failed_login_attempts > 0:
            return format_html(
                '<span style="color: orange;">주의 ({}회 실패)</span>', 
                obj.failed_login_attempts
            )
        else:
            return format_html('<span style="color: green;">정상</span>')
    account_status.short_description = '계정 상태'
    
    def account_lock_status(self, obj: User) -> str:
        """Display detailed account lock status"""
        if obj.is_account_locked():
            return format_html(
                '<span style="color: red;">잠김 ({}까지)</span>',
                obj.account_locked_until.strftime('%Y-%m-%d %H:%M:%S') if obj.account_locked_until else ''
            )
        else:
            return format_html('<span style="color: green;">정상</span>')
    account_lock_status.short_description = '계정 잠금 상태'
    
    def security_summary(self, obj: User) -> str:
        """Display security summary"""
        recent_logins = obj.login_history.filter(success=True)[:5]
        failed_logins = obj.login_history.filter(success=False).count()
        
        summary = f"""
        <strong>보안 요약:</strong><br>
        • 이메일 인증: {'완료' if obj.is_email_verified else '미완료'}<br>
        • 2FA 설정: {'활성' if obj.is_2fa_enabled else '비활성'}<br>
        • 실패한 로그인: {failed_logins}회<br>
        • 최근 성공 로그인: {recent_logins.count()}회<br>
        • 마지막 비밀번호 변경: {obj.last_password_change.strftime('%Y-%m-%d') if obj.last_password_change else '알 수 없음'}<br>
        • 비밀번호 변경 필요: {'예' if obj.needs_password_change() else '아니오'}
        """
        return format_html(summary)
    security_summary.short_description = '보안 요약'
    
    def unlock_accounts(self, request, queryset):
        """Admin action to unlock accounts"""
        count = 0
        for user in queryset:
            if user.is_account_locked():
                user.unlock_account()
                count += 1
        
        self.message_user(
            request, 
            f'{count}개의 계정이 잠금 해제되었습니다.'
        )
        logger.info(f"Admin {request.user.email} unlocked {count} accounts")
    unlock_accounts.short_description = '선택된 계정 잠금 해제'
    
    def lock_accounts(self, request, queryset):
        """Admin action to lock accounts"""
        count = 0
        for user in queryset.filter(is_active=True):
            if not user.is_account_locked():
                user.lock_account(duration_minutes=60)  # 1시간 잠금
                count += 1
        
        self.message_user(
            request, 
            f'{count}개의 계정이 1시간 동안 잠금되었습니다.'
        )
        logger.warning(f"Admin {request.user.email} locked {count} accounts")
    lock_accounts.short_description = '선택된 계정 1시간 잠금'
    
    def verify_emails(self, request, queryset):
        """Admin action to verify emails"""
        count = queryset.filter(is_email_verified=False).update(is_email_verified=True)
        self.message_user(
            request, 
            f'{count}개의 이메일이 인증되었습니다.'
        )
        logger.info(f"Admin {request.user.email} verified {count} emails")
    verify_emails.short_description = '선택된 사용자 이메일 인증'
    
    def force_password_change(self, request, queryset):
        """Admin action to force password change"""
        count = queryset.update(
            last_password_change=timezone.now() - timezone.timedelta(days=91)
        )
        self.message_user(
            request, 
            f'{count}명의 사용자에게 비밀번호 변경이 필요하도록 설정되었습니다.'
        )
        logger.info(f"Admin {request.user.email} forced password change for {count} users")
    force_password_change.short_description = '비밀번호 변경 강제'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related('profile').prefetch_related('login_history')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Enhanced UserProfile admin"""
    
    list_display = [
        'user_email', 'name', 'country', 'language', 'theme',
        'study_stats', 'created_at'
    ]
    list_filter = ['country', 'language', 'theme', 'created_at']
    search_fields = ['user__email', 'name', 'country']
    readonly_fields = ['created_at', 'updated_at', 'study_stats_detail']
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('user', 'name', 'bio', 'avatar')
        }),
        ('연락처', {
            'fields': ('phone_number', 'country', 'timezone')
        }),
        ('설정', {
            'fields': ('language', 'theme')
        }),
        ('학습 통계', {
            'fields': ('total_study_time', 'streak_days', 'study_stats_detail'),
            'classes': ('collapse',),
        }),
        ('메타데이터', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj: UserProfile) -> str:
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자 이메일'
    user_email.admin_order_field = 'user__email'
    
    def study_stats(self, obj: UserProfile) -> str:
        """Display study statistics"""
        hours = obj.total_study_time.total_seconds() / 3600 if obj.total_study_time else 0
        return f"{hours:.1f}시간, {obj.streak_days}일 연속"
    study_stats.short_description = '학습 통계'
    
    def study_stats_detail(self, obj: UserProfile) -> str:
        """Display detailed study statistics"""
        hours = obj.total_study_time.total_seconds() / 3600 if obj.total_study_time else 0
        
        stats = f"""
        <strong>상세 학습 통계:</strong><br>
        • 총 학습 시간: {hours:.2f}시간<br>
        • 연속 학습 일수: {obj.streak_days}일<br>
        • 평균 일일 학습: {(hours / max(obj.streak_days, 1)):.2f}시간
        """
        return format_html(stats)
    study_stats_detail.short_description = '상세 학습 통계'


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """LoginHistory admin"""
    
    list_display = [
        'user_email', 'ip_address', 'success_status', 'failure_reason',
        'location', 'created_at'
    ]
    list_filter = ['success', 'created_at', 'failure_reason']
    search_fields = ['user__email', 'ip_address', 'location']
    readonly_fields = ['user', 'ip_address', 'user_agent', 'success', 'failure_reason', 'location', 'created_at']
    ordering = ['-created_at']
    
    date_hierarchy = 'created_at'
    
    def user_email(self, obj: LoginHistory) -> str:
        """Display user email"""
        return obj.user.email if obj.user else '알 수 없음'
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def success_status(self, obj: LoginHistory) -> str:
        """Display success status with color"""
        if obj.success:
            return format_html('<span style="color: green;">성공</span>')
        else:
            return format_html('<span style="color: red;">실패</span>')
    success_status.short_description = '상태'
    success_status.admin_order_field = 'success'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    """EmailVerificationToken admin"""
    
    list_display = ['user_email', 'token_short', 'status', 'created_at', 'expires_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__email', 'token']
    readonly_fields = ['user', 'token', 'created_at', 'expires_at', 'status_detail']
    
    def user_email(self, obj: EmailVerificationToken) -> str:
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def token_short(self, obj: EmailVerificationToken) -> str:
        """Display shortened token"""
        return f"{str(obj.token)[:8]}..."
    token_short.short_description = '토큰'
    
    def status(self, obj: EmailVerificationToken) -> str:
        """Display token status"""
        if obj.is_used:
            return format_html('<span style="color: blue;">사용됨</span>')
        elif obj.is_expired():
            return format_html('<span style="color: red;">만료됨</span>')
        else:
            return format_html('<span style="color: green;">유효함</span>')
    status.short_description = '상태'
    
    def status_detail(self, obj: EmailVerificationToken) -> str:
        """Display detailed status"""
        status_text = "사용됨" if obj.is_used else ("만료됨" if obj.is_expired() else "유효함")
        return f"상태: {status_text}"
    status_detail.short_description = '상태 상세'
    
    def has_add_permission(self, request):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    """PasswordResetToken admin"""
    
    list_display = ['user_email', 'token_short', 'status', 'ip_address', 'created_at', 'expires_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__email', 'token', 'ip_address']
    readonly_fields = ['user', 'token', 'created_at', 'expires_at', 'ip_address', 'status_detail']
    
    def user_email(self, obj: PasswordResetToken) -> str:
        """Display user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    user_email.admin_order_field = 'user__email'
    
    def token_short(self, obj: PasswordResetToken) -> str:
        """Display shortened token"""
        return f"{str(obj.token)[:8]}..."
    token_short.short_description = '토큰'
    
    def status(self, obj: PasswordResetToken) -> str:
        """Display token status"""
        if obj.is_used:
            return format_html('<span style="color: blue;">사용됨</span>')
        elif obj.is_expired():
            return format_html('<span style="color: red;">만료됨</span>')
        else:
            return format_html('<span style="color: green;">유효함</span>')
    status.short_description = '상태'
    
    def status_detail(self, obj: PasswordResetToken) -> str:
        """Display detailed status"""
        status_text = "사용됨" if obj.is_used else ("만료됨" if obj.is_expired() else "유효함")
        return f"상태: {status_text}, IP: {obj.ip_address or '알 수 없음'}"
    status_detail.short_description = '상태 상세'
    
    def has_add_permission(self, request):
        return False


# Customize admin site
admin.site.site_header = 'StudyMate 관리자'
admin.site.site_title = 'StudyMate Admin'
admin.site.index_title = 'StudyMate 관리 대시보드'