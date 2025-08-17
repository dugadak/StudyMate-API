from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, time
from typing import Dict, Any, Optional, List
import logging
import json

from .models import (
    NotificationTemplate, NotificationSchedule, Notification,
    DeviceToken, NotificationPreference, NotificationBatch
)
from study.models import Subject

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Enhanced Notification Template serializer"""
    
    template_type_display = serializers.CharField(
        source='get_template_type_display', 
        read_only=True
    )
    variables_count = serializers.SerializerMethodField()
    usage_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'template_type', 'template_type_display',
            'title_template', 'message_template', 'variables',
            'is_active', 'priority', 'variables_count', 'usage_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_variables_count(self, obj) -> int:
        """Get number of template variables"""
        return len(obj.variables) if obj.variables else 0
    
    def get_usage_count(self, obj) -> int:
        """Get template usage count"""
        return obj.schedules.count()
    
    def validate_variables(self, value):
        """Validate variables format"""
        if not isinstance(value, list):
            raise serializers.ValidationError("변수는 리스트 형태여야 합니다.")
        
        for var in value:
            if not isinstance(var, str) or not var.strip():
                raise serializers.ValidationError("모든 변수는 문자열이어야 합니다.")
        
        return value
    
    def validate(self, attrs):
        """Enhanced validation"""
        title_template = attrs.get('title_template', '')
        message_template = attrs.get('message_template', '')
        variables = attrs.get('variables', [])
        
        # Check if all variables in templates are declared
        all_text = title_template + ' ' + message_template
        used_vars = []
        
        for var in variables:
            if f"{{{var}}}" in all_text:
                used_vars.append(var)
        
        # Warn about unused variables
        unused_vars = set(variables) - set(used_vars)
        if unused_vars:
            logger.warning(f"Template has unused variables: {unused_vars}")
        
        return attrs


class NotificationTemplateCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for template creation"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'name', 'template_type', 'title_template', 
            'message_template', 'variables', 'priority'
        ]
    
    def create(self, validated_data):
        """Create template with validation"""
        template = NotificationTemplate.objects.create(**validated_data)
        logger.info(f"Created notification template: {template.name}")
        return template


class NotificationScheduleSerializer(serializers.ModelSerializer):
    """Enhanced Notification Schedule serializer"""
    
    template = NotificationTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True)
    subject = serializers.StringRelatedField(read_only=True)
    subject_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    recurrence_type_display = serializers.CharField(
        source='get_recurrence_type_display', 
        read_only=True
    )
    
    # Computed fields
    is_due = serializers.SerializerMethodField()
    time_until_next = serializers.SerializerMethodField()
    sends_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationSchedule
        fields = [
            'id', 'template', 'template_id', 'subject', 'subject_id',
            'notification_time', 'recurrence_type', 'recurrence_type_display',
            'days_of_week', 'start_date', 'end_date', 'is_active',
            'status', 'status_display', 'timezone_name', 'last_sent_at',
            'next_scheduled_at', 'send_count', 'max_sends', 'context_data',
            'is_due', 'time_until_next', 'sends_remaining',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'last_sent_at', 'next_scheduled_at', 
            'send_count', 'created_at', 'updated_at'
        ]
    
    def get_is_due(self, obj) -> bool:
        """Check if schedule is due for sending"""
        if not obj.next_scheduled_at:
            return False
        return obj.next_scheduled_at <= timezone.now()
    
    def get_time_until_next(self, obj) -> Optional[str]:
        """Get time until next scheduled notification"""
        if not obj.next_scheduled_at:
            return None
        
        now = timezone.now()
        if obj.next_scheduled_at <= now:
            return "지금"
        
        diff = obj.next_scheduled_at - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}일 {hours}시간"
        elif hours > 0:
            return f"{hours}시간 {minutes}분"
        else:
            return f"{minutes}분"
    
    def get_sends_remaining(self, obj) -> Optional[int]:
        """Get remaining sends"""
        if not obj.max_sends:
            return None
        return max(0, obj.max_sends - obj.send_count)
    
    def validate_template_id(self, value):
        """Validate template selection"""
        try:
            template = NotificationTemplate.objects.get(id=value, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 알림 템플릿입니다.")
        
        return value
    
    def validate_subject_id(self, value):
        """Validate subject selection"""
        if value is None:
            return value
        
        try:
            subject = Subject.objects.get(id=value)
            # Check if user has access to this subject
            user = self.context['request'].user
            if not subject.user_subjects.filter(user=user).exists():
                raise serializers.ValidationError("해당 과목에 대한 권한이 없습니다.")
        except Subject.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 과목입니다.")
        
        return value
    
    def validate_days_of_week(self, value):
        """Validate days of week"""
        if not isinstance(value, list):
            raise serializers.ValidationError("요일은 리스트 형태여야 합니다.")
        
        for day in value:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise serializers.ValidationError("요일은 0-6 사이의 정수여야 합니다.")
        
        return value
    
    def validate(self, attrs):
        """Enhanced validation"""
        recurrence_type = attrs.get('recurrence_type')
        days_of_week = attrs.get('days_of_week', [])
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        max_sends = attrs.get('max_sends')
        
        # Validate custom recurrence
        if recurrence_type == 'custom' and not days_of_week:
            raise serializers.ValidationError(
                "사용자 정의 반복은 요일을 지정해야 합니다."
            )
        
        # Validate date range
        if end_date and start_date and end_date <= start_date:
            raise serializers.ValidationError(
                "종료일은 시작일보다 늦어야 합니다."
            )
        
        # Validate max sends
        if max_sends is not None and max_sends < 1:
            raise serializers.ValidationError(
                "최대 발송 횟수는 1 이상이어야 합니다."
            )
        
        return attrs
    
    def create(self, validated_data):
        """Create schedule with user and initial calculations"""
        user = self.context['request'].user
        template_id = validated_data.pop('template_id')
        subject_id = validated_data.pop('subject_id', None)
        
        template = NotificationTemplate.objects.get(id=template_id)
        subject = Subject.objects.get(id=subject_id) if subject_id else None
        
        schedule = NotificationSchedule.objects.create(
            user=user,
            template=template,
            subject=subject,
            **validated_data
        )
        
        # Calculate initial next scheduled time
        schedule.update_next_scheduled()
        
        logger.info(f"Created notification schedule for user {user.email}: {template.name}")
        return schedule


class NotificationScheduleSummarySerializer(serializers.ModelSerializer):
    """Summary serializer for schedule listing"""
    
    template_name = serializers.CharField(source='template.name', read_only=True)
    template_type = serializers.CharField(source='template.template_type', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = NotificationSchedule
        fields = [
            'id', 'template_name', 'template_type', 'subject_name',
            'notification_time', 'recurrence_type', 'status', 'status_display',
            'is_active', 'next_scheduled_at', 'send_count'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """Enhanced Notification serializer"""
    
    schedule = NotificationScheduleSummarySerializer(read_only=True)
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', 
        read_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    # Computed fields
    time_since_created = serializers.SerializerMethodField()
    is_actionable = serializers.SerializerMethodField()
    retry_available = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'schedule', 'notification_type', 'notification_type_display',
            'channel', 'channel_display', 'priority', 'priority_display',
            'title', 'message', 'status', 'status_display', 'scheduled_at',
            'sent_at', 'delivered_at', 'read_at', 'expired_at', 'retry_count',
            'max_retries', 'error_message', 'extra_data', 'action_url',
            'image_url', 'deep_link', 'tracking_id', 'time_since_created',
            'is_actionable', 'retry_available', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'sent_at', 'delivered_at', 'read_at', 'expired_at',
            'retry_count', 'error_message', 'tracking_id', 'created_at', 'updated_at'
        ]
    
    def get_time_since_created(self, obj) -> str:
        """Get human-readable time since creation"""
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days}일 전"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}시간 전"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}분 전"
        else:
            return "방금 전"
    
    def get_is_actionable(self, obj) -> bool:
        """Check if notification has actionable content"""
        return bool(obj.action_url or obj.deep_link)
    
    def get_retry_available(self, obj) -> bool:
        """Check if notification can be retried"""
        return obj.can_retry()


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'notification_type', 'channel', 'priority', 'title', 'message',
            'scheduled_at', 'action_url', 'image_url', 'deep_link', 'extra_data'
        ]
    
    def create(self, validated_data):
        """Create notification for current user"""
        user = self.context['request'].user
        notification = Notification.objects.create(
            user=user,
            **validated_data
        )
        
        logger.info(f"Created notification for user {user.email}: {notification.title}")
        return notification


class NotificationActionSerializer(serializers.Serializer):
    """Serializer for notification actions"""
    
    action = serializers.ChoiceField(choices=['read', 'dismiss'])
    
    def validate_action(self, value):
        """Validate action availability"""
        notification = self.context.get('notification')
        if not notification:
            raise serializers.ValidationError("알림을 찾을 수 없습니다.")
        
        if value == 'read' and notification.status != 'sent':
            raise serializers.ValidationError("발송된 알림만 읽음 처리할 수 있습니다.")
        
        if value == 'dismiss' and notification.status not in ['sent', 'read']:
            raise serializers.ValidationError("발송되거나 읽은 알림만 무시할 수 있습니다.")
        
        return value


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Enhanced Device Token serializer"""
    
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    is_healthy = serializers.SerializerMethodField()
    last_used_display = serializers.SerializerMethodField()
    
    class Meta:
        model = DeviceToken
        fields = [
            'id', 'token', 'platform', 'platform_display', 'device_id',
            'device_name', 'app_version', 'os_version', 'is_active',
            'is_primary', 'notification_settings', 'failure_count',
            'last_failure_at', 'is_healthy', 'last_used_display',
            'created_at', 'last_used_at'
        ]
        read_only_fields = [
            'id', 'user', 'failure_count', 'last_failure_at', 
            'created_at', 'last_used_at'
        ]
    
    def get_is_healthy(self, obj) -> bool:
        """Check if device token is healthy"""
        return obj.failure_count < 3
    
    def get_last_used_display(self, obj) -> str:
        """Get human-readable last used time"""
        if not obj.last_used_at:
            return "사용 안함"
        
        now = timezone.now()
        diff = now - obj.last_used_at
        
        if diff.days > 0:
            return f"{diff.days}일 전"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}시간 전"
        else:
            return "최근"
    
    def validate_token(self, value):
        """Validate token uniqueness for user"""
        user = self.context['request'].user
        
        if self.instance:
            # Update case
            if DeviceToken.objects.exclude(id=self.instance.id).filter(
                user=user, token=value
            ).exists():
                raise serializers.ValidationError("이미 등록된 디바이스 토큰입니다.")
        else:
            # Create case
            if DeviceToken.objects.filter(user=user, token=value).exists():
                raise serializers.ValidationError("이미 등록된 디바이스 토큰입니다.")
        
        return value
    
    def create(self, validated_data):
        """Create device token for current user"""
        user = self.context['request'].user
        
        # If this is the first token, make it primary
        if not DeviceToken.objects.filter(user=user).exists():
            validated_data['is_primary'] = True
        
        device_token = DeviceToken.objects.create(
            user=user,
            **validated_data
        )
        
        logger.info(f"Registered device token for user {user.email}: {device_token.platform}")
        return device_token


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Enhanced Notification Preference serializer"""
    
    quiet_hours_active = serializers.SerializerMethodField()
    total_enabled_types = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationPreference
        fields = [
            'push_notification_enabled', 'email_notification_enabled',
            'sms_notification_enabled', 'study_summary_enabled',
            'quiz_reminder_enabled', 'goal_reminder_enabled',
            'study_streak_enabled', 'subscription_reminder_enabled',
            'payment_notification_enabled', 'achievement_enabled',
            'milestone_enabled', 'weekly_report_enabled',
            'monthly_report_enabled', 'promotional_enabled',
            'newsletter_enabled', 'quiet_hours_enabled',
            'quiet_start_time', 'quiet_end_time', 'timezone_name',
            'max_daily_notifications', 'min_interval_minutes',
            'channel_preferences', 'quiet_hours_active',
            'total_enabled_types', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_quiet_hours_active(self, obj) -> bool:
        """Check if currently in quiet hours"""
        return obj.is_quiet_hours()
    
    def get_total_enabled_types(self, obj) -> int:
        """Count enabled notification types"""
        enabled_fields = [
            'study_summary_enabled', 'quiz_reminder_enabled',
            'goal_reminder_enabled', 'study_streak_enabled',
            'subscription_reminder_enabled', 'achievement_enabled',
            'weekly_report_enabled', 'monthly_report_enabled'
        ]
        
        return sum(1 for field in enabled_fields if getattr(obj, field))
    
    def validate_quiet_start_time(self, value):
        """Validate quiet start time"""
        if not isinstance(value, time):
            raise serializers.ValidationError("올바른 시간 형식이 아닙니다.")
        return value
    
    def validate_quiet_end_time(self, value):
        """Validate quiet end time"""
        if not isinstance(value, time):
            raise serializers.ValidationError("올바른 시간 형식이 아닙니다.")
        return value
    
    def validate_max_daily_notifications(self, value):
        """Validate daily notification limit"""
        if value < 1 or value > 50:
            raise serializers.ValidationError("일일 알림 개수는 1-50 사이여야 합니다.")
        return value
    
    def validate_min_interval_minutes(self, value):
        """Validate minimum interval"""
        if value < 1 or value > 1440:
            raise serializers.ValidationError("알림 간격은 1-1440분 사이여야 합니다.")
        return value
    
    def validate_channel_preferences(self, value):
        """Validate channel preferences format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("채널 설정은 딕셔너리 형태여야 합니다.")
        
        valid_channels = ['push', 'email', 'sms', 'in_app']
        valid_types = [choice[0] for choice in Notification.NOTIFICATION_TYPES]
        
        for notification_type, channels in value.items():
            if notification_type not in valid_types:
                raise serializers.ValidationError(f"유효하지 않은 알림 타입: {notification_type}")
            
            if not isinstance(channels, list):
                raise serializers.ValidationError("채널은 리스트 형태여야 합니다.")
            
            for channel in channels:
                if channel not in valid_channels:
                    raise serializers.ValidationError(f"유효하지 않은 채널: {channel}")
        
        return value


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Enhanced Notification Batch serializer"""
    
    template = NotificationTemplateSerializer(read_only=True)
    template_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    created_by = serializers.StringRelatedField(read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    success_rate_display = serializers.SerializerMethodField()
    estimated_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationBatch
        fields = [
            'id', 'name', 'description', 'status', 'status_display',
            'total_count', 'sent_count', 'failed_count', 'template',
            'template_id', 'filters', 'context_data', 'scheduled_at',
            'started_at', 'completed_at', 'created_by', 'success_rate_display',
            'estimated_duration', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_count', 'sent_count', 'failed_count', 'started_at',
            'completed_at', 'created_by', 'created_at', 'updated_at'
        ]
    
    def get_success_rate_display(self, obj) -> str:
        """Get formatted success rate"""
        return f"{obj.success_rate:.1f}%"
    
    def get_estimated_duration(self, obj) -> Optional[str]:
        """Get estimated duration for batch"""
        if obj.status == 'completed' and obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            minutes = duration.total_seconds() / 60
            
            if minutes < 1:
                return "1분 미만"
            elif minutes < 60:
                return f"{int(minutes)}분"
            else:
                hours = int(minutes / 60)
                remaining_minutes = int(minutes % 60)
                return f"{hours}시간 {remaining_minutes}분"
        
        # Estimate based on count (assuming ~100 notifications per minute)
        if obj.total_count > 0:
            estimated_minutes = max(1, obj.total_count / 100)
            return f"약 {int(estimated_minutes)}분"
        
        return None
    
    def validate_template_id(self, value):
        """Validate template selection"""
        if value is None:
            return value
        
        try:
            template = NotificationTemplate.objects.get(id=value, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise serializers.ValidationError("유효하지 않은 알림 템플릿입니다.")
        
        return value
    
    def validate_filters(self, value):
        """Validate filters format"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("필터는 딕셔너리 형태여야 합니다.")
        
        # Add specific filter validation here if needed
        return value
    
    def validate_scheduled_at(self, value):
        """Validate scheduled time"""
        if value <= timezone.now():
            raise serializers.ValidationError("예약 시간은 현재 시간보다 늦어야 합니다.")
        
        return value
    
    def create(self, validated_data):
        """Create batch with user"""
        user = self.context['request'].user
        template_id = validated_data.pop('template_id', None)
        
        template = None
        if template_id:
            template = NotificationTemplate.objects.get(id=template_id)
        
        batch = NotificationBatch.objects.create(
            created_by=user,
            template=template,
            **validated_data
        )
        
        logger.info(f"Created notification batch: {batch.name} by {user.email}")
        return batch


class NotificationAnalyticsSerializer(serializers.Serializer):
    """Serializer for notification analytics"""
    
    total_notifications = serializers.IntegerField()
    sent_notifications = serializers.IntegerField()
    failed_notifications = serializers.IntegerField()
    read_notifications = serializers.IntegerField()
    delivery_rate = serializers.FloatField()
    read_rate = serializers.FloatField()
    popular_types = serializers.ListField()
    channel_stats = serializers.DictField()
    hourly_stats = serializers.ListField()
    daily_stats = serializers.ListField()
    device_stats = serializers.DictField()


class BulkNotificationActionSerializer(serializers.Serializer):
    """Serializer for bulk notification actions"""
    
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(choices=['read', 'dismiss', 'delete'])
    
    def validate_notification_ids(self, value):
        """Validate notification IDs belong to user"""
        user = self.context['request'].user
        
        notifications = Notification.objects.filter(
            id__in=value,
            user=user
        )
        
        if notifications.count() != len(value):
            raise serializers.ValidationError("일부 알림을 찾을 수 없습니다.")
        
        return value