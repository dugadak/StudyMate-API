from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import (
    NotificationTemplate, NotificationSchedule, Notification,
    DeviceToken, NotificationPreference, NotificationBatch
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Enhanced admin for Notification Templates"""
    
    list_display = [
        'name', 'template_type', 'priority', 'is_active', 
        'usage_count', 'created_at'
    ]
    list_filter = ['template_type', 'is_active', 'priority', 'created_at']
    search_fields = ['name', 'title_template', 'message_template']
    ordering = ['-priority', 'name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('기본 정보', {
            'fields': ['name', 'template_type', 'priority', 'is_active']
        }),
        ('템플릿 내용', {
            'fields': ['title_template', 'message_template', 'variables']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def usage_count(self, obj):
        """Get template usage count"""
        count = obj.schedules.count()
        return format_html(
            '<span style="color: {};">{}</span>',
            'green' if count > 0 else 'gray',
            count
        )
    usage_count.short_description = '사용 횟수'
    
    def get_queryset(self, request):
        """Optimize queryset with prefetch"""
        return super().get_queryset(request).prefetch_related('schedules')


@admin.register(NotificationSchedule)
class NotificationScheduleAdmin(admin.ModelAdmin):
    """Enhanced admin for Notification Schedules"""
    
    list_display = [
        'user_email', 'template_name', 'status', 'recurrence_type',
        'next_scheduled_display', 'send_count', 'is_active'
    ]
    list_filter = [
        'status', 'recurrence_type', 'is_active', 'template__template_type',
        'created_at'
    ]
    search_fields = [
        'user__email', 'template__name', 'subject__name'
    ]
    ordering = ['-created_at']
    readonly_fields = [
        'last_sent_at', 'next_scheduled_at', 'send_count', 
        'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('기본 정보', {
            'fields': ['user', 'template', 'subject', 'is_active', 'status']
        }),
        ('스케줄 설정', {
            'fields': [
                'notification_time', 'recurrence_type', 'days_of_week',
                'start_date', 'end_date', 'timezone_name'
            ]
        }),
        ('제한 설정', {
            'fields': ['max_sends', 'context_data']
        }),
        ('실행 정보', {
            'fields': [
                'last_sent_at', 'next_scheduled_at', 'send_count'
            ],
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def user_email(self, obj):
        """Get user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    
    def template_name(self, obj):
        """Get template name with link"""
        url = reverse('admin:notifications_notificationtemplate_change', 
                     args=[obj.template.id])
        return format_html('<a href="{}">{}</a>', url, obj.template.name)
    template_name.short_description = '템플릿'
    
    def next_scheduled_display(self, obj):
        """Display next scheduled time with color coding"""
        if not obj.next_scheduled_at:
            return format_html('<span style="color: gray;">없음</span>')
        
        now = timezone.now()
        if obj.next_scheduled_at <= now:
            color = 'red'
            text = f'지연됨 ({obj.next_scheduled_at.strftime("%m/%d %H:%M")})'
        elif obj.next_scheduled_at <= now + timedelta(hours=1):
            color = 'orange'
            text = f'곧 실행 ({obj.next_scheduled_at.strftime("%m/%d %H:%M")})'
        else:
            color = 'green'
            text = obj.next_scheduled_at.strftime("%m/%d %H:%M")
        
        return format_html('<span style="color: {};">{}</span>', color, text)
    next_scheduled_display.short_description = '다음 실행'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'template', 'subject'
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Enhanced admin for Notifications"""
    
    list_display = [
        'user_email', 'title_short', 'notification_type', 'channel',
        'status_display', 'priority', 'scheduled_at', 'sent_at'
    ]
    list_filter = [
        'notification_type', 'channel', 'status', 'priority',
        'scheduled_at', 'created_at'
    ]
    search_fields = ['user__email', 'title', 'message']
    ordering = ['-created_at']
    readonly_fields = [
        'sent_at', 'delivered_at', 'read_at', 'expired_at',
        'retry_count', 'error_message', 'tracking_id',
        'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('기본 정보', {
            'fields': ['user', 'schedule', 'notification_type', 'channel', 'priority']
        }),
        ('내용', {
            'fields': ['title', 'message', 'action_url', 'image_url', 'deep_link']
        }),
        ('스케줄링', {
            'fields': ['scheduled_at', 'expired_at']
        }),
        ('상태 정보', {
            'fields': [
                'status', 'sent_at', 'delivered_at', 'read_at',
                'retry_count', 'max_retries', 'error_message', 'tracking_id'
            ],
            'classes': ['collapse']
        }),
        ('추가 데이터', {
            'fields': ['extra_data'],
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def user_email(self, obj):
        """Get user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    
    def title_short(self, obj):
        """Get shortened title"""
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = '제목'
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': 'orange',
            'scheduled': 'blue',
            'sending': 'purple',
            'sent': 'green',
            'failed': 'red',
            'read': 'darkgreen',
            'dismissed': 'gray',
            'expired': 'darkgray'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = '상태'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'schedule__template'
        )


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    """Enhanced admin for Device Tokens"""
    
    list_display = [
        'user_email', 'device_name_display', 'platform', 'is_active',
        'is_primary', 'failure_count', 'last_used_at'
    ]
    list_filter = ['platform', 'is_active', 'is_primary', 'created_at']
    search_fields = ['user__email', 'device_name', 'device_id']
    ordering = ['-last_used_at']
    readonly_fields = [
        'failure_count', 'last_failure_at', 'created_at', 'last_used_at'
    ]
    
    fieldsets = [
        ('기본 정보', {
            'fields': ['user', 'token', 'platform', 'is_active', 'is_primary']
        }),
        ('디바이스 정보', {
            'fields': ['device_id', 'device_name', 'app_version', 'os_version']
        }),
        ('설정', {
            'fields': ['notification_settings']
        }),
        ('상태 정보', {
            'fields': ['failure_count', 'last_failure_at'],
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'last_used_at'],
            'classes': ['collapse']
        })
    ]
    
    def user_email(self, obj):
        """Get user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    
    def device_name_display(self, obj):
        """Display device name with health indicator"""
        name = obj.device_name or f"{obj.get_platform_display()} Device"
        if obj.failure_count >= 3:
            name += ' ⚠️'
        elif obj.is_primary:
            name += ' ⭐'
        return name
    device_name_display.short_description = '디바이스'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Enhanced admin for Notification Preferences"""
    
    list_display = [
        'user_email', 'push_enabled', 'email_enabled', 'sms_enabled',
        'quiet_hours_enabled', 'max_daily_notifications'
    ]
    list_filter = [
        'push_notification_enabled', 'email_notification_enabled',
        'sms_notification_enabled', 'quiet_hours_enabled'
    ]
    search_fields = ['user__email']
    ordering = ['user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('사용자', {
            'fields': ['user']
        }),
        ('채널 설정', {
            'fields': [
                'push_notification_enabled', 'email_notification_enabled',
                'sms_notification_enabled'
            ]
        }),
        ('알림 타입 설정', {
            'fields': [
                'study_summary_enabled', 'quiz_reminder_enabled',
                'goal_reminder_enabled', 'study_streak_enabled',
                'subscription_reminder_enabled', 'payment_notification_enabled',
                'achievement_enabled', 'milestone_enabled',
                'weekly_report_enabled', 'monthly_report_enabled'
            ]
        }),
        ('마케팅 설정', {
            'fields': ['promotional_enabled', 'newsletter_enabled']
        }),
        ('시간 설정', {
            'fields': [
                'quiet_hours_enabled', 'quiet_start_time', 'quiet_end_time',
                'timezone_name'
            ]
        }),
        ('빈도 설정', {
            'fields': ['max_daily_notifications', 'min_interval_minutes']
        }),
        ('고급 설정', {
            'fields': ['channel_preferences'],
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def user_email(self, obj):
        """Get user email"""
        return obj.user.email
    user_email.short_description = '사용자'
    
    def push_enabled(self, obj):
        """Push notification status"""
        return '✓' if obj.push_notification_enabled else '✗'
    push_enabled.short_description = '푸시'
    
    def email_enabled(self, obj):
        """Email notification status"""
        return '✓' if obj.email_notification_enabled else '✗'
    email_enabled.short_description = '이메일'
    
    def sms_enabled(self, obj):
        """SMS notification status"""
        return '✓' if obj.sms_notification_enabled else '✗'
    sms_enabled.short_description = 'SMS'


@admin.register(NotificationBatch)
class NotificationBatchAdmin(admin.ModelAdmin):
    """Enhanced admin for Notification Batches"""
    
    list_display = [
        'name', 'status_display', 'total_count', 'sent_count',
        'failed_count', 'success_rate_display', 'created_by_email',
        'scheduled_at'
    ]
    list_filter = ['status', 'scheduled_at', 'created_at']
    search_fields = ['name', 'description', 'created_by__email']
    ordering = ['-created_at']
    readonly_fields = [
        'total_count', 'sent_count', 'failed_count', 'started_at',
        'completed_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('기본 정보', {
            'fields': ['name', 'description', 'status', 'created_by']
        }),
        ('설정', {
            'fields': ['template', 'filters', 'context_data', 'scheduled_at']
        }),
        ('진행 상황', {
            'fields': [
                'total_count', 'sent_count', 'failed_count',
                'started_at', 'completed_at'
            ],
            'classes': ['collapse']
        }),
        ('메타데이터', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def created_by_email(self, obj):
        """Get creator email"""
        return obj.created_by.email
    created_by_email.short_description = '생성자'
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'partially_failed': 'darkorange'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = '상태'
    
    def success_rate_display(self, obj):
        """Display success rate with color coding"""
        rate = obj.success_rate
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            rate
        )
    success_rate_display.short_description = '성공률'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'created_by', 'template'
        )
