from django.db import models
from django.conf import settings
from django.utils import timezone
from study.models import Subject


class NotificationSchedule(models.Model):
    STATUS_CHOICES = [
        ('active', '활성'),
        ('paused', '일시정지'),
        ('inactive', '비활성'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_schedules')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    notification_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'subject', 'notification_time']

    def __str__(self):
        return f"{self.user.email} - {self.subject.name} at {self.notification_time}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('study_summary', '학습 요약'),
        ('quiz_available', '퀴즈 이용 가능'),
        ('subscription_reminder', '구독 알림'),
        ('achievement', '성취 알림'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '대기중'),
        ('sent', '발송완료'),
        ('failed', '발송실패'),
        ('read', '읽음'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.user.email} - {self.title} ({self.get_status_display()})"

    def mark_as_read(self):
        if self.status == 'sent':
            self.status = 'read'
            self.read_at = timezone.now()
            self.save()


class DeviceToken(models.Model):
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.get_platform_display()}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    study_summary_enabled = models.BooleanField(default=True)
    quiz_reminder_enabled = models.BooleanField(default=True)
    subscription_reminder_enabled = models.BooleanField(default=True)
    achievement_enabled = models.BooleanField(default=True)
    push_notification_enabled = models.BooleanField(default=True)
    email_notification_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} Notification Preferences"
