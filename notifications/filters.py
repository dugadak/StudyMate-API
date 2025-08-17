import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import (
    NotificationTemplate, NotificationSchedule, Notification,
    DeviceToken, NotificationBatch
)


class NotificationTemplateFilter(django_filters.FilterSet):
    """Enhanced filters for NotificationTemplate"""
    
    template_type = django_filters.ChoiceFilter(
        choices=NotificationTemplate.TEMPLATE_TYPES
    )
    name = django_filters.CharFilter(lookup_expr='icontains')
    priority_min = django_filters.NumberFilter(
        field_name='priority',
        lookup_expr='gte'
    )
    priority_max = django_filters.NumberFilter(
        field_name='priority',
        lookup_expr='lte'
    )
    has_variables = django_filters.BooleanFilter(
        method='filter_has_variables',
        label='Has template variables'
    )
    popular = django_filters.BooleanFilter(
        method='filter_popular',
        label='Popular templates (used frequently)'
    )
    
    class Meta:
        model = NotificationTemplate
        fields = ['is_active']
    
    def filter_has_variables(self, queryset, name, value):
        """Filter templates with variables"""
        if value:
            return queryset.exclude(variables__isnull=True).exclude(variables__exact=[])
        else:
            return queryset.filter(Q(variables__isnull=True) | Q(variables__exact=[]))
    
    def filter_popular(self, queryset, name, value):
        """Filter popular templates (with more than 5 usages)"""
        from django.db.models import Count
        if value:
            return queryset.annotate(
                usage_count=Count('schedules')
            ).filter(usage_count__gt=5)
        else:
            return queryset.annotate(
                usage_count=Count('schedules')
            ).filter(usage_count__lte=5)


class NotificationScheduleFilter(django_filters.FilterSet):
    """Enhanced filters for NotificationSchedule"""
    
    status = django_filters.ChoiceFilter(
        choices=NotificationSchedule.STATUS_CHOICES
    )
    recurrence_type = django_filters.ChoiceFilter(
        choices=NotificationSchedule.RECURRENCE_TYPES
    )
    template_type = django_filters.ChoiceFilter(
        field_name='template__template_type',
        choices=NotificationTemplate.TEMPLATE_TYPES
    )
    subject_id = django_filters.NumberFilter(field_name='subject__id')
    is_due = django_filters.BooleanFilter(
        method='filter_is_due',
        label='Due for sending'
    )
    expires_soon = django_filters.BooleanFilter(
        method='filter_expires_soon',
        label='Expires within 7 days'
    )
    has_sent_notifications = django_filters.BooleanFilter(
        method='filter_has_sent_notifications',
        label='Has sent notifications'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    
    class Meta:
        model = NotificationSchedule
        fields = ['is_active']
    
    def filter_is_due(self, queryset, name, value):
        """Filter schedules due for sending"""
        now = timezone.now()
        if value:
            return queryset.filter(
                is_active=True,
                status='active',
                next_scheduled_at__isnull=False,
                next_scheduled_at__lte=now
            )
        else:
            return queryset.filter(
                Q(is_active=False) |
                Q(status__ne='active') |
                Q(next_scheduled_at__isnull=True) |
                Q(next_scheduled_at__gt=now)
            )
    
    def filter_expires_soon(self, queryset, name, value):
        """Filter schedules expiring soon"""
        if value:
            soon_date = timezone.now() + timedelta(days=7)
            return queryset.filter(
                end_date__isnull=False,
                end_date__lte=soon_date,
                is_active=True
            )
        return queryset
    
    def filter_has_sent_notifications(self, queryset, name, value):
        """Filter schedules that have sent notifications"""
        if value:
            return queryset.filter(send_count__gt=0)
        else:
            return queryset.filter(send_count=0)


class NotificationFilter(django_filters.FilterSet):
    """Enhanced filters for Notification"""
    
    notification_type = django_filters.ChoiceFilter(
        choices=Notification.NOTIFICATION_TYPES
    )
    status = django_filters.ChoiceFilter(
        choices=Notification.STATUS_CHOICES
    )
    channel = django_filters.ChoiceFilter(
        choices=Notification.CHANNEL_CHOICES
    )
    priority = django_filters.ChoiceFilter(
        choices=Notification.PRIORITY_CHOICES
    )
    schedule_id = django_filters.NumberFilter(field_name='schedule__id')
    title = django_filters.CharFilter(lookup_expr='icontains')
    message = django_filters.CharFilter(lookup_expr='icontains')
    is_unread = django_filters.BooleanFilter(
        method='filter_is_unread',
        label='Unread notifications'
    )
    is_failed = django_filters.BooleanFilter(
        method='filter_is_failed',
        label='Failed notifications'
    )
    can_retry = django_filters.BooleanFilter(
        method='filter_can_retry',
        label='Can be retried'
    )
    is_expired = django_filters.BooleanFilter(
        method='filter_is_expired',
        label='Expired notifications'
    )
    scheduled_after = django_filters.DateTimeFilter(
        field_name='scheduled_at',
        lookup_expr='gte'
    )
    scheduled_before = django_filters.DateTimeFilter(
        field_name='scheduled_at',
        lookup_expr='lte'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    sent_after = django_filters.DateTimeFilter(
        field_name='sent_at',
        lookup_expr='gte'
    )
    sent_before = django_filters.DateTimeFilter(
        field_name='sent_at',
        lookup_expr='lte'
    )
    recent_days = django_filters.NumberFilter(
        method='filter_recent_days',
        label='Notifications within last N days'
    )
    
    class Meta:
        model = Notification
        fields = []
    
    def filter_is_unread(self, queryset, name, value):
        """Filter unread notifications"""
        if value:
            return queryset.filter(status='sent')
        else:
            return queryset.exclude(status='sent')
    
    def filter_is_failed(self, queryset, name, value):
        """Filter failed notifications"""
        if value:
            return queryset.filter(status='failed')
        else:
            return queryset.exclude(status='failed')
    
    def filter_can_retry(self, queryset, name, value):
        """Filter notifications that can be retried"""
        if value:
            return queryset.filter(
                status='failed',
                retry_count__lt=F('max_retries')
            ).filter(
                Q(expired_at__isnull=True) |
                Q(expired_at__gt=timezone.now())
            )
        return queryset
    
    def filter_is_expired(self, queryset, name, value):
        """Filter expired notifications"""
        now = timezone.now()
        if value:
            return queryset.filter(
                Q(status='expired') |
                (Q(expired_at__isnull=False) & Q(expired_at__lt=now))
            )
        else:
            return queryset.exclude(
                Q(status='expired') |
                (Q(expired_at__isnull=False) & Q(expired_at__lt=now))
            )
    
    def filter_recent_days(self, queryset, name, value):
        """Filter notifications within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(created_at__gte=since_date)
        return queryset


class DeviceTokenFilter(django_filters.FilterSet):
    """Enhanced filters for DeviceToken"""
    
    platform = django_filters.ChoiceFilter(
        choices=DeviceToken.PLATFORM_CHOICES
    )
    device_id = django_filters.CharFilter(lookup_expr='icontains')
    device_name = django_filters.CharFilter(lookup_expr='icontains')
    app_version = django_filters.CharFilter()
    os_version = django_filters.CharFilter()
    is_healthy = django_filters.BooleanFilter(
        method='filter_is_healthy',
        label='Healthy devices (low failure count)'
    )
    has_failures = django_filters.BooleanFilter(
        method='filter_has_failures',
        label='Has recent failures'
    )
    last_used_days = django_filters.NumberFilter(
        method='filter_last_used_days',
        label='Last used within N days'
    )
    
    class Meta:
        model = DeviceToken
        fields = ['is_active', 'is_primary']
    
    def filter_is_healthy(self, queryset, name, value):
        """Filter healthy devices"""
        if value:
            return queryset.filter(failure_count__lt=3)
        else:
            return queryset.filter(failure_count__gte=3)
    
    def filter_has_failures(self, queryset, name, value):
        """Filter devices with recent failures"""
        if value:
            return queryset.filter(failure_count__gt=0)
        else:
            return queryset.filter(failure_count=0)
    
    def filter_last_used_days(self, queryset, name, value):
        """Filter devices used within last N days"""
        if value and value > 0:
            since_date = timezone.now() - timedelta(days=value)
            return queryset.filter(last_used_at__gte=since_date)
        return queryset


class NotificationBatchFilter(django_filters.FilterSet):
    """Enhanced filters for NotificationBatch"""
    
    status = django_filters.ChoiceFilter(
        choices=NotificationBatch.STATUS_CHOICES
    )
    name = django_filters.CharFilter(lookup_expr='icontains')
    template_type = django_filters.ChoiceFilter(
        field_name='template__template_type',
        choices=NotificationTemplate.TEMPLATE_TYPES
    )
    created_by_email = django_filters.CharFilter(
        field_name='created_by__email',
        lookup_expr='icontains'
    )
    min_total_count = django_filters.NumberFilter(
        field_name='total_count',
        lookup_expr='gte'
    )
    max_total_count = django_filters.NumberFilter(
        field_name='total_count',
        lookup_expr='lte'
    )
    success_rate_min = django_filters.NumberFilter(
        method='filter_success_rate_min',
        label='Minimum success rate'
    )
    is_completed = django_filters.BooleanFilter(
        method='filter_is_completed',
        label='Completed batches'
    )
    is_running = django_filters.BooleanFilter(
        method='filter_is_running',
        label='Currently running batches'
    )
    scheduled_after = django_filters.DateTimeFilter(
        field_name='scheduled_at',
        lookup_expr='gte'
    )
    scheduled_before = django_filters.DateTimeFilter(
        field_name='scheduled_at',
        lookup_expr='lte'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    
    class Meta:
        model = NotificationBatch
        fields = []
    
    def filter_success_rate_min(self, queryset, name, value):
        """Filter by minimum success rate"""
        if value is not None:
            return queryset.extra(
                where=[
                    "(sent_count * 100.0 / GREATEST(total_count, 1)) >= %s"
                ],
                params=[value]
            )
        return queryset
    
    def filter_is_completed(self, queryset, name, value):
        """Filter completed batches"""
        if value:
            return queryset.filter(status__in=['completed', 'partially_failed'])
        else:
            return queryset.exclude(status__in=['completed', 'partially_failed'])
    
    def filter_is_running(self, queryset, name, value):
        """Filter running batches"""
        if value:
            return queryset.filter(status='processing')
        else:
            return queryset.exclude(status='processing')