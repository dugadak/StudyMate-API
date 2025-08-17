from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
from typing import Dict, Any, List
import logging

from .models import (
    NotificationTemplate, NotificationSchedule, Notification,
    DeviceToken, NotificationPreference, NotificationBatch
)
from .serializers import (
    NotificationTemplateSerializer, NotificationTemplateCreateSerializer,
    NotificationScheduleSerializer, NotificationScheduleSummarySerializer,
    NotificationSerializer, NotificationCreateSerializer, NotificationActionSerializer,
    DeviceTokenSerializer, NotificationPreferenceSerializer,
    NotificationBatchSerializer, NotificationAnalyticsSerializer,
    BulkNotificationActionSerializer
)
from subscription.pagination import SubscriptionPagination

logger = logging.getLogger(__name__)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for Notification Templates"""
    
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination
    
    def get_queryset(self):
        """Get templates available to user (admin gets all, users get active ones)"""
        if self.request.user.is_staff:
            return NotificationTemplate.objects.all().order_by('-priority', 'name')
        return NotificationTemplate.objects.filter(is_active=True).order_by('-priority', 'name')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return NotificationTemplateCreateSerializer
        return NotificationTemplateSerializer
    
    @action(detail=True, methods=['post'])
    def test_render(self, request, pk=None):
        """Test template rendering with sample data"""
        template = self.get_object()
        context = request.data.get('context', {})
        
        try:
            title, message = template.render(context)
            
            # Validate that all required variables are provided
            if not template.validate_variables(context):
                missing_vars = set(template.variables) - set(context.keys())
                return Response({
                    'error': f'Missing variables: {", ".join(missing_vars)}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'title': title,
                'message': message,
                'variables_used': template.variables,
                'context_provided': list(context.keys())
            })
            
        except Exception as e:
            logger.error(f"Template rendering failed: {str(e)}")
            return Response({
                'error': f'Template rendering failed: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most used templates"""
        templates = self.get_queryset().annotate(
            usage_count=Count('schedules')
        ).order_by('-usage_count')[:10]
        
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get templates grouped by type"""
        template_type = request.query_params.get('type')
        if not template_type:
            return Response({
                'error': 'type parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        templates = self.get_queryset().filter(template_type=template_type)
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)


class NotificationScheduleViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for Notification Schedules"""
    
    serializer_class = NotificationScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination
    
    def get_queryset(self):
        """Get user's notification schedules"""
        return NotificationSchedule.objects.filter(
            user=self.request.user
        ).select_related('template', 'subject').order_by('-created_at')
    
    def get_serializer_class(self):
        """Use summary serializer for list view"""
        if self.action == 'list':
            return NotificationScheduleSummarySerializer
        return NotificationScheduleSerializer
    
    def perform_create(self, serializer):
        """Create schedule with user"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause a notification schedule"""
        schedule = self.get_object()
        schedule.status = 'paused'
        schedule.save(update_fields=['status'])
        
        logger.info(f"Paused notification schedule {schedule.id} for user {request.user.email}")
        return Response({'message': '알림 일정이 일시정지되었습니다.'})
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume a paused notification schedule"""
        schedule = self.get_object()
        if schedule.status == 'paused':
            schedule.status = 'active'
            schedule.update_next_scheduled()
            schedule.save()
            
            logger.info(f"Resumed notification schedule {schedule.id} for user {request.user.email}")
            return Response({'message': '알림 일정이 재개되었습니다.'})
        
        return Response({
            'error': '일시정지된 알림만 재개할 수 있습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def test_send(self, request, pk=None):
        """Send a test notification for this schedule"""
        schedule = self.get_object()
        
        try:
            # Create test notification
            title, message = schedule.template.render(schedule.context_data)
            
            notification = Notification.objects.create(
                user=schedule.user,
                schedule=schedule,
                notification_type=schedule.template.template_type,
                title=f"[테스트] {title}",
                message=message,
                scheduled_at=timezone.now(),
                priority='normal'
            )
            
            # Here you would trigger the actual sending
            # For now, just mark as sent
            notification.mark_as_sent()
            
            logger.info(f"Sent test notification for schedule {schedule.id}")
            return Response({
                'message': '테스트 알림이 발송되었습니다.',
                'notification_id': notification.id
            })
            
        except Exception as e:
            logger.error(f"Test notification failed: {str(e)}")
            return Response({
                'error': f'테스트 알림 발송 실패: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming notifications"""
        hours = int(request.query_params.get('hours', 24))
        until_time = timezone.now() + timedelta(hours=hours)
        
        schedules = self.get_queryset().filter(
            is_active=True,
            status='active',
            next_scheduled_at__isnull=False,
            next_scheduled_at__lte=until_time
        ).order_by('next_scheduled_at')
        
        serializer = NotificationScheduleSummarySerializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue schedules"""
        schedules = self.get_queryset().filter(
            is_active=True,
            status='active',
            next_scheduled_at__isnull=False,
            next_scheduled_at__lt=timezone.now()
        ).order_by('next_scheduled_at')
        
        serializer = NotificationScheduleSummarySerializer(schedules, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for Notifications"""
    
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination
    
    def get_queryset(self):
        """Get user's notifications"""
        return Notification.objects.filter(
            user=self.request.user
        ).select_related('schedule__template').order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action == 'create':
            return NotificationCreateSerializer
        elif self.action in ['mark_read', 'mark_dismissed']:
            return NotificationActionSerializer
        elif self.action == 'bulk_action':
            return BulkNotificationActionSerializer
        return NotificationSerializer
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        
        if notification.mark_as_read():
            return Response({'message': '알림을 읽음으로 표시했습니다.'})
        
        return Response({
            'error': '발송된 알림만 읽음 처리할 수 있습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def mark_dismissed(self, request, pk=None):
        """Mark notification as dismissed"""
        notification = self.get_object()
        
        if notification.mark_as_dismissed():
            return Response({'message': '알림을 무시했습니다.'})
        
        return Response({
            'error': '발송되거나 읽은 알림만 무시할 수 있습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry failed notification"""
        notification = self.get_object()
        
        if not notification.can_retry():
            return Response({
                'error': '재시도할 수 없는 알림입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset status and increment retry
        notification.status = 'pending'
        notification.scheduled_at = timezone.now()
        notification.save(update_fields=['status', 'scheduled_at'])
        
        logger.info(f"Retrying notification {notification.id} for user {request.user.email}")
        return Response({'message': '알림 재시도가 예약되었습니다.'})
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Perform bulk actions on notifications"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notification_ids = serializer.validated_data['notification_ids']
        action_type = serializer.validated_data['action']
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=request.user
        )
        
        success_count = 0
        
        for notification in notifications:
            try:
                if action_type == 'read':
                    if notification.mark_as_read():
                        success_count += 1
                elif action_type == 'dismiss':
                    if notification.mark_as_dismissed():
                        success_count += 1
                elif action_type == 'delete':
                    notification.delete()
                    success_count += 1
            except Exception as e:
                logger.error(f"Bulk action failed for notification {notification.id}: {str(e)}")
        
        return Response({
            'message': f'{success_count}개의 알림에 대해 작업을 완료했습니다.',
            'success_count': success_count,
            'total_count': len(notification_ids)
        })
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications"""
        notifications = self.get_queryset().filter(
            status='sent'
        ).order_by('-created_at')
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get notification summary"""
        user_notifications = self.get_queryset()
        
        summary = {
            'total': user_notifications.count(),
            'unread': user_notifications.filter(status='sent').count(),
            'failed': user_notifications.filter(status='failed').count(),
            'recent': user_notifications.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count(),
            'by_type': dict(
                user_notifications.values('notification_type').annotate(
                    count=Count('id')
                ).values_list('notification_type', 'count')
            ),
            'by_channel': dict(
                user_notifications.values('channel').annotate(
                    count=Count('id')
                ).values_list('channel', 'count')
            )
        }
        
        return Response(summary)


class DeviceTokenViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for Device Tokens"""
    
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination
    
    def get_queryset(self):
        """Get user's device tokens"""
        return DeviceToken.objects.filter(
            user=self.request.user
        ).order_by('-is_primary', '-last_used_at')
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set device token as primary"""
        device_token = self.get_object()
        device_token.set_as_primary()
        
        logger.info(f"Set primary device token for user {request.user.email}")
        return Response({'message': '기본 디바이스로 설정되었습니다.'})
    
    @action(detail=True, methods=['post'])
    def test_notification(self, request, pk=None):
        """Send test notification to device"""
        device_token = self.get_object()
        
        if not device_token.is_active:
            return Response({
                'error': '비활성화된 디바이스입니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create test notification
            notification = Notification.objects.create(
                user=device_token.user,
                notification_type='system_alert',
                channel='push',
                title='테스트 알림',
                message='디바이스 알림 테스트입니다.',
                scheduled_at=timezone.now()
            )
            
            # Here you would send to the actual device
            # For now, just mark as sent
            notification.mark_as_sent()
            
            return Response({
                'message': '테스트 알림이 발송되었습니다.',
                'notification_id': notification.id
            })
            
        except Exception as e:
            logger.error(f"Test notification failed: {str(e)}")
            return Response({
                'error': f'테스트 알림 발송 실패: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Check health of all user devices"""
        devices = self.get_queryset()
        
        health_summary = {
            'total_devices': devices.count(),
            'active_devices': devices.filter(is_active=True).count(),
            'healthy_devices': devices.filter(failure_count__lt=3).count(),
            'failed_devices': devices.filter(failure_count__gte=5).count(),
            'platforms': dict(
                devices.values('platform').annotate(
                    count=Count('id')
                ).values_list('platform', 'count')
            )
        }
        
        return Response(health_summary)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """ViewSet for Notification Preferences"""
    
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'put', 'patch']  # No creation or deletion
    
    def get_object(self):
        """Get or create user's notification preferences"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        if created:
            logger.info(f"Created notification preferences for user {self.request.user.email}")
        return preferences
    
    def list(self, request):
        """Return user's preferences as single object"""
        preferences = self.get_object()
        serializer = self.get_serializer(preferences)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Redirect to list (preferences are singleton per user)"""
        return self.list(request)
    
    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """Reset preferences to default values"""
        preferences = self.get_object()
        
        # Reset to default values
        default_fields = {
            'push_notification_enabled': True,
            'email_notification_enabled': False,
            'sms_notification_enabled': False,
            'study_summary_enabled': True,
            'quiz_reminder_enabled': True,
            'goal_reminder_enabled': True,
            'study_streak_enabled': True,
            'subscription_reminder_enabled': True,
            'payment_notification_enabled': True,
            'achievement_enabled': True,
            'milestone_enabled': True,
            'weekly_report_enabled': True,
            'monthly_report_enabled': True,
            'promotional_enabled': False,
            'newsletter_enabled': False,
            'quiet_hours_enabled': False,
            'max_daily_notifications': 10,
            'min_interval_minutes': 15,
            'channel_preferences': {}
        }
        
        for field, value in default_fields.items():
            setattr(preferences, field, value)
        
        preferences.save()
        
        logger.info(f"Reset notification preferences for user {request.user.email}")
        return Response({'message': '알림 설정이 기본값으로 초기화되었습니다.'})


class NotificationBatchViewSet(viewsets.ModelViewSet):
    """Enhanced ViewSet for Notification Batches"""
    
    serializer_class = NotificationBatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = SubscriptionPagination
    
    def get_queryset(self):
        """Get user's notification batches"""
        if self.request.user.is_staff:
            return NotificationBatch.objects.all().order_by('-created_at')
        return NotificationBatch.objects.filter(
            created_by=self.request.user
        ).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start batch processing"""
        batch = self.get_object()
        
        if batch.status != 'pending':
            return Response({
                'error': '대기 중인 배치만 시작할 수 있습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        batch.mark_as_started()
        
        # Here you would trigger the actual batch processing
        # This could be a Celery task
        
        logger.info(f"Started notification batch {batch.id}")
        return Response({'message': '배치 처리가 시작되었습니다.'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel batch processing"""
        batch = self.get_object()
        
        if batch.status not in ['pending', 'processing']:
            return Response({
                'error': '진행 중인 배치만 취소할 수 있습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        batch.status = 'failed'
        batch.save(update_fields=['status'])
        
        logger.info(f"Cancelled notification batch {batch.id}")
        return Response({'message': '배치 처리가 취소되었습니다.'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get batch statistics"""
        user_batches = self.get_queryset()
        
        stats = {
            'total_batches': user_batches.count(),
            'completed_batches': user_batches.filter(status='completed').count(),
            'failed_batches': user_batches.filter(status='failed').count(),
            'processing_batches': user_batches.filter(status='processing').count(),
            'total_notifications_sent': user_batches.aggregate(
                total=Count('sent_count')
            )['total'] or 0,
            'average_success_rate': user_batches.filter(
                status='completed'
            ).aggregate(
                avg_rate=Avg(F('sent_count') * 100.0 / F('total_count'))
            )['avg_rate'] or 0
        }
        
        return Response(stats)


class NotificationAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for Notification Analytics"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        """Get comprehensive notification analytics"""
        user = request.user
        days = int(request.query_params.get('days', 30))
        since_date = timezone.now() - timedelta(days=days)
        
        notifications = Notification.objects.filter(
            user=user,
            created_at__gte=since_date
        )
        
        # Basic stats
        total_notifications = notifications.count()
        sent_notifications = notifications.filter(status='sent').count()
        failed_notifications = notifications.filter(status='failed').count()
        read_notifications = notifications.filter(status='read').count()
        
        # Rates
        delivery_rate = (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0
        read_rate = (read_notifications / sent_notifications * 100) if sent_notifications > 0 else 0
        
        # Popular types
        popular_types = list(
            notifications.values('notification_type').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
        )
        
        # Channel stats
        channel_stats = dict(
            notifications.values('channel').annotate(
                count=Count('id')
            ).values_list('channel', 'count')
        )
        
        # Time-based stats
        hourly_stats = []
        daily_stats = []
        
        # Get hourly distribution
        for hour in range(24):
            count = notifications.filter(
                created_at__hour=hour
            ).count()
            hourly_stats.append({'hour': hour, 'count': count})
        
        # Get daily stats for the period
        for i in range(days):
            date = since_date.date() + timedelta(days=i)
            count = notifications.filter(
                created_at__date=date
            ).count()
            daily_stats.append({'date': date.isoformat(), 'count': count})
        
        # Device stats
        device_tokens = DeviceToken.objects.filter(user=user)
        device_stats = {
            'total_devices': device_tokens.count(),
            'active_devices': device_tokens.filter(is_active=True).count(),
            'platforms': dict(
                device_tokens.values('platform').annotate(
                    count=Count('id')
                ).values_list('platform', 'count')
            )
        }
        
        analytics_data = {
            'total_notifications': total_notifications,
            'sent_notifications': sent_notifications,
            'failed_notifications': failed_notifications,
            'read_notifications': read_notifications,
            'delivery_rate': round(delivery_rate, 2),
            'read_rate': round(read_rate, 2),
            'popular_types': popular_types,
            'channel_stats': channel_stats,
            'hourly_stats': hourly_stats,
            'daily_stats': daily_stats,
            'device_stats': device_stats
        }
        
        serializer = NotificationAnalyticsSerializer(analytics_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get quick notification summary"""
        user = request.user
        
        # Recent notifications (last 7 days)
        recent_notifications = Notification.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        
        summary = {
            'unread_count': Notification.objects.filter(
                user=user, 
                status='sent'
            ).count(),
            'recent_count': recent_notifications.count(),
            'failed_count': recent_notifications.filter(status='failed').count(),
            'active_schedules': NotificationSchedule.objects.filter(
                user=user,
                is_active=True,
                status='active'
            ).count(),
            'next_notification': None
        }
        
        # Get next scheduled notification
        next_schedule = NotificationSchedule.objects.filter(
            user=user,
            is_active=True,
            status='active',
            next_scheduled_at__isnull=False
        ).order_by('next_scheduled_at').first()
        
        if next_schedule:
            summary['next_notification'] = {
                'template_name': next_schedule.template.name,
                'scheduled_at': next_schedule.next_scheduled_at,
                'time_until': (next_schedule.next_scheduled_at - timezone.now()).total_seconds()
            }
        
        return Response(summary)
