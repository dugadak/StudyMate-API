from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta, datetime, time
from typing import Dict, Any, Optional, List
import logging
import json

from study.models import Subject

logger = logging.getLogger(__name__)


class NotificationTemplate(models.Model):
    """Enhanced Notification Template model for reusable notification content"""
    
    TEMPLATE_TYPES = [
        ('study_summary', '학습 요약'),
        ('quiz_reminder', '퀴즈 리마인더'),
        ('subscription_reminder', '구독 알림'),
        ('achievement', '성취 알림'),
        ('welcome', '환영 메시지'),
        ('study_streak', '학습 연속 기록'),
        ('goal_reminder', '목표 리마인더'),
        ('weekly_report', '주간 리포트'),
        ('monthly_report', '월간 리포트'),
        ('custom', '사용자 정의'),
    ]
    
    name = models.CharField(max_length=100, db_index=True)
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, db_index=True)
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    variables = models.JSONField(
        default=list,
        help_text="사용 가능한 변수 목록 (예: ['user_name', 'subject_name'])"
    )
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-10), MaxValueValidator(10)],
        help_text="알림 우선순위 (-10: 낮음, 0: 보통, 10: 높음)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'name']
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['priority', 'is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, context: Dict[str, Any]) -> tuple[str, str]:
        """Render template with context variables"""
        title = self.title_template
        message = self.message_template
        
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            message = message.replace(placeholder, str(value))
        
        return title, message
    
    def validate_variables(self, context: Dict[str, Any]) -> bool:
        """Validate that all required variables are provided"""
        for variable in self.variables:
            if variable not in context:
                return False
        return True


class NotificationSchedule(models.Model):
    """Enhanced Notification Schedule model with comprehensive scheduling options"""
    
    STATUS_CHOICES = [
        ('active', '활성'),
        ('paused', '일시정지'),
        ('inactive', '비활성'),
        ('expired', '만료'),
    ]
    
    RECURRENCE_TYPES = [
        ('once', '한 번'),
        ('daily', '매일'),
        ('weekly', '매주'),
        ('monthly', '매월'),
        ('weekdays', '평일만'),
        ('weekends', '주말만'),
        ('custom', '사용자 정의'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notification_schedules',
        db_index=True
    )
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="특정 과목에 대한 알림 (null이면 전체)"
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    notification_time = models.TimeField()
    recurrence_type = models.CharField(
        max_length=20, 
        choices=RECURRENCE_TYPES, 
        default='daily'
    )
    days_of_week = models.JSONField(
        default=list,
        help_text="요일 목록 (0=월요일, 6=일요일)"
    )
    start_date = models.DateField(default=timezone.now().date)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    timezone_name = models.CharField(
        max_length=50, 
        default='Asia/Seoul',
        help_text="사용자 시간대"
    )
    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    send_count = models.IntegerField(default=0)
    max_sends = models.IntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="최대 발송 횟수 (null이면 무제한)"
    )
    context_data = models.JSONField(
        default=dict,
        help_text="템플릿 렌더링에 사용할 추가 데이터"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['status', 'next_scheduled_at']),
            models.Index(fields=['template', 'is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.template.name} at {self.notification_time}"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError("종료일은 시작일보다 늦어야 합니다.")
        
        if self.max_sends and self.send_count >= self.max_sends:
            raise ValidationError("최대 발송 횟수에 도달했습니다.")
    
    def calculate_next_scheduled(self) -> Optional[datetime]:
        """Calculate next scheduled time"""
        from django.utils import timezone as tz
        import pytz
        
        if not self.is_active or self.status != 'active':
            return None
        
        if self.max_sends and self.send_count >= self.max_sends:
            return None
        
        try:
            user_tz = pytz.timezone(self.timezone_name)
        except:
            user_tz = pytz.timezone('Asia/Seoul')
        
        now = tz.now()
        today = now.astimezone(user_tz).date()
        
        # Start from today or start_date, whichever is later
        start_date = max(today, self.start_date)
        
        if self.end_date and start_date > self.end_date:
            return None
        
        # Calculate next occurrence based on recurrence type
        next_date = None
        
        if self.recurrence_type == 'once':
            if self.last_sent_at:
                return None
            next_date = start_date
        
        elif self.recurrence_type == 'daily':
            next_date = start_date
        
        elif self.recurrence_type == 'weekly':
            # Find next occurrence of the same day of week
            days_ahead = (start_date.weekday() - today.weekday()) % 7
            if days_ahead == 0 and now.astimezone(user_tz).time() >= self.notification_time:
                days_ahead = 7
            next_date = today + timedelta(days=days_ahead)
        
        elif self.recurrence_type == 'monthly':
            # Same day next month
            try:
                if today.day == start_date.day and now.astimezone(user_tz).time() < self.notification_time:
                    next_date = today
                else:
                    next_month = today.replace(day=28) + timedelta(days=4)
                    next_date = next_month.replace(day=min(start_date.day, next_month.day))
            except ValueError:
                return None
        
        elif self.recurrence_type == 'weekdays':
            # Monday to Friday
            current_weekday = today.weekday()
            if current_weekday < 5:  # Monday-Friday (0-4)
                if now.astimezone(user_tz).time() < self.notification_time:
                    next_date = today
                else:
                    next_date = today + timedelta(days=1)
                    if next_date.weekday() >= 5:  # Skip weekend
                        next_date = today + timedelta(days=7 - current_weekday)
            else:  # Weekend
                next_date = today + timedelta(days=7 - current_weekday)
        
        elif self.recurrence_type == 'weekends':
            # Saturday and Sunday
            current_weekday = today.weekday()
            if current_weekday >= 5:  # Saturday-Sunday (5-6)
                if now.astimezone(user_tz).time() < self.notification_time:
                    next_date = today
                else:
                    if current_weekday == 5:  # Saturday
                        next_date = today + timedelta(days=1)
                    else:  # Sunday
                        next_date = today + timedelta(days=6)
            else:  # Weekday
                next_date = today + timedelta(days=5 - current_weekday)
        
        elif self.recurrence_type == 'custom' and self.days_of_week:
            # Custom days of week
            current_weekday = today.weekday()
            days_ahead = None
            
            for day in sorted(self.days_of_week):
                if day > current_weekday:
                    days_ahead = day - current_weekday
                    break
                elif day == current_weekday and now.astimezone(user_tz).time() < self.notification_time:
                    days_ahead = 0
                    break
            
            if days_ahead is None:
                # Next week
                days_ahead = 7 - current_weekday + min(self.days_of_week)
            
            next_date = today + timedelta(days=days_ahead)
        
        if next_date and (not self.end_date or next_date <= self.end_date):
            # Combine date and time in user timezone
            naive_dt = datetime.combine(next_date, self.notification_time)
            localized_dt = user_tz.localize(naive_dt)
            return localized_dt.astimezone(tz.utc)
        
        return None
    
    def update_next_scheduled(self) -> None:
        """Update next_scheduled_at field"""
        self.next_scheduled_at = self.calculate_next_scheduled()
        self.save(update_fields=['next_scheduled_at'])
    
    def can_send(self) -> bool:
        """Check if notification can be sent"""
        if not self.is_active or self.status != 'active':
            return False
        
        if self.max_sends and self.send_count >= self.max_sends:
            return False
        
        if self.end_date and timezone.now().date() > self.end_date:
            return False
        
        return True
    
    def mark_sent(self) -> None:
        """Mark schedule as sent and update counters"""
        self.last_sent_at = timezone.now()
        self.send_count += 1
        
        if self.max_sends and self.send_count >= self.max_sends:
            self.status = 'expired'
        
        self.update_next_scheduled()
        self.save()


class Notification(models.Model):
    """Enhanced Notification model with comprehensive tracking"""
    
    NOTIFICATION_TYPES = [
        ('study_summary', '학습 요약'),
        ('quiz_reminder', '퀴즈 리마인더'),
        ('subscription_reminder', '구독 알림'),
        ('achievement', '성취 알림'),
        ('welcome', '환영 메시지'),
        ('study_streak', '학습 연속 기록'),
        ('goal_reminder', '목표 리마인더'),
        ('weekly_report', '주간 리포트'),
        ('monthly_report', '월간 리포트'),
        ('system_alert', '시스템 알림'),
        ('custom', '사용자 정의'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('scheduled', '예약됨'),
        ('sending', '발송중'),
        ('sent', '발송완료'),
        ('failed', '발송실패'),
        ('read', '읽음'),
        ('dismissed', '무시됨'),
        ('expired', '만료됨'),
    ]
    
    CHANNEL_CHOICES = [
        ('push', '푸시 알림'),
        ('email', '이메일'),
        ('sms', 'SMS'),
        ('in_app', '인앱 알림'),
        ('webhook', '웹훅'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', '낮음'),
        ('normal', '보통'),
        ('high', '높음'),
        ('urgent', '긴급'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        db_index=True
    )
    schedule = models.ForeignKey(
        NotificationSchedule,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30, 
        choices=NOTIFICATION_TYPES,
        db_index=True
    )
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='push'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal',
        db_index=True
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        db_index=True
    )
    scheduled_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    error_message = models.TextField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    action_url = models.URLField(blank=True, help_text="알림 클릭 시 이동할 URL")
    image_url = models.URLField(blank=True, help_text="알림 이미지 URL")
    deep_link = models.CharField(
        max_length=200, 
        blank=True,
        help_text="앱 내 딥링크"
    )
    tracking_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="외부 서비스 추적 ID"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['notification_type', 'status']),
            models.Index(fields=['priority', 'scheduled_at']),
            models.Index(fields=['channel', 'status']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.title} ({self.get_status_display()})"
    
    def clean(self) -> None:
        """Model validation"""
        super().clean()
        
        if self.expired_at and self.expired_at <= timezone.now():
            raise ValidationError("만료 시간은 현재 시간보다 늦어야 합니다.")
    
    def mark_as_read(self) -> bool:
        """Mark notification as read"""
        if self.status == 'sent':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at', 'updated_at'])
            logger.info(f"Marked notification {self.id} as read for user {self.user.email}")
            return True
        return False
    
    def mark_as_dismissed(self) -> bool:
        """Mark notification as dismissed"""
        if self.status in ['sent', 'read']:
            self.status = 'dismissed'
            self.save(update_fields=['status', 'updated_at'])
            logger.info(f"Dismissed notification {self.id} for user {self.user.email}")
            return True
        return False
    
    def can_retry(self) -> bool:
        """Check if notification can be retried"""
        return (
            self.status == 'failed' and 
            self.retry_count < self.max_retries and
            (not self.expired_at or timezone.now() < self.expired_at)
        )
    
    def increment_retry(self) -> None:
        """Increment retry count"""
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.status = 'expired'
        self.save(update_fields=['retry_count', 'status', 'updated_at'])
    
    def mark_as_sent(self, tracking_id: str = None) -> None:
        """Mark notification as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        if tracking_id:
            self.tracking_id = tracking_id
        self.save(update_fields=['status', 'sent_at', 'tracking_id', 'updated_at'])
        logger.info(f"Marked notification {self.id} as sent for user {self.user.email}")
    
    def mark_as_failed(self, error_message: str) -> None:
        """Mark notification as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.increment_retry()
        logger.error(f"Notification {self.id} failed for user {self.user.email}: {error_message}")
    
    @property
    def is_expired(self) -> bool:
        """Check if notification is expired"""
        return (
            self.status == 'expired' or
            (self.expired_at and timezone.now() > self.expired_at)
        )
    
    @property
    def time_since_sent(self) -> Optional[timedelta]:
        """Get time since notification was sent"""
        if self.sent_at:
            return timezone.now() - self.sent_at
        return None


class DeviceToken(models.Model):
    """Enhanced Device Token model with comprehensive device management"""
    
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web Push'),
        ('chrome', 'Chrome'),
        ('firefox', 'Firefox'),
        ('safari', 'Safari'),
        ('edge', 'Edge'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='device_tokens',
        db_index=True
    )
    token = models.TextField(db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    device_id = models.CharField(max_length=100, blank=True, db_index=True)
    device_name = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=20, blank=True)
    os_version = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_primary = models.BooleanField(default=False)
    notification_settings = models.JSONField(
        default=dict,
        help_text="디바이스별 알림 설정"
    )
    failure_count = models.IntegerField(default=0)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'token']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['platform', 'is_active']),
            models.Index(fields=['is_primary', 'is_active']),
        ]
    
    def __str__(self) -> str:
        device_info = self.device_name or f"{self.get_platform_display()} Device"
        return f"{self.user.email} - {device_info}"
    
    def mark_as_failed(self) -> None:
        """Mark token as failed"""
        self.failure_count += 1
        self.last_failure_at = timezone.now()
        
        # Deactivate after too many failures
        if self.failure_count >= 5:
            self.is_active = False
            logger.warning(f"Deactivated device token {self.id} for user {self.user.email} due to failures")
        
        self.save(update_fields=['failure_count', 'last_failure_at', 'is_active'])
    
    def mark_as_successful(self) -> None:
        """Mark token as successful (reset failure count)"""
        if self.failure_count > 0:
            self.failure_count = 0
            self.last_failure_at = None
            self.save(update_fields=['failure_count', 'last_failure_at'])
    
    def set_as_primary(self) -> None:
        """Set this token as primary for the user"""
        # Unset other primary tokens for this user
        DeviceToken.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        self.is_primary = True
        self.save(update_fields=['is_primary'])


class NotificationPreference(models.Model):
    """Enhanced Notification Preference model with granular controls"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notification_preferences'
    )
    
    # General preferences
    push_notification_enabled = models.BooleanField(default=True)
    email_notification_enabled = models.BooleanField(default=False)
    sms_notification_enabled = models.BooleanField(default=False)
    
    # Study-related preferences
    study_summary_enabled = models.BooleanField(default=True)
    quiz_reminder_enabled = models.BooleanField(default=True)
    goal_reminder_enabled = models.BooleanField(default=True)
    study_streak_enabled = models.BooleanField(default=True)
    
    # Subscription-related preferences
    subscription_reminder_enabled = models.BooleanField(default=True)
    payment_notification_enabled = models.BooleanField(default=True)
    
    # Achievement preferences
    achievement_enabled = models.BooleanField(default=True)
    milestone_enabled = models.BooleanField(default=True)
    
    # Report preferences
    weekly_report_enabled = models.BooleanField(default=True)
    monthly_report_enabled = models.BooleanField(default=True)
    
    # Marketing preferences
    promotional_enabled = models.BooleanField(default=False)
    newsletter_enabled = models.BooleanField(default=False)
    
    # Timing preferences
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start_time = models.TimeField(default=time(22, 0))  # 10 PM
    quiet_end_time = models.TimeField(default=time(8, 0))     # 8 AM
    timezone_name = models.CharField(max_length=50, default='Asia/Seoul')
    
    # Frequency preferences
    max_daily_notifications = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    min_interval_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
        help_text="알림 간 최소 간격 (분)"
    )
    
    # Channel preferences per notification type
    channel_preferences = models.JSONField(
        default=dict,
        help_text="알림 타입별 채널 설정 (예: {'study_summary': ['push', 'email']})"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self) -> str:
        return f"{self.user.email} Notification Preferences"
    
    def is_notification_allowed(self, notification_type: str, channel: str = 'push') -> bool:
        """Check if specific notification type and channel is allowed"""
        # Check general channel settings
        if channel == 'push' and not self.push_notification_enabled:
            return False
        elif channel == 'email' and not self.email_notification_enabled:
            return False
        elif channel == 'sms' and not self.sms_notification_enabled:
            return False
        
        # Check specific notification type settings
        type_setting_map = {
            'study_summary': self.study_summary_enabled,
            'quiz_reminder': self.quiz_reminder_enabled,
            'goal_reminder': self.goal_reminder_enabled,
            'study_streak': self.study_streak_enabled,
            'subscription_reminder': self.subscription_reminder_enabled,
            'achievement': self.achievement_enabled,
            'weekly_report': self.weekly_report_enabled,
            'monthly_report': self.monthly_report_enabled,
        }
        
        if notification_type in type_setting_map:
            if not type_setting_map[notification_type]:
                return False
        
        # Check channel preferences for specific type
        if self.channel_preferences:
            type_channels = self.channel_preferences.get(notification_type, [channel])
            if channel not in type_channels:
                return False
        
        return True
    
    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled:
            return False
        
        try:
            import pytz
            user_tz = pytz.timezone(self.timezone_name)
            current_time = timezone.now().astimezone(user_tz).time()
            
            if self.quiet_start_time <= self.quiet_end_time:
                # Same day (e.g., 10 PM to 11 PM)
                return self.quiet_start_time <= current_time <= self.quiet_end_time
            else:
                # Across midnight (e.g., 10 PM to 8 AM)
                return current_time >= self.quiet_start_time or current_time <= self.quiet_end_time
        except:
            return False
    
    def get_preferred_channels(self, notification_type: str) -> List[str]:
        """Get preferred channels for a notification type"""
        if self.channel_preferences and notification_type in self.channel_preferences:
            return self.channel_preferences[notification_type]
        
        # Default channels based on enabled settings
        channels = []
        if self.push_notification_enabled:
            channels.append('push')
        if self.email_notification_enabled:
            channels.append('email')
        if self.sms_notification_enabled:
            channels.append('sms')
        
        return channels or ['push']  # Fallback to push


class NotificationBatch(models.Model):
    """Model for tracking batch notification operations"""
    
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('processing', '처리중'),
        ('completed', '완료'),
        ('failed', '실패'),
        ('partially_failed', '부분 실패'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    filters = models.JSONField(
        default=dict,
        help_text="사용자 필터링 조건"
    )
    context_data = models.JSONField(
        default=dict,
        help_text="템플릿 렌더링용 공통 데이터"
    )
    scheduled_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_batches'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_count == 0:
            return 0.0
        return (self.sent_count / self.total_count) * 100
    
    def mark_as_started(self) -> None:
        """Mark batch as started"""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_as_completed(self) -> None:
        """Mark batch as completed"""
        if self.failed_count > 0 and self.sent_count > 0:
            self.status = 'partially_failed'
        elif self.failed_count > 0:
            self.status = 'failed'
        else:
            self.status = 'completed'
        
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def increment_sent(self) -> None:
        """Increment sent count"""
        self.sent_count = models.F('sent_count') + 1
        self.save(update_fields=['sent_count'])
    
    def increment_failed(self) -> None:
        """Increment failed count"""
        self.failed_count = models.F('failed_count') + 1
        self.save(update_fields=['failed_count'])